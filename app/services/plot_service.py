# -*- coding: utf-8 -*-
"""三位一体剧情脉络领域服务 (Plot Triad Service: 大纲 ↔ 时间线 ↔ 伏笔)"""
from typing import Optional, Any


def get_node_plot_triad(db, work_id: int, node_id: int) -> dict[str, Any]:
    """获取指定大纲节点的三位一体剧情聚合全貌（大纲详情 + 绑定事件 + 关联伏笔）。"""
    node = db.execute(
        "SELECT id, work_id, parent_id, title, synopsis, status, chapter_id FROM outline_nodes WHERE id = ? AND work_id = ?",
        (node_id, work_id),
    ).fetchone()
    if not node:
        return {}

    node_dict = dict(node)
    ch_id = node_dict.get("chapter_id")
    if ch_id is not None:
        events = db.execute(
            """SELECT id, time_label, event, characters, chapter_id, outline_node_id, created_at
               FROM timeline_events
               WHERE work_id = ? AND (outline_node_id = ? OR chapter_id = ?)
               ORDER BY sort_order ASC, id ASC""",
            (work_id, node_id, ch_id),
        ).fetchall()
        foreshadows = db.execute(
            """SELECT id, title, content, status, chapter_id, outline_node_id, created_at
               FROM foreshadows
               WHERE work_id = ? AND (outline_node_id = ? OR chapter_id = ?)
               ORDER BY id ASC""",
            (work_id, node_id, ch_id),
        ).fetchall()
    else:
        events = db.execute(
            """SELECT id, time_label, event, characters, chapter_id, outline_node_id, created_at
               FROM timeline_events
               WHERE work_id = ? AND outline_node_id = ?
               ORDER BY sort_order ASC, id ASC""",
            (work_id, node_id),
        ).fetchall()
        foreshadows = db.execute(
            """SELECT id, title, content, status, chapter_id, outline_node_id, created_at
               FROM foreshadows
               WHERE work_id = ? AND outline_node_id = ?
               ORDER BY id ASC""",
            (work_id, node_id),
        ).fetchall()

    return {
        "node": node_dict,
        "timeline_events": [dict(e) for e in events],
        "foreshadows": [dict(f) for f in foreshadows],
    }


def add_timeline_event(
    db,
    work_id: int,
    time_label: str,
    event: str,
    characters: str = "",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> dict:
    """向时间线添加一条剧情事件，规范记录关联的大纲节点与章节。"""
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM timeline_events WHERE work_id = ?",
        (work_id,),
    ).fetchone()[0]

    cur = db.execute(
        """INSERT INTO timeline_events (work_id, time_label, event, characters, chapter_id, outline_node_id, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (work_id, time_label.strip(), event.strip(), characters.strip(), chapter_id, outline_node_id, max_order),
    )
    db.commit()
    inserted_id = cur.lastrowid
    row = db.execute("SELECT * FROM timeline_events WHERE id = ?", (inserted_id,)).fetchone()
    return dict(row)


def add_foreshadow(
    db,
    work_id: int,
    title: str,
    content: str = "",
    status: str = "planted",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> dict:
    """向伏笔看板埋下一条伏笔，规范记录关联的大纲节点与章节。"""
    cur = db.execute(
        """INSERT INTO foreshadows (work_id, title, content, status, chapter_id, outline_node_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (work_id, title.strip(), content.strip(), status, chapter_id, outline_node_id),
    )
    db.commit()
    inserted_id = cur.lastrowid
    row = db.execute("SELECT * FROM foreshadows WHERE id = ?", (inserted_id,)).fetchone()
    return dict(row)


def batch_sync_triad_assets(
    db,
    work_id: int,
    timeline_events: list[dict],
    foreshadows: list[dict],
    outline_nodes: list[dict],
    default_outline_node_id: Optional[int] = None,
    default_chapter_id: Optional[int] = None,
) -> dict[str, int]:
    """批量原子化同步来自工作流推演或编辑的三位一体资产。"""
    stats = {
        "timeline_events_added": 0,
        "foreshadows_added": 0,
        "outline_nodes_added": 0,
    }

    # 1. 大纲节点挂载
    current_parent_id = default_outline_node_id
    for n in outline_nodes:
        title = (n.get("title") or "").strip()
        synopsis = (n.get("synopsis") or "").strip()
        parent_id = n.get("parent_id") or current_parent_id
        if not title:
            continue
        dup = db.execute(
            "SELECT id FROM outline_nodes WHERE work_id = ? AND title = ? AND (parent_id IS ? OR parent_id = ?)",
            (work_id, title, parent_id, parent_id),
        ).fetchone()
        if not dup:
            sort_order = db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM outline_nodes WHERE work_id = ? AND parent_id IS ?",
                (work_id, parent_id),
            ).fetchone()[0]
            cur = db.execute(
                """INSERT INTO outline_nodes (work_id, parent_id, title, synopsis, status, sort_order)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (work_id, parent_id, title, synopsis, sort_order),
            )
            stats["outline_nodes_added"] += 1
            if n.get("is_volume"):
                current_parent_id = cur.lastrowid

    # 2. 时间线事件入库
    for ev in timeline_events:
        event_text = (ev.get("event") or "").strip()
        if not event_text:
            continue
        time_label = (ev.get("time_label") or "未定时间").strip()
        chars = (ev.get("characters") or "").strip()
        node_id = ev.get("outline_node_id") or default_outline_node_id
        chap_id = ev.get("chapter_id") or default_chapter_id
        dup = db.execute(
            "SELECT id FROM timeline_events WHERE work_id = ? AND event = ? AND (chapter_id IS ? OR chapter_id = ?) AND (outline_node_id IS ? OR outline_node_id = ?)",
            (work_id, event_text, chap_id, chap_id, node_id, node_id),
        ).fetchone()
        if not dup:
            add_timeline_event(
                db,
                work_id=work_id,
                time_label=time_label,
                event=event_text,
                characters=chars,
                chapter_id=chap_id,
                outline_node_id=node_id,
            )
            stats["timeline_events_added"] += 1

    # 3. 伏笔记录入库
    for fs in foreshadows:
        title = (fs.get("title") or "").strip()
        if not title:
            continue
        content = (fs.get("content") or "").strip()
        status = fs.get("status") or "planted"
        node_id = fs.get("outline_node_id") or default_outline_node_id
        chap_id = fs.get("chapter_id") or default_chapter_id
        dup = db.execute(
            "SELECT id FROM foreshadows WHERE work_id = ? AND title = ? AND (chapter_id IS ? OR chapter_id = ?) AND (outline_node_id IS ? OR outline_node_id = ?)",
            (work_id, title, chap_id, chap_id, node_id, node_id),
        ).fetchone()
        if not dup:
            add_foreshadow(
                db,
                work_id=work_id,
                title=title,
                content=content,
                status=status,
                chapter_id=chap_id,
                outline_node_id=node_id,
            )
            stats["foreshadows_added"] += 1

    return stats
