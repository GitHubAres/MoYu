# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""故事大纲 API：节点树 CRUD 与章节关联。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(tags=["outline"])

NODE_STATUS = ("pending", "focus", "done")


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


# ---------- 大纲节点 ----------

@router.get("/works/{work_id}/outline")
def outline_tree(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    rows = _all(
        """SELECT n.*, c.title AS chapter_title, c.word_count AS chapter_words,
                  (SELECT COUNT(*) FROM timeline_events te WHERE te.outline_node_id = n.id) AS timeline_count,
                  (SELECT COUNT(*) FROM foreshadows f WHERE f.outline_node_id = n.id) AS foreshadow_count
           FROM outline_nodes n
           LEFT JOIN chapters c ON c.id = n.chapter_id
           WHERE n.work_id=? ORDER BY n.sort_order, n.id""", (work_id,))
    nodes = {r["id"]: {**r, "children": []} for r in rows}
    tree = []
    for r in rows:
        node = nodes[r["id"]]
        if r["parent_id"] in nodes:
            nodes[r["parent_id"]]["children"].append(node)
        else:
            tree.append(node)
    return tree


class NodeIn(BaseModel):
    title: str
    parent_id: int | None = None
    synopsis: str = ""
    status: str = "pending"


@router.post("/works/{work_id}/outline", status_code=201)
def create_node(work_id: int, body: NodeIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    db = get_db()
    if body.parent_id is not None:
        parent = _one("SELECT * FROM outline_nodes WHERE id=?", (body.parent_id,))
        if parent["work_id"] != work_id:
            raise HTTPException(400, "父节点不属于该作品")
    if body.status not in NODE_STATUS:
        raise HTTPException(400, f"status 仅支持 {'/'.join(NODE_STATUS)}")
    n = db.execute(
        """SELECT COALESCE(MAX(sort_order),0)+1 FROM outline_nodes
           WHERE work_id=? AND parent_id IS ?""",
        (work_id, body.parent_id)).fetchone()[0]
    cur = db.execute(
        "INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, status, sort_order) VALUES (?,?,?,?,?,?)",
        (work_id, body.parent_id, body.title, body.synopsis, body.status, n))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return _one("SELECT * FROM outline_nodes WHERE id=?", (cur.lastrowid,))


class NodePatch(BaseModel):
    title: str | None = None
    synopsis: str | None = None
    status: str | None = None
    sort_order: int | None = None
    parent_id: int | None = None


@router.patch("/outline/{node_id}")
def update_node(node_id: int, body: NodePatch):
    node = _one("SELECT * FROM outline_nodes WHERE id=?", (node_id,))
    db = get_db()
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in NODE_STATUS:
        raise HTTPException(400, f"status 仅支持 {'/'.join(NODE_STATUS)}")
    if "parent_id" in data:
        pid = data["parent_id"]
        if pid == node_id:
            raise HTTPException(400, "节点不能作为自己的父节点")
        if pid is not None:
            # 校验父节点同作品，且不在当前节点的子树内（避免成环）
            cur = pid
            while cur is not None:
                if cur == node_id:
                    raise HTTPException(400, "父节点不能是当前节点的子孙节点")
                row = db.execute("SELECT parent_id, work_id FROM outline_nodes WHERE id=?", (cur,)).fetchone()
                if row is None or row["work_id"] != node["work_id"]:
                    raise HTTPException(400, "父节点不属于该作品")
                cur = row["parent_id"]
    for k in ("title", "synopsis", "status", "sort_order", "parent_id"):
        if k in data:
            db.execute(f"UPDATE outline_nodes SET {k}=? WHERE id=?", (data[k], node_id))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (node["work_id"],))
    db.commit()
    return _one("SELECT * FROM outline_nodes WHERE id=?", (node_id,))


@router.delete("/outline/{node_id}", status_code=204)
def delete_node(node_id: int):
    _one("SELECT id FROM outline_nodes WHERE id=?", (node_id,))
    db = get_db()
    db.execute("DELETE FROM outline_nodes WHERE id=?", (node_id,))  # 子节点外键级联
    db.commit()


# ---------- 章节关联 ----------

def _node_and_work(node_id: int):
    node = _one("SELECT * FROM outline_nodes WHERE id=?", (node_id,))
    return node, node["work_id"]


@router.post("/outline/{node_id}/create-chapter", status_code=201)
def create_chapter_from_node(node_id: int):
    node, work_id = _node_and_work(node_id)
    if node["chapter_id"]:
        raise HTTPException(400, "该节点已关联章节")
    db = get_db()
    vol = db.execute(
        "SELECT * FROM volumes WHERE work_id=? ORDER BY sort_order DESC, id DESC LIMIT 1",
        (work_id,)).fetchone()
    if vol is None:
        cur = db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,1)",
                         (work_id, "卷一"))
        vol = db.execute("SELECT * FROM volumes WHERE id=?", (cur.lastrowid,)).fetchone()
    n = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM chapters WHERE volume_id=?",
                   (vol["id"],)).fetchone()[0]
    cur = db.execute("INSERT INTO chapters(volume_id, title, sort_order) VALUES (?,?,?)",
                     (vol["id"], node["title"], n))
    chapter_id = cur.lastrowid
    db.execute("UPDATE outline_nodes SET chapter_id=? WHERE id=?", (chapter_id, node_id))
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return _one("SELECT * FROM chapters WHERE id=?", (chapter_id,))


class LinkIn(BaseModel):
    chapter_id: int | None = None


@router.post("/outline/{node_id}/link-chapter")
def link_chapter(node_id: int, body: LinkIn):
    node, work_id = _node_and_work(node_id)
    db = get_db()
    warning = None
    if body.chapter_id is not None:
        row = db.execute(
            """SELECT c.id FROM chapters c
               JOIN volumes v ON v.id = c.volume_id
               WHERE c.id=? AND v.work_id=?""", (body.chapter_id, work_id)).fetchone()
        if row is None:
            raise HTTPException(400, "章节不存在或不属于该作品")
        existing_nodes = db.execute(
            "SELECT id, title FROM outline_nodes WHERE chapter_id=? AND work_id=? AND id != ?",
            (body.chapter_id, work_id, node_id)
        ).fetchall()
        if existing_nodes:
            titles = "、".join(r["title"] for r in existing_nodes)
            warning = f"该章节已绑定到大纲节点「{titles}」，多节点绑定可能导致上下文分流"
    db.execute("UPDATE outline_nodes SET chapter_id=? WHERE id=?", (body.chapter_id, node_id))
    db.commit()
    res = dict(_one("SELECT * FROM outline_nodes WHERE id=?", (node_id,)))
    if warning:
        res["warning"] = warning
    return res


@router.get("/works/{work_id}/outline/nodes/{node_id}/plot-items")
def get_node_plot_items(work_id: int, node_id: int):
    """聚合返回大纲节点名下的剧情时间线事件与关联伏笔（统一委托 asset_hub）。"""
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    _one("SELECT id FROM outline_nodes WHERE id=? AND work_id=?", (node_id, work_id))
    db = get_db()
    from app.services.asset_hub import aggregate_for_node
    return aggregate_for_node(db, work_id, node_id)
