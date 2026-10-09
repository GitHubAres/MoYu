# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""自动更新模块单元测试：语义化版本比对、环境探测、GitHub 检查模拟与 VPS 更新保护。"""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.update import (
    apply_mirror_to_url,
    clean_version_str,
    clear_update_cache,
    compare_versions,
    detect_environment,
    is_newer,
    parse_version,
)
from app.db import DEFAULT_SETTINGS, get_db
from app.version import APP_VERSION


def test_default_settings_contains_update_keys():
    """验证 app/db.py DEFAULT_SETTINGS 成功注册更新模块 5 个新配置项。"""
    assert "update_channel" in DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["update_channel"] == "stable"
    assert "update_auto_check" in DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["update_auto_check"] == "1"
    assert "update_last_check" in DEFAULT_SETTINGS
    assert "update_skipped_ver" in DEFAULT_SETTINGS
    assert "update_mirror" in DEFAULT_SETTINGS


def test_semver_parse_and_comparison():
    """验证版本清理、解析与比对纯函数的准确性。"""
    # 1. clean_version_str
    assert clean_version_str("v1.4.0") == "1.4.0"
    assert clean_version_str("V2.0.1") == "2.0.1"
    assert clean_version_str("  1.3.5  ") == "1.3.5"
    assert clean_version_str("") == "0.0.0"

    # 2. parse_version
    assert parse_version("1.4.0") == (1, 4, 0, "")
    assert parse_version("v1.4.0-beta.1") == (1, 4, 0, "beta.1")
    assert parse_version("2.1") == (2, 1, 0, "")

    # 3. compare_versions
    # 主版本比较
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("1.0.0", "2.0.0") == -1
    # 次版本比较
    assert compare_versions("1.4.0", "1.3.0") == 1
    assert compare_versions("1.3.0", "1.4.0") == -1
    # 修订版本比较
    assert compare_versions("1.4.2", "1.4.1") == 1
    assert compare_versions("1.4.1", "1.4.2") == -1
    # 相等
    assert compare_versions("1.4.0", "v1.4.0") == 0
    # 正式版优先于预发布版
    assert compare_versions("1.4.0", "1.4.0-beta.1") == 1
    assert compare_versions("1.4.0-rc1", "1.4.0") == -1

    # 4. is_newer
    assert is_newer("1.4.1", "1.4.0") is True
    assert is_newer("1.4.0", "1.4.0") is False
    assert is_newer("1.3.9", "1.4.0") is False


def test_apply_mirror_to_url():
    """验证镜像加速 URL 转换逻辑。"""
    raw_url = "https://github.com/GitHubAres/MoYu/releases/tag/v1.4.0"
    assert apply_mirror_to_url(raw_url, "") == raw_url
    assert apply_mirror_to_url(raw_url, "https://ghproxy.net") == f"https://ghproxy.net/{raw_url}"
    assert apply_mirror_to_url(raw_url, "https://ghproxy.net/") == f"https://ghproxy.net/{raw_url}"


def test_detect_environment(monkeypatch):
    """验证部署形态检测逻辑分支。"""
    # 模拟桌面端
    monkeypatch.setattr("app.api.update.IS_DESKTOP_EXE", True)
    assert detect_environment() == "desktop"

    # 模拟 Docker 容器
    monkeypatch.setattr("app.api.update.IS_DESKTOP_EXE", False)
    monkeypatch.setenv("MOYU_DOCKER", "1")
    assert detect_environment() == "docker"

    # 模拟 systemd 环境
    monkeypatch.delenv("MOYU_DOCKER", raising=False)
    monkeypatch.setenv("MOYU_SYSTEMD", "1")
    assert detect_environment() == "systemd"


