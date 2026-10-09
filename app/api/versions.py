# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""版本快照详情 / 恢复 / 对比 / 清理 API。"""
from fastapi import APIRouter, HTTPException

from ..db import get_db, word_count

router = APIRouter(tags=["versions"])


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _version(vid: int):
    return _one("SELECT * FROM chapter_versions WHERE id=?", (vid,))


@router.get("/versions/{version_id}")
def get_version(version_id: int):
    return _version(version_id)


@router.post("/versions/{version_id}/restore")
def restore_version(version_id: int):
    ver = _version(version_id)
    ch = _one("SELECT * FROM chapters WHERE id=?", (ver["chapter_id"],))
    db = get_db()
    # 恢复前自动留存当前正文，保证恢复操作本身可撤销
    db.execute(
        """INSERT INTO chapter_versions(chapter_id, content, word_count, source, label)
           VALUES (?,?,?,'restore_backup','恢复前自动留存')""",
        (ch["id"], ch["content"], ch["word_count"]))
    wc = word_count(ver["content"])
    db.execute(
        "UPDATE chapters SET content=?, word_count=?, updated_at=datetime('now','localtime') WHERE id=?",
        (ver["content"], wc, ch["id"]))
    db.execute(
        """UPDATE works SET updated_at=datetime('now','localtime')
           WHERE id=(SELECT work_id FROM volumes WHERE id=?)""",
        (ch["volume_id"],))
    db.commit()
    return _one("SELECT * FROM chapters WHERE id=?", (ch["id"],))


@router.get("/versions/{version_id}/diff")
def diff_version(version_id: int, against: str = "current"):
    """返回双方纯文本，行级 diff 由前端渲染。"""
    base = _version(version_id)
    if against == "current":
        ch = _one("SELECT * FROM chapters WHERE id=?", (base["chapter_id"],))
        other = {
            "id": "current", "label": "当前正文", "source": "current",
            "created_at": ch["updated_at"], "word_count": ch["word_count"],
            "content": ch["content"],
        }
    else:
        if not against.isdigit():
            raise HTTPException(400, "against 参数应为 current 或版本 ID")
        other = _version(int(against))
    return {"base": base, "against": other}


@router.post("/chapters/{chapter_id}/versions/prune")
def prune_versions(chapter_id: int):
    """自动快照超出 version_keep_auto 份时，删除最旧的部分（手动/AI/恢复留存不动）。"""
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    db = get_db()
    row = db.execute("SELECT value FROM app_settings WHERE key='version_keep_auto'").fetchone()
    keep = int(row["value"]) if row and row["value"].isdigit() else 30
    old = db.execute(
        """SELECT id FROM chapter_versions
           WHERE chapter_id=? AND source='auto'
           ORDER BY id DESC LIMIT -1 OFFSET ?""",
        (chapter_id, keep)).fetchall()
    ids = [r["id"] for r in old]
    if ids:
        marks = ",".join("?" * len(ids))
        db.execute(f"DELETE FROM chapter_versions WHERE id IN ({marks})", ids)
        db.commit()
    return {"deleted": len(ids), "keep": keep}


@router.delete("/versions/{version_id}", status_code=204)
def delete_version(version_id: int):
    _one("SELECT id FROM chapter_versions WHERE id=?", (version_id,))
    db = get_db()
    db.execute("DELETE FROM chapter_versions WHERE id=?", (version_id,))
    db.commit()
