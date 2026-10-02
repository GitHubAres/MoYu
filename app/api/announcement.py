# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""公告模块 API：远程拉取、本地快照缓存、内置兜底三级降级与用户确认 (Ack) 管理。"""
import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import get_db
from ..paths import STATIC_DIR
from ..version import APP_VERSION
from .update import apply_mirror_to_url, compare_versions

logger = logging.getLogger("moyu.announcement")

router = APIRouter(prefix="/announcements", tags=["announcements"])

BUILTIN_PATH = STATIC_DIR / "announcements" / "builtin.json"


class RemoteAnnouncementPayload(BaseModel):
    id: str = Field(..., max_length=100)
    level: str = Field("normal", pattern="^(normal|force)$")
    title: str = Field(..., max_length=100)
    body_md: str = Field(..., max_length=5000)
    link_url: Optional[str] = ""
    link_text: Optional[str] = ""
    version_tag: Optional[str] = ""
    starts_at: Optional[str] = ""
    ends_at: Optional[str] = ""
    min_app_version: Optional[str] = ""


class AckRequest(BaseModel):
    ack_type: str = Field("confirm", pattern="^(view|confirm|dismiss_forever)$")


def _is_time_active(starts_at: Optional[str], ends_at: Optional[str]) -> bool:
    """判断公告当前是否处于生效期内。"""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if starts_at and starts_at.strip():
        # 若以时区偏移格式存在，简单比较或前缀比较
        s = starts_at.strip()
        # 兼容简易 ISO 字符串比较
        if s > now_iso and not s.startswith(now_iso[:10]):
            try:
                s_dt = datetime.datetime.fromisoformat(s)
                if s_dt > datetime.datetime.now(datetime.timezone.utc):
                    return False
            except Exception:
                pass
    if ends_at and ends_at.strip():
        e = ends_at.strip()
        try:
            e_dt = datetime.datetime.fromisoformat(e)
            if e_dt < datetime.datetime.now(datetime.timezone.utc):
                return False
        except Exception:
            if e < now_iso:
                return False
    return True


def _load_builtin_announcement() -> Optional[Dict[str, Any]]:
    """读取应用内置 static/announcements/builtin.json 兜底数据。"""
    if not BUILTIN_PATH.exists():
        return None
    try:
        content = BUILTIN_PATH.read_text(encoding="utf-8")
        raw = json.loads(content)
        validated = RemoteAnnouncementPayload(**raw)
        return validated.model_dump()
    except Exception as exc:
        logger.debug("Failed to load builtin announcement: %s", exc)
        return None


def _save_announcement_to_db(item: Dict[str, Any], source: str) -> None:
    """持久化公告快照到 announcements 表。"""
    db = get_db()
    content_str = f"{item['title']}|{item['body_md']}|{item.get('level', 'normal')}"
    chash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.execute(
        """
        INSERT INTO announcements (
            id, source, level, title, body_md, link_url, link_text,
            version_tag, starts_at, ends_at, fetched_at, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source = excluded.source,
            level = excluded.level,
            title = excluded.title,
            body_md = excluded.body_md,
            link_url = excluded.link_url,
            link_text = excluded.link_text,
            version_tag = excluded.version_tag,
            starts_at = excluded.starts_at,
            ends_at = excluded.ends_at,
            fetched_at = excluded.fetched_at,
            content_hash = excluded.content_hash
        """,
        (
            item["id"],
            source,
            item.get("level", "normal"),
            item["title"],
            item["body_md"],
            item.get("link_url", ""),
            item.get("link_text", ""),
            item.get("version_tag", ""),
            item.get("starts_at", ""),
            item.get("ends_at", ""),
            now_str,
            chash,
        ),
    )
    db.commit()


