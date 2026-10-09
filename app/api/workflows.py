import json
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""写作工作流 API：定义 CRUD、步骤编排、运行与人工确认闸。"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import workflow_engine
from app.workflow_assets import (
    SyncAssetsIn,
    extract_structured_assets_from_text,
    sync_assets_to_database,
)
from app.ai_client import get_ai_config
from app.db import get_db

router = APIRouter(prefix="/workflows", tags=["workflows"])

INPUT_MODES = {"chapter", "prev_output", "merge", "none"}
REVIEW_ACTIONS = {"approve", "edit", "skip", "abort"}


class StepIn(BaseModel):
    title: str
    skill_id: Optional[int] = None
    input_mode: str = "chapter"
    prev_step_seq: Optional[int] = None
    ref_step_seqs: list[int] = []
    context_sources: list[str] = ["chapter", "triad"]
    output_var: str = ""
    instruction: str = ""
    length: str = "medium"
    candidates: int = 1
    requires_review: int = 1
    enabled: int = 1
class WorkflowIn(BaseModel):
    name: str
    description: str = ""
    icon: str = "account_tree"
    scope: str = "global"
    steps: list[StepIn] = []


class WorkflowPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    scope: Optional[str] = None
    enabled: Optional[int] = None


class StepsReplaceIn(BaseModel):
    steps: list[StepIn]


class RunStartIn(BaseModel):
    work_id: int
    chapter_id: Optional[int] = None
    outline_node_id: Optional[int] = None


class ReviewIn(BaseModel):
    action: str
    content: Optional[str] = None
    note: str = ""


def _row(r):
    return dict(r)


def _get_workflow(db, wf_id: int):
    row = db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")
    return row


def _validate_steps(db, steps: list[StepIn]):
    for s in steps:
        if not s.title.strip():
            raise HTTPException(400, "步骤展示名不能为空")
        if s.input_mode not in INPUT_MODES:
            raise HTTPException(400, f"非法的输入来源：{s.input_mode}")
        if s.skill_id is not None:
            sk = db.execute("SELECT * FROM skills WHERE id = ?", (s.skill_id,)).fetchone()
            if not sk:
                raise HTTPException(400, f"步骤「{s.title}」绑定的 Skill 不存在")
            if not sk["enabled"]:
                raise HTTPException(400, f"步骤「{s.title}」绑定的 Skill「{sk['title']}」已被禁用")


