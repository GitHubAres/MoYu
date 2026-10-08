# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""作品 / 卷 / 章 / 版本 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db, word_count

router = APIRouter(tags=["works"])


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


# ---------- 作品 ----------

@router.get("/works")
def list_works(q: str = ""):
    sql = """
        SELECT w.*, COALESCE(SUM(c.word_count), 0) AS total_words
        FROM works w
        LEFT JOIN volumes v ON v.work_id = w.id
        LEFT JOIN chapters c ON c.volume_id = v.id
    """
    args: list = []
    if q:
        sql += " WHERE w.title LIKE ?"
        args.append(f"%{q}%")
    sql += " GROUP BY w.id ORDER BY w.updated_at DESC"
    works = _all(sql, args)
    for w in works:
        last = get_db().execute(
            """SELECT c.id, c.title, c.updated_at FROM chapters c
               JOIN volumes v ON v.id = c.volume_id
               WHERE v.work_id = ? ORDER BY c.updated_at DESC LIMIT 1""",
            (w["id"],),
        ).fetchone()
        w["last_chapter"] = dict(last) if last else None
    return works


class WorkIn(BaseModel):
    title: str
    intro: str = ""
    genre: str = ""


@router.post("/works", status_code=201)
def create_work(body: WorkIn):
    db = get_db()
    cur = db.execute("INSERT INTO works(title, intro, genre) VALUES (?,?,?)",
                     (body.title, body.intro, body.genre))
    db.commit()
    return _one("SELECT * FROM works WHERE id=?", (cur.lastrowid,))


@router.get("/works/{work_id}")
def get_work(work_id: int):
    return _one("SELECT * FROM works WHERE id=?", (work_id,))


@router.patch("/works/{work_id}")
def update_work(work_id: int, body: dict):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    db = get_db()
    for k in ("title", "intro", "genre", "status", "cover_color", "cover_image"):
        if k in body:
            db.execute(f"UPDATE works SET {k}=?, updated_at=datetime('now','localtime') WHERE id=?",
                       (body[k], work_id))
    db.commit()
    return _one("SELECT * FROM works WHERE id=?", (work_id,))


@router.delete("/works/{work_id}", status_code=204)
def delete_work(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    db = get_db()
    db.execute("DELETE FROM workflow_run_steps WHERE run_id IN (SELECT id FROM workflow_runs WHERE work_id=?)", (work_id,))
    db.execute("DELETE FROM workflow_runs WHERE work_id=?", (work_id,))
    db.execute("DELETE FROM works WHERE id=?", (work_id,))
    db.commit()


@router.get("/works/{work_id}/tree")
def work_tree(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    volumes = _all("SELECT * FROM volumes WHERE work_id=? ORDER BY sort_order, id", (work_id,))
    for v in volumes:
        v["chapters"] = _all(
            """SELECT id, title, status, word_count, sort_order, updated_at
               FROM chapters WHERE volume_id=? ORDER BY sort_order, id""", (v["id"],))
    return volumes


# ---------- 卷 ----------

class VolumeIn(BaseModel):
    work_id: int
    title: str


@router.post("/volumes", status_code=201)
def create_volume(body: VolumeIn):
    _one("SELECT id FROM works WHERE id=?", (body.work_id,))
    db = get_db()
    n = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM volumes WHERE work_id=?",
                   (body.work_id,)).fetchone()[0]
    cur = db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,?)",
                     (body.work_id, body.title, n))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (body.work_id,))
    db.commit()
    return _one("SELECT * FROM volumes WHERE id=?", (cur.lastrowid,))


@router.patch("/volumes/{volume_id}")
def update_volume(volume_id: int, body: dict):
    _one("SELECT id FROM volumes WHERE id=?", (volume_id,))
    db = get_db()
    if "title" in body:
        db.execute("UPDATE volumes SET title=? WHERE id=?", (body["title"], volume_id))
    if "sort_order" in body:
        db.execute("UPDATE volumes SET sort_order=? WHERE id=?", (body["sort_order"], volume_id))
    db.commit()
    return _one("SELECT * FROM volumes WHERE id=?", (volume_id,))


@router.delete("/volumes/{volume_id}", status_code=204)
def delete_volume(volume_id: int):
    _one("SELECT id FROM volumes WHERE id=?", (volume_id,))
    db = get_db()
    db.execute("DELETE FROM volumes WHERE id=?", (volume_id,))
    db.commit()


# ---------- 章 ----------

class ChapterIn(BaseModel):
    volume_id: int
    title: str


@router.post("/chapters", status_code=201)
def create_chapter(body: ChapterIn):
    _one("SELECT id FROM volumes WHERE id=?", (body.volume_id,))
    db = get_db()
    n = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM chapters WHERE volume_id=?",
                   (body.volume_id,)).fetchone()[0]
    cur = db.execute("INSERT INTO chapters(volume_id, title, sort_order) VALUES (?,?,?)",
                     (body.volume_id, body.title, n))
    db.commit()
    return _one("SELECT * FROM chapters WHERE id=?", (cur.lastrowid,))


@router.get("/chapters/{chapter_id}")
def get_chapter(chapter_id: int):
    return _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))


class ChapterPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None
    sort_order: int | None = None
    cursor_pos: int | None = None
    snapshot_source: str | None = None  # 内容变更时顺带存版本快照
    snapshot_label: str | None = None   # 快照可读标签


@router.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: int, body: ChapterPatch):
    old = _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
    db = get_db()
    if body.title is not None:
        db.execute("UPDATE chapters SET title=? WHERE id=?", (body.title, chapter_id))
        # 同步更新关联大纲节点的标题，保持章节与大纲一致
        db.execute("UPDATE outline_nodes SET title=? WHERE chapter_id=?", (body.title, chapter_id))
    if body.status is not None:
        db.execute("UPDATE chapters SET status=? WHERE id=?", (body.status, chapter_id))
    if body.sort_order is not None:
        db.execute("UPDATE chapters SET sort_order=? WHERE id=?", (body.sort_order, chapter_id))
    if body.cursor_pos is not None:
        db.execute("UPDATE chapters SET cursor_pos=? WHERE id=?", (body.cursor_pos, chapter_id))
    if body.content is not None:
        wc = word_count(body.content)
        db.execute("UPDATE chapters SET content=?, word_count=? WHERE id=?",
                   (body.content, wc, chapter_id))
        if body.snapshot_source:
            # 自动快照节流：无标签的 auto 快照距上一份不足 5 分钟则原地更新，防止版本表膨胀；
            # 带标签的（如"采纳前自动留存"）始终新写一份
            if body.snapshot_source == "auto" and not body.snapshot_label:
                last = db.execute(
                    """SELECT id FROM chapter_versions
                       WHERE chapter_id=? AND source='auto'
                         AND created_at > datetime('now','localtime','-5 minutes')""",
                    (chapter_id,)).fetchone()
                if last:
                    db.execute("UPDATE chapter_versions SET content=?, word_count=? WHERE id=?",
                               (body.content, wc, last["id"]))
                else:
                    db.execute(
                        "INSERT INTO chapter_versions(chapter_id, content, word_count, source, label) VALUES (?,?,?,?,?)",
                        (chapter_id, body.content, wc, "auto", body.snapshot_label or ""))
            else:
                db.execute(
                    "INSERT INTO chapter_versions(chapter_id, content, word_count, source, label) VALUES (?,?,?,?,?)",
                    (chapter_id, body.content, wc, body.snapshot_source, body.snapshot_label or ""))
    db.execute("UPDATE chapters SET updated_at=datetime('now','localtime') WHERE id=?", (chapter_id,))
    db.execute(
        """UPDATE works SET updated_at=datetime('now','localtime')
           WHERE id=(SELECT work_id FROM volumes WHERE id=?)""",
        (old["volume_id"],))
    db.commit()
    return _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))


@router.get("/chapters/{chapter_id}/delete-impact")
def get_chapter_delete_impact(chapter_id: int):
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    db = get_db()
    foreshadows_count = db.execute("SELECT COUNT(*) FROM foreshadows WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    timeline_events_count = db.execute("SELECT COUNT(*) FROM timeline_events WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    outline_nodes_count = db.execute("SELECT COUNT(*) FROM outline_nodes WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    return {
        "chapter_id": chapter_id,
        "foreshadows": foreshadows_count,
        "timeline_events": timeline_events_count,
        "outline_nodes": outline_nodes_count,
        "total": foreshadows_count + timeline_events_count + outline_nodes_count,
    }


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: int):
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    db = get_db()
    from app.services.asset_hub import detach_chapter
    impact = detach_chapter(db, chapter_id)
    db.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
    db.commit()
    return {
        "ok": True,
        "impact": impact,
    }


# ---------- 版本快照 ----------

class SnapshotIn(BaseModel):
    label: str = ""


@router.post("/chapters/{chapter_id}/snapshot", status_code=201)
def snapshot(chapter_id: int, body: SnapshotIn | None = None):
    ch = _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))
    label = (body.label if body else "") or ""
    db = get_db()
    cur = db.execute(
        "INSERT INTO chapter_versions(chapter_id, content, word_count, source, label) VALUES (?,?,?,'manual',?)",
        (chapter_id, ch["content"], ch["word_count"], label))
    db.commit()
    return _one("SELECT * FROM chapter_versions WHERE id=?", (cur.lastrowid,))


@router.get("/chapters/{chapter_id}/versions")
def list_versions(chapter_id: int):
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    return _all(
        """SELECT id, word_count, source, label, created_at, substr(content,1,60) AS preview
           FROM chapter_versions WHERE chapter_id=? ORDER BY id DESC""", (chapter_id,))


# ---------- 仪表盘统计 ----------

@router.get("/stats/dashboard")
def dashboard_stats():
    db = get_db()
    total = db.execute("SELECT COALESCE(SUM(word_count),0) FROM chapters").fetchone()[0]
    today = db.execute(
        """SELECT COALESCE(SUM(word_count),0) FROM chapters
           WHERE date(updated_at)=date('now','localtime')""").fetchone()[0]
    works = db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    chapters = db.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
    return {"total_words": total, "today_words": today,
            "work_count": works, "chapter_count": chapters}
