# -*- coding: utf-8 -*-
"""墨语 MoYu 资产中枢 (AssetHub)

统一管理创作资产（时间线事件、伏笔、大纲节点、章节）的绑定契约、写侧幂等入库、读侧聚合及解绑善后。
全库关于 foreshadows 与 timeline_events 的写入口统一收口于此。
"""
from typing import Any, Optional
from app.services.output_normalizer import sanitize_asset_item


def resolve_binding(
    db,
    work_id: int,
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[int]]:
    """两键互派生与合法性校验：

    - 若只提供 outline_node_id，自动反查回填其所属的 chapter_id；
    - 若只提供 chapter_id，自动反查绑定到该章节的首个 outline_node_id；
    - 两者都提供时，校验属于该作品且互不冲突。
    返回: (chapter_id, outline_node_id)
    """
    if outline_node_id and not chapter_id:
        row = db.execute(
            "SELECT chapter_id FROM outline_nodes WHERE id = ? AND work_id = ?",
            (outline_node_id, work_id),
        ).fetchone()
        if row and row[0]:
            chapter_id = row[0]
    elif chapter_id and not outline_node_id:
        row = db.execute(
            "SELECT id FROM outline_nodes WHERE chapter_id = ? AND work_id = ? ORDER BY id ASC LIMIT 1",
            (chapter_id, work_id),
        ).fetchone()
        if row and row[0]:
            outline_node_id = row[0]

    # 校验合法性
    if chapter_id is not None:
        c = db.execute(
            """SELECT c.id FROM chapters c
               JOIN volumes v ON v.id = c.volume_id
               WHERE c.id = ? AND v.work_id = ?""",
            (chapter_id, work_id),
        ).fetchone()
        if not c:
            raise ValueError(f"章节 id={chapter_id} 不存在或不属于作品 {work_id}")

    if outline_node_id is not None:
        n = db.execute(
            "SELECT id FROM outline_nodes WHERE id = ? AND work_id = ?",
            (outline_node_id, work_id),
        ).fetchone()
        if not n:
            raise ValueError(f"大纲节点 id={outline_node_id} 不存在或不属于作品 {work_id}")

    return chapter_id, outline_node_id


