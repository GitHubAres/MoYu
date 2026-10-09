# -*- coding: utf-8 -*-
"""三位一体剧情脉络领域服务 (Plot Triad Service: 大纲 ↔ 时间线 ↔ 伏笔)"""
from typing import Optional, Any
from app.services.asset_hub import upsert_timeline_event, upsert_foreshadow


def add_timeline_event(
    db,
    work_id: int,
    time_label: str,
    event: str,
    characters: str = "",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> dict:
    """向时间线添加一条剧情事件（统一委托 asset_hub）。"""
    return upsert_timeline_event(
        db,
        work_id=work_id,
        event=event,
        time_label=time_label,
        characters=characters,
        chapter_id=chapter_id,
        outline_node_id=outline_node_id,
    )


def add_foreshadow(
    db,
    work_id: int,
    title: str,
    content: str = "",
    status: str = "planted",
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
) -> dict:
    """向伏笔看板埋下一条伏笔（统一委托 asset_hub）。"""
    return upsert_foreshadow(
        db,
        work_id=work_id,
        title=title,
        content=content,
        status=status,
        chapter_id=chapter_id,
        outline_node_id=outline_node_id,
    )


def batch_sync_triad_assets(
    db,
    work_id: int,
    timeline_events: list[dict],
    foreshadows: list[dict],
    outline_nodes: list[dict],
    default_outline_node_id: Optional[int] = None,
    default_chapter_id: Optional[int] = None,
) -> dict[str, Any]:
    """批量原子化同步来自工作流推演或编辑的三位一体资产。"""
    stats = {
        "timeline_events_added": 0,
        "foreshadows_added": 0,
        "outline_nodes_added": 0,
        "outline_synopsis_updated": 0,
        "rejected_count": 0,
        "rejected_items": [],
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
            "SELECT id, synopsis FROM outline_nodes WHERE work_id = ? AND title = ? AND (parent_id IS ? OR parent_id = ?)",
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
        else:
            dup_id, dup_synopsis = dup[0], dup[1]
            old_synopsis = (dup_synopsis or "").strip()
            if synopsis and synopsis != old_synopsis:
                db.execute(
                    "UPDATE outline_nodes SET synopsis = ? WHERE id = ?",
                    (synopsis, dup_id),
                )
                stats["outline_synopsis_updated"] += 1

    # 2. 时间线事件入库（委托 asset_hub）
    for ev in timeline_events:
        event_text = (ev.get("event") or "").strip()
        if not event_text:
            continue
        time_label = (ev.get("time_label") or "未定时间").strip()
        chars = (ev.get("characters") or "").strip()
        node_id = ev.get("outline_node_id") or default_outline_node_id
        chap_id = ev.get("chapter_id") or default_chapter_id
        res = upsert_timeline_event(
            db,
            work_id=work_id,
            time_label=time_label,
            event=event_text,
            characters=chars,
            chapter_id=chap_id,
            outline_node_id=node_id,
        )
        if res.get("_rejected"):
            stats["rejected_count"] += 1
            if len(stats["rejected_items"]) < 20:
                stats["rejected_items"].append({
                    "kind": "timeline_event",
                    "title": event_text,
                    "reason": res.get("_reason", "校验未通过"),
                })
        elif res.get("_is_new"):
            stats["timeline_events_added"] += 1

    # 3. 伏笔记录入库（委托 asset_hub）
    for fs in foreshadows:
        title = (fs.get("title") or "").strip()
        if not title:
            continue
        content = (fs.get("content") or "").strip()
        status = fs.get("status") or "planted"
        node_id = fs.get("outline_node_id") or default_outline_node_id
        chap_id = fs.get("chapter_id") or default_chapter_id
        res = upsert_foreshadow(
            db,
            work_id=work_id,
            title=title,
            content=content,
            status=status,
            chapter_id=chap_id,
            outline_node_id=node_id,
        )
        if res.get("_rejected"):
            stats["rejected_count"] += 1
            if len(stats["rejected_items"]) < 20:
                stats["rejected_items"].append({
                    "kind": "foreshadow",
                    "title": title,
                    "reason": res.get("_reason", "校验未通过"),
                })
        elif res.get("_is_new"):
            stats["foreshadows_added"] += 1

    return stats
