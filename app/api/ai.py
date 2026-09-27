"""AI 助手 API：生成（流式 / 非流式）与连接测试。"""
import asyncio
import json

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..ai_client import AIError, chat, chat_stream, get_ai_config
from ..db import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

# 内置任务提示词模板
TASK_PROMPTS = {
    "continue": "你是一位资深中文小说续写助手。请严格承接给定上下文的剧情、人物与文风，自然地续写后续内容。只输出正文，不要任何解释。",
    "expand": "你是一位资深中文小说扩写助手。请在保留原意的前提下，对给定文本做细节扩充：补充环境、动作、心理与感官描写。只输出扩写后的正文。",
    "condense": "你是一位资深中文小说缩写助手。请压缩给定文本，保留关键情节与信息，删去冗余描写。只输出缩写后的正文。",
    "polish": "你是一位资深中文小说润色助手。请改写润色给定文本：修正语病、优化句式与用词、增强画面感，不改变情节走向。只输出润色后的正文。",
    "outline": "你是一位资深小说大纲策划。请根据上下文与要求生成结构清晰的分章大纲（每章一行：章节名 + 一句话梗概）。",
    "check": "你是一位严谨的小说设定核查员。请检查给定正文与设定之间是否存在矛盾，逐条列出问题并附原文引用；若无问题，请明确说明「未发现矛盾」。",
}

LENGTH_HINTS = {
    "short": "篇幅控制在 100~200 字。",
    "medium": "篇幅控制在 300~500 字。",
    "long": "篇幅 800 字以上。",
}


class GenIn(BaseModel):
    task: str
    instruction: str = ""
    context: str = ""
    selection: str = ""
    length: str = "medium"
    candidates: int = 1
    stream: bool = False
    work_id: int | None = None  # 带上时可注入文风档案、兜底取最近章节作上下文


def _resolve_config(task: str | None) -> dict:
    """按任务读取 route_{task}_* 覆盖配置，非空字段覆盖主配置。"""
    cfg = get_ai_config()
    if task and task in TASK_PROMPTS:
        rows = get_db().execute(
            "SELECT key, value FROM app_settings WHERE key LIKE 'route_%'").fetchall()
        ov = {r["key"]: (r["value"] or "").strip() for r in rows}
        for field, suffix in (("ai_base_url", "base_url"),
                              ("ai_api_key", "api_key"),
                              ("ai_model", "model")):
            v = ov.get(f"route_{task}_{suffix}")
            if v:
                cfg[field] = v
    return cfg


def _check_config(cfg: dict) -> dict:
    if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
        raise HTTPException(400, "未配置 AI 接口，请先到系统设置页配置")
    return cfg


def _work_style(work_id: int) -> str:
    row = get_db().execute("SELECT style_profile FROM works WHERE id=?",
                           (work_id,)).fetchone()
    return (row["style_profile"] or "").strip() if row else ""


def _latest_context(work_id: int) -> str:
    """兜底上下文：取该作品最近更新的章节正文。"""
    row = get_db().execute(
        "SELECT c.content FROM chapters c JOIN volumes v ON v.id=c.volume_id "
        "WHERE v.work_id=? ORDER BY c.updated_at DESC LIMIT 1",
        (work_id,)).fetchone()
    return (row["content"] or "").strip()[:3000] if row else ""


def _build_messages(body: GenIn, style: str = "") -> list:
    sys_prompt = TASK_PROMPTS.get(body.task, TASK_PROMPTS["continue"])
    sys_prompt += "\n" + LENGTH_HINTS.get(body.length, LENGTH_HINTS["medium"])
    if style:
        sys_prompt = ("【作者文风档案】\n" + style
                      + "\n\n请在生成时严格贴合上述文风。\n\n" + sys_prompt)
    parts = []
    if body.context:
        parts.append("【上下文】\n" + body.context)
    if body.selection:
        parts.append("【选中文本】\n" + body.selection)
    if body.instruction:
        parts.append("【写作要求】\n" + body.instruction)
    return [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n\n".join(parts) or "请开始。"}]


def _estimate(text_len: int) -> int:
    """读不到 usage 时按字符数 / 2 粗估。"""
    return max(1, text_len // 2)


def _add_tokens(n: int):
    if n <= 0:
        return
    db = get_db()
    row = db.execute("SELECT value FROM app_settings WHERE key='token_used'").fetchone()
    cur = int(row["value"]) if row and str(row["value"]).isdigit() else 0
    db.execute(
        "INSERT INTO app_settings(key, value) VALUES('token_used', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(cur + n),))
    db.commit()


@router.post("/generate")
async def generate(body: GenIn):
    task = body.task if body.task in TASK_PROMPTS else "continue"
    cfg = _check_config(_resolve_config(task))
    body.candidates = max(1, min(body.candidates, 3))
    style = _work_style(body.work_id) if body.work_id else ""
    if not body.context and body.work_id:
        body.context = _latest_context(body.work_id)
    messages = _build_messages(body, style)

    if not body.stream:
        # 多候选用并发请求（很多兼容服务不支持 n>1）
        results = await asyncio.gather(
            *(chat(messages, cfg) for _ in range(body.candidates)),
            return_exceptions=True)
        texts, total, err = [], 0, None
        for r in results:
            if isinstance(r, Exception):
                err = r
                continue
            text, usage = r
            texts.append(text)
            total += usage if usage else _estimate(len(text))
        if not texts and err:
            raise HTTPException(502, str(err))
        _add_tokens(total)
        return {"candidates": texts, "usage": {"total_tokens": total}}

    async def event_stream():
        total = 0
        try:
            for i in range(body.candidates):  # 候选顺序流式输出，不并发交错
                yield "data: " + json.dumps({"candidate": i, "start": True}, ensure_ascii=False) + "\n\n"
                usage_box: dict = {}
                text_len = 0
                async for delta in chat_stream(messages, cfg, usage_box):
                    text_len += len(delta)
                    yield "data: " + json.dumps({"candidate": i, "delta": delta}, ensure_ascii=False) + "\n\n"
                total += usage_box.get("total_tokens") or _estimate(text_len)
            _add_tokens(total)
            yield "data: " + json.dumps({"done": True, "usage": {"total_tokens": total}}, ensure_ascii=False) + "\n\n"
        except AIError as e:
            yield "data: " + json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": f"生成失败：{e}"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class TestIn(BaseModel):
    task: str | None = None  # 指定任务时按其路由覆盖配置测试


@router.post("/test")
async def test_connection(body: TestIn | None = None):
    cfg = _resolve_config(body.task if body else None)
    if not cfg.get("ai_base_url") or not cfg.get("ai_api_key"):
        return {"ok": False, "message": "尚未填写 Base URL 或 API Key"}
    try:
        async with httpx.AsyncClient(
                base_url=cfg["ai_base_url"].rstrip("/"),
                headers={"Authorization": f"Bearer {cfg['ai_api_key']}"},
                timeout=15.0) as c:
            resp = await c.get("/models")
        if resp.status_code == 200:
            return {"ok": True, "message": "连接成功，模型列表可用"}
        if resp.status_code == 401:
            return {"ok": False, "message": "API Key 无效（401）"}
        # /models 不可用时退化为极短 chat 验证
        if not cfg.get("ai_model"):
            return {"ok": False, "message": "请填写模型名"}
        await chat([{"role": "user", "content": "hi"}], cfg, max_tokens=1)
        return {"ok": True, "message": "连接成功（chat 验证通过）"}
    except AIError as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"连接失败：{e}"}
