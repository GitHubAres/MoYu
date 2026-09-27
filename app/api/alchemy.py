"""炼丹炉 API：拆书蒸馏 / 资料融汇 / 开炉炼丹。"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai_client import AIError, chat, get_ai_config
from ..db import get_db
from . import io_export

router = APIRouter(prefix="/alchemy", tags=["alchemy"])

AI_NOT_CONFIGURED = "尚未配置 AI 接口，请先到「系统设置」填写 Base URL、API Key 与模型名后再试。"

LORE_CATEGORIES = ("character", "place", "faction", "item", "term")


# ---------- 公共工具 ----------

def _ai_cfg() -> dict:
    cfg = get_ai_config()
    if not (cfg.get("ai_base_url") and cfg.get("ai_api_key") and cfg.get("ai_model")):
        raise HTTPException(400, AI_NOT_CONFIGURED)
    return cfg


async def _chat(system: str, user: str) -> str:
    cfg = _ai_cfg()
    try:
        text, _ = await chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}], cfg)
    except AIError as e:
        raise HTTPException(502, str(e))
    return text or ""


def _parse_json_obj(raw: str) -> dict | None:
    """容错解析：截取首个 { 到最后一个 } 再 json.loads。"""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _read_import_text(file_token: str) -> tuple[str, str]:
    """按 file_token 读取暂存文件纯文本，返回 (文件名, 全文)。"""
    token = Path(file_token or "").name
    if not token:
        raise HTTPException(400, "缺少 file_token")
    path = io_export.IMPORT_DIR / token
    if not path.is_file():
        raise HTTPException(404, "暂存文件不存在或已过期，请重新上传")
    try:
        if path.suffix.lower() == ".docx":
            text = io_export._read_docx(path)
        else:
            text = io_export._decode(path.read_bytes())
    except ValueError as e:
        raise HTTPException(400, str(e))
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise HTTPException(400, "文件内容为空")
    return path.stem, text


def _sample_three(text: str, total: int) -> str:
    """开头/中段/结尾各取一段，合计不超过 total 字。"""
    if len(text) <= total:
        return text
    seg = total // 3
    head = text[:seg]
    mid_at = max(0, (len(text) - seg) // 2)
    middle = text[mid_at:mid_at + seg]
    tail = text[-seg:]
    return head + "\n……（中段节选）……\n" + middle + "\n……（结尾节选）……\n" + tail


def _work(work_id: int) -> dict:
    row = get_db().execute("SELECT * FROM works WHERE id=?", (work_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _normalize_entity(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    if not name:
        return None
    category = str(item.get("category") or "term").strip()
    if category not in LORE_CATEGORIES:
        category = "term"
    return {"category": category, "name": name[:80],
            "content": str(item.get("content") or "").strip(),
            "tags": str(item.get("tags") or "").strip()[:200]}


def _normalize_outline(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    parent = item.get("parent")
    return {"title": title[:80],
            "synopsis": str(item.get("synopsis") or "").strip(),
            "parent": str(parent).strip()[:80] if parent else None}


def _insert_entities(work_id: int, entities: list[dict]) -> tuple[int, int]:
    """批量入库设定条目，同名同分类跳过。返回 (入库数, 跳过数)。"""
    db = get_db()
    created = skipped = 0
    for e in entities:
        exists = db.execute(
            "SELECT id FROM entities WHERE work_id=? AND category=? AND name=?",
            (work_id, e["category"], e["name"])).fetchone()
        if exists:
            skipped += 1
            continue
        db.execute(
            "INSERT INTO entities(work_id, category, name, content, fields_json, tags) VALUES (?,?,?,?,?,?)",
            (work_id, e["category"], e["name"], e["content"], "{}", e["tags"]))
        created += 1
    if created:
        db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?",
                   (work_id,))
    return created, skipped


def _insert_outline(work_id: int, outline: list[dict]) -> int:
    """按 parent 标题建树入库；找不到父则作顶层。返回入库节点数。"""
    db = get_db()
    created = 0
    title_map: dict[str, int] = {}  # 本批次 标题 -> 节点 id
    for node in outline:
        parent_id = None
        if node.get("parent"):
            parent_id = title_map.get(node["parent"])
            if parent_id is None:
                row = db.execute(
                    "SELECT id FROM outline_nodes WHERE work_id=? AND title=? ORDER BY id LIMIT 1",
                    (work_id, node["parent"])).fetchone()
                parent_id = row["id"] if row else None
        n = db.execute(
            "SELECT COALESCE(MAX(sort_order),0)+1 FROM outline_nodes WHERE work_id=? AND parent_id IS ?",
            (work_id, parent_id)).fetchone()[0]
        cur = db.execute(
            "INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, sort_order) VALUES (?,?,?,?,?)",
            (work_id, parent_id, node["title"], node["synopsis"], n))
        title_map[node["title"]] = cur.lastrowid
        created += 1
    if created:
        db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?",
                   (work_id,))
    return created


# ---------- 1. 拆书蒸馏 ----------

ANALYZE_PROMPT = (
    "你是一位资深网文编辑与文本分析专家。请通读下面的小说文本样本，输出一份「拆书」拆解报告。\n"
    "输出要求：用简体中文 Markdown，包含以下五个小节（以 ## 作为小节标题）：\n"
    "## 叙事视角（人称、视角切换、叙述距离）\n"
    "## 句式与用词（句长节奏、修辞偏好、高频用词特征）\n"
    "## 节奏结构（场景切换、钩子设置、张弛安排）\n"
    "## 人物塑造（出场方式、对白风格、性格呈现手法）\n"
    "## 可借鉴清单（5-8 条可直接模仿的具体写法，每条一行、以 - 开头）\n"
    "只输出报告正文，不要寒暄。"
)


class AnalyzeIn(BaseModel):
    file_token: str | None = None
    work_id: int | None = None


@router.post("/analyze")
async def analyze(body: AnalyzeIn):
    if not body.file_token and not body.work_id:
        raise HTTPException(400, "请提供 file_token 或 work_id 之一")

    parts: list[str] = []
    if body.file_token:
        name, text = _read_import_text(body.file_token)
        sample = _sample_three(text, 8000)
        parts.append(f"【文件：{name}】\n{sample}")
        sample_info = {"source": "file", "name": name,
                       "total_chars": len(text), "sampled_chars": len(sample)}
    else:
        work = _work(body.work_id)
        db = get_db()
        chapters = db.execute(
            """SELECT c.title, c.content FROM chapters c
               JOIN volumes v ON v.id=c.volume_id
               WHERE v.work_id=? ORDER BY v.sort_order, c.sort_order, c.id""",
            (body.work_id,)).fetchall()
        chapters = [c for c in chapters if (c["content"] or "").strip()]
        if not chapters:
            raise HTTPException(400, "该作品暂无正文内容，无法拆解")
        picked = chapters[:2] + ([] if len(chapters) <= 4 else chapters[-2:])
        seen, uniq = set(), []
        for c in picked:
            if id(c) not in seen:
                seen.add(id(c))
                uniq.append(c)
        budget = 8000 // len(uniq)
        total_chars = sum(len(c["content"]) for c in chapters)
        for c in uniq:
            text = c["content"].strip()
            sample = text[:budget] + ("\n……" if len(text) > budget else "")
            parts.append(f"【章节：{c['title']}】\n{sample}")
        sample_info = {"source": "work", "name": work["title"],
                       "chapter_count": len(chapters),
                       "sampled_chapters": [c["title"] for c in uniq],
                       "total_chars": total_chars,
                       "sampled_chars": sum(len(p) for p in parts)}

    report = await _chat(ANALYZE_PROMPT, "\n\n".join(parts))
    if not report.strip():
        raise HTTPException(502, "AI 未返回有效的拆解报告")
    return {"report": report.strip(), "sample_info": sample_info}


class SaveStyleIn(BaseModel):
    work_id: int
    style_profile: str


@router.post("/save-style")
def save_style(body: SaveStyleIn):
    _work(body.work_id)
    profile = body.style_profile.strip()
    if not profile:
        raise HTTPException(400, "文风档案内容为空")
    db = get_db()
    db.execute(
        "UPDATE works SET style_profile=?, updated_at=datetime('now','localtime') WHERE id=?",
        (profile, body.work_id))
    db.commit()
    return {"ok": True, "style_profile": profile}


# ---------- 2. 资料融汇 ----------

EXTRACT_PROMPT = (
    "你是一位小说设定整理助手。请阅读下面的资料文本，提炼其中的设定信息与情节线索。\n"
    "只输出一个 JSON 对象，不要输出任何其他文字，格式为：\n"
    '{"entities": [{"category": "character|place|faction|item|term", "name": "名称", '
    '"content": "一段设定描述", "tags": "逗号分隔标签"}], '
    '"outline": [{"title": "节点标题", "synopsis": "梗概", "parent": "父节点标题或null"}]}\n'
    "规则：entities 提炼人物/地点/势力/物品/术语等设定，宁缺毋滥；"
    "outline 提炼故事结构（卷/篇为父，章/事件为子），顶层节点 parent 为 null。"
)


class ExtractLoreIn(BaseModel):
    file_token: str


@router.post("/extract-lore")
async def extract_lore(body: ExtractLoreIn):
    name, text = _read_import_text(body.file_token)
    raw = await _chat(EXTRACT_PROMPT, f"【资料：{name}】\n{text[:12000]}")
    data = _parse_json_obj(raw)
    if data is None:
        raise HTTPException(422, "AI 返回内容无法解析为结构化数据，原文片段："
                            + raw.strip()[:500])
    entities = [e for e in
                (_normalize_entity(i) for i in data.get("entities") or [])
                if e]
    outline = [o for o in
               (_normalize_outline(i) for i in data.get("outline") or [])
               if o]
    return {"entities": entities, "outline": outline,
            "source": {"name": name, "total_chars": len(text)}}


class ImportLoreIn(BaseModel):
    work_id: int
    entities: list[dict] = Field(default_factory=list)
    outline: list[dict] = Field(default_factory=list)


@router.post("/import-lore")
def import_lore(body: ImportLoreIn):
    _work(body.work_id)
    entities = [e for e in (_normalize_entity(i) for i in body.entities) if e]
    outline = [o for o in (_normalize_outline(i) for i in body.outline) if o]
    created_e, skipped = _insert_entities(body.work_id, entities)
    created_o = _insert_outline(body.work_id, outline)
    get_db().commit()
    return {"created": {"entities": created_e, "outline": created_o},
            "skipped": skipped}


# ---------- 3. 开炉炼丹 ----------

BREW_PROMPTS = {
    "framework": (
        "你是一位资深网文策划。根据作者的构思，拟定作品的题材框架。\n"
        "只输出一个 JSON 对象，不要输出任何其他文字，格式为：\n"
        '{"title_suggestions": ["候选书名1", "候选书名2", "候选书名3"], '
        '"genre": "题材类型", "selling_point": "核心卖点", '
        '"main_line": "主线一句话", "audience": "目标读者"}'),
    "world": (
        "你是一位世界观架构师。根据已确定的题材框架，设计世界观设定条目。\n"
        "只输出一个 JSON 对象，不要输出任何其他文字，格式为：\n"
        '{"entities": [{"category": "place|faction|term|item", "name": "名称", '
        '"content": "一段设定描述", "tags": "逗号分隔标签"}]}\n'
        "产出 4-8 条，以地点/势力/术语为主，宁缺毋滥。"),
    "characters": (
        "你是一位人物设定师。根据已确定的题材框架与世界观，设计主要角色卡。\n"
        "只输出一个 JSON 对象，不要输出任何其他文字，格式为：\n"
        '{"entities": [{"category": "character", "name": "姓名", '
        '"content": "身份/性格/背景/目标 的完整描述", "tags": "逗号分隔标签"}]}\n'
        "产出 3-6 名主要角色，content 中必须涵盖身份、性格、背景、目标四个方面。"),
    "outline": (
        "你是一位大纲架构师。根据已确定的题材框架、世界观与角色，拟定卷章大纲。\n"
        "只输出一个 JSON 对象，不要输出任何其他文字，格式为：\n"
        '{"outline": [{"title": "节点标题", "synopsis": "梗概", '
        '"parent": "父节点标题或null"}]}\n'
        "规则：卷/部为顶层节点（parent 为 null），章节为对应卷的子节点；"
        "章节标题建议形如「第X章 ……」。"),
}


class BrewIn(BaseModel):
    step: str
    instruction: str = ""
    context: str = ""


@router.post("/brew")
async def brew(body: BrewIn):
    if body.step not in BREW_PROMPTS:
        raise HTTPException(400, "step 仅支持 framework/world/characters/outline")
    user = ""
    if body.context.strip():
        user += "【已确认的前序内容】\n" + body.context.strip() + "\n\n"
    if body.instruction.strip():
        user += "【作者指令】\n" + body.instruction.strip()
    if not user:
        user = "作者暂无具体指令，请自由发挥，给出合理方案。"
    raw = await _chat(BREW_PROMPTS[body.step], user)
    data = _parse_json_obj(raw)
    if data is None:
        raise HTTPException(422, "AI 返回内容无法解析为结构化数据，原文片段："
                            + raw.strip()[:500])

    if body.step == "framework":
        result = {
            "title_suggestions": [str(t)[:80] for t in
                                  (data.get("title_suggestions") or [])
                                  if str(t).strip()][:5],
            "genre": str(data.get("genre") or "").strip(),
            "selling_point": str(data.get("selling_point") or "").strip(),
            "main_line": str(data.get("main_line") or "").strip(),
            "audience": str(data.get("audience") or "").strip(),
        }
    elif body.step == "outline":
        result = {"outline": [o for o in
                              (_normalize_outline(i) for i in data.get("outline") or [])
                              if o]}
    else:  # world / characters
        entities = [e for e in
                    (_normalize_entity(i) for i in data.get("entities") or [])
                    if e]
        if body.step == "characters":
            for e in entities:
                e["category"] = "character"
        result = {"entities": entities}
    return {"step": body.step, "result": result}


# ---------- 4. 成丹入库 ----------

class CompleteIn(BaseModel):
    mode: str
    work_id: int | None = None
    title: str | None = None
    genre: str = ""
    intro: str = ""
    brew: dict = Field(default_factory=dict)


@router.post("/complete", status_code=201)
def complete(body: CompleteIn):
    if body.mode not in ("new", "existing"):
        raise HTTPException(400, "mode 仅支持 new / existing")
    db = get_db()
    brew = body.brew or {}
    framework = brew.get("framework") or {}

    if body.mode == "new":
        title = (body.title or "").strip() or \
            ((framework.get("title_suggestions") or [""])[0]).strip()
        if not title:
            raise HTTPException(400, "新建作品需要填写书名")
        genre = body.genre.strip() or str(framework.get("genre") or "").strip()
        intro = body.intro.strip() or str(framework.get("main_line") or "").strip()
        cur = db.execute(
            "INSERT INTO works(title, intro, genre) VALUES (?,?,?)",
            (title, intro, genre))
        work_id = cur.lastrowid
        db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,1)",
                   (work_id, "卷一"))
    else:
        if not body.work_id:
            raise HTTPException(400, "填充到现有作品需要提供 work_id")
        _work(body.work_id)
        work_id = body.work_id

    entities = []
    for key in ("world", "characters"):
        for item in (brew.get(key) or {}).get("entities") or []:
            e = _normalize_entity(item)
            if e:
                entities.append(e)
    outline = [o for o in
               (_normalize_outline(i)
                for i in (brew.get("outline") or {}).get("outline") or [])
               if o]

    created_e, skipped = _insert_entities(work_id, entities)
    created_o = _insert_outline(work_id, outline)
    db.execute("UPDATE works SET updated_at=datetime('now','localtime') WHERE id=?",
               (work_id,))
    db.commit()
    return {"work_id": work_id,
            "created": {"entities": created_e, "outline": created_o},
            "skipped": skipped}
