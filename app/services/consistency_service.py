# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队 · MIT
# Licensed under the MIT License. See LICENSE.
"""剧情一致性巡检引擎 (Consistency Inspector Service)。

基于万相谱实体档案、时间线事件、伏笔回收状态与大纲设定，
对章节正文进行深度审校，发掘潜在的设定冲突、状态不一致与"吃书"漏洞。
"""
from typing import Optional, List, Dict, Any
import json
import re
from app.ai_client import chat, get_ai_config
from app.services.context_service import assemble_plot_triad_block


CONSISTENCY_SYSTEM_PROMPT = """你是一位极其严苛的网文总编辑与世界观设定质检专家。
你的任务是审查小说章节正文，比对已有的【万相谱设定档案】、【时间线事件】与【伏笔状态】，揪出潜在的“吃书”漏洞与剧情逻辑冲突。

【审查重点】：
1. 人物状态冲突 (character_status)：如肢体残疾/伤势突然痊愈、死亡角色复活、性格/修为境界与档案不符、称呼或身份倒错等。
2. 道具/法则冲突 (item_status)：如已损毁/遗失的法宝神兵突然完整出现、法则/代价被无视等。
3. 时间线与地理冲突 (timeline_error)：事件先后顺序倒错、角色出现在不可能到达的地点。
4. 伏笔断裂 (foreshadow_break)：已设定的关键伏笔或约束条件被正文无视或产生不可调和的矛盾。

【输出规范】：
请仅以标准 JSON 数组返回检测到的冲突列表。若无任何冲突，返回空数组 []。
严禁输出任何多余的开场白、Markdown 标记或总结文字。
每个冲突对象必须包含以下字段：
[
  {
    "type": "character_status" | "item_status" | "timeline_error" | "foreshadow_break",
    "entity_name": "涉及的主要实体或角色名",
    "severity": "warn" | "error" | "info",
    "description": "清晰简短地指出前后冲突之处（如：第3章中设定林渊左臂已断，此处描述'双手结印'产生矛盾）",
    "quote": "章节正文中的直接冲突原句（5~30字）",
    "suggestion": "具体的修文分析与修改建议说明",
    "replacement": "精准用于直接替换 quote 原句的修订文案（例如 quote 是'双手结印'，此处填'单手掐诀'；需保持主谓宾与语境流畅，若不适合单句替换可留空字符串）"
  }
]
"""


def build_consistency_context(db, work_id: int, chapter_id: int) -> dict[str, Any]:
    """抽取本章登场/相关的万相谱实体、时间线事件、伏笔状态与大纲梗概。"""
    # 1. 查找本章关联的实体
    linked_ent_rows = db.execute(
        """SELECT e.id, e.category, e.name, e.fields_json, e.content, e.tags
           FROM chapter_entities ce
           JOIN entities e ON ce.entity_id = e.id
           WHERE ce.chapter_id = ? AND e.work_id = ?""",
        (chapter_id, work_id)
    ).fetchall()

    # 若本章尚未手动绑定实体，默认召回作品内标记为主角或核心角色的实体（最多8个）
    if not linked_ent_rows:
        linked_ent_rows = db.execute(
            """SELECT id, category, name, fields_json, content, tags
               FROM entities
               WHERE work_id = ? AND (category IN ('character', 'item') OR tags LIKE '%主角%')
               ORDER BY id ASC LIMIT 8""",
            (work_id,)
        ).fetchall()

    entities_data = []
    for r in linked_ent_rows:
        f_json = {}
        try:
            f_json = json.loads(r["fields_json"] or "{}")
        except Exception:
            pass
        entities_data.append({
            "name": r["name"],
            "category": r["category"],
            "tags": r["tags"],
            "fields": f_json,
            "summary": r["content"] or "",
        })

    # 2. 查找已发生的时间线事件
    timeline_rows = db.execute(
        """SELECT time_label, event, characters FROM timeline_events
           WHERE work_id = ? ORDER BY sort_order ASC, id ASC LIMIT 15""",
        (work_id,)
    ).fetchall()
    timeline_data = [
        {"time": r["time_label"] or "", "event": r["event"], "characters": r["characters"] or ""}
        for r in timeline_rows
    ]

    # 3. 查找伏笔表
    foreshadow_rows = db.execute(
        """SELECT title, content, status FROM foreshadows
           WHERE work_id = ? ORDER BY id ASC LIMIT 10""",
        (work_id,)
    ).fetchall()
    foreshadows_data = [
        {"title": r["title"], "content": r["content"] or "", "status": r["status"]}
        for r in foreshadow_rows
    ]

    # 4. 当前章大纲梗概
    outline_row = db.execute(
        "SELECT title, synopsis FROM outline_nodes WHERE chapter_id = ? AND work_id = ? LIMIT 1",
        (chapter_id, work_id)
    ).fetchone()
    outline_data = {
        "title": outline_row["title"] if outline_row else "",
        "synopsis": outline_row["synopsis"] if outline_row else "",
    }

    return {
        "entities": entities_data,
        "timeline": timeline_data,
        "foreshadows": foreshadows_data,
        "outline": outline_data,
    }


