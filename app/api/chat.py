# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""AI 修撰使多轮对话路由：会话管理、多轮历史装配、SSE 流式交互与采纳状态维护。"""
import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai_client import AIError, chat, chat_stream
from app.ai_tasks import create_task, fail_task, finish_task, start_task
from app.db import get_db
from app.features import AIOrchestrator, build_skill_system_prompt, get_ai_config, resolve_skill

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    chapter_id: int
    message: str = ""
    task: str = "continue"
    selection: str = ""
    skill_id: Optional[int] = None
    context: str = ""
    length: str = "medium"
    stream: bool = True


class NewSessionIn(BaseModel):
    chapter_id: int


class MessageAdoptIn(BaseModel):
    adopted: int = 1


@router.get("")
def get_chat_history(chapter_id: int):
    """获取指定章节当前激活的对话会话及全量消息列表。"""
    db = get_db()
    chap = db.execute("SELECT c.id, v.work_id FROM chapters c JOIN volumes v ON c.volume_id = v.id WHERE c.id = ?", (chapter_id,)).fetchone()
    if not chap:
        raise HTTPException(404, "章节不存在")

    session = db.execute(
        "SELECT * FROM chat_sessions WHERE chapter_id=? ORDER BY id DESC LIMIT 1",
        (chapter_id,),
    ).fetchone()

    if not session:
        return {"session": None, "messages": []}

    messages = db.execute(
        """SELECT id, session_id, role, content, task_type, meta_json, adopted, created_at
           FROM chat_messages
           WHERE session_id=?
           ORDER BY id ASC""",
        (session["id"],),
    ).fetchall()

    return {
        "session": dict(session),
        "messages": [dict(m) for m in messages],
    }


