# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""伏笔看板 API：按状态分栏（已埋设/待回收/已回收）。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["board"])

STATUSES = ("planted", "pending", "resolved")

LIST_SQL = """
    SELECT f.*, c.title AS chapter_title, n.title AS outline_title
    FROM foreshadows f
    LEFT JOIN chapters c ON c.id = f.chapter_id
    LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
"""


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _foreshadow(fid: int):
    return _one(LIST_SQL + " WHERE f.id=?", (fid,))


def _check_status(status: str):
    if status not in STATUSES:
        raise HTTPException(400, f"status 须为 {'/'.join(STATUSES)}")


def _check_outline_node(work_id: int, outline_node_id: int | None):
    if outline_node_id is None:
        return
    row = get_db().execute(
        "SELECT id FROM outline_nodes WHERE id=? AND work_id=?",
        (outline_node_id, work_id)).fetchone()
    if row is None:
        raise HTTPException(400, "所选大纲节点不存在或不属于该作品")


@router.get("/works/{work_id}/foreshadows")
def list_foreshadows(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    return _all(LIST_SQL + " WHERE f.work_id=? ORDER BY f.id DESC", (work_id,))


class ForeshadowIn(BaseModel):
    title: str
    content: str = ""
    status: str = "planted"
    chapter_id: int | None = None
    outline_node_id: int | None = None


@router.post("/works/{work_id}/foreshadows", status_code=201)
def create_foreshadow(work_id: int, body: ForeshadowIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    _check_status(body.status)
    db = get_db()
    from app.services.asset_hub import upsert_foreshadow
    try:
        return upsert_foreshadow(
            db,
            work_id=work_id,
            title=body.title,
            content=body.content,
            status=body.status,
            chapter_id=body.chapter_id,
            outline_node_id=body.outline_node_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/foreshadows/{foreshadow_id}")
def update_foreshadow(foreshadow_id: int, body: dict):
    old = _foreshadow(foreshadow_id)
    db = get_db()
    if "status" in body:
        _check_status(body["status"])
    if body.get("chapter_id") is not None:
        _one("SELECT id FROM chapters WHERE id=?", (body["chapter_id"],))
    if body.get("outline_node_id") is not None:
        _check_outline_node(old["work_id"], body["outline_node_id"])
    for k in ("title", "content", "status", "chapter_id", "outline_node_id"):
        if k in body:
            db.execute(f"UPDATE foreshadows SET {k}=? WHERE id=?", (body[k], foreshadow_id))
    db.commit()
    return _foreshadow(foreshadow_id)


@router.delete("/foreshadows/{foreshadow_id}", status_code=204)
def delete_foreshadow(foreshadow_id: int):
    _one("SELECT id FROM foreshadows WHERE id=?", (foreshadow_id,))
    db = get_db()
    db.execute("DELETE FROM foreshadows WHERE id=?", (foreshadow_id,))
    db.commit()


# ---------- 章节跨卷移动（拖拽排序用，works.py 的 PATCH 不支持改 volume_id） ----------

class ChapterMoveIn(BaseModel):
    volume_id: int
    sort_order: int | None = None  # 缺省时排到目标卷末尾


@router.post("/chapters/{chapter_id}/move")
def move_chapter(chapter_id: int, body: ChapterMoveIn):
    ch = _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
    vol = _one("SELECT * FROM volumes WHERE id=?", (body.volume_id,))
    db = get_db()
    if body.sort_order is None:
        n = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM chapters WHERE volume_id=?",
                       (body.volume_id,)).fetchone()[0]
    else:
        n = body.sort_order
    db.execute("UPDATE chapters SET volume_id=?, sort_order=?, updated_at=datetime('now','localtime') WHERE id=?",
               (body.volume_id, n, chapter_id))
    for vid in {ch["volume_id"], vol["id"]}:
        db.execute(
            """UPDATE works SET updated_at=datetime('now','localtime')
               WHERE id=(SELECT work_id FROM volumes WHERE id=?)""", (vid,))
    db.commit()
    return _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
