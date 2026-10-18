# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队 · MIT
import json
import re
from typing import Any

CHATTER_PREFIXES_STRONG = [
    "好的", "好的，", "如上所述", "综上所述", "这是为您", "这是给你",
    "供你参考", "供您参考", "如果有任何", "祝创作顺利",
]

CHATTER_PREFIXES_AMBIGUOUS = [
    "感谢", "期待", "祝你", "祝你创作", "希望以上", "希望这", "希望能",
    "如需", "如果需要", "如有需要", "请注意", "注意：", "以下是", "以下为",
]

CHATTER_PREFIXES = CHATTER_PREFIXES_STRONG + CHATTER_PREFIXES_AMBIGUOUS

CHATTER_CONTAINS = [
    "修改后的内容", "修改后的正文", "修改后的版本", "改写后的内容", "优化后的内容",
    "完整内容如下", "内容如下：", "这是我的创作", "希望对你有帮助",
    "如有任何问题", "请随时告诉我", "随时告诉我",
]

HEADING_KEYWORDS = {
    "世界观设定", "世界观 · 设定", "世界观", "设定集", "设定",
    "伏笔暗线", "伏笔", "暗线", "线索", "伏笔线索",
    "时间线", "时间线事件", "剧情事件", "编年事件",
    "角色关系网", "关系网", "人物关系",
    "势力格局", "地理场景", "道具神兵",
    "分卷大纲", "章节大纲", "故事大纲", "大纲",
}

CHARACTER_FIELD_KEYWORDS = [
    "身份", "定位", "职业", "角色定位",
    "性格", "特质", "人设", "性格特质",
    "背景", "身世", "过往", "前史", "出身",
    "目标", "动机", "欲望", "核心动机", "核心欲望", "目标与变化",
    "主要角色", "表面欲望", "核心冲突",
]


def strip_ai_chatter(text: str, strict: bool = True) -> str:
    """删除 AI 套话行与分隔线行，保留正常句子与原有换行结构。
    strict=True (用于 AI 产出): 强词表无条件删 + 弱词表在满足边界条件时删
    strict=False (用于用户正文): 仅用强词表，弱词表完全不启用
    """
    if not text:
        return ""
    lines = text.splitlines()

    # 计算全文首尾各 3 个非空行的索引
    non_empty_indices = [idx for idx, line in enumerate(lines) if line.strip()]
    if len(non_empty_indices) <= 6:
        boundary_indices = set(non_empty_indices)
    else:
        boundary_indices = set(non_empty_indices[:3] + non_empty_indices[-3:])

    cleaned_lines = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        # 检查纯分隔线行 (---, ===, ***, ___)
        if len(stripped) >= 3 and set(stripped) <= {'-', '=', '*', '_'}:
            continue

        stripped_lower = stripped.lower()

        # 检查包含词
        if any(contain.lower() in stripped_lower for contain in CHATTER_CONTAINS):
            continue

        # 检查强套话词表（无条件整行删除）
        if any(stripped_lower.startswith(p.lower()) for p in CHATTER_PREFIXES_STRONG):
            continue

        # 检查弱套话词表（仅在 strict=True 且满足条件时删除）
        if strict and any(stripped_lower.startswith(p.lower()) for p in CHATTER_PREFIXES_AMBIGUOUS):
            # 弱词表命中条件：长度 <= 25 且 位于首尾各3行非空行内 且 不含标点冒号逗号
            has_punct = any(ch in stripped for ch in [':', '：', ',', '，'])
            if len(stripped) <= 25 and (idx in boundary_indices) and not has_punct:
                continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def strip_heading_only_lines(text: str) -> tuple[str, list[dict]]:
    """删除纯标题行（如 ### 世界观设定、### 伏笔暗线、### 时间线），保留角色卡等数据卡。
    返回: (清洗后文本, 被删行列表)，元素形如 {"title": "<标题文本>", "line_no": <行号>}
    """
    if not text:
        return "", []
    lines = text.splitlines()
    cleaned_lines = []
    deleted_headings = []
    for i, line in enumerate(lines):
        m = re.match(r'^\s{0,3}#{1,6}\s*(.+)$', line)
        if m:
            heading = m.group(1).strip()
            heading_clean = re.sub(r'^[#\s]+|[#\s]+$', '', heading).strip()
            # 包含冒号的视为有内联内容，不作为纯标题行删除
            if len(heading_clean) <= 20 and ':' not in heading_clean and '：' not in heading_clean:
                # 检查是否为角色档案卡标题（如 ### 宁恪（主角） 或后文紧跟角色字段）
                is_character_card = False
                if '(' in heading_clean or '（' in heading_clean:
                    # 含别名/角色括号标记，且不属于纯模块标题词
                    if heading_clean not in HEADING_KEYWORDS and not any(kw in heading_clean for kw in ["世界观", "伏笔", "暗线", "时间线", "关系网", "大纲"]):
                        is_character_card = True

                if not is_character_card:
                    # 检查后文 1~6 行是否包含角色卡专用字段 (- **身份**：等)
                    for nxt in lines[i + 1:min(len(lines), i + 7)]:
                        nxt_s = nxt.strip()
                        if nxt_s.startswith(('#', '---')):
                            break
                        if any(f"**{kw}**" in nxt_s or f"【{kw}】" in nxt_s for kw in CHARACTER_FIELD_KEYWORDS):
                            is_character_card = True
                            break

                if not is_character_card:
                    # 属于纯标题行，删除并记录
                    deleted_headings.append({"title": heading_clean, "line_no": i + 1})
                    continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines), deleted_headings


