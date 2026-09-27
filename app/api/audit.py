"""设定一致性检查 API：纯建议，不修改任何正文/设定。"""
import json

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/audit", tags=["audit"])

AI_NOT_CONFIGURED = "尚未配置 AI 接口，请先到「系统设置」填写 Base URL、API Key 与模型名后再试。"

SYSTEM_PROMPT = (
    "你是一位长篇小说的设定一致性审校助手。对照给定的作品设定库，检查章节正文中是否存在"
    "设定矛盾、前后遗忘、时间线错位等问题。"
    "只输出一个 JSON 数组，不要输出任何其他文字。数组元素的字段为：\n"
    "type: 「矛盾」「遗忘」「时间线」「其他」之一；\n"
    "severity: 「high」「medium」「low」之一；\n"
    "entity: 相关设定名称（无明确对应设定时填空字符串）；\n"
    "issue: 问题描述（一两句话）；\n"
    "quote: 正文中的原文引用（须原文照录，找不到确切原文时填空字符串）；\n"
    "chapter_title: 问题所在章节标题。\n"
    "若没有发现问题，输出空数组 []。只报告有把握的问题，不要臆测。"
)


def _settings() -> dict:
    rows = get_db().execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _build_context(work_id: int, chapter_ids: list[int]) -> tuple[str, int]:
    db = get_db()
    entities = db.execute(
        "SELECT category, name, content, tags FROM entities "
        "WHERE work_id=? AND archived=0 ORDER BY category, id", (work_id,)).fetchall()
    cat_names = {"character": "角色", "location": "地点", "faction": "势力",
                 "item": "物品", "term": "术语", "custom": "自定义"}
    ent_lines = [f"- 【{cat_names.get(e['category'], e['category'])}】{e['name']}"
                 + (f"（标签：{e['tags']}）" if e["tags"] else "")
                 + f"：{(e['content'] or '').strip()[:400]}"
                 for e in entities]

    chapters = []
    for cid in chapter_ids:
        ch = db.execute(
            "SELECT c.id, c.title, c.content FROM chapters c "
            "JOIN volumes v ON v.id=c.volume_id WHERE c.id=? AND v.work_id=?",
            (cid, work_id)).fetchone()
        if ch:
            chapters.append(ch)
    if not chapters:
        raise HTTPException(400, "所选章节不存在或不属于该作品")
    ch_texts = [f"### 章节《{ch['title']}》\n{(ch['content'] or '').strip()[:6000]}"
                for ch in chapters]

    context = (
        "【作品设定库】\n" + ("\n".join(ent_lines) if ent_lines else "（暂无设定条目）")
        + "\n\n【待检查章节正文】\n" + "\n\n".join(ch_texts)
    )
    return context, len(chapters)


def _parse_issues(raw: str) -> list[dict]:
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            if isinstance(data, list):
                # 过滤无实质内容的条目（模型有时为每章返回空壳对象而非空数组）
                return [n for n in (_normalize(i) for i in data if isinstance(i, dict))
                        if n["issue"].strip()]
        except json.JSONDecodeError:
            pass
    return [{"type": "其他", "severity": "low", "entity": "",
             "issue": "AI 返回内容无法解析为结构化问题，原始输出如下：\n" + raw.strip()[:2000],
             "quote": "", "chapter_title": ""}]


def _normalize(item: dict) -> dict:
    sev = item.get("severity", "low")
    if sev not in ("high", "medium", "low"):
        sev = "low"
    typ = item.get("type", "其他")
    if typ not in ("矛盾", "遗忘", "时间线", "其他"):
        typ = "其他"
    return {"type": typ, "severity": sev,
            "entity": str(item.get("entity", "") or ""),
            "issue": str(item.get("issue", "") or ""),
            "quote": str(item.get("quote", "") or ""),
            "chapter_title": str(item.get("chapter_title", "") or "")}


class AuditIn(BaseModel):
    work_id: int
    chapter_ids: list[int]


@router.post("/run")
async def run_audit(body: AuditIn):
    if not body.chapter_ids:
        raise HTTPException(400, "请先选择至少一章作为检查范围")
    db = get_db()
    if not db.execute("SELECT id FROM works WHERE id=?", (body.work_id,)).fetchone():
        raise HTTPException(404, "资源不存在")

    s = _settings()
    base_url = (s.get("ai_base_url") or "").rstrip("/")
    api_key = s.get("ai_api_key") or ""
    model = s.get("ai_model") or ""
    if not (base_url and api_key and model):
        raise HTTPException(400, AI_NOT_CONFIGURED)

    context, checked = _build_context(body.work_id, body.chapter_ids)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "stream": False,
                      "messages": [
                          {"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": context}]})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"AI 接口连接失败：{e}")
    if resp.status_code != 200:
        raise HTTPException(502, f"AI 接口返回错误（{resp.status_code}）：{resp.text[:200]}")

    data = resp.json()
    try:
        raw = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, "AI 接口返回格式异常")
    usage = data.get("usage") or {}

    return {"issues": _parse_issues(raw), "checked_chapters": checked, "usage": usage}