def test_update_check_endpoint_cached_and_new_version(client):
    """测试 /api/update/check 接口在有新版本时的返回结构与缓存机制。"""
    clear_update_cache()

    mock_release_payload = {
        "tag_name": "v99.0.0",
        "name": "墨语 MoYu v99.0.0 革命性更新",
        "body": "### 新增功能\n- 支持跨星系量子写作同步",
        "published_at": "2026-10-02T12:00:00Z",
        "html_url": "https://github.com/GitHubAres/MoYu/releases/tag/v99.0.0",
        "assets": [
            {
                "name": "墨语MoYu-v99.0.0-win64.exe",
                "browser_download_url": "https://github.com/GitHubAres/MoYu/releases/download/v99.0.0/MoYu.exe"
            },
            {
                "name": "manifest.json",
                "browser_download_url": "https://github.com/GitHubAres/MoYu/releases/download/v99.0.0/manifest.json"
            }
        ]
    }

    with patch("app.api.update.fetch_github_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_release_payload

        # 首次调用：发起请求，未命中缓存
        r1 = client.get("/api/update/check")
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert data1["ok"] is True
        assert data1["has_update"] is True
        assert data1["latest_version"] == "99.0.0"
        assert data1["cached"] is False
        assert data1["exe_name"] == "墨语MoYu-v99.0.0-win64.exe"
        assert mock_fetch.call_count == 1

        # 第二次调用：命中 10 分钟缓存
        r2 = client.get("/api/update/check")
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["cached"] is True
        assert mock_fetch.call_count == 1  # 未重复请求远程

        # 第三次调用：加 force=true 参数强制刷新
        r3 = client.get("/api/update/check?force=true")
        assert r3.status_code == 200
        data3 = r3.json()
        assert data3["cached"] is False
        assert mock_fetch.call_count == 2


def test_update_check_endpoint_up_to_date(client):
    """测试当远端版本不高于当前版本时，正确标记 has_update = False。"""
    clear_update_cache()

    mock_release_payload = {
        "tag_name": f"v{APP_VERSION}",
        "name": f"墨语 MoYu v{APP_VERSION}",
        "body": "当前稳定版本",
        "published_at": "2026-10-01T12:00:00Z",
        "html_url": "https://github.com/GitHubAres/MoYu/releases/latest",
        "assets": []
    }

    with patch("app.api.update.fetch_github_release", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_release_payload

        r = client.get("/api/update/check?force=true")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["has_update"] is False
        assert data["latest_version"] == clean_version_str(APP_VERSION)


def test_skip_version_endpoint(client):
    """测试跳过指定版本的接口功能与缓存同步失效。"""
    r = client.post("/api/update/skip", json={"version": "1.5.0"})
    assert r.status_code == 200
    assert r.json()["skipped_version"] == "1.5.0"

    db = get_db()
    row = db.execute("SELECT value FROM app_settings WHERE key = 'update_skipped_ver'").fetchone()
    assert row is not None
    assert row["value"] == "1.5.0"


def test_apply_update_protection_desktop_and_docker(client, monkeypatch):
    """验证桌面版与 Docker 容器环境下禁止执行 POST /api/update/apply。"""
    # 1. 桌面端模式
    monkeypatch.setattr("app.api.update.detect_environment", lambda: "desktop")
    r_desk = client.post("/api/update/apply")
    assert r_desk.status_code == 400
    assert "桌面客户端" in r_desk.json()["detail"]

    # 2. Docker 容器模式
    monkeypatch.setattr("app.api.update.detect_environment", lambda: "docker")
    r_dock = client.post("/api/update/apply")
    assert r_dock.status_code == 400
    assert "Docker" in r_dock.json()["detail"]


def test_apply_update_systemd_trigger_and_status(client, monkeypatch):
    """验证在可更新环境下触发一键更新时成功执行数据备份并启动后台工作流。"""
    monkeypatch.setattr("app.api.update.detect_environment", lambda: "systemd")
    monkeypatch.setattr("app.api.update.is_authenticated", lambda req: True)

    with patch("threading.Thread") as mock_thread:
        r = client.post("/api/update/apply")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "backup_file" in data
        assert mock_thread.called

    # 查验更新状态接口
    st = client.get("/api/update/status")
    assert st.status_code == 200
    status_data = st.json()
    assert status_data["status"] in ("running", "idle", "success")
