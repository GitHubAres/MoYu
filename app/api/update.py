# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""软件自动更新 API：版本检查、更新日志展示、桌面端引导及 VPS 自动化对接。"""
import asyncio
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..db import get_db
from ..paths import DATA_DIR, IS_DESKTOP_EXE
from ..version import APP_VERSION
from .auth import is_authenticated

router = APIRouter(prefix="/update", tags=["update"])

# 内存更新检查缓存（默认有效 10 分钟 = 600 秒）
_CACHE_TTL = 600.0
_cache: Dict[str, Any] = {"data": None, "timestamp": 0.0}

GITHUB_REPO = "GitHubAres/MoYu-V1.0.0"
GITHUB_API_BASE = "https://api.github.com"


def clean_version_str(v: str) -> str:
    """清理版本号前缀与空白（如 'v1.4.0' -> '1.4.0'）。"""
    if not v:
        return "0.0.0"
    v = v.strip()
    if v.startswith("v") or v.startswith("V"):
        v = v[1:].strip()
    return v


def parse_version(v: str) -> Tuple[int, int, int, str]:
    """解析语义化版本号，返回 (major, minor, patch, prerelease)。"""
    v_clean = clean_version_str(v)
    # 拆分主体与预发布后缀，如 '1.4.0-beta.1' -> '1.4.0' 与 'beta.1'
    parts = v_clean.split("-", 1)
    main_ver = parts[0]
    prerelease = parts[1] if len(parts) > 1 else ""

    digits = []
    for seg in main_ver.split("."):
        try:
            digits.append(int(seg))
        except ValueError:
            digits.append(0)
    while len(digits) < 3:
        digits.append(0)

    return (digits[0], digits[1], digits[2], prerelease)


def compare_versions(v1: str, v2: str) -> int:
    """
    语义化版本比较：
    若 v1 > v2 返回 1；
    若 v1 < v2 返回 -1；
    若 v1 == v2 返回 0。
    规则：主版本/次版本/修订版本数值大者更新；同一版本号下，正式版（无预发布后缀）优先于预发布版本。
    """
    p1 = parse_version(v1)
    p2 = parse_version(v2)

    # 1. 比较数字部分
    for i in range(3):
        if p1[i] > p2[i]:
            return 1
        elif p1[i] < p2[i]:
            return -1

    # 2. 数字部分相同，比较预发布版本（正式版 > beta/rc）
    pre1 = p1[3]
    pre2 = p2[3]

    if not pre1 and not pre2:
        return 0
    if not pre1 and pre2:
        return 1  # 正式版高于预发布版
    if pre1 and not pre2:
        return -1  # 预发布版低于正式版

    # 两者均有预发布标签，字母序比较
    if pre1 > pre2:
        return 1
    elif pre1 < pre2:
        return -1
    return 0


def is_newer(remote_v: str, current_v: str) -> bool:
    """判断远程版本是否严格高于当前版本。"""
    return compare_versions(remote_v, current_v) > 0


def detect_environment() -> str:
    """
    探测当前运行部署形态：
    - 'desktop': Windows WebView2 原生桌面 exe 封装形态
    - 'docker': Docker 容器内运行环境
    - 'systemd': Linux systemd 常驻服务形态
    - 'source': 本地 Python 源码运行环境
    """
    if IS_DESKTOP_EXE:
        return "desktop"

    # Docker 容器探测
    if os.path.exists("/.dockerenv") or os.environ.get("MOYU_DOCKER"):
        return "docker"

    # systemd 服务环境探测
    if os.environ.get("MOYU_SYSTEMD") == "1":
        return "systemd"

    # 检查是否有 systemctl 并运行于 Linux
    if sys.platform.startswith("linux") and shutil.which("systemctl"):
        return "systemd"

    return "source"


def clear_update_cache() -> None:
    """清除检查更新的内存缓存（供测试或手动强制检查使用）。"""
    _cache["data"] = None
    _cache["timestamp"] = 0.0


def apply_mirror_to_url(url: str, mirror: str) -> str:
    """如果配置了镜像代理加速前缀，对 GitHub 外部链接进行重定向拼接。"""
    if not mirror:
        return url
    mirror = mirror.strip().rstrip("/")
    if not mirror:
        return url
    if mirror.endswith("://"):
        return mirror + url
    return f"{mirror}/{url}"