def extract_assets_block(text: str) -> dict | None:
    """解析 <!-- MOYU:ASSETS ... MOYU:ASSETS --> 资产契约块，严格容错解析。
    取文本中最后一个匹配块，防范前文引用的示例干扰；若未闭合尝试末尾宽容补齐。
    """
    if not text:
        return None
    patterns = [
        r'<!--\s*MOYU:ASSETS\s*([\s\S]*?)\s*MOYU:ASSETS\s*-->',   # 双标记
        r'<!--\s*MOYU:ASSETS\s*([\s\S]*?)\s*-->',                  # 单标记收尾
    ]
    raw_json = None
    for pat in patterns:
        matches = list(re.finditer(pat, text, re.IGNORECASE))
        if matches:
            raw_json = matches[-1].group(1).strip()
            break

    # 宽容处理：如果因 token 截断未闭合
    if raw_json is None and "<!-- MOYU:ASSETS" in text.upper():
        idx = text.upper().rfind("<!-- MOYU:ASSETS")
        tail = text[idx + len("<!-- MOYU:ASSETS"):].strip()
        # 去掉可能的开门注释符号
        if tail.startswith("-->"):
            tail = tail[3:].strip()
        # 补齐尾部
        if "{" in tail and not tail.endswith("}"):
            raw_json = tail + "}"
        else:
            raw_json = tail

    if raw_json is None:
        return None
    # 剥离 markdown 代码围栏
    raw_json = re.sub(r'^```(?:json)?\s*', '', raw_json, flags=re.IGNORECASE)
    raw_json = re.sub(r'\s*```$', '', raw_json)
    # 替换中文引号
    raw_json = raw_json.replace('“', '"').replace('”', '"')
    # 容错：剥离对象或数组末尾的多余逗号
    raw_json = re.sub(r',\s*([}\]])', r'\1', raw_json)

    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            return None
        valid_keys = ["entities", "relations", "timeline_events", "foreshadows", "outline_nodes", "notes", "chapter_synopses"]
        res: dict = {}
        for k in valid_keys:
            val = data.get(k)
            res[k] = val if isinstance(val, list) else []
        wi = data.get("work_info")
        if isinstance(wi, dict):
            res["work_info"] = {
                "title": str(wi.get("title") or "").strip(),
                "genre": str(wi.get("genre") or "").strip(),
                "intro": str(wi.get("intro") or "").strip(),
            }
        else:
            res["work_info"] = {"title": "", "genre": "", "intro": ""}
        return res
    except Exception:
        return None