def _insert_steps(db, wf_id: int, steps: list[StepIn]):
    for seq, s in enumerate(steps):
        # 规范化 ref_step_seqs
        ref_seqs = [int(x) for x in s.ref_step_seqs if isinstance(x, int) and x < seq]
        if not ref_seqs and s.prev_step_seq is not None and s.prev_step_seq < seq and s.input_mode in ("prev_output", "merge"):
            ref_seqs = [s.prev_step_seq]
        # 若未指定具体步骤但模式要求前序输出，默认引用紧邻的上一步 (seq - 1)
        if not ref_seqs and s.input_mode in ("prev_output", "merge") and seq > 0:
            ref_seqs = [seq - 1]

        # 规范化 context_sources
        ctx_sources = [c for c in s.context_sources if c in ("chapter", "triad")]
        if not ctx_sources and not s.ref_step_seqs:
            if s.input_mode in ("chapter", "merge"):
                ctx_sources = ["chapter", "triad"]
            elif s.input_mode in ("prev_output", "none"):
                ctx_sources = []

        # 双向兼容 input_mode 与 prev_step_seq
        prev_seq = ref_seqs[-1] if ref_seqs else (s.prev_step_seq if s.prev_step_seq is not None and s.prev_step_seq < seq else None)
        mode = s.input_mode
        if ref_seqs and ("chapter" in ctx_sources or "triad" in ctx_sources):
            mode = "merge"
        elif ref_seqs:
            mode = "prev_output"
        elif "chapter" in ctx_sources or "triad" in ctx_sources:
            mode = "chapter"
        elif not ref_seqs and not ctx_sources:
            mode = "none"

        db.execute(
            """INSERT INTO workflow_steps(
                   workflow_id, seq, title, skill_id, input_mode, prev_step_seq,
                   ref_step_seqs, context_sources,
                   output_var, instruction, length, candidates, requires_review, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (wf_id, seq, s.title.strip(), s.skill_id, mode, prev_seq,
             json.dumps(ref_seqs), json.dumps(ctx_sources),
             s.output_var or f"step{seq}", s.instruction, s.length,
             max(1, min(s.candidates, 3)), 1 if s.requires_review else 0,
             1 if s.enabled else 0),
        )
def _steps_of(db, wf_id: int) -> list[dict]:
    rows = db.execute(
        """SELECT ws.*, sk.title AS skill_title, sk.name AS skill_name, sk.applies_to AS skill_applies_to
           FROM workflow_steps ws
           LEFT JOIN skills sk ON sk.id = ws.skill_id
           WHERE ws.workflow_id = ? ORDER BY ws.seq""",
        (wf_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = _row(r)
        ref_seqs = []
        if d.get("ref_step_seqs"):
            try:
                ref_seqs = json.loads(d["ref_step_seqs"])
            except Exception:
                ref_seqs = []
        if not ref_seqs and d.get("prev_step_seq") is not None and d.get("input_mode") in ("prev_output", "merge"):
            ref_seqs = [d["prev_step_seq"]]
        d["ref_step_seqs"] = ref_seqs if isinstance(ref_seqs, list) else []

        ctx_src = []
        if d.get("context_sources"):
            try:
                ctx_src = json.loads(d["context_sources"])
            except Exception:
                ctx_src = []
        if not ctx_src:
            mode = d.get("input_mode", "chapter")
            if mode in ("chapter", "merge"):
                ctx_src = ["chapter", "triad"]
            elif mode == "prev_output":
                ctx_src = []
            elif mode == "none":
                ctx_src = []
        d["context_sources"] = ctx_src if isinstance(ctx_src, list) else []
        out.append(d)
    return out


def _run_detail(db, run_id: int) -> dict:
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "运行实例不存在")
    steps = db.execute(
        "SELECT * FROM workflow_run_steps WHERE run_id = ? ORDER BY step_seq", (run_id,)
    ).fetchall()
    total = len(steps)
    done = sum(1 for s in steps if s["status"] in ("approved", "skipped"))
    wf = db.execute("SELECT name, icon FROM workflows WHERE id = ?", (run["workflow_id"],)).fetchone()
    wf_step_defs = {s["seq"]: s for s in _steps_of(db, run["workflow_id"])}

    out = _row(run)
    out_steps = []
    for s in steps:
        d = _row(s)
        s_def = wf_step_defs.get(d["step_seq"])
        if s_def:
            d["ref_step_seqs"] = s_def.get("ref_step_seqs", [])
            d["context_sources"] = s_def.get("context_sources", [])
            d["skill_title"] = s_def.get("skill_title", "")
            d["instruction"] = s_def.get("instruction", "")
        else:
            d["ref_step_seqs"] = []
            d["context_sources"] = []
            d["skill_title"] = ""
            d["instruction"] = ""
        out_steps.append(d)

    out["steps"] = out_steps
    out["total_steps"] = total
    out["finished_steps"] = done
    out["workflow_name"] = wf["name"] if wf else ""
    out["workflow_icon"] = wf["icon"] if wf else "account_tree"
    if dict(run).get("outline_node_id"):
        nd = db.execute("SELECT title FROM outline_nodes WHERE id = ?", (run["outline_node_id"],)).fetchone()
        out["outline_node_title"] = nd["title"] if nd else ""
    else:
        out["outline_node_title"] = ""
    return out


# ---------- 运行实例（字面路由须先于 /{wf_id} 声明） ----------

@router.get("/runs")
def list_runs(workflow_id: Optional[int] = None, limit: int = 50):
    db = get_db()
    sql = """SELECT wr.*, w.name AS workflow_name, w.icon AS workflow_icon
             FROM workflow_runs wr LEFT JOIN workflows w ON w.id = wr.workflow_id"""
    args: list = []
    if workflow_id is not None:
        sql += " WHERE wr.workflow_id = ?"
        args.append(workflow_id)
    sql += " ORDER BY wr.id DESC LIMIT ?"
    args.append(max(1, min(limit, 200)))
    return [_row(r) for r in db.execute(sql, args).fetchall()]


@router.get("/runs/{run_id}")
def get_run(run_id: int):
    return _run_detail(get_db(), run_id)


@router.post("/runs/{run_id}/steps/{seq}/review")
async def review_step(run_id: int, seq: int, body: ReviewIn):
    """人工确认闸：approve 采纳继续 / edit 以修改稿继续 / skip 跳过 / abort 中止。后端强制校验状态。"""
    if body.action not in REVIEW_ACTIONS:
        raise HTTPException(400, f"非法的确认操作：{body.action}")
    db = get_db()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "运行实例不存在")
    if body.action == "abort":
        workflow_engine.cancel_run(run_id)
        return {"ok": True, "status": "cancelled"}
    if run["status"] != "awaiting_review":
        raise HTTPException(400, "当前运行未处于待确认状态")
    rs = db.execute(
        "SELECT * FROM workflow_run_steps WHERE run_id = ? AND step_seq = ?", (run_id, seq)
    ).fetchone()
    if not rs or rs["status"] != "awaiting_review":
        raise HTTPException(400, "该步骤不在待确认状态")

    if body.action == "skip":
        db.execute(
            """UPDATE workflow_run_steps SET status='skipped', review_note=?,
               updated_at=datetime('now','localtime') WHERE run_id=? AND step_seq=?""",
            (body.note, run_id, seq),
        )
    else:
        if body.action == "edit":
            if body.content is None:
                raise HTTPException(400, "edit 操作必须携带修改后的内容 content")
            db.execute(
                """UPDATE workflow_run_steps SET output=?, status='approved', review_note=?,
                   updated_at=datetime('now','localtime') WHERE run_id=? AND step_seq=?""",
                (body.content[:workflow_engine.MAX_OUTPUT_CHARS], body.note, run_id, seq),
            )
        else:
            db.execute(
                """UPDATE workflow_run_steps SET status='approved', review_note=?,
                   updated_at=datetime('now','localtime') WHERE run_id=? AND step_seq=?""",
                (body.note, run_id, seq),
            )
    db.execute("UPDATE workflow_runs SET status='running' WHERE id=?", (run_id,))
    db.commit()
    workflow_engine.resume_run(run_id)
    return {"ok": True, "status": "running"}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int):
    db = get_db()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "运行实例不存在")
    if run["status"] in ("done", "cancelled"):
        return {"ok": True, "status": run["status"]}
    workflow_engine.cancel_run(run_id)
    return {"ok": True, "status": "cancelled"}


@router.post("/runs/{run_id}/retry")
async def retry_run(run_id: int):
    """从失败/中止处重跑：失败步骤及其后续全部重置为 pending。"""
    db = get_db()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "运行实例不存在")
    if run["status"] not in ("failed", "cancelled"):
        raise HTTPException(400, "仅失败或已中止的运行可以重跑")
    failed = db.execute(
        "SELECT MIN(step_seq) FROM workflow_run_steps WHERE run_id = ? AND status IN ('failed','running','awaiting_review')",
        (run_id,),
    ).fetchone()[0]
    if failed is None:
        failed = run["current_step"]
    db.execute(
        """UPDATE workflow_run_steps SET status='pending', output='', review_note='',
           token_used=0, elapsed_ms=0, updated_at=datetime('now','localtime')
           WHERE run_id = ? AND step_seq >= ? AND status != 'skipped'""",
        (run_id, failed),
    )
    db.execute(
        "UPDATE workflow_runs SET status='running', error_msg='', current_step=? WHERE id=?",
        (failed, run_id),
    )
    db.commit()
    workflow_engine.resume_run(run_id)
    return {"ok": True, "status": "running", "from_step": failed}



# ---------- 创作资产提取与全功能规范同步 ----------

class ExtractContentIn(BaseModel):
    content: Optional[str] = None


@router.post("/runs/{run_id}/steps/{seq}/extracted-assets")
@router.get("/runs/{run_id}/steps/{seq}/extracted-assets")
def get_extracted_assets(run_id: int, seq: int, body: Optional[ExtractContentIn] = None):
    """从指定步骤或传入的方案内容中自动抽取结构化资产 (立项/实体/关系/大纲/伏笔/世界观)"""
    db = get_db()
    if body and body.content:
        raw_text = body.content
    else:
        rs = db.execute("SELECT output FROM workflow_run_steps WHERE run_id = ? AND step_seq = ?", (run_id, seq)).fetchone()
        if not rs:
            raise HTTPException(404, "工作流步骤不存在")
        raw_text = rs["output"] or ""
    return {"ok": True, "assets": extract_structured_assets_from_text(raw_text)}


@router.get("/runs/{run_id}/summary-assets")
def get_summary_assets(run_id: int):
    """汇总工作流全流程所有步骤的产出，合并抽取全功能结构化资产并进行库内差异比对"""
    db = get_db()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "工作流运行实例不存在")
    work_id = run["work_id"]

    steps = db.execute(
        "SELECT step_seq, output FROM workflow_run_steps WHERE run_id = ? ORDER BY step_seq ASC",
        (run_id,),
    ).fetchall()
    combined_texts = [r["output"] for r in steps if r["output"]]
    full_text = chr(10).join(combined_texts)
    raw_assets = extract_structured_assets_from_text(full_text)

    # 查重比对与元数据增强
    existing_entities = {
        r["name"].strip().lower(): r["category"]
        for r in db.execute("SELECT name, category FROM entities WHERE work_id=?", (work_id,)).fetchall()
        if r["name"]
    } if work_id else {}
    existing_outlines = {
        r["title"].strip().lower()
        for r in db.execute("SELECT title FROM outline_nodes WHERE work_id=?", (work_id,)).fetchall()
        if r["title"]
    } if work_id else set()
    existing_foreshadows = {
        r["title"].strip().lower()
        for r in db.execute("SELECT title FROM foreshadows WHERE work_id=?", (work_id,)).fetchall()
        if r["title"]
    } if work_id else set()

    annotated_entities = []
    for ent in raw_assets.get("entities", []):
        d = dict(ent)
        key = ent.get("name", "").strip().lower()
        if key in existing_entities:
            d["is_new"] = False
            d["existing_category"] = existing_entities[key]
        else:
            d["is_new"] = True
        annotated_entities.append(d)
    raw_assets["entities"] = annotated_entities

    annotated_outlines = []
    for node in raw_assets.get("outline_nodes", []):
        d = dict(node)
        d["is_new"] = (node.get("title", "").strip().lower() not in existing_outlines)
        annotated_outlines.append(d)
    raw_assets["outline_nodes"] = annotated_outlines

    annotated_fs = []
    for fs in raw_assets.get("foreshadows", []):
        d = dict(fs)
        d["is_new"] = (fs.get("title", "").strip().lower() not in existing_foreshadows)
        annotated_fs.append(d)
    raw_assets["foreshadows"] = annotated_fs

    return {
        "ok": True,
        "run_meta": {
            "work_id": work_id,
            "chapter_id": run["chapter_id"],
            "outline_node_id": run["outline_node_id"],
            "status": run["status"]
        },
        "assets": raw_assets
    }

@router.post("/runs/{run_id}/steps/{seq}/sync-assets")
def sync_step_assets(run_id: int, seq: int, body: SyncAssetsIn):
    """将选定的创作资产规范写入墨语系统 (万相谱/图谱/大纲树/资料便签/正文)"""
    db = get_db()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404, "工作流运行实例不存在")
    work_id = run["work_id"]
    if not work_id:
        raise HTTPException(400, "该工作流未关联具体作品，无法规范同步到作品资产库")

    summary = sync_assets_to_database(db, work_id, body, run_id=run_id, seq=seq)
    return {"ok": True, "work_id": work_id, "summary": summary}

# ---------- 工作流定义 ----------

@router.get("")
def list_workflows(scope: Optional[str] = None, enabled: Optional[int] = None):
    db = get_db()
    sql = "SELECT * FROM workflows"
    conds, args = [], []
    if scope:
        conds.append("scope = ?")
        args.append(scope)
    if enabled is not None:
        conds.append("enabled = ?")
        args.append(1 if enabled else 0)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY builtin DESC, id ASC"
    out = []
    for r in db.execute(sql, args).fetchall():
        d = _row(r)
        d["step_count"] = db.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND enabled = 1", (r["id"],)
        ).fetchone()[0]
        d["running_count"] = db.execute(
            "SELECT COUNT(*) FROM workflow_runs WHERE workflow_id = ? AND status IN ('running','awaiting_review')",
            (r["id"],),
        ).fetchone()[0]
        out.append(d)
    return out


@router.post("", status_code=201)
def create_workflow(body: WorkflowIn):
    if not body.name.strip():
        raise HTTPException(400, "工作流名称不能为空")
    db = get_db()
    _validate_steps(db, body.steps)
    cur = db.execute(
        "INSERT INTO workflows(name, description, icon, scope, enabled, builtin) VALUES (?, ?, ?, ?, 1, 0)",
        (body.name.strip(), body.description, body.icon, body.scope),
    )
    wf_id = cur.lastrowid
    _insert_steps(db, wf_id, body.steps)
    db.commit()
    return get_workflow(wf_id)


@router.get("/{wf_id}")
def get_workflow(wf_id: int):
    db = get_db()
    wf = _get_workflow(db, wf_id)
    out = _row(wf)
    out["steps"] = _steps_of(db, wf_id)
    return out


@router.patch("/{wf_id}")
def patch_workflow(wf_id: int, body: WorkflowPatch):
    db = get_db()
    _get_workflow(db, wf_id)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "name" in fields:
        if not str(fields["name"]).strip():
            raise HTTPException(400, "工作流名称不能为空")
        fields["name"] = str(fields["name"]).strip()
    if "enabled" in fields:
        fields["enabled"] = 1 if fields["enabled"] else 0
    if not fields:
        return get_workflow(wf_id)
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(
        f"UPDATE workflows SET {cols}, updated_at=datetime('now','localtime') WHERE id=?",
        (*fields.values(), wf_id),
    )
    db.commit()
    return get_workflow(wf_id)


@router.delete("/{wf_id}", status_code=204)
def delete_workflow(wf_id: int):
    db = get_db()
    wf = _get_workflow(db, wf_id)
    if wf["builtin"]:
        raise HTTPException(403, "内置示例工作流不可删除，可创建副本后修改")
    db.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (wf_id,))
    db.execute("DELETE FROM workflows WHERE id = ?", (wf_id,))
    db.commit()


@router.post("/{wf_id}/duplicate")
def duplicate_workflow(wf_id: int):
    db = get_db()
    wf = _get_workflow(db, wf_id)
    cur = db.execute(
        "INSERT INTO workflows(name, description, icon, scope, enabled, builtin) VALUES (?, ?, ?, ?, 1, 0)",
        (wf["name"] + "（副本）", wf["description"], wf["icon"], wf["scope"]),
    )
    new_id = cur.lastrowid
    steps = _steps_of(db, wf_id)
    for s in steps:
        db.execute(
            """INSERT INTO workflow_steps(
                   workflow_id, seq, title, skill_id, input_mode, prev_step_seq,
                   output_var, instruction, length, candidates, requires_review, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, s["seq"], s["title"], s["skill_id"], s["input_mode"], s["prev_step_seq"],
             s["output_var"], s["instruction"], s["length"], s["candidates"],
             s["requires_review"], s["enabled"]),
        )
    db.commit()
    return get_workflow(new_id)


