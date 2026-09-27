"""提示词中心 API：内置预设 + 自定义模板 CRUD。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter(prefix="/prompts", tags=["prompts"])

TASK_TYPES = {
    "continue": "续写",
    "expand": "扩写",
    "shorten": "缩写",
    "rewrite": "改写润色",
    "outline": "大纲生成",
    "audit": "设定检查",
}

BUILTIN_PROMPTS = [
    ("续写·顺延文势", "continue",
     "你是一位长篇小说写作助手。请阅读以下上下文，顺着既有文势自然续写，"
     "保持人物的口吻与叙事节奏一致，不要复述已有内容。\n\n"
     "【上下文】\n{{context}}\n\n"
     "【当前选区】\n{{selection}}\n\n"
     "【写作要求】\n{{instruction}}\n\n请直接输出续写的正文，不要输出解释。"),
    ("扩写·充实细节", "expand",
     "你是一位长篇小说写作助手。请将选区内容扩写得更丰满：补充环境、动作、心理与感官细节，"
     "不改变情节走向，保持原有文风。\n\n"
     "【上下文】\n{{context}}\n\n"
     "【待扩写选区】\n{{selection}}\n\n"
     "【写作要求】\n{{instruction}}\n\n请直接输出扩写后的正文，不要输出解释。"),
    ("缩写·凝练取舍", "shorten",
     "你是一位长篇小说写作助手。请将选区内容缩写压缩，保留关键情节信息与最有力的意象，"
     "删去冗余铺陈，语言凝练。\n\n"
     "【上下文】\n{{context}}\n\n"
     "【待缩写选区】\n{{selection}}\n\n"
     "【写作要求】\n{{instruction}}\n\n请直接输出缩写后的正文，不要输出解释。"),
    ("改写润色·字句打磨", "rewrite",
     "你是一位长篇小说写作助手。请对选区文字进行改写润色：修正语病、替换平淡表达、"
     "调整句式节奏，但保留原意与叙事视角。\n\n"
     "【上下文】\n{{context}}\n\n"
     "【待润色选区】\n{{selection}}\n\n"
     "【写作要求】\n{{instruction}}\n\n请直接输出润色后的正文，不要输出解释。"),
    ("大纲生成·纲举目张", "outline",
     "你是一位长篇小说策划助手。请基于已有上下文与设定，生成结构清晰的故事大纲，"
     "按「卷/章」层级列出节点，每个节点给出标题与一句话梗概，注意承接收束已有伏笔。\n\n"
     "【上下文】\n{{context}}\n\n"
     "【相关要求】\n{{instruction}}\n\n请直接输出大纲，不要输出解释。"),
    ("设定检查·脉络稽核", "audit",
     "你是一位长篇小说的设定一致性审校助手。请对照作品设定库，检查所选章节正文中"
     "是否存在与设定矛盾、遗忘前后文、时间线错位等问题。\n\n"
     "【作品设定】\n{{context}}\n\n"
     "【待检查章节】\n{{selection}}\n\n"
     "【检查要求】\n{{instruction}}\n\n"
     "请逐条列出问题：问题类型、严重程度、涉及设定、问题描述、原文引用、所在章节。"),
]


def _seed_builtin():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0] == 0:
        for name, task_type, template in BUILTIN_PROMPTS:
            db.execute(
                "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,1)",
                (name, task_type, template))
        db.commit()


_seed_builtin()


def _one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return dict(row)


def _all(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


@router.get("")
def list_prompts(task_type: str = ""):
    sql = "SELECT * FROM prompts"
    args: list = []
    if task_type:
        sql += " WHERE task_type=?"
        args.append(task_type)
    sql += " ORDER BY builtin DESC, id"
    return _all(sql, args)


class PromptIn(BaseModel):
    name: str
    task_type: str = "continue"
    template: str


@router.post("", status_code=201)
def create_prompt(body: PromptIn):
    if body.task_type not in TASK_TYPES:
        raise HTTPException(400, f"未知任务类型：{body.task_type}")
    db = get_db()
    cur = db.execute(
        "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,0)",
        (body.name, body.task_type, body.template))
    db.commit()
    return _one("SELECT * FROM prompts WHERE id=?", (cur.lastrowid,))


@router.patch("/{prompt_id}")
def update_prompt(prompt_id: int, body: dict):
    _one("SELECT id FROM prompts WHERE id=?", (prompt_id,))
    db = get_db()
    for k in ("name", "task_type", "template"):
        if k in body:
            db.execute(f"UPDATE prompts SET {k}=? WHERE id=?", (body[k], prompt_id))
    db.commit()
    return _one("SELECT * FROM prompts WHERE id=?", (prompt_id,))


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: int):
    row = _one("SELECT * FROM prompts WHERE id=?", (prompt_id,))
    if row["builtin"]:
        raise HTTPException(400, "内置模板不可删除，可复制副本后修改")
    db = get_db()
    db.execute("DELETE FROM prompts WHERE id=?", (prompt_id,))
    db.commit()


@router.post("/{prompt_id}/duplicate", status_code=201)
def duplicate_prompt(prompt_id: int):
    row = _one("SELECT * FROM prompts WHERE id=?", (prompt_id,))
    db = get_db()
    cur = db.execute(
        "INSERT INTO prompts(name, task_type, template, builtin) VALUES (?,?,?,0)",
        (row["name"] + "（副本）", row["task_type"], row["template"]))
    db.commit()
    return _one("SELECT * FROM prompts WHERE id=?", (cur.lastrowid,))
