# -*- coding: utf-8 -*-
"""统一上下文装配服务

负责将大纲节点、三位一体剧情卡片、正文、前情摘要、万相谱实体、文风档案
统一装配为标准领域知识上下文，消除前后端双链路组装差异。
"""
from typing import Any, Optional
import json
from app.services.asset_hub import aggregate_for_node


def assemble_plot_triad_block(db, work_id: int, outline_node_id: Optional[int]) -> str:
    """提取并格式化目标大纲节点的剧情脉络三位一体卡片。"""
    if not outline_node_id:
        return ""
    triad = aggregate_for_node(db, work_id, outline_node_id)
    if not triad or not triad.get("node"):
        return ""

    node = triad["node"]
    out_lines = ["【目标大纲节点】\n标题：" + node["title"]]
    if node.get("synopsis"):
        out_lines.append("剧情梗概：" + node["synopsis"])

    events = triad.get("timeline_events", [])
    if events:
        out_lines.append("\n【已绑定时间线事件】")
        for ev in events:
            c_str = f"（涉及人物：{ev['characters']}）" if ev.get("characters") else ""
            t_label = ev.get("time_label") or "未定"
            out_lines.append(f"- [{t_label}] {ev['event']} {c_str}")

    foreshadows = triad.get("foreshadows", [])
    if foreshadows:
        out_lines.append("\n【已布局相关伏笔】")
        for fs in foreshadows:
            st = "已回收" if fs.get("status") == "resolved" else "草蛇灰线"
            out_lines.append(f"- [{st}] {fs['title']}: {fs.get('description', '')}")

    return "\n".join(out_lines)


def format_entity_block(entity: dict[str, Any]) -> str:
    """将万相谱实体字典格式化为紧凑的设定卡片文本块。"""
    name = entity.get("name") or "未命名"
    cat = entity.get("category") or "未分类"
    lines = [f"【设定·{cat}】{name}"]

    fields_json = entity.get("fields_json")
    fields = {}
    if fields_json:
        if isinstance(fields_json, str):
            try:
                fields = json.loads(fields_json)
            except Exception:
                fields = {}
        elif isinstance(fields_json, dict):
            fields = fields_json

    if fields:
        field_strs = [f"{k}: {v}" for k, v in fields.items() if v]
        if field_strs:
            lines.append("属性: " + "; ".join(field_strs))

    content = entity.get("content") or ""
    if content.strip():
        lines.append(content.strip())

    tags = entity.get("tags") or ""
    if tags.strip():
        lines.append("标签: " + tags.strip())

    return "\n".join(lines)


def assemble_writing_context(
    db,
    work_id: int,
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
    outline_node_ids: Optional[list[int]] = None,
    entity_ids: Optional[list[int]] = None,
    include_current_chapter: bool = True,
    include_prev_chapter: bool = True,
    include_outline: bool = True,
    include_style: bool = True,
    current_chapter_limit: int = 3000,
    prev_chapter_limit: int = 500,
) -> str:
    """统一为写作/对话装配领域上下文（正文 + 前情 + 三位一体大纲 + 万相谱实体 + 文风档案）。"""
    parts = []

    # 1. 当前章节正文（前 3000 字）
    if include_current_chapter and chapter_id:
        c_row = db.execute("SELECT content FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if c_row and c_row[0]:
            content = c_row[0].strip()
            if content:
                snippet = content[:current_chapter_limit]
                parts.append("【当前章节（前 3000 字）】\n" + snippet)

    # 2. 前情摘要（上一章末 500 字）
    if include_prev_chapter and chapter_id:
        prev_row = db.execute(
            """SELECT c.content FROM chapters c
               JOIN chapters curr ON curr.id = ?
               JOIN volumes v_curr ON curr.volume_id = v_curr.id
               JOIN volumes v ON c.volume_id = v.id
               WHERE v.work_id = ?
                 AND ((v.sort_order = v_curr.sort_order AND c.sort_order < curr.sort_order)
                      OR (v.sort_order < v_curr.sort_order))
               ORDER BY v.sort_order DESC, c.sort_order DESC LIMIT 1""",
            (chapter_id, work_id),
        ).fetchone()
        if prev_row and prev_row[0]:
            prev_content = prev_row[0].strip()
            if prev_content:
                snippet = prev_content[-prev_chapter_limit:]
                parts.append("【前情摘要（上一章末 500 字）】\n" + snippet)

    # 3. 关联大纲节点与剧情脉络（三位一体卡片）
    if include_outline:
        target_node_ids = []
        if outline_node_ids:
            target_node_ids.extend(outline_node_ids)
        elif outline_node_id:
            target_node_ids.append(outline_node_id)
        elif chapter_id:
            node_rows = db.execute(
                "SELECT id FROM outline_nodes WHERE chapter_id = ? AND work_id = ? ORDER BY id ASC",
                (chapter_id, work_id),
            ).fetchall()
            target_node_ids.extend(r[0] for r in node_rows)

        seen_nodes = set()
        for nid in target_node_ids:
            if nid in seen_nodes:
                continue
            seen_nodes.add(nid)
            triad_block = assemble_plot_triad_block(db, work_id, nid)
            if triad_block:
                parts.append(triad_block)

    # 4. 万相谱实体档案
    if entity_ids:
        seen_entities = set()
        for eid in entity_ids:
            if eid in seen_entities:
                continue
            seen_entities.add(eid)
            e_row = db.execute(
                "SELECT id, category, name, fields_json, content, tags FROM entities WHERE id = ? AND work_id = ?",
                (eid, work_id),
            ).fetchone()
            if e_row:
                parts.append(format_entity_block(dict(e_row)))

    # 5. 文风档案
    if include_style:
        w_row = db.execute("SELECT style_profile FROM works WHERE id = ?", (work_id,)).fetchone()
        if w_row and w_row[0] and w_row[0].strip():
            parts.append("【文风档案】\n" + w_row[0].strip())

    return "\n\n----\n\n".join(parts)


def assemble_workflow_context(
    db,
    work_id: int,
    chapter_id: Optional[int] = None,
    outline_node_id: Optional[int] = None,
    chapter_text: str = "",
    prev_step_text: str = "",
    input_mode: str = "chapter",
    context_sources: Optional[list[str]] = None,
) -> str:
    """为工作流步骤装配完整、紧凑的领域上下文（三位一体大纲卡 + 章节正文 + 前序输出）。"""
    parts = []

    if context_sources is not None:
        include_triad = "triad" in context_sources
        include_chapter = "chapter" in context_sources
    else:
        # 向后兼容旧 input_mode
        include_triad = input_mode != "none"
        include_chapter = input_mode in ("chapter", "merge")

    if include_triad:
        triad_block = assemble_plot_triad_block(db, work_id, outline_node_id)
        if triad_block:
            parts.append(triad_block)

    if include_chapter and chapter_text:
        parts.append("【本章正文】\n" + chapter_text)

    if prev_step_text:
        if prev_step_text.startswith("【前序"):
            parts.append(prev_step_text)
        else:
            parts.append("【前序步骤输出】\n" + prev_step_text)

    return "\n\n".join(parts)
