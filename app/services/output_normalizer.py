# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队 · MIT
import json
import re
from typing import Any

CHATTER_PREFIXES = [
    "好的", "好的，", "以下是", "以下为", "如上所述", "综上所述", "这是为您", "这是给你",
    "希望以上", "希望这", "希望能", "如需", "如果需要", "如有需要", "请注意", "注意：",
    "供你参考", "供您参考", "祝你", "祝创作", "感谢", "期待", "如果有任何",
]

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


def strip_ai_chatter(text: str) -> str:
    """删除 AI 套话行与分隔线行，保留正常句子与原有换行结构。"""
    if not text:
        return ""
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        # 检查纯分隔线行 (---, ===, ***, ___)
        if len(stripped) >= 3 and set(stripped) <= {'-', '=', '*', '_'}:
            continue

        # 检查前缀词表 (大小写不敏感)
        stripped_lower = stripped.lower()
        if any(stripped_lower.startswith(prefix.lower()) for prefix in CHATTER_PREFIXES):
            continue

        # 检查包含词
        if any(contain.lower() in stripped_lower for contain in CHATTER_CONTAINS):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def strip_heading_only_lines(text: str) -> str:
    """删除纯标题行（如 ### 世界观设定、### 伏笔暗线、### 时间线），保留角色卡等数据卡。"""
    if not text:
        return ""
    lines = text.splitlines()
    cleaned_lines = []
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
                    # 属于纯标题行，删除
                    continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def extract_assets_block(text: str) -> dict | None:
    """解析 <!-- MOYU:ASSETS ... MOYU:ASSETS --> 资产契约块，严格容错解析。"""
    if not text:
        return None
    match = re.search(r'<!--\s*MOYU:ASSETS\s*([\s\S]*?)\s*MOYU:ASSETS\s*-->', text, re.IGNORECASE)
    if not match:
        return None

    raw_json = match.group(1).strip()
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
        valid_keys = ["entities", "relations", "timeline_events", "foreshadows", "outline_nodes"]
        res: dict[str, list] = {}
        for k in valid_keys:
            val = data.get(k)
            res[k] = val if isinstance(val, list) else []
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
    else:
        title = item.get("title") or item.get("name") or item.get("event") or item.get("label") or ""

    if not isinstance(title, str):
        title = str(title) if title is not None else ""

    title_strip = title.strip()

    # 2. 标题为空
    if not title_strip:
        return False, "标题为空"

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
