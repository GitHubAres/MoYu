# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""剧情时间线 API：事件 CRUD + AI 从章节提取（先预览、确认后再入库）。"""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai_client import AIError, chat, get_ai_config
from ..db import get_db

router = APIRouter(tags=["timeline"])

AI_NOT_CONFIGURED = "尚未配置 AI 接口，请先到「系统设置」填写 Base URL、API Key 与模型名后再试。"

SYSTEM_PROMPT = (
    "你是一位长篇小说的剧情梳理助手。阅读给定章节正文，提取其中的关键剧情事件，"
    "按故事内时间顺序排列。只输出一个 JSON 数组，不要输出任何其他文字。数组元素的字段为：\n"
    "time_label: 故事内时间标签（如「开宗第三年·春」「决战前夜」），正文无明确时间时给简短推断；\n"
    "event: 事件描述（一两句话，写清谁做了什么、结果如何）；\n"
    "characters: 涉及的主要人物，用顿号分隔，无则空字符串；\n"
    "chapter_title: 该事件所在章节的标题（须与给定标题完全一致）。\n"
    "只提取推动剧情的关键事件，不要罗列细节，每章最多 5 条。若没有可提取的事件，输出空数组 []。"
)


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _event(work_id: int, event_id: int) -> dict:
    return _one(
        """SELECT t.*, c.title AS chapter_title, n.title AS outline_title FROM timeline_events t
           LEFT JOIN chapters c ON c.id = t.chapter_id
           LEFT JOIN outline_nodes n ON n.id = t.outline_node_id
           WHERE t.id=? AND t.work_id=?""", (event_id, work_id))


def _check_chapter(work_id: int, chapter_id: int | None):
    if chapter_id is None:
        return
    row = get_db().execute(
        """SELECT c.id FROM chapters c JOIN volumes v ON v.id=c.volume_id
           WHERE c.id=? AND v.work_id=?""", (chapter_id, work_id)).fetchone()
    if row is None:
        raise HTTPException(400, "所选章节不存在或不属于该作品")


def _check_outline_node(work_id: int, outline_node_id: int | None):
    if outline_node_id is None:
        return
    row = get_db().execute(
        """SELECT id FROM outline_nodes WHERE id=? AND work_id=?""",
        (outline_node_id, work_id)).fetchone()
    if row is None:
        raise HTTPException(400, "所选大纲节点不存在或不属于该作品")


# ---------- CRUD ----------

@router.get("/works/{work_id}/timeline")
def list_events(work_id: int):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    return _all(
        """SELECT t.*, c.title AS chapter_title, n.title AS outline_title FROM timeline_events t
           LEFT JOIN chapters c ON c.id = t.chapter_id
           LEFT JOIN outline_nodes n ON n.id = t.outline_node_id
           WHERE t.work_id=? ORDER BY t.sort_order, t.id""", (work_id,))


class EventIn(BaseModel):
    time_label: str = ""
    event: str
    characters: str = ""
    chapter_id: int | None = None
    outline_node_id: int | None = None


