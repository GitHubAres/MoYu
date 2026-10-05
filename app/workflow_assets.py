# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队 · MIT
# Licensed under the MIT License. See LICENSE.
"""工作流步骤创作资产提取与各业务系统规范同步服务"""
import json
import re
from typing import Optional
from pydantic import BaseModel


class AssetEntityIn(BaseModel):
    category: str = "character"
    name: str
    content: str = ""
    tags: str = ""


class AssetRelationIn(BaseModel):
    from_name: str
    to_name: str
    label: str = "关联"


class AssetOutlineIn(BaseModel):
    title: str
    synopsis: str = ""
    is_volume: bool = False


class AssetNoteIn(BaseModel):
    title: str = "世界观设定"
    content: str = ""
    tags: str = "世界观"


class SyncAssetsIn(BaseModel):
    entities: list[AssetEntityIn] = []
    relations: list[AssetRelationIn] = []
    outline_nodes: list[AssetOutlineIn] = []
    notes: list[AssetNoteIn] = []
    apply_to_chapter: bool = False
    chapter_content: Optional[str] = None


def extract_structured_assets_from_text(text: str) -> dict:
    assets = {
        "entities": [],
        "relations": [],
        "outline_nodes": [],
        "notes": [],
    }
    if not text or not text.strip():
        return assets

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    category_map = {
        "character": ["人物", "角色", "主角", "配角", "反派", "导师", "化身", "修士", "姓名"],
        "item": ["道具", "物品", "法宝", "武器", "功法", "秘籍", "灵药", "丹药", "神物", "金手指", "词条"],
        "location": ["地点", "场景", "世界", "宗门驻地", "秘境", "遗迹", "城池", "界域", "凡域", "深渊"],
        "faction": ["势力", "宗门", "家族", "帮派", "组织", "巨企", "门派", "圣地", "皇朝"],
    }
    cat_lookup = {}
    for cat, kws in category_map.items():
        for kw in kws:
            cat_lookup[kw] = cat

    ent_pattern_a = re.compile(
        r'^[#*>\-\s]*[【\[](人物|角色|主角|配角|反派|道具|法宝|功法|武器|物品|地点|场景|势力|宗门|家族|门派)[】\]]\s*[:：]?\s*([^\s:：(（—–\-]+)(?:[（(]([^）)]+)[）)])?\s*[:：—–\-]?\s*(.*)$'
    )
    ent_pattern_b = re.compile(
        r'^[#*>\-\s]*\*\*(人物|角色|主角|配角|反派|道具|法宝|功法|武器|物品|地点|场景|势力|宗门|家族|门派)\*\*\s*[:：]\s*([^\s:：(（—–\-]+)(?:[（(]([^）)]+)[）)])?\s*[:：—–\-]?\s*(.*)$'
    )
    ent_pattern_c = re.compile(r'^[#*>\-\s]*(?:方向|方案|选项)\s*\d+[:：\s]+[【\[]([^】\]]+)[】\]]\s*([^\s(（:：—–\-]+)')

    seen_entities = set()
    for line in lines:
        m = ent_pattern_a.match(line) or ent_pattern_b.match(line)
        if m:
            raw_cat, name, tag_info, desc = m.groups()
            name = name.strip("*# ")
            if len(name) >= 2 and len(name) <= 25 and name not in seen_entities:
                seen_entities.add(name)
                cat = cat_lookup.get(raw_cat, "character")
                tags = [raw_cat]
                if tag_info:
                    tags.extend([t.strip() for t in re.split(r'[,，/、\s]+', tag_info) if t.strip()])
                assets["entities"].append({
                    "category": cat,
                    "name": name,
                    "content": desc.strip() if desc else (tag_info or ""),
                    "tags": ",".join(tags),
                })
        else:
            mc = ent_pattern_c.match(line)
            if mc:
                tag_label, ent_name = mc.groups()
                ent_name = ent_name.strip("*# ")
                if len(ent_name) >= 2 and len(ent_name) <= 20 and ent_name not in seen_entities:
                    seen_entities.add(ent_name)
                    assets["entities"].append({
                        "category": "character",
                        "name": ent_name,
                        "content": line,
                        "tags": f"立项候选,{tag_label}",
                    })

    rel_pattern = re.compile(
        r'^[#*>\-\s]*(?:【([^】]+)】|([^\s\-–—>]+))\s*(?:[-–—]>|->|—>|到|与|和|对)\s*(?:【([^】]+)】|([^\s(（:：]+))\s*(?:[（(]([^）)]+)[）)]|[-—–]\[([^\]]+)\][-—–]>|[:：]\s*([^\n]+))'
    )
    seen_relations = set()
    for line in lines:
        m = rel_pattern.match(line)
        if m:
            g = m.groups()
            src = (g[0] or g[1] or "").strip("* ")
            dst = (g[2] or g[3] or "").strip("* ")
            rel_label = (g[4] or g[5] or g[6] or "关联").strip()
            if src and dst and src != dst and len(src) <= 20 and len(dst) <= 20 and len(rel_label) <= 30:
                rel_key = f"{src}->{dst}:{rel_label}"
                if rel_key not in seen_relations:
                    seen_relations.add(rel_key)
                    assets["relations"].append({
                        "from_name": src,
                        "to_name": dst,
                        "label": rel_label,
                    })

    outline_pattern = re.compile(
        r'^[#*>\-\s]*(第[0-9一二三四五六七八九十百]+[卷章幕集场]|卷[0-9一二三四五六七八九十]+|Chapter\s*\d+|第[0-9一二三四五六七八九十]+节)[：:\s]+([^\n—–\-]+)(?:[—–\-:：]\s*(.*))?$'
    )
    for line in lines:
        m = outline_pattern.match(line)
        if m:
            prefix, title, synopsis = m.groups()
            full_title = f"{prefix} {title.strip()}".strip()
            assets["outline_nodes"].append({
                "title": full_title,
                "synopsis": synopsis.strip() if synopsis else "",
                "is_volume": "卷" in prefix or "幕" in prefix,
            })

    note_header_pattern = re.compile(
        r'^[#*>\-\s]*(?:【(世界观|力量体系|法则|设定|背景|升级机制|境界划分)】|(?:\*{2}|#{2,4})\s*(世界观|力量体系|法则|设定|背景|升级机制|境界划分|规则[一二三四五六七八九十0-9]+)[：:\s]*(.*))'
    )
    for i, line in enumerate(lines):
        m = note_header_pattern.match(line)
        if m:
            tag = (m.group(1) or m.group(2) or "设定").strip()
            sub = (m.group(3) or "").strip()
            title = f"{tag}{(' · ' + sub) if sub else ''}"
            content_lines = []
            for next_line in lines[i + 1:i + 12]:
                if next_line.startswith(('#', '【', '---')):
                    break
                content_lines.append(next_line)
            assets["notes"].append({
                "title": title,
                "content": "\n".join(content_lines).strip() or line,
                "tags": f"世界观,{tag}",
            })

    return assets


