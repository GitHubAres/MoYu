# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""AI 任务基础设施：任务台账（Task Ledger）服务层。"""
import json
import time

from app.db import get_db

VALID_STATUSES = {"pending", "running", "done", "failed", "cancelled"}


def _row(r):
    return dict(r)


def create_task(work_id: int | None, task_type: str, input_summary: str = "") -> int:
    """创建任务，返回任务 id。"""
    db = get_db()
    cur = db.execute(
        "INSERT INTO ai_tasks(work_id, task_type, input_summary, status) VALUES (?,?,?,?)",
        (work_id, task_type, input_summary, "pending"),
    )
    db.commit()
    return cur.lastrowid


def get_task(task_id: int) -> dict:
    row = get_db().execute("SELECT * FROM ai_tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    return _row(row)


def start_task(task_id: int):
    db = get_db()
    db.execute(
        "UPDATE ai_tasks SET status='running', updated_at=datetime('now','localtime') WHERE id=?",
        (task_id,),
    )
    db.commit()


def finish_task(task_id: int, output: dict, token_used: int = 0, elapsed_ms: int = 0):
    db = get_db()
    db.execute(
        """UPDATE ai_tasks
           SET status='done', output_json=?, token_used=?, elapsed_ms=?,
               updated_at=datetime('now','localtime')
           WHERE id=?""",
        (json.dumps(output, ensure_ascii=False), token_used, elapsed_ms, task_id),
    )
    db.commit()


def fail_task(task_id: int, error_msg: str, elapsed_ms: int = 0):
    db = get_db()
    db.execute(
        """UPDATE ai_tasks
           SET status='failed', error_msg=?, elapsed_ms=?,
               updated_at=datetime('now','localtime')
           WHERE id=?""",
        (error_msg, elapsed_ms, task_id),
    )
    db.commit()


def cancel_task(task_id: int):
    db = get_db()
    db.execute(
        "UPDATE ai_tasks SET status='cancelled', updated_at=datetime('now','localtime') WHERE id=?",
        (task_id,),
    )
    db.commit()


def list_tasks(work_id: int | None = None, task_type: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    sql = "SELECT * FROM ai_tasks"
    args = []
    conds = []
    if work_id is not None:
        conds.append("work_id=?")
        args.append(work_id)
    if task_type:
        conds.append("task_type=?")
        args.append(task_type)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    return [_row(r) for r in get_db().execute(sql, args).fetchall()]


def retry_task(task_id: int) -> int:
    """复制原任务创建一条新任务，返回新任务 id。"""
    old = get_task(task_id)
    return create_task(old["work_id"], old["task_type"], old["input_summary"])


def task_context():
    """返回一个上下文管理器，用于包裹 AI 调用：自动更新 running/done/failed。"""
    class _Context:
        def __init__(self, work_id, task_type, input_summary):
            self.task_id = create_task(work_id, task_type, input_summary)
            self._start = None

        def __enter__(self):
            start_task(self.task_id)
            self._start = time.time()
            return self.task_id

        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed = int((time.time() - self._start) * 1000) if self._start else 0
            if exc_val:
                fail_task(self.task_id, str(exc_val), elapsed)
            return False

    return _Context

async def run_async_task(task_id: int, coro):
    start_task(task_id)
    t0 = time.time()
    try:
        res = await coro
        elapsed = int((time.time() - t0) * 1000)
        token_used = res.get("token_used", 0) if isinstance(res, dict) else 0
        finish_task(task_id, res if isinstance(res, dict) else {"result": res}, token_used=token_used, elapsed_ms=elapsed)
        return res
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        fail_task(task_id, str(e), elapsed_ms=elapsed)
        return None