def format_consistency_dossier(context_bundle: dict[str, Any]) -> str:
    """将结构化档案格式化为 AI 审校输入文本。"""
    lines = []

    # 实体档案
    if context_bundle.get("entities"):
        lines.append("【已知万相谱实体档案】")
        for e in context_bundle["entities"]:
            fields_desc = []
            f = e.get("fields") or {}
            for k in ["identity", "personality", "cultivation_level", "cheat_name", "background", "goal"]:
                if f.get(k):
                    fields_desc.append(f"{k}: {f[k]}")
            field_str = (" (" + "；".join(fields_desc) + ")") if fields_desc else ""
            lines.append(f"- [{e['category']}] {e['name']}{field_str}：{e['summary']}")
        lines.append("")

    # 时间线
    if context_bundle.get("timeline"):
        lines.append("【已知时间线关键事件】")
        for t in context_bundle["timeline"]:
            chars_str = f" (涉及: {t['characters']})" if t['characters'] else ""
            lines.append(f"- [{t['time'] or '前序'}] {t['event']}{chars_str}")
        lines.append("")

    # 伏笔
    if context_bundle.get("foreshadows"):
        lines.append("【关键伏笔与预设】")
        for fs in context_bundle["foreshadows"]:
            lines.append(f"- [{fs['status']}] {fs['title']}：{fs['content']}")
        lines.append("")

    # 本章大纲
    if context_bundle.get("outline") and context_bundle["outline"].get("synopsis"):
        lines.append(f"【本章大纲梗概】: {context_bundle['outline']['title']} - {context_bundle['outline']['synopsis']}")
        lines.append("")

    return "\n".join(lines)


async def inspect_chapter_consistency(
    db,
    work_id: int,
    chapter_id: int,
    content: Optional[str] = None,
    cfg: Optional[dict] = None
) -> list[dict[str, Any]]:
    """核心巡检入口：装配背景并调用模型分析潜在冲突。"""
    chap = db.execute("SELECT title, content FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    if not chap:
        raise ValueError(f"章节 id={chapter_id} 不存在")

    target_content = (content if content is not None else (chap["content"] or "")).strip()
    if not target_content:
        return []

    context_bundle = build_consistency_context(db, work_id, chapter_id)
    dossier_text = format_consistency_dossier(context_bundle)

    if not cfg:
        cfg = get_ai_config()
    if not cfg or not cfg.get("ai_api_key") or not cfg.get("ai_model"):
        # 未配置 AI 时返回空列表（优雅兜底）
        return []

    content_snippet = target_content[:4000]
    chap_title = chap["title"] or "未命名章节"
    user_prompt = f"{dossier_text}\n\n【待审查章节正文（{chap_title}）】：\n{content_snippet}\n\n请严格对照上方档案审校正文，找出所有前后不一致、“吃书”或逻辑冲突的地方，输出标准 JSON 数组："

    messages = [
        {"role": "system", "content": CONSISTENCY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        reply_text, _ = await chat(messages, cfg)
        # 提取并解析 JSON 数组
        match = re.search(r"\[[\s\S]*\]", reply_text.strip())
        if match:
            raw_json = match.group(0)
            conflicts = json.loads(raw_json)
            if isinstance(conflicts, list):
                # 校验字段结构合法性
                sanitized = []
                for item in conflicts:
                    if isinstance(item, dict) and item.get("description"):
                        sanitized.append({
                            "type": item.get("type", "character_status"),
                            "entity_name": item.get("entity_name", ""),
                            "severity": item.get("severity", "warn"),
                            "description": item.get("description", ""),
                            "quote": item.get("quote", ""),
                            "suggestion": item.get("suggestion", ""),
                            "replacement": item.get("replacement", ""),
                        })
                return sanitized
    except Exception as e:
        # 模型输出解析失败或网络异常时不阻塞主链路
        return []

    return []