async def _fetch_remote_announcement() -> Optional[Dict[str, Any]]:
    """通过 httpx 从配置的 URL 异步拉取远程公告，超时 5 秒，异常静默降级。"""
    db = get_db()
    row_url = db.execute("SELECT value FROM app_settings WHERE key = 'announcement_url'").fetchone()
    url = (row_url["value"] if row_url else "").strip()
    if not url:
        return None

    row_mirror = db.execute("SELECT value FROM app_settings WHERE key = 'update_mirror'").fetchone()
    mirror = (row_mirror["value"] if row_mirror else "").strip()
    final_url = apply_mirror_to_url(url, mirror) if mirror else url

    headers = {
        "Accept": "application/json",
        "User-Agent": f"MoYu-Client/{APP_VERSION}",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(final_url, headers=headers)
            if resp.status_code != 200:
                logger.debug("Remote announcement returned %s", resp.status_code)
                return None
            data = resp.json()
            payload = RemoteAnnouncementPayload(**data)
            dict_data = payload.model_dump()

            # 校验 min_app_version
            if dict_data.get("min_app_version"):
                min_ver = dict_data["min_app_version"].strip()
                if compare_versions(APP_VERSION, min_ver) < 0:
                    logger.debug("App version %s < min_app_version %s", APP_VERSION, min_ver)
                    return None

            return dict_data
    except Exception as exc:
        logger.debug("Remote announcement fetch failed (silent fallback): %s", exc)
        return None


@router.get("/latest")
async def get_latest_announcement():
    """
    获取当前生效的最新公告：
    三级降级机制：远程源 (5s 超时) -> 本地已存快照缓存 -> static/announcements/builtin.json 兜底。
    返回公告详情附带当前客户端的确认状态 (acked, ack_type, acked_at)。
    """
    # 1. 尝试远程拉取并落库
    remote_data = await _fetch_remote_announcement()
    if remote_data:
        _save_announcement_to_db(remote_data, source="remote")

    db = get_db()

    # 2. 查询本地快照缓存（按 fetched_at 倒序）
    rows = db.execute(
        """
        SELECT a.*, k.acked_at, k.ack_type
        FROM announcements a
        LEFT JOIN announcement_acks k ON a.id = k.announcement_id
        ORDER BY a.fetched_at DESC, a.rowid DESC
        """
    ).fetchall()

    active_candidate = None
    for r in rows:
        d = dict(r)
        if _is_time_active(d.get("starts_at"), d.get("ends_at")):
            active_candidate = d
            break

    # 3. 若本地无有效记录，加载内置 JSON
    if not active_candidate:
        builtin_data = _load_builtin_announcement()
        if builtin_data:
            _save_announcement_to_db(builtin_data, source="builtin")
            # 重新查询
            row = db.execute(
                """
                SELECT a.*, k.acked_at, k.ack_type
                FROM announcements a
                LEFT JOIN announcement_acks k ON a.id = k.announcement_id
                WHERE a.id = ?
                """,
                (builtin_data["id"],),
            ).fetchone()
            if row:
                active_candidate = dict(row)

    if not active_candidate:
        return {"ok": True, "announcement": None}

    # 封装 ack 状态
    acked = bool(active_candidate.get("acked_at"))
    active_candidate["acked"] = acked
    return {
        "ok": True,
        "announcement": active_candidate,
    }


@router.get("")
def list_announcements():
    """获取所有历史公告快照列表（供公告中心使用），按获取时间倒序排列。"""
    db = get_db()
    rows = db.execute(
        """
        SELECT a.*, k.acked_at, k.ack_type
        FROM announcements a
        LEFT JOIN announcement_acks k ON a.id = k.announcement_id
        ORDER BY a.fetched_at DESC, a.rowid DESC
        """
    ).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d["acked"] = bool(d.get("acked_at"))
        items.append(d)

    return {"ok": True, "announcements": items}


@router.post("/{announcement_id}/ack")
def ack_announcement(announcement_id: str, body: AckRequest):
    """记录用户对公告的确认或关闭状态（幂等写入）。"""
    db = get_db()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 验证公告是否存在，若不存在先尝试内置
    row = db.execute("SELECT id FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
    if not row:
        builtin = _load_builtin_announcement()
        if builtin and builtin["id"] == announcement_id:
            _save_announcement_to_db(builtin, source="builtin")
        else:
            raise HTTPException(status_code=404, detail="公告不存在")

    db.execute(
        """
        INSERT INTO announcement_acks (announcement_id, acked_at, ack_type)
        VALUES (?, ?, ?)
        ON CONFLICT(announcement_id) DO UPDATE SET
            acked_at = excluded.acked_at,
            ack_type = excluded.ack_type
        """,
        (announcement_id, now_str, body.ack_type),
    )
    db.commit()

    return {
        "ok": True,
        "announcement_id": announcement_id,
        "ack_type": body.ack_type,
        "acked_at": now_str,
    }