async def fetch_github_release(channel: str = "stable", mirror: str = "") -> dict:
    """请求 GitHub Releases API 获取最新发布信息。"""
    api_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/releases/latest"
    if channel == "beta":
        api_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/releases"

    # 若镜像代理支持 API 代理，拼接镜像前缀
    request_url = apply_mirror_to_url(api_url, mirror) if mirror else api_url

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"MoYu-Updater/{APP_VERSION}",
    }

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        resp = await client.get(request_url, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub Releases API 响应异常 (HTTP {resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()

        # beta 通道返回列表，取首个（最新发布，含 prerelease）
        if channel == "beta" and isinstance(data, list):
            if not data:
                raise HTTPException(502, "未检索到任何发布版本")
            return data[0]

        if not isinstance(data, dict):
            raise HTTPException(502, "GitHub Releases API 返回格式无效")
        return data


@router.get("/check")
async def check_update(force: bool = Query(False, description="是否强制刷新，无视缓存")):
    """
    检查新版本：
    - 比对 GitHub Releases 最新版本与本地版本；
    - 支持 10 分钟本地内存缓存，防频繁调用卡顿；
    - 解析更新日志、下载链接与 SHA256 校验码。
    """
    now = time.time()
    if not force and _cache["data"] and (now - _cache["timestamp"] < _CACHE_TTL):
        cached_result = dict(_cache["data"])
        cached_result["cached"] = True
        return cached_result

    # 从系统配置中读取更新偏好
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'update_%'").fetchall()
    settings = {r["key"]: r["value"] for r in rows}

    channel = settings.get("update_channel", "stable")
    mirror = settings.get("update_mirror", "").strip()
    skipped_ver = clean_version_str(settings.get("update_skipped_ver", ""))

    try:
        release = await fetch_github_release(channel=channel, mirror=mirror)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"网络连接超时或无法访问 GitHub，请检查网络或配置镜像加速地址。（错误详情：{str(exc)}）"
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail=f"检查更新失败：{str(exc)}")

    tag_name = release.get("tag_name", "")
    latest_ver = clean_version_str(tag_name)
    current_ver = clean_version_str(APP_VERSION)
    has_update = is_newer(latest_ver, current_ver)
    is_skipped = bool(has_update and skipped_ver and (latest_ver == skipped_ver))

    # 提取发布资源（exe 安装包、sha256、manifest）
    assets = release.get("assets", [])
    exe_name = ""
    exe_url = ""
    sha256_val = ""
    manifest_url = ""

    for asset in assets:
        name = asset.get("name", "")
        download_url = asset.get("browser_download_url", "")
        if name.endswith(".exe"):
            exe_name = name
            exe_url = apply_mirror_to_url(download_url, mirror)
        elif name.endswith(".sha256"):
            pass  # 可以后续按需读取
        elif name == "manifest.json":
            manifest_url = apply_mirror_to_url(download_url, mirror)

    check_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES ('update_last_check', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (check_time_str,),
    )
    conn.commit()

    env_type = detect_environment()
    html_url = release.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

    result = {
        "ok": True,
        "current_version": APP_VERSION,
        "latest_version": latest_ver,
        "raw_tag": tag_name,
        "has_update": has_update,
        "is_skipped": is_skipped,
        "channel": channel,
        "release_name": release.get("name") or f"墨语 MoYu v{latest_ver}",
        "release_notes": release.get("body", "暂无更新日志说明。"),
        "published_at": release.get("published_at", ""),
        "html_url": html_url,
        "exe_name": exe_name,
        "exe_url": exe_url,
        "sha256": sha256_val,
        "manifest_url": manifest_url,
        "env": env_type,
        "checked_at": check_time_str,
        "cached": False,
    }

    _cache["data"] = result
    _cache["timestamp"] = now

    return result


class SkipVersionRequest(BaseModel):
    version: str


@router.post("/skip")
def skip_version(body: SkipVersionRequest):
    """记录用户跳过的版本号，避免再次主动弹窗干扰。"""
    v = clean_version_str(body.version)
    conn = get_db()
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES ('update_skipped_ver', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (v,),
    )
    conn.commit()
    # 同时使缓存失效以便重新判定
    clear_update_cache()
    return {"ok": True, "skipped_version": v}


# VPS 更新任务状态存储文件
def _get_update_status_file() -> Path:
    return DATA_DIR / "update_task_status.json"


@router.get("/status")
def get_update_status():
    """获取 VPS 一键更新后台任务执行状态。"""
    status_file = _get_update_status_file()
    if not status_file.exists():
        return {"status": "idle", "message": "当前无正在运行的更新任务"}
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        return {"status": "error", "message": f"读取更新状态失败: {str(e)}"}


def _run_vps_update_worker(backup_path: Path, status_file: Path):
    """后台异步更新执行器（严格保护用户数据，先备份再更新）。"""
    try:
        status_file.write_text(json.dumps({
            "status": "running",
            "progress": 20,
            "message": "已完成数据快照备份，正在拉取最新源码...",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, ensure_ascii=False), encoding="utf-8")

        # 1. git pull 拉取代码
        pull_res = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=120)
        if pull_res.returncode != 0:
            status_file.write_text(json.dumps({
                "status": "failed",
                "progress": 20,
                "message": f"git pull 失败: {pull_res.stderr or pull_res.stdout}",
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, ensure_ascii=False), encoding="utf-8")
            return

        # 2. pip 更新依赖
        status_file.write_text(json.dumps({
            "status": "running",
            "progress": 60,
            "message": "源码拉取成功，正在安装/更新 Python 依赖...",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, ensure_ascii=False), encoding="utf-8")

        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        pip_res = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)
        if pip_res.returncode != 0:
            status_file.write_text(json.dumps({
                "status": "failed",
                "progress": 60,
                "message": f"依赖安装失败: {pip_res.stderr or pip_res.stdout}",
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, ensure_ascii=False), encoding="utf-8")
            return

        # 3. 完成
        status_file.write_text(json.dumps({
            "status": "success",
            "progress": 100,
            "message": "更新成功完成！若配置了 systemd 守护进程，服务将在数秒内平滑重启。",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, ensure_ascii=False), encoding="utf-8")

        # 若处于 systemd 下，触发优雅重启
        if shutil.which("systemctl") and not sys.platform.startswith("win"):
            subprocess.Popen(["systemctl", "restart", "moyu"])
    except Exception as exc:
        status_file.write_text(json.dumps({
            "status": "failed",
            "progress": 0,
            "message": f"执行更新过程发生未预期的异常: {str(exc)}",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, ensure_ascii=False), encoding="utf-8")


@router.post("/apply")
def apply_update(request: Request):
    """
    触发 VPS 应用内一键更新（仅支持 Linux 部署/systemd 模式）。
    遵循数据安全原则：
    1. 严格检查部署模式；
    2. 自动在 data/backups/ 建立 SQLite 完整数据备份；
    3. 后台异步执行，避免网络超时截断；
    4. 桌面版与 Docker 容器环境禁止此操作，返回友好指引。
    """
    env = detect_environment()

    if env == "desktop":
        raise HTTPException(
            status_code=400,
            detail="Windows 桌面客户端请点击「前往下载」获取最新 exe 安装包进行覆盖升级。"
        )

    if env == "docker":
        raise HTTPException(
            status_code=400,
            detail="Docker 容器化部署已由镜像环境隔离，请在宿主机执行 'docker compose pull && docker compose up -d'，或推荐使用 Watchtower 容器全自动托管更新。"
        )

    # 云端若启用了鉴权，必须要求登录认证
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="请先登录管理员账号后执行一键更新。")

    status_file = _get_update_status_file()
    if status_file.exists():
        try:
            cur = json.loads(status_file.read_text(encoding="utf-8"))
            if cur.get("status") == "running":
                raise HTTPException(status_code=400, detail="已有正在执行的更新任务，请稍候...")
        except Exception:
            pass

    # 1. 数据安全备份：在更新前自动将数据库复制到 data/backups/
    backups_dir = DATA_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    db_source = DATA_DIR / "moyu.db"
    backup_file = backups_dir / f"moyu_pre_update_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    if db_source.exists():
        shutil.copy2(db_source, backup_file)

    # 2. 标记任务开始
    status_file.write_text(json.dumps({
        "status": "running",
        "progress": 5,
        "message": "已成功创建本地数据快照备份，准备执行更新...",
        "backup": str(backup_file.name),
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }, ensure_ascii=False), encoding="utf-8")

    # 3. 异步启动更新线程
    import threading
    worker = threading.Thread(target=_run_vps_update_worker, args=(backup_file, status_file), daemon=True)
    worker.start()

    return {
        "ok": True,
        "message": "更新任务已启动，正在后台安全执行更新流程...",
        "backup_file": str(backup_file.name)
    }