def sync_assets_to_database(db, work_id: int, body: SyncAssetsIn, run_id: int = 0, seq: int = 0) -> dict:
    summary = {
        "entities_added": 0,
        "relations_added": 0,
        "outlines_added": 0,
        "notes_added": 0,
        "chapter_synced": False,
    }

    # 1. 万相谱实体同步
    name_to_id = {}
    existing_entities = db.execute("SELECT id, name FROM entities WHERE work_id=?", (work_id,)).fetchall()
    for r in existing_entities:
        name_to_id[r["name"]] = r["id"]

    for ent in body.entities:
        name = ent.name.strip()
        if not name:
            continue
        if name in name_to_id:
            eid = name_to_id[name]
            if ent.content:
                db.execute(
                    "UPDATE entities SET content = content || '\n' || ?, updated_at=datetime('now','localtime') WHERE id=?",
                    (ent.content, eid),
                )
        else:
            cur = db.execute(
                "INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (work_id, ent.category or "character", name, ent.content, json.dumps({}, ensure_ascii=False), ent.tags),
            )
            name_to_id[name] = cur.lastrowid
            summary["entities_added"] += 1

    # 2. 万相图谱关系同步
    for rel in body.relations:
        from_name = rel.from_name.strip()
        to_name = rel.to_name.strip()
        label = rel.label.strip() or "关联"
        if not from_name or not to_name or from_name == to_name:
            continue
        from_id = name_to_id.get(from_name)
        to_id = name_to_id.get(to_name)
        if from_id and to_id:
            dup = db.execute(
                "SELECT id FROM entity_relations WHERE work_id=? AND from_id=? AND to_id=? AND label=?",
                (work_id, from_id, to_id, label),
            ).fetchone()
            if not dup:
                db.execute(
                    "INSERT INTO entity_relations (work_id, from_id, to_id, label) VALUES (?, ?, ?, ?)",
                    (work_id, from_id, to_id, label),
                )
                summary["relations_added"] += 1

    # 3. 故事大纲同步
    current_vol_id = None
    for node in body.outline_nodes:
        title = node.title.strip()
        synopsis = node.synopsis.strip()
        if not title:
            continue
        dup = db.execute("SELECT id FROM outline_nodes WHERE work_id=? AND title=?", (work_id, title)).fetchone()
        if dup:
            if node.is_volume:
                current_vol_id = dup["id"]
            continue
        parent_id = None if node.is_volume else current_vol_id
        sort_order = db.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM outline_nodes WHERE work_id=? AND parent_id IS ?",
            (work_id, parent_id),
        ).fetchone()[0]
        cur = db.execute(
            "INSERT INTO outline_nodes (work_id, parent_id, title, synopsis, status, sort_order) VALUES (?, ?, ?, ?, 'pending', ?)",
            (work_id, parent_id, title, synopsis, sort_order),
        )
        if node.is_volume:
            current_vol_id = cur.lastrowid
        summary["outlines_added"] += 1

    # 4. 世界观资料便签同步
    for note in body.notes:
        title = note.title.strip() or "世界观设定"
        content = note.content.strip()
        tags = note.tags.strip() or "世界观"
        if not content:
            continue
        full_text = f"【{title}】\n{content}"
        dup = db.execute("SELECT id FROM notes WHERE work_id=? AND content LIKE ?", (work_id, f"%{title}%")).fetchone()
        if not dup:
            db.execute("INSERT INTO notes (work_id, content, tags) VALUES (?, ?, ?)", (work_id, full_text, tags))
            summary["notes_added"] += 1

    # 5. 文章正文与版本沉淀同步
    run = db.execute("SELECT chapter_id FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    chapter_id = run["chapter_id"] if run else None
    if body.apply_to_chapter and chapter_id and body.chapter_content:
        from app.db import word_count
        chap = db.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if chap:
            wc = word_count(body.chapter_content)
            db.execute(
                """INSERT INTO chapter_versions (chapter_id, content, word_count, source, label)
                   VALUES (?, ?, ?, 'workflow', ?)""",
                (chapter_id, body.chapter_content, wc, f"工作流 #{run_id} 步骤 {seq + 1} 采纳"),
            )
            db.execute(
                "UPDATE chapters SET content=?, word_count=?, updated_at=datetime('now','localtime') WHERE id=?",
                (body.chapter_content, wc, chapter_id),
            )
            summary["chapter_synced"] = True

    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return summary