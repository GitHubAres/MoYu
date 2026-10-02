# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""灵感便签 API。"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/notes", tags=["notes"])


def _row(r):
    return dict(r)


@router.get("")
def list_notes(work_id: int | None = None):
    db = get_db()
    if work_id:
        rows = db.execute(
            "SELECT * FROM notes WHERE work_id=? OR work_id IS NULL ORDER BY id DESC",
            (work_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
    return [_row(r) for r in rows]


class NoteIn(BaseModel):
    content: str
    tags: str = ""
    work_id: int | None = None


@router.post("", status_code=201)
def create_note(body: NoteIn):
    db = get_db()
    cur = db.execute("INSERT INTO notes(work_id, content, tags) VALUES (?,?,?)",
                     (body.work_id, body.content, body.tags))
    db.commit()
    return _row(db.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone())


@router.patch("/{note_id}")
def update_note(note_id: int, body: dict):
    db = get_db()
    if not db.execute("SELECT id FROM notes WHERE id=?", (note_id,)).fetchone():
        from fastapi import HTTPException
        raise HTTPException(404, "便签不存在")
    for k in ("content", "tags", "work_id"):
        if k in body:
            db.execute(f"UPDATE notes SET {k}=? WHERE id=?", (body[k], note_id))
    db.commit()
    return _row(db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone())


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int):
    db = get_db()
    db.execute("DELETE FROM notes WHERE id=?", (note_id,))
    db.commit()