@router.post("/works/{work_id}/timeline", status_code=201)
def create_event(work_id: int, body: EventIn):
    _one("SELECT id FROM works WHERE id=?", (work_id,))
    if not body.event.strip():
        raise HTTPException(400, "事件内容不能为空")
    db = get_db()
    from app.services.asset_hub import upsert_timeline_event
    try:
        return upsert_timeline_event(
            db,
            work_id=work_id,
            event=body.event,
            time_label=body.time_label,
            characters=body.characters,
            chapter_id=body.chapter_id,
            outline_node_id=body.outline_node_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


class EventPatch(BaseModel):
    time_label: str | None = None
    event: str | None = None
    characters: str | None = None
    chapter_id: int | None = None
    outline_node_id: int | None = None
    sort_order: int | None = None


@router.patch("/timeline/{event_id}")
def update_event(event_id: int, body: EventPatch):
    old = _one("SELECT * FROM timeline_events WHERE id=?", (event_id,))
    db = get_db()
    data = body.model_dump(exclude_unset=True)
    if "chapter_id" in data:
        _check_chapter(old["work_id"], data["chapter_id"])
    if "outline_node_id" in data:
        _check_outline_node(old["work_id"], data["outline_node_id"])
    if data.get("event") is not None and not data["event"].strip():
        raise HTTPException(400, "事件内容不能为空")
    for k in ("time_label", "event", "characters", "chapter_id", "outline_node_id", "sort_order"):
        if k in data:
            v = data[k]
            db.execute(f"UPDATE timeline_events SET {k}=? WHERE id=?",
                       (v.strip() if isinstance(v, str) else v, event_id))
    db.commit()
    return _event(old["work_id"], event_id)


@router.delete("/timeline/{event_id}", status_code=204)
def delete_event(event_id: int):
    _one("SELECT id FROM timeline_events WHERE id=?", (event_id,))
    db = get_db()
    db.execute("DELETE FROM timeline_events WHERE id=?", (event_id,))
    db.commit()


# ---------- AI 提取 ----------

class ExtractIn(BaseModel):
    work_id: int
    chapter_ids: list[int]


def _normalize(item: dict) -> dict:
    return {"time_label": str(item.get("time_label", "") or ""),
            "event": str(item.get("event", "") or ""),
            "characters": str(item.get("characters", "") or ""),
            "chapter_title": str(item.get("chapter_title", "") or "")}


def _parse_events(raw: str) -> list[dict]:
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            if isinstance(data, list):
                return [_normalize(i) for i in data
                        if isinstance(i, dict) and str(i.get("event", "") or "").strip()]
        except json.JSONDecodeError:
            pass
    return [{"time_label": "", "characters": "", "chapter_title": "",
             "event": "AI 返回内容无法解析为结构化事件，原始输出如下：\n" + raw.strip()[:2000]}]


@router.post("/timeline/extract")
async def extract_events(body: ExtractIn):
    if not body.chapter_ids:
        raise HTTPException(400, "请先选择至少一章作为提取范围")
    db = get_db()
    _one("SELECT id FROM works WHERE id=?", (body.work_id,))

    chapters = []
    for cid in body.chapter_ids:
        ch = db.execute(
            """SELECT c.id, c.title, c.content FROM chapters c
               JOIN volumes v ON v.id=c.volume_id WHERE c.id=? AND v.work_id=?""",
            (cid, body.work_id)).fetchone()
        if ch:
            chapters.append(ch)
    if not chapters:
        raise HTTPException(400, "所选章节不存在或不属于该作品")

    cfg = get_ai_config()
    if not (cfg.get("ai_base_url") and cfg.get("ai_api_key") and cfg.get("ai_model")):
        raise HTTPException(400, AI_NOT_CONFIGURED)

    context = "\n\n".join(
        f"### 章节《{ch['title']}》\n{(ch['content'] or '').strip()[:3000]}" for ch in chapters)
    try:
        raw, total_tokens = await chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": context}], cfg)
    except AIError as e:
        raise HTTPException(502, str(e))

    title_to_id = {ch["title"]: ch["id"] for ch in chapters}
    events = []
    for ev in _parse_events(raw):
        ev["chapter_id"] = title_to_id.get(ev.pop("chapter_title"))
        events.append(ev)
    usage = {"total_tokens": total_tokens} if total_tokens else {}
    return {"events": events, "usage": usage}


class ImportIn(BaseModel):
    work_id: int
    events: list[EventIn]


@router.post("/timeline/import", status_code=201)
def import_events(body: ImportIn):
    _one("SELECT id FROM works WHERE id=?", (body.work_id,))
    events = [e for e in body.events if e.event.strip()]
    if not events:
        raise HTTPException(400, "没有可入库的事件")
    db = get_db()
    from app.services.asset_hub import upsert_timeline_event
    created = []
    for e in events:
        try:
            res = upsert_timeline_event(
                db,
                work_id=body.work_id,
                event=e.event,
                time_label=e.time_label,
                characters=e.characters,
                chapter_id=e.chapter_id,
                outline_node_id=e.outline_node_id,
            )
            created.append(res)
        except ValueError as err:
            raise HTTPException(400, str(err))
    return created
