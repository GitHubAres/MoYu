# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队 · MIT
# Licensed under the MIT License. See LICENSE.
"""工作流步骤创作资产提取与各业务系统规范同步服务"""
import json
import re
from typing import Optional
from pydantic import BaseModel
from app.services.output_normalizer import (
    extract_assets_block,
    sanitize_asset_item,
    strip_ai_chatter,
    strip_assets_blocks,
    strip_heading_only_lines,
)


class AssetWorkInfoIn(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    intro: Optional[str] = None


class AssetTimelineEventIn(BaseModel):
    time_label: str = ""
    event: str
    characters: str = ""
    outline_node_id: Optional[int] = None


class AssetForeshadowIn(BaseModel):
    title: str
    content: str = ""
    status: str = "planted"
    outline_node_id: Optional[int] = None


class AssetEntityIn(BaseModel):
    category: str = "character"
    name: str
    content: str = ""
    tags: str = ""
    fields_json: Optional[dict | str] = {}


class AssetRelationIn(BaseModel):
    from_name: str
    to_name: str
    label: str = "关联"


class AssetOutlineIn(BaseModel):
    title: str
    synopsis: str = ""
    is_volume: bool = False
    parent_id: Optional[int] = None


class AssetNoteIn(BaseModel):
    title: str = "世界观设定"
    content: str = ""
    tags: str = "世界观"


class SyncAssetsIn(BaseModel):
    work_info: Optional[AssetWorkInfoIn] = None
    entities: list[AssetEntityIn] = []
    relations: list[AssetRelationIn] = []
    outline_nodes: list[AssetOutlineIn] = []
    foreshadows: list[AssetForeshadowIn] = []
    timeline_events: list[AssetTimelineEventIn] = []
    notes: list[AssetNoteIn] = []
    chapter_id: Optional[int] = None
    apply_to_chapter: bool = False
    chapter_content: Optional[str] = None


def clean_str(s: str) -> str:
    return re.sub(r'[*#_`]', '', s).strip()


def _heuristic_extract_assets(text: str) -> tuple[dict, list[dict]]:
    assets = {
        "work_info": {
            "title": "",
            "genre": "",
            "intro": "",
        },
        "entities": [],
        "relations": [],
        "outline_nodes": [],
        "foreshadows": [],
        "timeline_events": [],
        "notes": [],
    }
    rejected = []
    if not text or not text.strip():
        return assets, rejected
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    category_map = {
        "character": ["人物", "角色", "主角", "配角", "反派", "导师", "化身", "修士", "姓名", "对手", "宿敌", "弃子", "审查员", "NPC", "主要角色"],
        "item": ["道具", "物品", "法宝", "武器", "功法", "秘籍", "灵药", "丹药", "神物", "金手指", "词条", "芯片", "概念", "毒药", "密钥", "神兵", "至宝", "装备"],
        "location": ["地点", "场景", "世界", "宗门驻地", "秘境", "遗迹", "城池", "界域", "凡域", "深渊", "酒店", "机房", "候场室", "宴会厅", "书库", "洞府", "战场", "禁地", "福地"],
        "faction": ["势力", "宗门", "家族", "帮派", "组织", "巨企", "门派", "圣地", "皇朝", "集团", "矩阵", "引擎", "世家", "教派", "商会", "联盟"],
        "lore": ["法则", "规则", "体系", "力量体系", "设定", "境界", "概念", "世界观", "序列", "天道", "神通"],
    }
    cat_lookup = {}
    for cat, kws in category_map.items():
        for kw in kws:
            cat_lookup[kw] = cat

    seen_entities = set()
    seen_relations = set()

    # 0. 故事立项识别 (书名 / 题材 / 简介 / 核心看点)
    for line in lines:
        if not assets["work_info"]["title"]:
            m_book = re.search(r'《([^》]{2,30})》', line)
            if m_book and any(k in line for k in ["书名", "作品", "标题", "方向", "方案", "选项", "小说", "项目", "命名"]):
                assets["work_info"]["title"] = clean_str(m_book.group(1))
            else:
                m_t = re.search(r'(?:书\s*名|作品名|小说名|项目名)\s*[:：]\s*(?:《)?([^》\n\r]+)(?:》)?', line)
                if m_t:
                    assets["work_info"]["title"] = clean_str(m_t.group(1))

        if not assets["work_info"]["genre"]:
            m_g = re.search(r'(?:题材|类型|分类|核心题材|题材标签|定位)\s*[:：]\s*([^\n\r]+)', line)
            if m_g:
                assets["work_info"]["genre"] = clean_str(m_g.group(1))
            else:
                m_g2 = re.search(r'【(?:题材|类型|分类|标签)】\s*([^\n\r]+)', line)
                if m_g2:
                    assets["work_info"]["genre"] = clean_str(m_g2.group(1))
                elif any(k in line for k in ["方向", "方案", "选项"]):
                    m_g3 = re.search(r'[【\[]([^】\]]{2,15})[】\]]', line)
                    if m_g3 and not any(bad in m_g3.group(1) for bad in ["方案", "方向", "选项", "路线", "Option"]):
                        assets["work_info"]["genre"] = clean_str(m_g3.group(1))

        if not assets["work_info"]["intro"]:
            m_i = re.search(r'(?:一句话简介|核心看点|核心创意|故事梗概|作品简介|核心脑洞|故事简介|简介|梗概)\s*[:：]\s*([^\n\r]+)', line)
            if m_i:
                assets["work_info"]["intro"] = clean_str(m_i.group(1))

    # 1. 结构化 Markdown 表格提取 (核心人物欲望矩阵表、关系网拓扑表、伏笔表等)
    table_headers = None
    foreshadow_headers = None
    timeline_headers = None
    cat_headers = None
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            cols = [clean_str(c) for c in line.strip("|").split("|")]
            if not cols or cols[0].startswith(":-") or cols[0].startswith("-"):
                continue

            # 检测是否为人物表表头
            if any(k in cols[0] for k in ["角色", "人物", "姓名"]):
                table_headers = cols
                continue

            # 检测是否为关系表表头
            if any(k in cols[0] for k in ["关系对", "人物对", "关系双方"]):
                table_headers = cols
                continue

            # 检测是否为伏笔表表头
            if any(k in cols[0] for k in ["伏笔", "线索", "暗线", "钩子"]):
                foreshadow_headers = cols
                continue

            # 检测是否为时间线表表头
            if any(k in cols[0] for k in ["时间", "时间线", "编年", "时期", "节点"]) or (len(cols) > 1 and any(k in cols[1] for k in ["时间", "事件"])):
                timeline_headers = cols
                continue

            # 检测是否为 势力/地点/道具/法则 表头
            if any(k in cols[0] for k in ["势力", "宗门", "家族", "帮派", "组织", "门派", "世家", "教派", "商会", "联盟", "皇朝", "集团"]):
                cat_headers = (cols, "faction")
                continue
            if any(k in cols[0] for k in ["地点", "空间", "场景", "世界", "秘境", "城池", "界域", "洞府", "战场", "禁地", "遗迹", "福地"]):
                cat_headers = (cols, "location")
                continue
            if any(k in cols[0] for k in ["道具", "法宝", "武器", "物品", "灵药", "丹药", "神物", "功法", "秘籍", "神兵", "至宝", "装备"]):
                cat_headers = (cols, "item")
                continue
            if any(k in cols[0] for k in ["法则", "体系", "设定", "概念", "规则", "境界", "力量体系", "序列", "天道", "神通"]):
                cat_headers = (cols, "lore")
                continue

            # 提取伏笔表格数据
            if foreshadow_headers and any(k in foreshadow_headers[0] for k in ["伏笔", "线索", "暗线", "钩子"]):
                f_title = clean_str(cols[0])
                if f_title and len(f_title) <= 50 and not any(k in f_title for k in ["表头", "---"]):
                    desc_parts = []
                    for idx, col in enumerate(cols[1:], 1):
                        if idx < len(foreshadow_headers) and col:
                            desc_parts.append(f"【{foreshadow_headers[idx]}】{col}")
                    assets["foreshadows"].append({
                        "title": f_title,
                        "content": "\n".join(desc_parts),
                        "status": "planted",
                    })
                continue

            # 提取时间线表格数据
            if timeline_headers and any(k in timeline_headers[0] for k in ["时间", "时间线", "编年", "时期", "节点"]):
                time_val = clean_str(cols[0])
                event_val = clean_str(cols[1]) if len(cols) > 1 else ""
                char_val = clean_str(cols[2]) if len(cols) > 2 else ""
                for idx, h in enumerate(timeline_headers):
                    if idx < len(cols):
                        if any(k in h for k in ["事件", "剧情", "内容"]):
                            event_val = clean_str(cols[idx])
                        elif any(k in h for k in ["人物", "角色"]):
                            char_val = clean_str(cols[idx])
                        elif any(k in h for k in ["时间", "节点", "时期"]):
                            time_val = clean_str(cols[idx])
                if event_val and not any(k in event_val for k in ["表头", "---", "事件"]):
                    assets["timeline_events"].append({
                        "time_label": time_val if time_val not in ["表头", "---", "时间"] else "未定时间",
                        "event": event_val,
                        "characters": char_val,
                    })
                continue

            # 提取多品类实体表格数据
            if cat_headers:
                h_cols, cur_cat = cat_headers
                raw_name = clean_str(cols[0])
                if raw_name and len(raw_name) <= 25 and raw_name not in seen_entities and not any(k in raw_name for k in ["表头", "---"]):
                    seen_entities.add(raw_name)
                    desc_parts = []
                    for idx, col in enumerate(cols[1:], 1):
                        if idx < len(h_cols) and col:
                            desc_parts.append(f"【{h_cols[idx]}】{col}")
                    assets["entities"].append({
                        "category": cur_cat,
                        "name": raw_name,
                        "content": "\n".join(desc_parts),
                        "tags": h_cols[0],
                    })
                continue

            # 提取关系对表格数据: 如 | 宁恪 ↔ 陆玄 | 恶毒少爷 vs 逆袭战神 | 争夺叙事推动权 | ...
            if any(sep in cols[0] for sep in ["↔", "<->", "->", "→", "vs", "VS", "与", "对"]):
                m_rel = re.split(r'[\s]*(?:↔|<->|->|→|vs|VS|与)[\s]*', cols[0])
                if len(m_rel) == 2:
                    src, dst = clean_str(m_rel[0]), clean_str(m_rel[1])
                    surface = cols[1] if len(cols) > 1 else ""
                    conflict = cols[2] if len(cols) > 2 else ""
                    label = surface.split()[0] if surface else (conflict.split()[0] if conflict else "关联")
                    label = re.sub(r'[\s/]+.*$', '', label)[:15] or "关联"
                    # 过滤表头及长句子
                    if src and dst and src != dst and len(src) <= 12 and len(dst) <= 12 and not any(bad in (src+dst) for bad in ["矩阵", "拓扑", "架构", "报告", "闭环", "地基", "规则", "计划", "实处", "耗时"]):
                        rel_key = f"{src}->{dst}:{label}"
                        if rel_key not in seen_relations:
                            seen_relations.add(rel_key)
                            assets["relations"].append({
                                "from_name": src,
                                "to_name": dst,
                                "label": label,
                            })
                continue

            # 提取人物矩阵表格数据
            if table_headers and any(k in table_headers[0] for k in ["角色", "人物"]):
                raw_name = cols[0]
                role = cols[1] if len(cols) > 1 else ""
                desc_parts = []
                for idx, col in enumerate(cols[2:], 2):
                    if idx < len(table_headers) and col:
                        desc_parts.append(f"【{table_headers[idx]}】{col}")
                desc = "\n".join(desc_parts)

                m_alias = re.match(r"^([^\s(（]+)\s*[（(]([^）)]+)[）)]", raw_name)
                name = m_alias.group(1).strip() if m_alias else raw_name
                alias = m_alias.group(2).strip() if m_alias else ""
                name = clean_str(name)

                if name and len(name) <= 20 and name not in seen_entities and not any(k in name for k in ["表头", "属性", "---"]) and not re.match(r'^[0-9一二三四五六七八九十]+[、.\s]*$', name) and not name.endswith(("分区", "接口", "矩阵", "简介", "计划表")):
                    seen_entities.add(name)
                    tags = ["主要角色"]
                    if role:
                        tags.append(role.split("/")[0].strip())
                    if alias:
                        tags.append(f"别名:{alias}")
                    assets["entities"].append({
                        "category": "character",
                        "name": name,
                        "content": f"【定位】{role}\n{desc}".strip(),
                        "tags": ",".join(tags),
                    })

    # 2. 档案卡标题与标准标签提取 (### 宁恪（Ning Ke）、**主角**：林渊)
    card_pattern = re.compile(r'^[#*>\-\s]*###\s+([^\s:：（(—–#\-]+)(?:[（(]([^）)]+)[）)])?')
    all_cats_re = "|".join(re.escape(k) for k in cat_lookup.keys())
    ent_pattern_a = re.compile(
        rf'^[#*>\-\s]*[【\[]({all_cats_re})[】\]]\s*[:：]?\s*([^\s:：(（—–\-]+)(?:[（(]([^）)]+)[）)])?\s*[:：—–\-]?\s*(.*)$'
    )
    ent_pattern_b = re.compile(
        rf'^[#*>\-\s]*\*\*({all_cats_re})\*\*\s*[:：]\s*([^\s:：(（—–\-]+)(?:[（(]([^）)]+)[）)])?\s*[:：—–\-]?\s*(.*)$'
    )
    ent_pattern_c = re.compile(r'^[#*>\-\s]*(?:方向|方案|选项)\s*\d+[:：\s]+[【\[]([^】\]]+)[】\]]\s*(?:《[^》]+》)?\s*([^\s(（:：—–\-]+)')

    for i, line in enumerate(lines):
        # timeline event recognition
        tl_m = (
            re.match(r'^[#*>\-\s]*[【\[]?(?:\u65f6\u95f4\u7ebf\u4e8b\u4ef6|\u65f6\u95f4\u7ebf|\u5267\u60c5\u4e8b\u4ef6|\u7f16\u5e74\u4e8b\u4ef6)[】\]]?\s*[:\uff1a]?\s*(.*)$', line)
            or re.match(r'^[#*>\-\s]*\*\*(?:\u65f6\u95f4\u7ebf\u4e8b\u4ef6|\u65f6\u95f4\u7ebf|\u5267\u60c5\u4e8b\u4ef6|\u7f16\u5e74\u4e8b\u4ef6)\*\*\s*[:\uff1a]?\s*(.*)$', line)
        )
        if tl_m and any(k in line for k in ['\u65f6\u95f4', '\u4e8b\u4ef6', '\u5267\u60c5']):
            raw_body = tl_m.group(1).strip()
            if raw_body:
                m_time = re.search(r'(?:\u65f6\u95f4|\u65f6\u95f4\u8282\u70b9|\u65f6\u671f)[:\uff1a]\s*([^\uff1b;\uff0c,\n|]+)', raw_body)
                time_label = clean_str(m_time.group(1)) if m_time else ''
                m_chars = re.search(r'(?:\u4eba\u7269|\u89d2\u8272|\u6d89\u53ca\u4eba\u7269|\u6d89\u53ca\u89d2\u8272)[:\uff1a]\s*([^\uff1b;\n|)]+)', raw_body)
                characters = clean_str(m_chars.group(1)) if m_chars else ''
                m_event = re.search(r'(?:\u4e8b\u4ef6|\u5185\u5bb9|\u5267\u60c5)[:\uff1a]\s*(.*?)(?:[\uff1b;|\n]|(?:[\uff0c,]\s*(?:\u4eba\u7269|\u89d2\u8272)[:\uff1a])|\)|$)', raw_body)
                if m_event and clean_str(m_event.group(1)):
                    event = clean_str(m_event.group(1))
                else:
                    rem = raw_body
                    if m_time:
                        rem = rem.replace(m_time.group(0), '')
                    if m_chars:
                        rem = rem.replace(m_chars.group(0), '')
                    rem = re.sub(r'^[#*>\-\s:\uff1a|\uff1b;,\uff0c()\uff08\uff09]+', '', rem).strip()
                    rem = re.sub(r'[\s:\uff1a|\uff1b;,\uff0c()\uff08\uff09]+$', '', rem).strip()
                    event = clean_str(rem)
                if event:
                    assets['timeline_events'].append({
                        'time_label': time_label or '\u672a\u5b9a\u65f6\u95f4',
                        'event': event,
                        'characters': characters,
                    })
            else:
                for nxt in lines[i+1:min(len(lines), i+15)]:
                    if nxt.startswith(('#', '---')):
                        break
                    nxt_s = nxt.strip()
                    m_ev = re.match(r'^[-*>\s\u20220-9.、]*([^\n·:：]+?)[·:：\s]+([^\n]+)$', nxt_s)
                    if m_ev:
                        t_lbl = clean_str(m_ev.group(1))
                        ev_txt = clean_str(m_ev.group(2))
                        if ev_txt and t_lbl:
                            assets['timeline_events'].append({
                                'time_label': t_lbl,
                                'event': ev_txt,
                                'characters': '',
                            })
            continue

        # 单独的清单式时间线项识别 (- 开元三年 · 顾风下山，途经剑阁)
        m_tline = re.match(r'^[-*>\s\u2022]*([^·:：\n]{2,15})[·:：]\s*([^·:：\n].+)$', line)
        if m_tline:
            c_time = clean_str(m_tline.group(1))
            c_event = clean_str(m_tline.group(2))
            if any(k in c_time for k in ['年', '月', '日', '春', '夏', '秋', '冬', '初', '末', '前', '后', '世', '代', '纪', '元', '时', '刻', '夜', '第']):
                if c_event and len(c_event) >= 2 and not any(bad in c_event for bad in ['---', '===']):
                    assets['timeline_events'].append({
                        'time_label': c_time,
                        'event': c_event,
                        'characters': '',
                    })
                    continue

        # foreshadow item
        fs_m = (
            re.match(r'^[#*>\-\s]*[【\[](?:\u4f0f\u7b14|\u6697\u7ebf|\u7ebf\u7d22|\u4f0f\u7b14\u7ebf\u7d22)[】\]]\s*[:\uff1a]?\s*([^\n]+)', line)
            or re.match(r'^[#*>\-\s]*\*\*(?:\u4f0f\u7b14|\u6697\u7ebf|\u7ebf\u7d22|\u4f0f\u7b14\u7ebf\u7d22)\*\*\s*[:\uff1a]?\s*([^\n]+)', line)
            or re.match(r'^[#*>\-\s]*(?:\u4f0f\u7b14|\u6697\u7ebf|\u7ebf\u7d22|\u4f0f\u7b14\u7ebf\u7d22)\s*[:\uff1a]\s*([^\n]+)', line)
        )
        if fs_m:
            fs_text = clean_str(fs_m.group(1))
            parts = re.split(r'[:\uff1a—–\-]+', fs_text, maxsplit=1)
            f_title = parts[0].strip()[:30]
            f_content = parts[1].strip() if len(parts) > 1 else fs_text
            assets['foreshadows'].append({
                'title': f_title,
                'content': f_content,
                'status': 'planted',
            })
            continue

        # 优先匹配模式: 方向/方案/选项中的主要人物 (如 #### 方向 1：【古典仙侠】林渊)
        mc3 = ent_pattern_c.match(line)
        if mc3:
            tag_label, ent_name = mc3.groups()
            ent_name = clean_str(ent_name)
            if len(ent_name) >= 2 and len(ent_name) <= 20 and ent_name not in seen_entities:
                seen_entities.add(ent_name)
                assets["entities"].append({
                    "category": "character",
                    "name": ent_name,
                    "content": line,
                    "tags": f"立项候选,{tag_label}",
                })
            continue

        # 模式1: ### 宁恪（Ning Ke）
        mc = card_pattern.match(line)
        if mc:
            raw_cname = mc.group(1).strip()
            alias = mc.group(2) or ""
            ok, reason = sanitize_asset_item({"name": raw_cname}, "entity")
            if not ok:
                rejected.append({"kind": "entity", "title": raw_cname, "reason": reason})
                continue
            if not any(k in raw_cname for k in ["规则", "设定", "卷", "章", "场景", "关系", "核心", "一、", "二、", "三、", "四、", "五、", "方向", "方案", "简介", "计划", "分区", "接口"]):
                cname = clean_str(raw_cname)
                if len(cname) >= 2 and len(cname) <= 20 and cname not in seen_entities and not re.match(r'^[0-9一二三四五六七八九十]+[、.\s]*$', cname):
                    seen_entities.add(cname)
                    sub_desc = []
                    fields_dict = {}
                    for nxt in lines[i+1:i+15]:
                        if nxt.startswith(('###', '##', '#', '---')):
                            break
                        if nxt.startswith(('-', '*', '>')):
                            clean_line = clean_str(nxt)
                            sub_desc.append(clean_line)
                            kv_m = re.search(r'[*_\s]*([^\s:：*_\-]+)[*_\s]*[:：]\s*(.*)$', clean_line)
                            if kv_m:
                                k_raw = kv_m.group(1).strip()
                                val_clean = clean_str(kv_m.group(2).strip())
                                if any(x in k_raw for x in ["身份", "定位", "职业", "角色定位"]):
                                    fields_dict["identity"] = val_clean
                                elif any(x in k_raw for x in ["性格", "特质", "人设", "性格特质"]):
                                    fields_dict["personality"] = val_clean
                                elif any(x in k_raw for x in ["背景", "身世", "过往", "前史", "出身"]):
                                    fields_dict["background"] = val_clean
                                elif any(x in k_raw for x in ["目标", "动机", "欲望", "目标与变化", "核心动机", "核心欲望"]):
                                    fields_dict["goal"] = val_clean
                    if alias and "aliases" not in fields_dict:
                        fields_dict["aliases"] = [alias]

                    assets["entities"].append({
                        "category": "character",
                        "name": cname,
                        "content": "\n".join(sub_desc),
                        "fields_json": fields_dict,
                        "tags": f"角色档案{',' + alias if alias else ''}",
                    })
            continue

        # 模式2: 【分类】名称：描述
        ma = ent_pattern_a.match(line) or ent_pattern_b.match(line)
        if ma:
            raw_cat, name, tag_info, desc = ma.groups()
            name = clean_str(name)
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
            continue



    # 3. 常见非表格连线关系 (林渊 -> 青云宗 (叛出))
    rel_line_pattern = re.compile(
        r'^[#*>\-\s]*(?:【([^】]+)】|([^\s\-–—>]+))\s*(?:[-–—]>|->|—>|到|与|和|对)\s*(?:【([^】]+)】|([^\s(（:：]+))\s*(?:[（(]([^）)]+)[）)]|[-—–]\[([^\]]+)\][-—–]>|[:：]\s*([^\n]+))'
    )
    for line in lines:
        if line.startswith("|"):
            continue
        m = rel_line_pattern.match(line)
        if m:
            g = m.groups()
            src = clean_str(g[0] or g[1] or "")
            dst = clean_str(g[2] or g[3] or "")
            rel_label = clean_str(g[4] or g[5] or g[6] or "关联")
            if src and dst and src != dst and len(src) <= 12 and len(dst) <= 12 and len(rel_label) <= 20 and not any(bad in (src+dst) for bad in ["矩阵", "拓扑", "架构", "报告", "闭环", "地基", "规则", "计划", "实处", "耗时"]):
                rel_key = f"{src}->{dst}:{rel_label}"
                if rel_key not in seen_relations:
                    seen_relations.add(rel_key)
                    assets["relations"].append({
                        "from_name": src,
                        "to_name": dst,
                        "label": rel_label,
                    })

    # 4. 故事大纲节点识别 (分卷、章节、场景细纲)
    vol_pattern = re.compile(r'^[#*>\-\s]*(第[0-9一二三四五六七八九十百]+卷|卷[0-9一二三四五六七八九十]+)\s*[·:：\s]+([^\n(（]+)(?:[（(]([^）)]+)[）)])?')
    chap_pattern = re.compile(r'^[#*>\-\s]*(第\s*[0-9一二三四五六七八九十百]+\s*章|Chapter\s*\d+|第\s*[0-9一二三四五六七八九十百]+\s*节)\s*[·:：\s]+([^\n(（]+)(?:[（(]([^）)]+)[）)])?')

    for i, line in enumerate(lines):
        mv = vol_pattern.match(line)
        if mv:
            prefix, v_title, v_desc = mv.groups()
            full_title = f"{prefix} {v_title.strip()}".strip()
            synopsis_lines = []
            for nxt in lines[i+1:i+10]:
                if nxt.startswith(('#', '---')):
                    break
                if nxt.startswith('-') or nxt.startswith('*'):
                    synopsis_lines.append(clean_str(nxt))
            assets["outline_nodes"].append({
                "title": full_title,
                "synopsis": (v_desc or "") + ("；" if v_desc and synopsis_lines else "") + "；".join(synopsis_lines[:3]),
                "is_volume": True,
            })
            continue

        mc = chap_pattern.match(line)
        if mc:
            prefix, c_title, c_desc = mc.groups()
            full_title = f"{prefix} {c_title.strip()}".strip()
            event_desc = []
            for nxt in lines[i+1:i+6]:
                if nxt.startswith(('#', '---')):
                    break
                if any(k in nxt for k in ["事件", "功能", "钩子", "目标", "冲突"]):
                    event_desc.append(clean_str(nxt))
            assets["outline_nodes"].append({
                "title": full_title,
                "synopsis": (c_desc or "") + ("；" if c_desc and event_desc else "") + "；".join(event_desc),
                "is_volume": False,
            })

    # 5. 世界观/法则/设定资料识别
    rule_pattern = re.compile(r'^[#*>\-\s]*###\s+(规则[一二三四五六七八九十0-9]+|核心法则[一二三四五六七八九十0-9]*|法则[一二三四五六七八九十0-9]*|设定[一二三四五六七八九十0-9]*)[：:\s·]+([^\n(（]+)(?:[（(]([^）)]+)[）)])?')
    note_header_pattern = re.compile(r'^[#*>\-\s]*(?:【(世界观|力量体系|法则|设定|背景|升级机制|境界划分)】|(?:\*{2}|#{2,4})\s*(世界观|力量体系|法则|设定|背景|升级机制|境界划分)[：:\s]*(.*))')

    for i, line in enumerate(lines):
        mr = rule_pattern.match(line)
        if mr:
            tag, r_title, en_name = mr.groups()
            full_title = f"{tag} · {r_title.strip()}"
            ok, reason = sanitize_asset_item({"title": full_title}, "note")
            if not ok:
                rejected.append({"kind": "note", "title": full_title, "reason": reason})
                continue
            content_lines = []
            for nxt in lines[i+1:i+16]:
                if nxt.startswith(('###', '##', '#', '---')):
                    break
                content_lines.append(nxt)
            assets["notes"].append({
                "title": full_title,
                "content": "\n".join(content_lines).strip() or line,
                "tags": f"世界观,{tag}",
            })
            continue

        mn = note_header_pattern.match(line)
        if mn:
            tag = (mn.group(1) or mn.group(2) or "设定").strip()
            sub = (mn.group(3) or "").strip()
            title = f"{tag}{(' · ' + sub) if sub else ''}"
            ok, reason = sanitize_asset_item({"title": title}, "note")
            if not ok:
                rejected.append({"kind": "note", "title": title, "reason": reason})
                continue
            content_lines = []
            for nxt in lines[i+1:i+12]:
                if nxt.startswith(('#', '【', '---')):
                    break
                content_lines.append(nxt)
            assets["notes"].append({
                "title": title,
                "content": "\n".join(content_lines).strip() or line,
                "tags": f"世界观,{tag}",
            })

    for k, kind_name in [
        ("entities", "entity"),
        ("relations", "relation"),
        ("outline_nodes", "outline_node"),
        ("foreshadows", "foreshadow"),
        ("timeline_events", "timeline_event"),
        ("notes", "note"),
    ]:
        valid_items = []
        for item in assets[k]:
            ok, reason = sanitize_asset_item(item, kind_name)
            if ok:
                valid_items.append(item)
            else:
                t_val = (
                    item.get("name")
                    if kind_name == "entity"
                    else item.get("label")
                    if kind_name == "relation"
                    else item.get("event")
                    if kind_name == "timeline_event"
                    else item.get("title") or ""
                )
                rejected.append({"kind": kind_name, "title": t_val, "reason": reason})
        assets[k] = valid_items

    return assets, rejected


_CONTRACT_TITLE_KEYS = [
    ("entities", "name"),
    ("relations", "label"),
    ("outline_nodes", "title"),
    ("foreshadows", "title"),
    ("timeline_events", "event"),
    ("notes", "title"),
]


def merge_assets(assets_list: list[dict]) -> dict:
    """合并多次抽取结果：按「种类 + 标题」去重（先出现者优先），合并 _rejected 与 source。"""
    merged = {
        "work_info": {"title": "", "genre": "", "intro": ""},
        "entities": [],
        "relations": [],
        "outline_nodes": [],
        "foreshadows": [],
        "timeline_events": [],
        "notes": [],
        "_rejected": [],
        "source": "contract",
    }
    sources = []
    for a in assets_list or []:
        if not isinstance(a, dict):
            continue
        sources.append(a.get("source") or "heuristic")
        # work_info：先非空者胜
        for k in ("title", "genre", "intro"):
            if not merged["work_info"][k]:
                merged["work_info"][k] = ((a.get("work_info") or {}).get(k) or "")
        # 资产：按 种类+标题 去重
        for field, tkey in _CONTRACT_TITLE_KEYS:
            seen = {str(i.get(tkey, "")).strip() for i in merged[field]}
            for item in a.get(field) or []:
                if not isinstance(item, dict):
                    continue
                tv = str(item.get(tkey, "")).strip()
                if tv and tv in seen:
                    continue
                if tv:
                    seen.add(tv)
                merged[field].append(item)
        # rejected：按 (kind, title, reason) 去重
        seen_r = {(r.get("kind"), r.get("title"), r.get("reason")) for r in merged["_rejected"]}
        for r in a.get("_rejected") or []:
            if not isinstance(r, dict):
                continue
            key = (r.get("kind"), r.get("title"), r.get("reason"))
            if key in seen_r:
                continue
            seen_r.add(key)
            merged["_rejected"].append(r)
    if not sources:
        merged["source"] = "heuristic"
    elif all(s == "contract" for s in sources):
        merged["source"] = "contract"
    elif all(s == "heuristic" for s in sources):
        merged["source"] = "heuristic"
    else:
        merged["source"] = "mixed"
    return merged


def extract_structured_assets_from_text(text: str, source_kind: str = "ai") -> dict:
    assets = {
        "work_info": {
            "title": "",
            "genre": "",
            "intro": "",
        },
        "entities": [],
        "relations": [],
        "outline_nodes": [],
        "foreshadows": [],
        "timeline_events": [],
        "notes": [],
        "_rejected": [],
        "source": "heuristic",
    }
    if not text or not text.strip():
        return assets

    # step1: 清洗套话 (AI产出 strict=True，章节正文 strict=False)
    strict_flag = (source_kind == "ai")
    text = strip_ai_chatter(text, strict=strict_flag)

    # step2: 优先解析契约块
    block = extract_assets_block(text)
    if block is not None:
        source = "contract"
        rejected = []
        for kind, field in [
            ("entity", "entities"),
            ("relation", "relations"),
            ("timeline_event", "timeline_events"),
            ("foreshadow", "foreshadows"),
            ("outline_node", "outline_nodes"),
        ]:
            for item in block.get(field, []):
                ok, reason = sanitize_asset_item(item, kind)
                if ok:
                    assets[field].append(item)
                else:
                    t_val = (
                        item.get("name")
                        if kind == "entity"
                        else item.get("label")
                        if kind == "relation"
                        else item.get("event")
                        if kind == "timeline_event"
                        else item.get("title") or ""
                    )
                    rejected.append({"kind": kind, "title": t_val, "reason": reason})

        # 正文部分仍走原有启发式抽取兜底补充
        text_remain = strip_assets_blocks(text)
        text_remain, text_remain_deleted = strip_heading_only_lines(text_remain)
        heur_assets, heur_rejected = _heuristic_extract_assets(text_remain)
        for dh in text_remain_deleted:
            t = dh["title"]
            if not any(r["title"] == t for r in rejected):
                k_hint = "foreshadow" if "伏笔" in t else "timeline_event" if "时间" in t else "note" if any(x in t for x in ["世界观", "设定", "法则", "体系"]) else "entity"
                rejected.append({"kind": k_hint, "title": t, "reason": "疑似纯标题"})
        rejected.extend(heur_rejected)

        # 故事立项补充
        if not assets["work_info"]["title"]:
            assets["work_info"]["title"] = heur_assets["work_info"]["title"]
        if not assets["work_info"]["genre"]:
            assets["work_info"]["genre"] = heur_assets["work_info"]["genre"]
        if not assets["work_info"]["intro"]:
            assets["work_info"]["intro"] = heur_assets["work_info"]["intro"]

        # 同一条资产不得重复进入结果（按「种类 + 标题」去重，契约块优先）
        for field, title_key in [
            ("entities", "name"),
            ("relations", "label"),
            ("timeline_events", "event"),
            ("foreshadows", "title"),
            ("outline_nodes", "title"),
            ("notes", "title"),
        ]:
            seen_titles = {item.get(title_key, "") for item in assets[field]}
            for h_item in heur_assets.get(field, []):
                h_title = h_item.get(title_key, "")
                if h_title and h_title not in seen_titles:
                    assets[field].append(h_item)
                    seen_titles.add(h_title)

        assets["_rejected"] = rejected
        assets["source"] = source
        return assets
    else:
        source = "heuristic"
        cleaned_text, deleted_headings = strip_heading_only_lines(text)
        heur_assets, rejected = _heuristic_extract_assets(cleaned_text)
        assets.update(heur_assets)

        for dh in deleted_headings:
            sh = dh["title"]
            if not any(r["title"] == sh for r in rejected):
                k_hint = (
                    "foreshadow" if "伏笔" in sh
                    else "timeline_event" if "时间" in sh
                    else "note" if any(x in sh for x in ["世界观", "设定", "法则", "体系"])
                    else "entity"
                )
                rejected.append({"kind": k_hint, "title": sh, "reason": "疑似纯标题"})

        assets["_rejected"] = rejected
        assets["source"] = source
        return assets


def sync_assets_to_database(db, work_id: int, body: SyncAssetsIn, run_id: int = 0, seq: int = 0) -> dict:
    summary = {
        "work_info_updated": False,
        "entities_added": 0,
        "relations_added": 0,
        "outlines_added": 0,
        "foreshadows_added": 0,
        "timeline_events_added": 0,
        "notes_added": 0,
        "chapter_synced": False,
        "rejected_count": 0,
        "rejected_items": [],
    }

    run_meta = db.execute("SELECT chapter_id, outline_node_id FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    target_outline_id = run_meta["outline_node_id"] if run_meta else None
    target_chap_id = body.chapter_id or (run_meta["chapter_id"] if run_meta else None)
    if not target_chap_id and work_id:
        chap_row = db.execute(
            """SELECT c.id FROM chapters c 
               JOIN volumes v ON v.id = c.volume_id 
               WHERE v.work_id = ? 
               ORDER BY v.sort_order ASC, c.sort_order ASC, c.id ASC LIMIT 1""",
            (work_id,)
        ).fetchone()
        if chap_row:
            target_chap_id = chap_row["id"]

    # 0. 故事立项：规范同步至作品基本信息 (works 表)
    if body.work_info:
        w_title = (body.work_info.title or "").strip()
        w_genre = (body.work_info.genre or "").strip()
        w_intro = (body.work_info.intro or "").strip()
        updates, params = [], []
        if w_title:
            updates.append("title = ?")
            params.append(w_title)
        if w_genre:
            updates.append("genre = ?")
            params.append(w_genre)
        if w_intro:
            updates.append("intro = ?")
            params.append(w_intro)
        if updates:
            params.append(work_id)
            db.execute(f"UPDATE works SET {', '.join(updates)}, updated_at=datetime('now','localtime') WHERE id=?", tuple(params))
            summary["work_info_updated"] = True

    # 1. 万相谱实体同步
    name_to_id = {}
    existing_entities = db.execute("SELECT id, name FROM entities WHERE work_id=?", (work_id,)).fetchall()
    for r in existing_entities:
        name_to_id[r["name"]] = r["id"]

    for ent in body.entities:
        name = ent.name.strip()
        ok_ent, r_ent = sanitize_asset_item({"name": name, "category": ent.category, "content": ent.content}, "entity")
        if not ok_ent:
            summary["rejected_count"] += 1
            if len(summary["rejected_items"]) < 20:
                summary["rejected_items"].append({"kind": "entity", "title": name, "reason": r_ent})
            continue
        if not name:
            continue
        f_json = ent.fields_json
        if isinstance(f_json, dict):
            fields_str = json.dumps(f_json, ensure_ascii=False)
        elif isinstance(f_json, str) and f_json.strip():
            fields_str = f_json
        else:
            fields_str = "{}"

        if name in name_to_id:
            eid = name_to_id[name]
            exist_row = db.execute("SELECT fields_json FROM entities WHERE id=?", (eid,)).fetchone()
            try:
                exist_fields = json.loads(exist_row["fields_json"] or "{}") if exist_row else {}
            except Exception:
                exist_fields = {}
            if isinstance(f_json, dict):
                for k, v in f_json.items():
                    if v and not exist_fields.get(k):
                        exist_fields[k] = v
            new_fields_str = json.dumps(exist_fields, ensure_ascii=False)

            if ent.content:
                db.execute(
                    """UPDATE entities 
                       SET content = CASE WHEN content != '' THEN content || '\n' || ? ELSE ? END, 
                           fields_json = ?, 
                           updated_at = datetime('now','localtime') 
                       WHERE id = ?""",
                    (ent.content, ent.content, new_fields_str, eid),
                )
            else:
                db.execute(
                    """UPDATE entities SET fields_json = ?, updated_at = datetime('now','localtime') WHERE id = ?""",
                    (new_fields_str, eid),
                )
        else:
            cur = db.execute(
                "INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (work_id, ent.category or "character", name, ent.content, fields_str, ent.tags),
            )
            eid = cur.lastrowid
            name_to_id[name] = eid
            summary["entities_added"] += 1

        if target_chap_id:
            db.execute(
                "INSERT OR IGNORE INTO chapter_entities (chapter_id, entity_id) VALUES (?, ?)",
                (target_chap_id, eid)
            )

    # 2. 万相图谱关系同步
    for rel in body.relations:
        from_name = rel.from_name.strip()
        to_name = rel.to_name.strip()
        label = rel.label.strip() or "关联"
        ok_rel, r_rel = sanitize_asset_item({"from": from_name, "to": to_name, "label": label}, "relation")
        if not ok_rel:
            summary["rejected_count"] += 1
            if len(summary["rejected_items"]) < 20:
                summary["rejected_items"].append({"kind": "relation", "title": label, "reason": r_rel})
            continue
        if not from_name or not to_name or from_name == to_name:
            continue
        from_id = name_to_id.get(from_name)
        to_id = name_to_id.get(to_name)
        if not from_id:
            cur = db.execute(
                "INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?, 'character', ?, '', '{}', '关系推断')",
                (work_id, from_name),
            )
            from_id = cur.lastrowid
            name_to_id[from_name] = from_id
            summary["entities_added"] += 1
        if not to_id:
            cur = db.execute(
                "INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?, 'character', ?, '', '{}', '关系推断')",
                (work_id, to_name),
            )
            to_id = cur.lastrowid
            name_to_id[to_name] = to_id
            summary["entities_added"] += 1

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

    # 3. 三位一体剧情脉络同步 (大纲 / 时间线 / 伏笔)，统一委托 plot_service
    from app.services.plot_service import batch_sync_triad_assets

    triad_stats = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=[(e.model_dump() if hasattr(e, "model_dump") else e.dict()) for e in body.timeline_events],
        foreshadows=[(f.model_dump() if hasattr(f, "model_dump") else f.dict()) for f in body.foreshadows],
        outline_nodes=[(o.model_dump() if hasattr(o, "model_dump") else o.dict()) for o in body.outline_nodes],
        default_outline_node_id=target_outline_id,
        default_chapter_id=target_chap_id,
    )
    summary["outlines_added"] += triad_stats["outline_nodes_added"]
    summary["foreshadows_added"] += triad_stats["foreshadows_added"]
    summary["timeline_events_added"] += triad_stats["timeline_events_added"]
    summary["rejected_count"] += triad_stats.get("rejected_count", 0)
    for r_item in triad_stats.get("rejected_items", []):
        if len(summary["rejected_items"]) < 20:
            summary["rejected_items"].append(r_item)


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
                (chapter_id, body.chapter_content, wc, (f"工作流 #{run_id} 全流程汇总采纳" if seq == 0 else f"工作流 #{run_id} 步骤 {seq + 1} 采纳")),
            )
            db.execute(
                "UPDATE chapters SET content=?, word_count=?, updated_at=datetime('now','localtime') WHERE id=?",
                (body.chapter_content, wc, chapter_id),
            )
            summary["chapter_synced"] = True

    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?", (work_id,))
    db.commit()
    return summary