@router.put("/{wf_id}/steps")
def replace_steps(wf_id: int, body: StepsReplaceIn):
    db = get_db()
    _get_workflow(db, wf_id)
    _validate_steps(db, body.steps)
    db.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (wf_id,))
    _insert_steps(db, wf_id, body.steps)
    db.execute("UPDATE workflows SET updated_at=datetime('now','localtime') WHERE id=?", (wf_id,))
    db.commit()
    return get_workflow(wf_id)


@router.post("/{wf_id}/runs", status_code=201)
async def start_run(wf_id: int, body: RunStartIn):
    db = get_db()
    wf = _get_workflow(db, wf_id)
    if not wf["enabled"]:
        raise HTTPException(400, "该工作流已停用，请先启用")
    steps = db.execute(
        "SELECT * FROM workflow_steps WHERE workflow_id = ? AND enabled = 1 ORDER BY seq", (wf_id,)
    ).fetchall()
    if not steps:
        raise HTTPException(400, "该工作流没有可执行的步骤")
    for s in steps:
        if s["skill_id"]:
            sk = db.execute("SELECT enabled, title FROM skills WHERE id = ?", (s["skill_id"],)).fetchone()
            if not sk:
                raise HTTPException(400, f"步骤「{s['title']}」绑定的 Skill 已被删除，请换绑后重试")
            if not sk["enabled"]:
                raise HTTPException(400, f"步骤「{s['title']}」绑定的 Skill「{sk['title']}」已被禁用")
    work = db.execute("SELECT id FROM works WHERE id = ?", (body.work_id,)).fetchone()
    if not work:
        raise HTTPException(404, "作品不存在")
    if body.chapter_id is not None:
        ch = db.execute(
            """SELECT c.id FROM chapters c JOIN volumes v ON v.id = c.volume_id
               WHERE c.id = ? AND v.work_id = ?""",
            (body.chapter_id, body.work_id),
        ).fetchone()
        if not ch:
            raise HTTPException(400, "章节不存在或不属于该作品")
    if body.outline_node_id is not None:
        nd = db.execute(
            "SELECT id FROM outline_nodes WHERE id = ? AND work_id = ?",
            (body.outline_node_id, body.work_id),
        ).fetchone()
        if not nd:
            raise HTTPException(400, "大纲节点不存在或不属于该作品")
    cfg = get_ai_config()
    if not cfg.get("ai_api_key") or not cfg.get("ai_model"):
        raise HTTPException(400, "未配置 AI 接口，请先到系统设置页配置")

    cur = db.execute(
        "INSERT INTO workflow_runs(workflow_id, work_id, chapter_id, outline_node_id, status) VALUES (?, ?, ?, ?, 'pending')",
        (wf_id, body.work_id, body.chapter_id, body.outline_node_id),
    )
    run_id = cur.lastrowid
    for s in steps:
        db.execute(
            "INSERT INTO workflow_run_steps(run_id, step_seq, title, status) VALUES (?, ?, ?, 'pending')",
            (run_id, s["seq"], s["title"]),
        )
    db.commit()
    workflow_engine.start_run(run_id)
    return {"run_id": run_id}