def sanitize_asset_item(item: dict, kind: str) -> tuple[bool, str]:
    """单条资产校验，返回 (是否通过, 不通过原因)。"""
    if not isinstance(item, dict):
        return False, "无效条目"

    # 1. 提取标题字段
    if kind == "foreshadow":
        title = item.get("title", "")
    elif kind == "timeline_event":
        title = item.get("event", "")
    elif kind == "entity":
        title = item.get("name", "")
    elif kind == "outline_node":
        title = item.get("title", "")
    elif kind == "relation":
        title = item.get("label", "")
    elif kind == "note":
        title = item.get("title", "")
    elif kind in ("chapter_synopsis", "chapter_synopses"):
        title = item.get("node_title", "")
    else:
        title = item.get("title") or item.get("name") or item.get("event") or item.get("label") or ""

    if not isinstance(title, str):
        title = str(title) if title is not None else ""

    title_strip = title.strip()

    # 2. 标题为空
    if not title_strip:
        return False, "标题为空"

    if kind in ("chapter_synopsis", "chapter_synopses"):
        syn = item.get("synopsis", "")
        if not isinstance(syn, str):
            syn = str(syn) if syn is not None else ""
        if not syn.strip():
            return False, "梗概为空"

    # 3. 标题长度 > 30
    if len(title_strip) > 30:
        return False, "标题过长"

    # 4. 标题命中套话词表
    title_lower = title_strip.lower()
    if any(title_lower.startswith(p.lower()) for p in CHATTER_PREFIXES) or any(c.lower() in title_lower for c in CHATTER_CONTAINS):
        return False, "疑似 AI 套话"

    # 5. 标题或内容含截断标记
    check_texts = [title]
    for v in item.values():
        if isinstance(v, str):
            check_texts.append(v)
        elif isinstance(v, (list, dict)):
            check_texts.append(json.dumps(v, ensure_ascii=False))

    for txt in check_texts:
        if "[中段内容已截断]" in txt or "……[" in txt or "]……" in txt:
            return False, "含截断标记"

    # 6. 纯标点或纯符号
    if not re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', title_strip):
        return False, "无有效内容"

    # 7. 纯标题行或章节元数据识别（避免将“伏笔暗线”、“世界观设定”等作为资产名称）
    if re.match(r'^\s*#{1,6}\s*', title_strip) or title_strip in HEADING_KEYWORDS:
        return False, "疑似纯标题"

    return True, ""


