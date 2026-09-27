"""文风档案 API：生成 / 查看 / 编辑 / 清空作品的文风学习档案。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai_client import AIError, chat, get_ai_config
from ..db import get_db

router = APIRouter(tags=["style"])

AI_NOT_CONFIGURED = "尚未配置 AI 接口，请先到「系统设置」填写 Base URL、API Key 与模型名后再试。"

SYSTEM_PROMPT = (
    "你是一位中文小说文体分析专家。请通读下面的章节节选，提炼作者的文风档案。\n"
    "输出要求：用中文纯文本输出 5-8 条要点，每条一行、以「·」开头；"
    "内容须涵盖叙事视角、句式偏好、用词特征、节奏特点、对话风格等维度，"
    "可结合具体观察到的写作习惯。不要输出标题、序号说明或任何其他文字。"
)


def _work(work_id: int) -> dict:
    row = get_db().execute("SELECT * FROM works WHERE id=?", (work_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


@router.get("/works/{work_id}/style")
def get_style(work_id: int):
    return {"style_profile": _work(work_id).get("style_profile") or ""}


class StyleGenIn(BaseModel):
    chapter_ids: list[int]


@router.post("/works/{work_id}/style/generate")
async def generate_style(work_id: int, body: StyleGenIn):
    _work(work_id)
    if not 1 <= len(body.chapter_ids) <= 3:
        raise HTTPException(400, "请选择 1~3 章作为分析样本")

    cfg = get_ai_config()
    if not (cfg.get("ai_base_url") and cfg.get("ai_api_key") and cfg.get("ai_model")):
        raise HTTPException(400, AI_NOT_CONFIGURED)

    db = get_db()
    excerpts = []
    for cid in body.chapter_ids:
        ch = db.execute(
            "SELECT c.title, c.content FROM chapters c "
            "JOIN volumes v ON v.id=c.volume_id WHERE c.id=? AND v.work_id=?",
            (cid, work_id)).fetchone()
        if ch is None:
            raise HTTPException(400, "所选章节不存在或不属于该作品")
        text = (ch["content"] or "").strip()
        if text:
            excerpts.append(f"### 章节《{ch['title']}》\n{text[:2500]}")
    if not excerpts:
        raise HTTPException(400, "所选章节均无正文内容，无法分析文风")

    try:
        text, usage = await chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": "【章节节选】\n" + "\n\n".join(excerpts)}],
            cfg)
    except AIError as e:
        raise HTTPException(502, str(e))

    profile = text.strip()
    if not profile:
        raise HTTPException(502, "AI 未返回有效的文风档案内容")
    db.execute("UPDATE works SET style_profile=? WHERE id=?", (profile, work_id))
    db.commit()
    return {"style_profile": profile,
            "usage": {"total_tokens": usage} if usage else {}}


class StyleIn(BaseModel):
    style_profile: str = ""


@router.put("/works/{work_id}/style")
def save_style(work_id: int, body: StyleIn):
    _work(work_id)
    db = get_db()
    db.execute("UPDATE works SET style_profile=? WHERE id=?",
               (body.style_profile.strip(), work_id))
    db.commit()
    return {"style_profile": body.style_profile.strip()}


@router.delete("/works/{work_id}/style")
def clear_style(work_id: int):
    _work(work_id)
    db = get_db()
    db.execute("UPDATE works SET style_profile='' WHERE id=?", (work_id,))
    db.commit()
    return {"style_profile": ""}
