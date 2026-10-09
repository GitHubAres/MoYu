import json
from app.services.context_service import assemble_workflow_context
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
from app.services.output_normalizer import (
    extract_assets_block,
    sanitize_asset_item,
    strip_ai_chatter,
)
from app.workflow_assets import extract_structured_assets_from_text

MAX_OUTPUT_CHARS = 32000      # 单步输出入库上限
PREV_HEAD_CHARS = 2000        # 前序输出引用：保留头部
PREV_TAIL_CHARS = 2000        # 前序输出引用：保留尾部

_running_tasks: dict[int, asyncio.Task] = {}

_STEP_REF_RE = re.compile(r"\{\{steps\.(\d+)\.(output|assets|summary)\}\}")


def _format_compact_assets(raw_output: str) -> str:
    """将步骤输出中的结构化资产渲染为紧凑清单，全量不截断。"""
    if not raw_output or not raw_output.strip():
        return "(无结构化资产)"

    block = extract_assets_block(raw_output)
    if block is None:
        data = extract_structured_assets_from_text(raw_output)
    else:
        data = block

    lines = []
    # 实体
    for ent in data.get("entities", []):
        ok, _ = sanitize_asset_item(ent, "entity")
        if not ok:
            continue
        name = ent.get("name", "")
        cat = ent.get("category", "")
        raw_cnt = ent.get("content") or ""
        desc = raw_cnt.strip().split("\n")[0][:40] if raw_cnt else ""
        lines.append(f"· 【实体·{cat}】{name}" + (f"：{desc}" if desc else ""))

    # 关系
    for rel in data.get("relations", []):
        ok, _ = sanitize_asset_item(rel, "relation")
        if not ok:
            continue
        fn = rel.get("from_name", "")
        tn = rel.get("to_name", "")
        lbl = rel.get("label", "关联")
        lines.append(f"· 【关系】{fn} -> {tn}（{lbl}）")

    # 时间线
    for tl in data.get("timeline_events", []):
        ok, _ = sanitize_asset_item(tl, "timeline_event")
        if not ok:
            continue
        lbl = tl.get("time_label", "")
        ev = tl.get("event", "")
        lines.append(f"· 【时间线】{lbl} · {ev}")

    # 伏笔
    for fs in data.get("foreshadows", []):
        ok, _ = sanitize_asset_item(fs, "foreshadow")
        if not ok:
            continue
        title = fs.get("title", "")
        raw_cnt = fs.get("content") or ""
        cnt = raw_cnt.strip().split("\n")[0][:40] if raw_cnt else ""
        lines.append(f"· 【伏笔】{title}" + (f"：{cnt}" if cnt else ""))

    # 大纲
    for out in data.get("outline_nodes", []):
        ok, _ = sanitize_asset_item(out, "outline_node")
        if not ok:
            continue
        title = out.get("title", "")
        raw_syn = out.get("synopsis") or ""
        syn = raw_syn.strip().split("\n")[0][:40] if raw_syn else ""
        lines.append(f"· 【大纲】{title}" + (f"：{syn}" if syn else ""))

    if not lines:
        return "(无结构化资产)"
    return "\n".join(lines)


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
        seq = int(m.group(1))
        kind = m.group(2)
        raw = outputs.get(seq, "")
        if kind == "output":
            return _truncate_prev(raw)
        elif kind == "assets":
            return _format_compact_assets(raw)
        elif kind == "summary":
            cleaned = strip_ai_chatter(raw).strip()
            return cleaned[:300]
        return _truncate_prev(raw)

    return _STEP_REF_RE.sub(_sub, template or "")


def _parse_json_list(val) -> list:
    if isinstance(val, list):
        return val
    if not val:
        return []
    try:
        res = json.loads(val)
        return res if isinstance(res, list) else []
    except Exception:
        return []