def upsert_foreshadow(
    db,
    work_id: int,
    title: str,
    content: str = "",
    status: str = "planted",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> dict[str, Any]:
    """向伏笔看板写入伏笔（保证双键契约与回流幂等）。

    幂等键：work_id + title + 绑定关系 (chapter_id / outline_node_id)。
    """
    title = (title or "").strip()
    content = (content or "").strip()
    status = (status or "planted").strip()

    ok, reason = sanitize_asset_item({"title": title, "content": content, "status": status}, "foreshadow")
    if not ok:
        return {
            "id": None,
            "work_id": work_id,
            "title": title,
            "content": content,
            "status": status,
            "chapter_id": chapter_id,
            "outline_node_id": outline_node_id,
            "_rejected": True,
            "_reason": reason,
            "_is_new": False,
        }

    if not title:
        raise ValueError("伏笔标题不能为空")
    chapter_id, outline_node_id = resolve_binding(db, work_id, chapter_id, outline_node_id)

    query = """
        SELECT id FROM foreshadows
        WHERE work_id = ? AND title = ?
          AND (chapter_id IS ? OR chapter_id = ?)
          AND (outline_node_id IS ? OR outline_node_id = ?)
        LIMIT 1
    """
    dup = db.execute(
        query,
        (work_id, title, chapter_id, chapter_id, outline_node_id, outline_node_id),
    ).fetchone()

    is_new = False
    if dup:
        fs_id = dup[0]
        if content:
            db.execute(
                "UPDATE foreshadows SET content = COALESCE(NULLIF(content, ''), ?), status = ? WHERE id = ?",
                (content, status, fs_id),
            )
            db.commit()
    else:
        cur = db.execute(
            """INSERT INTO foreshadows (work_id, title, content, status, chapter_id, outline_node_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (work_id, title, content, status, chapter_id, outline_node_id),
        )
        db.commit()
        fs_id = cur.lastrowid
        is_new = True

    row = db.execute(
        """SELECT f.*, c.title AS chapter_title, n.title AS outline_title
           FROM foreshadows f
           LEFT JOIN chapters c ON c.id = f.chapter_id
           LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
           WHERE f.id = ?""",
        (fs_id,),
    ).fetchone()

    res = dict(row)
    res["_is_new"] = is_new
    return res


def upsert_timeline_event(
    db,
    work_id: int,
    event: str,
    time_label: str = "",
    characters: str = "",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
    sort_order: Optional[int] = None,
) -> dict[str, Any]:
    """向时间线写入剧情事件（保证双键契约与回流幂等）。

    幂等键：work_id + event + 绑定关系 (chapter_id / outline_node_id)。
    """
    event = (event or "").strip()
    time_label = (time_label or "").strip()
    characters = (characters or "").strip()

    ok, reason = sanitize_asset_item({"event": event, "time_label": time_label, "characters": characters}, "timeline_event")
    if not ok:
        return {
            "id": None,
            "work_id": work_id,
            "event": event,
            "time_label": time_label,
            "characters": characters,
            "chapter_id": chapter_id,
            "outline_node_id": outline_node_id,
            "sort_order": sort_order,
            "_rejected": True,
            "_reason": reason,
            "_is_new": False,
        }

    if not event:
        raise ValueError("事件内容不能为空")
    chapter_id, outline_node_id = resolve_binding(db, work_id, chapter_id, outline_node_id)

    query = """
        SELECT id FROM timeline_events
        WHERE work_id = ? AND event = ?
          AND (chapter_id IS ? OR chapter_id = ?)
          AND (outline_node_id IS ? OR outline_node_id = ?)
        LIMIT 1
    """
    dup = db.execute(
        query,
        (work_id, event, chapter_id, chapter_id, outline_node_id, outline_node_id),
    ).fetchone()

    is_new = False
    if dup:
        ev_id = dup[0]
    else:
        if sort_order is None:
            max_order = db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM timeline_events WHERE work_id = ?",
                (work_id,),
            ).fetchone()[0]
            sort_order = max_order

        cur = db.execute(
            """INSERT INTO timeline_events (work_id, time_label, event, characters, chapter_id, outline_node_id, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (work_id, time_label, event, characters, chapter_id, outline_node_id, sort_order),
        )
        db.commit()
        ev_id = cur.lastrowid
        is_new = True

    row = db.execute(
        """SELECT te.*, c.title AS chapter_title, n.title AS outline_title
           FROM timeline_events te
           LEFT JOIN chapters c ON c.id = te.chapter_id
           LEFT JOIN outline_nodes n ON n.id = te.outline_node_id
           WHERE te.id = ?""",
        (ev_id,),
    ).fetchone()

    res = dict(row)
    res["_is_new"] = is_new
    return res


def aggregate_for_node(db, work_id: int, node_id: int) -> dict[str, Any]:
    """唯一读侧大纲节点剧情聚合口：包含直接绑节点 OR 绑该节点所属章节的数据。"""
    node = db.execute(
        "SELECT id, work_id, parent_id, title, synopsis, status, chapter_id FROM outline_nodes WHERE id = ? AND work_id = ?",
        (node_id, work_id),
    ).fetchone()
    if not node:
        return {"node_id": node_id, "node": {}, "timeline_events": [], "foreshadows": []}

    node_dict = dict(node)
    ch_id = node_dict.get("chapter_id")
    if ch_id is not None:
        tl_sql = """
            SELECT te.*, c.title AS chapter_title, n.title AS outline_title
            FROM timeline_events te
            LEFT JOIN chapters c ON c.id = te.chapter_id
            LEFT JOIN outline_nodes n ON n.id = te.outline_node_id
            WHERE te.work_id = ? AND (te.outline_node_id = ? OR te.chapter_id = ?)
            ORDER BY te.sort_order ASC, te.id ASC
        """
        tl_params = (work_id, node_id, ch_id)

        fs_sql = """
            SELECT f.*, c.title AS chapter_title, n.title AS outline_title
            FROM foreshadows f
            LEFT JOIN chapters c ON c.id = f.chapter_id
            LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
            WHERE f.work_id = ? AND (f.outline_node_id = ? OR f.chapter_id = ?)
            ORDER BY f.id DESC
        """
        fs_params = (work_id, node_id, ch_id)
    else:
        tl_sql = """
            SELECT te.*, c.title AS chapter_title, n.title AS outline_title
            FROM timeline_events te
            LEFT JOIN chapters c ON c.id = te.chapter_id
            LEFT JOIN outline_nodes n ON n.id = te.outline_node_id
            WHERE te.work_id = ? AND te.outline_node_id = ?
            ORDER BY te.sort_order ASC, te.id ASC
        """
        tl_params = (work_id, node_id)

        fs_sql = """
            SELECT f.*, c.title AS chapter_title, n.title AS outline_title
            FROM foreshadows f
            LEFT JOIN chapters c ON c.id = f.chapter_id
            LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
            WHERE f.work_id = ? AND f.outline_node_id = ?
            ORDER BY f.id DESC
        """
        fs_params = (work_id, node_id)

    timeline_events = [dict(r) for r in db.execute(tl_sql, tl_params).fetchall()]
    foreshadows = [dict(r) for r in db.execute(fs_sql, fs_params).fetchall()]

    return {
        "node_id": node_id,
        "node": node_dict,
        "timeline_events": timeline_events,
        "foreshadows": foreshadows,
    }


def aggregate_for_chapter(db, work_id: int, chapter_id: int) -> dict[str, Any]:
    """唯一读侧章节剧情聚合口：包含直接绑章节 OR 绑该章节所对应节点的数据。"""
    node_rows = db.execute(
        "SELECT id FROM outline_nodes WHERE work_id = ? AND chapter_id = ?",
        (work_id, chapter_id),
    ).fetchall()
    node_ids = [r[0] for r in node_rows]

    if node_ids:
        placeholders = ",".join("?" for _ in node_ids)
        tl_sql = f"""
            SELECT te.*, c.title AS chapter_title, n.title AS outline_title
            FROM timeline_events te
            LEFT JOIN chapters c ON c.id = te.chapter_id
            LEFT JOIN outline_nodes n ON n.id = te.outline_node_id
            WHERE te.work_id = ? AND (te.chapter_id = ? OR te.outline_node_id IN ({placeholders}))
            ORDER BY te.sort_order ASC, te.id ASC
        """
        tl_params = (work_id, chapter_id, *node_ids)

        fs_sql = f"""
            SELECT f.*, c.title AS chapter_title, n.title AS outline_title
            FROM foreshadows f
            LEFT JOIN chapters c ON c.id = f.chapter_id
            LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
            WHERE f.work_id = ? AND (f.chapter_id = ? OR f.outline_node_id IN ({placeholders}))
            ORDER BY f.id DESC
        """
        fs_params = (work_id, chapter_id, *node_ids)
    else:
        tl_sql = """
            SELECT te.*, c.title AS chapter_title, n.title AS outline_title
            FROM timeline_events te
            LEFT JOIN chapters c ON c.id = te.chapter_id
            LEFT JOIN outline_nodes n ON n.id = te.outline_node_id
            WHERE te.work_id = ? AND te.chapter_id = ?
            ORDER BY te.sort_order ASC, te.id ASC
        """
        tl_params = (work_id, chapter_id)

        fs_sql = """
            SELECT f.*, c.title AS chapter_title, n.title AS outline_title
            FROM foreshadows f
            LEFT JOIN chapters c ON c.id = f.chapter_id
            LEFT JOIN outline_nodes n ON n.id = f.outline_node_id
            WHERE f.work_id = ? AND f.chapter_id = ?
            ORDER BY f.id DESC
        """
        fs_params = (work_id, chapter_id)

    timeline_events = [dict(r) for r in db.execute(tl_sql, tl_params).fetchall()]
    foreshadows = [dict(r) for r in db.execute(fs_sql, fs_params).fetchall()]

    return {
        "chapter_id": chapter_id,
        "timeline_events": timeline_events,
        "foreshadows": foreshadows,
    }


def detach_chapter(db, chapter_id: int) -> dict[str, Any]:
    """删前影响面统计与安全解绑：解除章节与伏笔、时间线事件、大纲节点的绑定，杜绝孤儿化。"""
    foreshadows_count = db.execute("SELECT COUNT(*) FROM foreshadows WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    timeline_events_count = db.execute("SELECT COUNT(*) FROM timeline_events WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    outline_nodes_count = db.execute("SELECT COUNT(*) FROM outline_nodes WHERE chapter_id=?", (chapter_id,)).fetchone()[0]
    total = foreshadows_count + timeline_events_count + outline_nodes_count

    db.execute("UPDATE foreshadows SET chapter_id=NULL WHERE chapter_id=?", (chapter_id,))
    db.execute("UPDATE timeline_events SET chapter_id=NULL WHERE chapter_id=?", (chapter_id,))
    db.execute("UPDATE outline_nodes SET chapter_id=NULL WHERE chapter_id=?", (chapter_id,))
    db.commit()

    return {
        "chapter_id": chapter_id,
        "foreshadows": foreshadows_count,
        "timeline_events": timeline_events_count,
        "outline_nodes": outline_nodes_count,
        "total": total,
    }


def list_unbound_assets(db, work_id: int) -> dict:
    """两键皆空的产物：可看见、可归位。"""
    foreshadows = db.execute(
        "SELECT id, title, content, status, chapter_id, outline_node_id FROM foreshadows "
        "WHERE work_id=? AND chapter_id IS NULL AND outline_node_id IS NULL ORDER BY id DESC",
        (work_id,)).fetchall()
    timeline_events = db.execute(
        "SELECT id, time_label, event, characters, chapter_id, outline_node_id FROM timeline_events "
        "WHERE work_id=? AND chapter_id IS NULL AND outline_node_id IS NULL ORDER BY id DESC",
        (work_id,)).fetchall()
    return {"foreshadows": [dict(r) for r in foreshadows],
            "timeline_events": [dict(r) for r in timeline_events]}
