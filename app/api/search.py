"""全局搜索 API：跨表 LIKE 检索，分组返回。"""
from fastapi import APIRouter

from ..db import get_db

router = APIRouter(tags=["search"])

GROUP_LIMIT = 5
TOTAL_LIMIT = 20


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _snippet(text: str, q: str, span: int = 30) -> str:
    """取命中处前后各 span 字的片段；未命中则返回开头片段。"""
    text = text or ""
    idx = text.lower().find(q.lower())
    if idx < 0:
        return text[: span * 2]
    start = max(0, idx - span)
    end = min(len(text), idx + len(q) + span)
    frag = text[start:end]
    return ("…" if start > 0 else "") + frag + ("…" if end < len(text) else "")


@router.get("/search")
def global_search(q: str = ""):
    q = "".join(q.split())  # 去空格
    if not q:
        return {"q": "", "results": []}
    like = f"%{q}%"
    results: list = []

    # 作品：标题 / 简介
    for w in _all(
        "SELECT id, title, intro FROM works WHERE title LIKE ? OR intro LIKE ? LIMIT ?",
        (like, like, GROUP_LIMIT)):
        results.append({
            "type": "work", "id": w["id"], "title": w["title"],
            "snippet": _snippet(w["intro"], q) if q.lower() in (w["intro"] or "").lower() else "",
        })

    # 章节：标题 / 正文
    for c in _all(
        """SELECT c.id, c.title, c.content, v.work_id, w.title AS work_title
           FROM chapters c
           JOIN volumes v ON v.id = c.volume_id
           JOIN works w ON w.id = v.work_id
           WHERE c.title LIKE ? OR c.content LIKE ? LIMIT ?""",
        (like, like, GROUP_LIMIT)):
        results.append({
            "type": "chapter", "id": c["id"], "title": c["title"],
            "work_id": c["work_id"], "work_title": c["work_title"],
            "snippet": _snippet(c["content"], q) if q.lower() in (c["content"] or "").lower() else "",
        })

    # 设定：名称 / 内容 / 标签
    for e in _all(
        """SELECT e.id, e.name, e.category, e.work_id, w.title AS work_title
           FROM entities e JOIN works w ON w.id = e.work_id
           WHERE e.name LIKE ? OR e.content LIKE ? OR e.tags LIKE ? LIMIT ?""",
        (like, like, like, GROUP_LIMIT)):
        results.append({
            "type": "entity", "id": e["id"], "name": e["name"],
            "category": e["category"], "work_id": e["work_id"],
            "work_title": e["work_title"],
        })

    # 大纲节点：标题 / 梗概
    for o in _all(
        "SELECT id, title, work_id FROM outline_nodes WHERE title LIKE ? OR synopsis LIKE ? LIMIT ?",
        (like, like, GROUP_LIMIT)):
        results.append({
            "type": "outline", "id": o["id"], "title": o["title"], "work_id": o["work_id"],
        })

    return {"q": q, "results": results[:TOTAL_LIMIT]}