@router.post("/session/new")
def create_new_session(body: NewSessionIn):
    """为指定章节显式新建对话会话（重置当前轮次）。"""
    db = get_db()
    chap = db.execute("SELECT c.id, v.work_id FROM chapters c JOIN volumes v ON c.volume_id = v.id WHERE c.id = ?", (body.chapter_id,)).fetchone()
    if not chap:
        raise HTTPException(404, "章节不存在")

    cur = db.execute(
        "INSERT INTO chat_sessions (work_id, chapter_id) VALUES (?, ?)",
        (chap["work_id"], chap["id"]),
    )
    db.commit()
    new_session = db.execute("SELECT * FROM chat_sessions WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"session": dict(new_session), "messages": []}


@router.patch("/messages/{message_id}")
def update_message_adoption(message_id: int, body: MessageAdoptIn):
    """更新 AI 回复消息的采纳状态（1: 已采纳, 0: 撤销采纳）。"""
    db = get_db()
    msg = db.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
    if not msg:
        raise HTTPException(404, "消息不存在")

    db.execute("UPDATE chat_messages SET adopted=? WHERE id=?", (1 if body.adopted else 0, message_id))
    db.commit()

    updated = db.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
    return dict(updated)


@router.post("")
async def send_chat_message(body: ChatIn):
    """发送对话消息，组装多轮上下文并返回流式或非流式生成结果。"""
    db = get_db()
    chap = db.execute("SELECT c.id, v.work_id FROM chapters c JOIN volumes v ON c.volume_id = v.id WHERE c.id = ?", (body.chapter_id,)).fetchone()
    if not chap:
        raise HTTPException(404, "章节不存在")
    work_id = chap["work_id"]

    cfg = get_ai_config()
    if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
        raise HTTPException(400, "未配置 AI 接口，请先到系统设置页配置")

    # 获取或自动创建当前章节的 session
    session = db.execute(
        "SELECT * FROM chat_sessions WHERE chapter_id=? ORDER BY id DESC LIMIT 1",
        (body.chapter_id,),
    ).fetchone()

    if not session:
        cur = db.execute(
            "INSERT INTO chat_sessions (work_id, chapter_id) VALUES (?, ?)",
            (work_id, body.chapter_id),
        )
        db.commit()
        session = db.execute("SELECT * FROM chat_sessions WHERE id=?", (cur.lastrowid,)).fetchone()
    session_id = session["id"]

    # 记录用户本轮输入消息
    user_prompt_text = body.message.strip()
    task_desc = {
        "continue": "续写后续正文",
        "expand": "扩写选区细节",
        "condense": "缩写凝练文本",
        "polish": "改写润色正文",
        "outline": "大纲构思推演",
        "check": "一致性检查",
        "analyze": "分析评价作品",
    }.get(body.task, "创作")
    display_content = user_prompt_text or f"请对选区或当前章节进行{task_desc}"

    user_meta = json.dumps(
        {
            "task": body.task,
            "selection": body.selection,
            "skill_id": body.skill_id,
            "length": body.length,
        },
        ensure_ascii=False,
    )

    cur_user = db.execute(
        """INSERT INTO chat_messages (session_id, role, content, task_type, meta_json, adopted)
           VALUES (?, 'user', ?, ?, ?, 0)""",
        (session_id, display_content, body.task, user_meta),
    )
    user_msg_id = cur_user.lastrowid
    db.execute("UPDATE chat_sessions SET updated_at=datetime('now','localtime') WHERE id=?", (session_id,))
    db.commit()

    # 读取该 session 的历史记录（除刚插入的本条 user 消息外作为多轮前情）
    history_rows = db.execute(
        """SELECT role, content FROM chat_messages
           WHERE session_id=? AND id < ?
           ORDER BY id ASC""",
        (session_id, user_msg_id),
    ).fetchall()

    # 组装 System Prompt 与长度要求
    task = body.task if body.task in AIOrchestrator.BASIC_PROMPTS else "continue"
    # 对话场景下，指令由当前 user 消息轮次承载
    sys_prompt, consumed = build_skill_system_prompt(
        skill_id=body.skill_id,
        task=task,
        context=body.context,
        selection=body.selection,
        instruction="",
        length=body.length,
    )

    # 收集「修撰使思考过程」步骤信息（Agent 风格任务追踪）
    ctx_count = len([x for x in body.context.split("\n\n----\n\n") if x.strip()]) if body.context.strip() else 0
    sel_len = len(body.selection.strip())
    len_label = {"short": "简", "medium": "中", "long": "长"}.get(body.length, f"{body.length}字" if str(body.length).isdigit() else "中")
    parse_detail = f"{task_desc} · 篇幅{len_label}"
    if sel_len:
        parse_detail += f" · 选区 {sel_len} 字"
    parse_detail += f" · 挂载上下文 {ctx_count} 项"

    steps = [{"id": "parse", "title": "解析创作任务", "detail": parse_detail, "status": "done"}]

    skill_row = resolve_skill(body.skill_id, task)
    if skill_row:
        source_label = {"builtin": "内置", "custom": "自定义", "migrated": "迁移", "imported": "导入"}.get(skill_row["source"], skill_row["source"])
        steps.append({
            "id": "skill",
            "title": "匹配写作技能",
            "detail": f"{skill_row['title']}（{skill_row['name']}@{skill_row['version']} · {source_label}）",
            "status": "done",
        })
        ref_rows = db.execute(
            "SELECT path FROM skill_files WHERE skill_id = ? AND path LIKE 'references/%' ORDER BY path ASC",
            (skill_row["id"],),
        ).fetchall()
        if ref_rows:
            names = [r["path"].split("/")[-1] for r in ref_rows]
            shown = "、".join(names[:3]) + (" 等" if len(names) > 3 else "")
            steps.append({
                "id": "refs",
                "title": "装载方法论参考",
                "detail": f"{shown}（共 {len(names)} 份）",
                "status": "done",
            })
    else:
        steps.append({"id": "skill", "title": "匹配写作技能", "detail": "内置基础写作提示词", "status": "done"})

    steps.append({"id": "prompt", "title": "装配系统提示词", "detail": f"约 {len(sys_prompt)} 字", "status": "done"})
    steps.append({"id": "model", "title": f"连接模型 {cfg.get('ai_model', '')}", "detail": "流式通道就绪", "status": "done"})

    # 组装完整的 messages 数组
    messages = [{"role": "system", "content": sys_prompt}]
    for r in history_rows:
        role_mapped = "assistant" if r["role"] in ("ai", "assistant") else "user"
        messages.append({"role": role_mapped, "content": r["content"]})

    # 本轮消息的结构化上下文拼装
    current_parts = []
    if body.context and not consumed.get("context"):
        current_parts.append("【上下文】\n" + body.context)
    if body.selection and not consumed.get("selection"):
        current_parts.append("【选中文本】\n" + body.selection)
    if user_prompt_text:
        current_parts.append("【写作要求】\n" + user_prompt_text)
    elif not current_parts:
        current_parts.append("请顺应前文继续创作。")

    final_user_turn = "\n\n".join(current_parts)
    messages.append({"role": "user", "content": final_user_turn})

    # 创建异步追踪任务
    task_id = create_task(work_id, f"chat_{body.task}", f"修撰使多轮对话 [{task}]")
    start_time = time.time()
    start_task(task_id)

    # 非流式模式（供测试或特殊场景调用）
    if not body.stream:
        try:
            reply_text, total_tokens = await chat(messages, cfg)
            elapsed = int((time.time() - start_time) * 1000)
            done_steps = [*steps, {"id": "generate", "title": "生成正文", "detail": f"输出 {len(reply_text)} 字 · 用时 {elapsed / 1000:.1f}s", "status": "done"}]
            meta = json.dumps({"task_id": task_id, "task": body.task, "length": body.length, "steps": done_steps}, ensure_ascii=False)
            cur_ai = db.execute(
                """INSERT INTO chat_messages (session_id, role, content, task_type, meta_json, adopted)
                   VALUES (?, 'ai', ?, ?, ?, 0)""",
                (session_id, reply_text, body.task, meta),
            )
            ai_msg_id = cur_ai.lastrowid
            db.execute("UPDATE chat_sessions SET updated_at=datetime('now','localtime') WHERE id=?", (session_id,))
            db.commit()
            finish_task(task_id, {"message_id": ai_msg_id, "content": reply_text}, token_used=total_tokens or 0, elapsed_ms=elapsed)
            return {
                "session_id": session_id,
                "user_message_id": user_msg_id,
                "message_id": ai_msg_id,
                "content": reply_text,
                "task_id": task_id,
            }
        except Exception as e:
            fail_task(task_id, str(e), int((time.time() - start_time) * 1000))
            raise HTTPException(502, f"AI 对话生成失败: {e}")

    # SSE 流式模式
    async def event_stream():
        full_text = []
        total_tokens = 0
        gen_step = {"id": "generate", "title": "生成正文", "detail": "流式输出中…", "status": "doing"}
        run_steps = [*steps, gen_step]
        try:
            yield "data: " + json.dumps({"session_id": session_id, "task_id": task_id, "user_message_id": user_msg_id}, ensure_ascii=False) + "\n\n"
            for st in steps:
                yield "data: " + json.dumps({"step": st}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"step": gen_step}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"candidate": 0, "start": True}, ensure_ascii=False) + "\n\n"

            async for delta in chat_stream(messages, cfg, {}):
                full_text.append(delta)
                yield "data: " + json.dumps({"candidate": 0, "delta": delta}, ensure_ascii=False) + "\n\n"

            final_reply = "".join(full_text)
            elapsed = int((time.time() - start_time) * 1000)

            gen_step["status"] = "done"
            gen_step["detail"] = f"输出 {len(final_reply)} 字 · 用时 {elapsed / 1000:.1f}s"
            yield "data: " + json.dumps({"step": gen_step}, ensure_ascii=False) + "\n\n"

            # 写库记录 AI 回复（meta 携带思考步骤供历史回放）
            thread_db = get_db()
            meta = json.dumps({"task_id": task_id, "task": body.task, "length": body.length, "steps": run_steps}, ensure_ascii=False)
            cur_ai = thread_db.execute(
                """INSERT INTO chat_messages (session_id, role, content, task_type, meta_json, adopted)
                   VALUES (?, 'ai', ?, ?, ?, 0)""",
                (session_id, final_reply, body.task, meta),
            )
            ai_msg_id = cur_ai.lastrowid
            thread_db.execute("UPDATE chat_sessions SET updated_at=datetime('now','localtime') WHERE id=?", (session_id,))
            thread_db.commit()

            finish_task(task_id, {"message_id": ai_msg_id, "content": final_reply}, token_used=total_tokens, elapsed_ms=elapsed)
            yield "data: " + json.dumps({"done": True, "message_id": ai_msg_id, "task_id": task_id}, ensure_ascii=False) + "\n\n"
        except AIError as e:
            fail_task(task_id, str(e), int((time.time() - start_time) * 1000))
            gen_step["status"] = "error"
            gen_step["detail"] = str(e)
            yield "data: " + json.dumps({"step": gen_step}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"error": str(e), "task_id": task_id}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            fail_task(task_id, f"生成失败：{e}", int((time.time() - start_time) * 1000))
            gen_step["status"] = "error"
            gen_step["detail"] = f"生成失败：{e}"
            yield "data: " + json.dumps({"step": gen_step}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"error": f"生成失败：{e}", "task_id": task_id}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
