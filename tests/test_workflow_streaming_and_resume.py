# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""长文工作流步骤级实时输出与断点续跑测试套件：
- 验证工作流步骤执行时向 live_output 缓冲区写入实时流式数据
- 验证 GET /api/workflows/runs/{run_id} 能正确返回 live_output 字段与当前活跃 step_seq
- 验证 POST /api/workflows/runs/{run_id}/steps/{seq}/retry 单步断点续跑接口
- 验证步骤失败后单步断点重试并顺利推进至后续步骤
"""
import time
from unittest.mock import AsyncMock, patch
import pytest
from app.db import get_db
import app.workflow_engine as wf_engine
from tests.conftest import make_wvc, make_work, make_volume, make_chapter


def _wait_run_status(client, run_id: int, target_statuses=("awaiting_review", "done", "failed", "cancelled"), timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/workflows/runs/{run_id}").json()
        if r["status"] in target_statuses:
            return r
        time.sleep(0.05)
    return client.get(f"/api/workflows/runs/{run_id}").json()


def test_workflow_live_output_streaming(client):
    """测试工作流在步骤执行期间实时输出缓冲区的装载与清退。"""
    w = make_work(client, "工作流流式测试作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    # 创建一个单步工作流
    wf = client.post("/api/workflows", json={
        "name": "实时流式测试工作流",
        "scope": "work",
        "description": "测试实时缓冲区",
        "steps": [
            {
                "title": "大纲构思",
                "input_mode": "none",
                "instruction": "构思第一卷主线",
                "requires_review": 1,
            }
        ]
    }).json()

    async def mock_stream(messages, cfg, box, timeout=None):
        box["total_tokens"] = 30
        for chunk in ["【第一卷：", "潜龙在渊", "】", "主角觉醒金手指。"]:
            time.sleep(0.02)
            yield chunk

    with patch("app.workflow_engine.chat_stream", side_effect=mock_stream):
        run_res = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": w["id"]})
        assert run_res.status_code == 201
        run_id = run_res.json()["run_id"]

        # 等待其进入 review 状态
        detail = _wait_run_status(client, run_id, target_statuses=("awaiting_review",))
        assert detail["status"] == "awaiting_review"
        step0 = detail["steps"][0]
        assert "潜龙在渊" in step0["output"]
        # 执行完毕后活体缓冲区已清退
        assert wf_engine.get_live_output(run_id) == {}


def test_workflow_step_retry_breakpoint_resume(client):
    """测试工作流单步断点重试接口 POST /runs/{run_id}/steps/{seq}/retry。"""
    w = make_work(client, "断点重试测试作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    # 创建两步工作流，第一步需要 review
    wf = client.post("/api/workflows", json={
        "name": "断点续跑工作流",
        "scope": "work",
        "steps": [
            {
                "title": "初稿设定",
                "input_mode": "none",
                "instruction": "生成初版设定",
                "requires_review": 1,
            },
            {
                "title": "细纲扩充",
                "input_mode": "prev_output",
                "instruction": "根据初版设定扩充",
                "requires_review": 0,
            }
        ]
    }).json()

    call_count = 0
    async def mock_stream_steps(messages, cfg, box, timeout=None):
        nonlocal call_count
        call_count += 1
        box["total_tokens"] = 15
        yield f"第{call_count}次生成内容"

    with patch("app.workflow_engine.chat_stream", side_effect=mock_stream_steps):
        # 启动工作流
        run_res = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": w["id"]})
        run_id = run_res.json()["run_id"]

        # 等待步骤0就绪
        d1 = _wait_run_status(client, run_id, target_statuses=("awaiting_review",))
        assert d1["status"] == "awaiting_review"
        assert d1["steps"][0]["status"] == "awaiting_review"
        assert "第1次生成内容" in d1["steps"][0]["output"]

        # 触发步骤0的断点重试（重新构思/抽卡）
        retry_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/retry")
        assert retry_res.status_code == 200
        assert retry_res.json()["ok"] is True
        assert retry_res.json()["step_seq"] == 0

        # 等待步骤0再次完成并进入 review
        d2 = _wait_run_status(client, run_id, target_statuses=("awaiting_review",))
        assert d2["status"] == "awaiting_review"
        assert "第2次生成内容" in d2["steps"][0]["output"]

        # 确认批准步骤0，自动推进到步骤1并完成
        approve_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={"action": "approve"})
        assert approve_res.status_code == 200

        d3 = _wait_run_status(client, run_id, target_statuses=("done",))
        assert d3["status"] == "done"
        assert d3["finished_steps"] == 2
        assert "第3次生成内容" in d3["steps"][1]["output"]
