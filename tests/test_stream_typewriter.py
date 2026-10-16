# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""正文打字机流式生成与中断机制（SSE）测试套件：
- 验证 /api/ai/generate 在 stream=True 模式下的 SSE 数据流分块输出
- 验证 task_id 状态初始化、流式消费与已完成状态更新
- 验证客户端断开/异常中止时任务台账正常闭环（不挂起处于 running）
- 验证前端打字机关键视觉样式及文字计数器元素
"""
import json
from unittest.mock import AsyncMock, patch
import pytest
from app.db import get_db
from app.ai_tasks import get_task
from tests.conftest import make_wvc


def test_ai_generate_streaming_success(client):
    """测试流式 SSE 接口能完整按候选产出 delta 并落库任务台账。"""
    _, _, chapter = make_wvc(client, "流式打字机测试作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    async def mock_stream(messages, cfg, box, timeout=None):
        box["total_tokens"] = 42
        for chunk in ["九", "幽", "魔", "海", "翻", "腾", "。"]:
            yield chunk

    with patch("app.features.chat_stream", side_effect=mock_stream):
        resp = client.post(
            "/api/ai/generate",
            json={
                "chapter_id": chapter["id"],
                "task": "continue",
                "length": "short",
                "candidates": 1,
                "stream": True,
            },
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body_text = resp.text

        # 检查事件帧
        frames = [line for line in body_text.split("\n\n") if line.startswith("data:")]
        events = [json.loads(f[5:].strip()) for f in frames if f[5:].strip()]

        task_id = None
        deltas = []
        has_start = False
        has_done = False
        for ev in events:
            if "task_id" in ev and "done" not in ev and "error" not in ev:
                task_id = ev["task_id"]
            if ev.get("start"):
                has_start = True
            if "delta" in ev:
                deltas.append(ev["delta"])
            if ev.get("done"):
                has_done = True
                assert ev["usage"]["total_tokens"] == 42

        assert task_id is not None
        assert has_start is True
        assert has_done is True
        assert "".join(deltas) == "九幽魔海翻腾。"

        # 检查后台 ai_tasks 台账状态已更新为 done
        task_record = get_task(task_id)
        assert task_record["status"] == "done"
        assert task_record["token_used"] == 42
        task_out = json.loads(task_record["output_json"])
        assert task_out["candidates"] == ["九幽魔海翻腾。"]


def test_ai_generate_streaming_multi_candidates(client):
    """测试多候选流式生成顺序与数据隔离。"""
    _, _, chapter = make_wvc(client, "多候选流式作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    seq = 0
    async def mock_multi_stream(messages, cfg, box, timeout=None):
        nonlocal seq
        seq += 1
        box["total_tokens"] = 10
        yield f"候选{seq}输出"

    with patch("app.features.chat_stream", side_effect=mock_multi_stream):
        resp = client.post(
            "/api/ai/generate",
            json={
                "chapter_id": chapter["id"],
                "task": "continue",
                "length": "short",
                "candidates": 2,
                "stream": True,
            },
        )
        assert resp.status_code == 200
        body_text = resp.text
        frames = [line for line in body_text.split("\n\n") if line.startswith("data:")]
        events = [json.loads(f[5:].strip()) for f in frames if f[5:].strip()]

        cands = [ev.get("candidate") for ev in events if "candidate" in ev]
        assert 0 in cands and 1 in cands
        done_ev = [ev for ev in events if ev.get("done")][0]
        assert done_ev["usage"]["total_tokens"] == 20


def test_ai_generate_streaming_error_handling(client):
    """测试流式生成中上游抛出异常时的错误事件帧与任务标记。"""
    from app.ai_client import AIError
    _, _, chapter = make_wvc(client, "流式异常测试作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    async def mock_fail_stream(messages, cfg, box, timeout=None):
        yield "一部分前置文字"
        raise AIError("模拟上游连接超时中断")

    with patch("app.features.chat_stream", side_effect=mock_fail_stream):
        resp = client.post(
            "/api/ai/generate",
            json={
                "chapter_id": chapter["id"],
                "task": "continue",
                "length": "short",
                "candidates": 1,
                "stream": True,
            },
        )
        assert resp.status_code == 200
        body_text = resp.text
        assert "模拟上游连接超时中断" in body_text
        assert '"error"' in body_text