def _build_step_context(
    db, run, step, outputs: dict[int, str], chapter_text: str, step_titles: dict[int, str] | None = None
) -> str:
    step_dict = dict(step)
    mode = step_dict.get("input_mode") or "chapter"

    # 1. 解析引用的前序步骤列表
    ref_seqs = _parse_json_list(step_dict.get("ref_step_seqs"))
    if not ref_seqs and mode in ("prev_output", "merge"):
        # 兼容旧单字段 prev_step_seq
        ref_seq = step_dict.get("prev_step_seq")
        if ref_seq is None:
            earlier = [s for s in outputs if s < step_dict["seq"]]
            ref_seq = max(earlier) if earlier else None
        if ref_seq is not None:
            ref_seqs = [ref_seq]

    # 2. 解析上下文来源标记 (chapter, triad)
    context_sources = _parse_json_list(step_dict.get("context_sources"))
    if not context_sources:
        if mode in ("chapter", "merge"):
            context_sources = ["chapter", "triad"]
        elif mode == "prev_output":
            context_sources = []
        elif mode == "none":
            context_sources = []

    # 3. 组装多前序步骤输出文本块（按步骤序号升序，且只允许引用当前步之前）
    prev_blocks = []
    valid_seqs = sorted(s for s in set(ref_seqs) if isinstance(s, int) and s < step_dict["seq"])
    for s_seq in valid_seqs:
        raw = outputs.get(s_seq, "")
        if raw:
            t_label = f" ({step_titles[s_seq]})" if step_titles and s_seq in step_titles and step_titles[s_seq] else ""
            header = f"【前序参考：步骤 {s_seq + 1}{t_label}】" + chr(10)
            prev_blocks.append(header + _truncate_prev(raw))

            # 追加前序结构化资产（可信，全量不截断）
            compact_assets = _format_compact_assets(raw)
            if compact_assets and compact_assets != "(无结构化资产)":
                asset_header = f"【前序结构化资产（可信，全量）：步骤 {s_seq + 1}{t_label}】" + chr(10)
                asset_note = "以下是结构化产出（可信，可直接引用）；原始正文片段可能包含套话与标题，仅供文风参考。" + chr(10)
                prev_blocks.append(asset_header + asset_note + compact_assets)

    prev_step_text = (chr(10) + chr(10)).join(prev_blocks)

    return assemble_workflow_context(
        db=db,
        work_id=run["work_id"],
        chapter_id=dict(run).get("chapter_id"),
        outline_node_id=dict(run).get("outline_node_id"),
        chapter_text=chapter_text,
        prev_step_text=prev_step_text,
        input_mode=mode,
        context_sources=context_sources,
    )
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
            step_titles = {s["seq"]: s["title"] for s in steps}
            context = _build_step_context(db, run, step, outputs, chapter_text, step_titles=step_titles)
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

                # B-3: 仅当该步骤 instruction 或技能手册涉及产出资产时追加输出契约要求
                asset_kws = ["实体", "人物", "角色", "设定", "世界观", "时间线", "伏笔", "暗线", "大纲", "关系", "分卷", "细纲", "立项", "势力", "道具", "场景"]
                target_check = (instruction or "") + " " + (sys_prompt or "")
                if any(k in target_check for k in asset_kws):
                    contract_clause = (
                        "【输出契约】若本步骤产出可入库资产（实体/关系/时间线事件/伏笔/大纲节点），"
                        "必须在回答末尾追加如下契约块，正文里写什么都可以，但契约块必须存在且为合法 JSON：\n"
                        "<!-- MOYU:ASSETS\n"
                        "{\n"
                        '  "entities": [],\n'
                        '  "relations": [],\n'
                        '  "timeline_events": [],\n'
                        '  "foreshadows": [],\n'
                        '  "outline_nodes": []\n'
                        "}\n"
                        "MOYU:ASSETS -->\n"
                        "没有对应资产的种类填空数组，不要省略键。"
                    )
                    parts.append(contract_clause)
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
