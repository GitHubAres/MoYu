"""设定人物库 API：分类条目 CRUD、归档、章节关联。"""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["entities"])

CATEGORIES = ("character", "place", "faction", "item", "term", "custom")


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _serialize(e: dict) -> dict:
    """fields_json 解析为 fields 对象，便于前端直接使用。"""
    try:
        e["fields"] = json.loads(e.get("fields_json") or "{}")
    except (ValueError, TypeError):
        e["fields"] = {}
    return e


def _check_category(category: str):
    if category not in CATEGORIES:
        raise HTTPException(400, f"category 仅支持 {'/'.join(CATEGORIES)}")


# ---------- 条目 ----------

@router.get("/works/{work_id}/entities")
def list_entities(work_id: int, category: str = "", q: str = "", archived: int = 0):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    sql = "SELECT * FROM entities WHERE work_id=? AND archived=?"
    args: list = [work_id, 1 if archived else 0]
    if category:
        _check_category(category)
        sql += " AND category=?"
        args.append(category)
    if q:
        sql += " AND (name LIKE ? OR tags LIKE ? OR content LIKE ?)"
        args += [f"%{q}%"] * 3
    sql += " ORDER BY updated_at DESC, id DESC"
    return [_serialize(e) for e in _all(sql, args)]


class EntityIn(BaseModel):
    category: str = "character"
    name: str
    content: str = ""
    fields_json: dict = {}
    tags: str = ""


@router.post("/works/{work_id}/entities", status_code=201)
def create_entity(work_id: int, body: EntityIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    _check_category(body.category)
    db = get_db()
    cur = db.execute(
        "INSERT INTO entities(work_id, category, name, content, fields_json, tags) VALUES (?,?,?,?,?,?)",
        (work_id, body.category, body.name, body.content,
         json.dumps(body.fields_json, ensure_ascii=False), body.tags))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (cur.lastrowid,)))


@router.get("/entities/{entity_id}")
def get_entity(entity_id: int):
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


class EntityPatch(BaseModel):
    category: str | None = None
    name: str | None = None
    content: str | None = None
    fields_json: dict | None = None
    tags: str | None = None


@router.patch("/entities/{entity_id}")
def update_entity(entity_id: int, body: EntityPatch):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    data = body.model_dump(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        _check_category(data["category"])
    db = get_db()
    for k in ("category", "name", "content", "tags"):
        if data.get(k) is not None:
            db.execute(f"UPDATE entities SET {k}=? WHERE id=?", (data[k], entity_id))
    if data.get("fields_json") is not None:
        db.execute("UPDATE entities SET fields_json=? WHERE id=?",
                   (json.dumps(data["fields_json"], ensure_ascii=False), entity_id))
    db.execute("UPDATE entities SET updated_at=datetime('now','localtime') WHERE id=?", (entity_id,))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(entity_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("DELETE FROM entities WHERE id=?", (entity_id,))
    db.commit()


@router.post("/entities/{entity_id}/archive")
def toggle_archive(entity_id: int):
    e = _one("SELECT id, archived FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("UPDATE entities SET archived=?, updated_at=datetime('now','localtime') WHERE id=?",
               (0 if e["archived"] else 1, entity_id))
    db.commit()
    return _serialize(_one("SELECT * FROM entities WHERE id=?", (entity_id,)))


# ---------- 章节关联 ----------

@router.get("/entities/{entity_id}/chapters")
def entity_chapters(entity_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    return _all(
        """SELECT c.id, c.title, c.status, c.word_count, c.updated_at,
                  v.title AS volume_title, v.id AS volume_id
           FROM chapter_entities ce
           JOIN chapters c ON c.id = ce.chapter_id
           JOIN volumes v ON v.id = c.volume_id
           WHERE ce.entity_id=? ORDER BY v.sort_order, c.sort_order, c.id""", (entity_id,))


class ChapterLinkIn(BaseModel):
    chapter_id: int


@router.post("/entities/{entity_id}/chapters", status_code=201)
def link_entity_chapter(entity_id: int, body: ChapterLinkIn):
    e = _one("SELECT id, work_id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    row = db.execute(
        """SELECT c.id FROM chapters c
           JOIN volumes v ON v.id = c.volume_id
           WHERE c.id=? AND v.work_id=?""", (body.chapter_id, e["work_id"])).fetchone()
    if row is None:
        raise HTTPException(400, "章节不存在或不属于该作品")
    db.execute("INSERT OR IGNORE INTO chapter_entities(chapter_id, entity_id) VALUES (?,?)",
               (body.chapter_id, entity_id))
    db.commit()
    return entity_chapters(entity_id)


@router.delete("/entities/{entity_id}/chapters/{chapter_id}", status_code=204)
def unlink_entity_chapter(entity_id: int, chapter_id: int):
    _one("SELECT id FROM entities WHERE id=?", (entity_id,))
    db = get_db()
    db.execute("DELETE FROM chapter_entities WHERE entity_id=? AND chapter_id=?",
               (entity_id, chapter_id))
    db.commit()


@router.get("/chapters/{chapter_id}/entities")
def chapter_entities(chapter_id: int):
    """某章节关联的设定条目（工作台 AI 上下文用）。"""
    _one("SELECT id FROM chapters WHERE id=?", (chapter_id,))
    return _all(
        """SELECT e.id, e.name, e.category, e.tags, substr(e.content,1,200) AS content
           FROM entities e JOIN chapter_entities ce ON ce.entity_id=e.id
           WHERE ce.chapter_id=? AND e.archived=0""", (chapter_id,))