def strip_assets_blocks(text: str) -> str:
    """删除文本中全部 MOYU:ASSETS 契约块（兼容双标记与单标记收尾）。"""
    if not text:
        return ""
    text = re.sub(r'<!--\s*MOYU:ASSETS[\s\S]*?MOYU:ASSETS\s*-->', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<!--\s*MOYU:ASSETS[\s\S]*?-->', '', text, flags=re.IGNORECASE)
    return text


# 墨语产物契约：唯一权威 schema（被 build_contract_clause 与炼丹炉合并共用）
ASSET_CONTRACT_KEYS = [
    "work_info", "entities", "relations", "timeline_events",
    "foreshadows", "outline_nodes", "chapter_synopses", "notes",
]

# 合法实体分类与伏笔状态枚举（契约强制校验边界）
_CONTRACT_CATEGORIES = ("character", "place", "faction", "item", "term", "custom")
_CONTRACT_FORESHADOW_STATUS = ("planted", "pending", "recovered")


# 每技能应产出的资产键声明（契约适配式重构核心元数据）。
# 这是「技能 → 墨语核心模块」的唯一映射源，被 build_skill_system_prompt 与
# workflow_engine 共用，消除直接调用与 workflow 两条路径的契约口径分歧。
# 键名严格取自 ASSET_CONTRACT_KEYS；空列表表示该技能不强制产出结构化资产。
SKILL_ASSET_CONTRACTS: dict[str, list[str]] = {
    # 一、立项与世界观体系 (Premise & Worldbuilding)
    "novel-premise":        ["work_info", "entities", "notes"],
    "novel-world":          ["entities", "relations", "timeline_events", "notes"],
    "novel-magic-system":   ["entities", "notes"],
    "novel-cast":           ["entities", "relations"],
    "novel-faction-graph":  ["entities", "relations"],

    # 二、大纲拓扑与剧情架构 (Plot Architecture)
    "novel-outline-macro":    ["outline_nodes", "timeline_events", "foreshadows"],
    "novel-scene":            ["outline_nodes", "foreshadows", "entities", "timeline_events"],
    "novel-timeline":         ["timeline_events"],
    "novel-foreshadow-matrix":["foreshadows", "timeline_events"],
    "novel-hook-engineer":    ["notes", "foreshadows"],
    "novel-lead-arc":         ["entities", "outline_nodes", "notes"],

    # 三、正文撰写与文风修撰 (Drafting & Stylistic Craft)
    "prose-continue":       ["entities", "foreshadows", "timeline_events"],
    "prose-expand":         ["entities", "notes"],
    "prose-polish":         ["notes"],
    "prose-dialogue":       ["notes"],
    "prose-combat":         ["timeline_events", "notes"],
    "prose-sensory":        ["notes"],
    "novel-forge":          ["entities", "relations", "timeline_events",
                             "foreshadows", "outline_nodes", "notes"],

    # 四、审校质检与回溯反馈 (Audit & Consistency Quality Gate)
    "audit-consistency":     ["notes"],
    "audit-foreshadow":      ["foreshadows", "notes"],
    "audit-timeline":        ["timeline_events", "notes"],
    "audit-de-aitone":       ["notes"],
    "audit-pacing-rhythm":   ["notes", "work_info"],
    "audit-synopsis-distill":["chapter_synopses", "notes"],
}


def build_contract_clause(required_keys: list[str]) -> str:
    """构建 MOYU:ASSETS 契约提示词（schema 强制版）。

    required_keys: 本任务需要产出的产物键；其余键保留并填空数组。
    仅列出本任务涉及的产物键、以空数组/空对象占位，并附字段强规则，
    使墨语 output_normalizer 以高识别率解析并入核心模块。
    """
    if not required_keys:
        return ""
    required = [k for k in ASSET_CONTRACT_KEYS if k in set(required_keys)]
    if not required:
        return ""
    req_label = "、".join(required)

    # 仅列出本任务涉及的产物键，键以空数组/空对象占位（模型照此结构填充）
    lines = []
    for k in required:
        if k == "work_info":
            lines.append('  "work_info": {"title": "", "genre": "", "intro": ""}')
        else:
            lines.append(f'  "{k}": []')
    example = "<!-- MOYU:ASSETS\n{\n" + ",\n".join(lines) + "\n}\nMOYU:ASSETS -->"

    return (
        "【结构化产物交付契约 MOYU:ASSETS（强制）】\n"
        "若本次产出可沉淀入库的创作资产，必须在回答**末尾**追加如下契约块"
        "（HTML 注释包裹的合法 JSON），严格照此结构输出；正文写于契约块之外。\n"
        f"{example}\n"
        f"本任务必须产出的产物键：{req_label}（其余种类保留键并填空数组 []）。\n"
        "字段规则：\n"
        "1. entity.category 仅限 character/place/faction/item/term；人物实体可用 fields_json 承载欲望/创伤/弧光/说话方式等高维设定；\n"
        "2. relations 子项结构：{\"from_name\": \"起点角色\", \"to_name\": \"终点角色\", \"label\": \"关系/冲突说明\"}；\n"
        "3. timeline_events 子项结构：{\"time_label\": \"时间点\", \"event\": \"事件描述\", \"characters\": \"相关角色\"}；\n"
        "4. foreshadows 子项结构：{\"title\": \"伏笔标题\", \"content\": \"线索内容\", \"status\": \"planted/pending/recovered\"}；\n"
        "5. outline_node.is_volume=true 表示分卷，false 表示章节；parent_title 填所属分卷名；\n"
        "6. 所有 title/name/event 须 ≤30 字、非空、非 AI 套话；\n"
        "7. 严禁将大段章节正文塞入契约块，契约块只放结构化元数据。"
    )


def canonicalize_assets(raw: dict | None) -> dict:
    """将任意来源（契约块 / 启发式）抽取出的资产字典归一到权威 schema。

    保证 8 个产物键全部存在且为 list（work_info 为 dict），
    实体 category 归一到枚举，伏笔 status 归一到枚举，过滤非法条目交由调用方取舍。
    """
    res: dict = {k: [] for k in ASSET_CONTRACT_KEYS}
    res["work_info"] = {"title": "", "genre": "", "intro": ""}
    if not isinstance(raw, dict):
        return res

    if isinstance(raw.get("work_info"), dict):
        wi = raw["work_info"]
        res["work_info"] = {
            "title": str(wi.get("title") or "").strip(),
            "genre": str(wi.get("genre") or "").strip(),
            "intro": str(wi.get("intro") or "").strip(),
        }

    for k in ASSET_CONTRACT_KEYS:
        if k == "work_info":
            continue
        val = raw.get(k)
        if isinstance(val, list):
            res[k] = [v for v in val if isinstance(v, dict)]

    # 实体 category 归一
    for ent in res.get("entities", []):
        cat = str(ent.get("category", "")).strip().lower()
        if cat not in _CONTRACT_CATEGORIES:
            # 中文别名兼容（兜底，与 workflow_assets.normalize_category 对齐）
            alias = {
                "人物": "character", "角色": "character", "主角": "character", "配角": "character",
                "地点": "place", "场景": "place", "地理": "place", "location": "place",
                "势力": "faction", "组织": "faction", "门派": "faction", "阵营": "faction",
                "道具": "item", "物品": "item", "神兵": "item",
                "术语": "term", "设定": "term", "概念": "term", "世界观": "term", "规则": "term",
                "lore": "term",
            }
            ent["category"] = alias.get(cat, "term")
        # fields_json 兜底为对象
        fj = ent.get("fields_json")
        if isinstance(fj, str):
            try:
                ent["fields_json"] = json.loads(fj) if fj.strip() else {}
            except Exception:
                ent["fields_json"] = {}
        elif not isinstance(fj, dict):
            ent["fields_json"] = {}

    # 伏笔 status 归一
    for fs in res.get("foreshadows", []):
        st = str(fs.get("status", "")).strip().lower()
        fs["status"] = st if st in _CONTRACT_FORESHADOW_STATUS else "planted"

    return res
