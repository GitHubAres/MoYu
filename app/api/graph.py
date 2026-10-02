# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""人物关系图谱 API：图谱数据查询与实体关系 CRUD。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["graph"])


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


@router.get("/works/{work_id}/graph")
def get_graph(work_id: int):
    """某作品的关系图谱：全部未归档设定条目为节点，实体关系为边。"""
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    nodes = _all(
        "SELECT id, name, category, tags FROM entities WHERE work_id=? AND archived=0 ORDER BY id",
        (work_id,))
    for n in nodes:
        n["tags"] = [t for t in (n.get("tags") or "").split(",") if t]
    edges = _all(
        "SELECT id, from_id, to_id, label FROM entity_relations WHERE work_id=? ORDER BY id",
        (work_id,))
    return {"nodes": nodes, "edges": edges}


class RelationIn(BaseModel):
    from_id: int
    to_id: int
    label: str = ""


@router.post("/works/{work_id}/relations", status_code=201)
def create_relation(work_id: int, body: RelationIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    if body.from_id == body.to_id:
        raise HTTPException(400, "不能与自身建立关系")
    for eid in (body.from_id, body.to_id):
        e = _one("SELECT id, work_id FROM entities WHERE id=?", (eid,))
        if e["work_id"] != work_id:
            raise HTTPException(400, "实体不存在或不属于该作品")
    db = get_db()
    dup = db.execute(
        "SELECT id FROM entity_relations WHERE work_id=? AND from_id=? AND to_id=? AND label=?",
        (work_id, body.from_id, body.to_id, body.label)).fetchone()
    if dup:
        raise HTTPException(400, "相同的关系已存在")
    cur = db.execute(
        "INSERT INTO entity_relations(work_id, from_id, to_id, label) VALUES (?,?,?,?)",
        (work_id, body.from_id, body.to_id, body.label))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return _one("SELECT * FROM entity_relations WHERE id=?", (cur.lastrowid,))


class RelationPatch(BaseModel):
    label: str


@router.patch("/relations/{relation_id}")
def update_relation(relation_id: int, body: RelationPatch):
    _one("SELECT id FROM entity_relations WHERE id=?", (relation_id,))
    db = get_db()
    db.execute("UPDATE entity_relations SET label=? WHERE id=?", (body.label, relation_id))
    db.commit()
    return _one("SELECT * FROM entity_relations WHERE id=?", (relation_id,))


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(relation_id: int):
    _one("SELECT id FROM entity_relations WHERE id=?", (relation_id,))
    db = get_db()
    db.execute("DELETE FROM entity_relations WHERE id=?", (relation_id,))
    db.commit()
