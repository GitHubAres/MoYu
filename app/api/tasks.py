# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""AI 任务台账 API。"""
from fastapi import APIRouter, HTTPException

from ..ai_tasks import cancel_task, get_task, list_tasks, retry_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks_api(work_id: int | None = None, task_type: str = "", limit: int = 50, offset: int = 0):
    return list_tasks(work_id=work_id, task_type=task_type, limit=limit, offset=offset)


@router.get("/{task_id}")
def get_task_api(task_id: int):
    try:
        return get_task(task_id)
    except ValueError:
        raise HTTPException(404, "任务不存在")


@router.post("/{task_id}/cancel")
def cancel_task_api(task_id: int):
    try:
        cancel_task(task_id)
        return get_task(task_id)
    except ValueError:
        raise HTTPException(404, "任务不存在")


@router.post("/{task_id}/retry", status_code=201)
def retry_task_api(task_id: int):
    try:
        new_id = retry_task(task_id)
    except ValueError:
        raise HTTPException(404, "任务不存在")
    return {"id": new_id, "status": "pending"}
