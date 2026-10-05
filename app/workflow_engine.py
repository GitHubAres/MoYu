# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""写作工作流运行器：纯编排薄引擎。

只做三件事：准备上下文 → 调现有 AI 链路（build_skill_system_prompt + ai_client.chat）→
记录结果并决定是否暂停（人工确认闸）。AI 调用本身零新增代码路径。
所有输出只落 workflow_run_steps.output，任何路径不直接写正文。
"""
import asyncio
import re
import time

from app.ai_client import chat, get_ai_config, get_ai_timeout
from app.ai_tasks import create_task, fail_task, finish_task, start_task
from app.db import get_db
from app.features import build_skill_system_prompt

MAX_OUTPUT_CHARS = 32000      # 单步输出入库上限
PREV_HEAD_CHARS = 2000        # 前序输出引用：保留头部
PREV_TAIL_CHARS = 2000        # 前序输出引用：保留尾部

_running_tasks: dict[int, asyncio.Task] = {}

_STEP_REF_RE = re.compile(r"\{\{steps\.(\d+)\.output\}\}")


def _truncate_prev(text: str) -> str:
    """长链路上下文膨胀对策：前序输出只保留头尾，中段标记截断。"""
    if len(text) <= PREV_HEAD_CHARS + PREV_TAIL_CHARS + 100:
        return text
    return text[:PREV_HEAD_CHARS] + "\n……[中段内容已截断]……\n" + text[-PREV_TAIL_CHARS:]


def _approved_outputs(db, run_id: int) -> dict[int, str]:
    rows = db.execute(
        "SELECT step_seq, output FROM workflow_run_steps WHERE run_id = ? AND status = 'approved'",
        (run_id,),
    ).fetchall()
    return {r["step_seq"]: r["output"] or "" for r in rows}


def _chapter_content(db, chapter_id: int | None) -> str:
    if not chapter_id:
        return ""
    row = db.execute("SELECT content FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    return (row["content"] or "") if row else ""


def _render_instruction(template: str, outputs: dict[int, str]) -> str:
    def _sub(m):
        return _truncate_prev(outputs.get(int(m.group(1)), ""))

    return _STEP_REF_RE.sub(_sub, template or "")


def _build_step_context(step, outputs: dict[int, str], chapter_text: str) -> str:
    mode = step["input_mode"] or "chapter"
    parts = []
    if mode in ("chapter", "merge") and chapter_text:
        parts.append("【本章正文】\n" + chapter_text)
    if mode in ("prev_output", "merge"):
        ref_seq = step["prev_step_seq"]
        if ref_seq is None:
            earlier = [s for s in outputs if s < step["seq"]]
            ref_seq = max(earlier) if earlier else None
        prev = outputs.get(ref_seq, "") if ref_seq is not None else ""
        if prev:
            parts.append(f"【前序步骤输出（第 {ref_seq} 步）】\n" + _truncate_prev(prev))
    return "\n\n".join(parts)


def _set_run(db, run_id: int, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE workflow_runs SET {cols} WHERE id = ?", (*fields.values(), run_id))
    db.commit()


def _set_run_step(db, run_id: int, seq: int, **fields):
    fields["updated_at"] = "__now__"
    cols = ", ".join(
        "updated_at = datetime('now','localtime')" if k == "updated_at" else f"{k} = ?"
        for k in fields
    )
    vals = [v for v in fields.values() if v != "__now__"]
    db.execute(
        f"UPDATE workflow_run_steps SET {cols} WHERE run_id = ? AND step_seq = ?",
        (*vals, run_id, seq),
    )
    db.commit()


async def _execute(run_id: int):
    db = get_db()
    try:
        run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        if not run or run["status"] in ("done", "cancelled"):
            return
        steps = db.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND enabled = 1 ORDER BY seq",
            (run["workflow_id"],),
        ).fetchall()
        chapter_text = _chapter_content(db, run["chapter_id"])

        for step in steps:
            seq = step["seq"]
            rs = db.execute(
                "SELECT * FROM workflow_run_steps WHERE run_id = ? AND step_seq = ?",
                (run_id, seq),
            ).fetchone()
            if rs is None or rs["status"] in ("approved", "skipped"):
                continue

            # 步骤边界检查取消信号
            cur = db.execute("SELECT status FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
            if cur["status"] == "cancelled":
                return

            _set_run(db, run_id, status="running", current_step=seq,
                     started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
            _set_run_step(db, run_id, seq, status="running")

            outputs = _approved_outputs(db, run_id)
            context = _build_step_context(step, outputs, chapter_text)
            instruction = _render_instruction(step["instruction"], outputs)

            task_id = create_task(run["work_id"], "workflow_step",
                                  f"工作流步骤 · {step['title']}")
            _set_run_step(db, run_id, seq, ai_task_id=task_id)
            start_task(task_id)
            t0 = time.time()
            try:
                sys_prompt, consumed = build_skill_system_prompt(
                    skill_id=step["skill_id"],
                    task="continue",
                    context=context,
                    selection="",
                    instruction=instruction,
                    length=step["length"] or "medium",
                )
                cfg = get_ai_config()
                if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
                    raise RuntimeError("未配置 AI 接口，请先到系统设置页配置")
                parts = []
                if context and not consumed.get("context"):
                    parts.append("【上下文】\n" + context)
                if instruction and not consumed.get("instruction"):
                    parts.append("【写作要求】\n" + instruction)
                # 写作工作流多为长篇小说草稿生成、长章精修或世界观设定等任务，
                # 需充分的等待窗口，默认放宽至 600 秒（10分钟），或取用户设置中更大的配置
                wf_timeout = max(get_ai_timeout(cfg, fallback=600.0), 300.0)
                step_cfg = dict(cfg)
                step_cfg["ai_timeout"] = wf_timeout
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": "\n\n".join(parts) or "请开始。"},
                ]
                text, tokens = await chat(messages, step_cfg)
                elapsed = int((time.time() - t0) * 1000)
                tokens = tokens if isinstance(tokens, int) else 0
                finish_task(task_id, {"text": text[:MAX_OUTPUT_CHARS]},
                            token_used=tokens, elapsed_ms=elapsed)
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                fail_task(task_id, str(e), elapsed)
                _set_run_step(db, run_id, seq, status="failed", elapsed_ms=elapsed)
                _set_run(db, run_id, status="failed", error_msg=f"第 {seq + 1} 步「{step['title']}」失败：{e}")
                return

            _set_run_step(db, run_id, seq, output=(text or "")[:MAX_OUTPUT_CHARS],
                          token_used=tokens, elapsed_ms=elapsed)

            if step["requires_review"]:
                # 人工确认闸：挂起运行，等待 review 接口唤醒
                _set_run_step(db, run_id, seq, status="awaiting_review")
                _set_run(db, run_id, status="awaiting_review")
                return

            _set_run_step(db, run_id, seq, status="approved")
            total = db.execute(
                "SELECT COALESCE(SUM(token_used), 0) FROM workflow_run_steps WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            _set_run(db, run_id, token_used=total)

        total = db.execute(
            "SELECT COALESCE(SUM(token_used), 0) FROM workflow_run_steps WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        _set_run(db, run_id, status="done", token_used=total,
                 finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:  # 引擎自身异常兜底，绝不让运行状态悬空
        _set_run(db, run_id, status="failed", error_msg=f"运行器异常：{e}")
    finally:
        _running_tasks.pop(run_id, None)


def start_run(run_id: int) -> asyncio.Task:
    """启动（或恢复）运行；同一 run 不重复启动。"""
    existing = _running_tasks.get(run_id)
    if existing and not existing.done():
        return existing
    task = asyncio.create_task(_execute(run_id))
    _running_tasks[run_id] = task
    return task


def resume_run(run_id: int) -> asyncio.Task:
    return start_run(run_id)


def cancel_run(run_id: int) -> None:
    """取消即置 cancelled，后台任务在下个步骤边界退出。"""
    db = get_db()
    _set_run(db, run_id, status="cancelled",
             finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
