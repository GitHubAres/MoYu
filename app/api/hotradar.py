# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""热点雷达业务路由：榜单查询、手动刷新、热点收藏、一键立项。"""
import json
import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..db import get_db
from ..services.hotradar_fetcher import fetch_all_platforms, save_hot_topics
from ..services.hotradar_scheduler import cleanup_expired_topics
from .auth import is_authenticated

router = APIRouter(prefix="/hotradar", tags=["hotradar"])

# 刷新节流记录（上次成功刷新的时间戳）
_LAST_REFRESH_TIMESTAMP = 0.0
_REFRESH_COOLDOWN_SECONDS = 30.0  # 30秒内禁止重复高频触发


def _require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="请先登录后操作。")


class ToOutlineRequest(BaseModel):
    topic_id: int
    direction: Optional[str] = ""
    target_readers: Optional[str] = ""


class CollectRequest(BaseModel):
    topic_id: int
    collected: Optional[bool] = None  # None 表示切换 toggle
    work_id: Optional[int] = None     # 关联沉淀创作资产的目标作品 ID


@router.get("/list")
def list_hot_topics(
    platform: Optional[str] = Query(None, description="平台过滤：起点/番茄/晋江"),
    genre: Optional[str] = Query(None, description="题材关键词过滤"),
    collected: Optional[int] = Query(None, description="是否已收藏：0/1"),
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
):
    """查询热榜列表，支持按平台、题材标签与收藏状态筛选"""
    db = get_db()
    query = "SELECT * FROM hot_topics WHERE 1=1"
    params = []

    if platform and platform.strip():
        query += " AND platform = ?"
        params.append(platform.strip())

    if collected is not None:
        query += " AND collected = ?"
        params.append(1 if collected else 0)

    if genre and genre.strip():
        query += " AND (genre_tags LIKE ? OR title LIKE ?)"
        kw = f"%{genre.strip()}%"
        params.extend([kw, kw])

    query += " ORDER BY platform ASC, rank ASC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["genre_tags"] = json.loads(item.get("genre_tags") or "[]")
        except Exception:
            item["genre_tags"] = []
        item["collected"] = bool(item.get("collected"))
        results.append(item)

    return {
        "ok": True,
        "total": len(results),
        "items": results,
    }


@router.post("/refresh")
async def refresh_hot_topics(request: Request):
    """手动触发热榜抓取刷新（施加冷却防护防刷）"""
    _require_auth(request)
    global _LAST_REFRESH_TIMESTAMP
    now = time.time()
    elapsed = now - _LAST_REFRESH_TIMESTAMP

    if elapsed < _REFRESH_COOLDOWN_SECONDS:
        remain = int(_REFRESH_COOLDOWN_SECONDS - elapsed)
        return {
            "ok": False,
            "message": f"刷新过于频繁，请等待 {remain} 秒后再试。",
            "cooldown_remaining": remain,
        }

    try:
        topics = await fetch_all_platforms(limit_per_platform=50)
        conn = get_db()
        count = save_hot_topics(conn, topics)
        cleanup_expired_topics(conn, days=7)
        _LAST_REFRESH_TIMESTAMP = now
        return {
            "ok": True,
            "message": f"热榜更新完成，已同步 {count} 条数据。",
            "synced_count": count,
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"热榜更新失败：{str(e)}",
            "synced_count": 0,
        }


@router.post("/collect")
def toggle_collect_topic(body: CollectRequest, request: Request):
    """收藏或取消收藏某个热点条目，并在收藏时通过 asset_hub 沉淀创作资产"""
    _require_auth(request)
    db = get_db()
    row = db.execute("SELECT * FROM hot_topics WHERE id = ?", (body.topic_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="热点条目不存在。")

    cur_collected = bool(row["collected"])
    new_status = not cur_collected if body.collected is None else bool(body.collected)

    db.execute("UPDATE hot_topics SET collected = ? WHERE id = ?", (1 if new_status else 0, body.topic_id))
    db.commit()

    asset_result = None
    if new_status:
        # 当作者主动收藏时，通过 asset_hub 写入 MOYU:ASSETS 契约块沉淀创作资产
        from ..services.asset_hub import record_hot_topic_asset
        asset_result = record_hot_topic_asset(db, body.work_id, dict(row))

    return {
        "ok": True,
        "topic_id": body.topic_id,
        "collected": new_status,
        "asset": asset_result,
        "message": "已收藏并沉淀灵感资产" if new_status else "已取消收藏",
    }


@router.post("/to-outline")
def hot_topic_to_outline_draft(body: ToOutlineRequest, request: Request):
    """
    基于热点条目生成 P0 立项草稿（work_info：标题建议、一句话故事、方向、目标读者等）。
    注意：本接口仅返回草稿供作者在前端预览确认，未经作者确认绝不写入 works 表。
    """
    _require_auth(request)
    db = get_db()
    row = db.execute("SELECT * FROM hot_topics WHERE id = ?", (body.topic_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="未找到对应的热点数据。")

    title = row["title"]
    platform = row["platform"]
    try:
        tags = json.loads(row["genre_tags"] or "[]")
    except Exception:
        tags = []

    primary_genre = tags[0] if tags else "通用题材"
    sub_genres = " / ".join(tags[1:]) if len(tags) > 1 else primary_genre

    # 构造规范立项草稿建议
    draft = {
        "topic_id": body.topic_id,
        "reference_work": f"《{title}》（{platform}热榜）",
        "suggested_title": f"{title}衍生立项灵感",
        "genre": primary_genre,
        "sub_genres": tags,
        "direction": body.direction or f"参考【{platform}】热门爆款《{title}》，聚焦【{sub_genres}】核心看点，构建差异化反差设定。",
        "target_readers": body.target_readers or f"{primary_genre}受众、热衷快节奏与高爽点设定的读者群体",
        "one_sentence_story": f"在{primary_genre}背景下，主角凭借独特反差金手指在危机中破局崛起，融合《{title}》的情绪节奏。",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    return {
        "ok": True,
        "draft": draft,
        "message": "立项草稿已生成，请在前端预览确认后再创建作品。",
    }