# -*- coding: utf-8 -*-
"""统一上下文装配服务"""
from typing import Optional
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
            st = "已回收" if fs.get("status") == "resolved" else "埋设中"
            c_str = f"：{fs['content']}" if fs.get("content") else ""
            out_lines.append(f"- 《{fs['title']}》（{st}）{c_str}")

    return "\n".join(out_lines)


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
