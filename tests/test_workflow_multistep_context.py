# -*- coding: utf-8 -*-
"""工作流多前序步骤上下文装配机制专属回归测试"""
import time
from unittest.mock import patch
from app.db import get_db
from tests.conftest import make_wvc


def _wait_run_status(client, run_id: int, target_statuses=("awaiting_review", "done", "failed", "cancelled"), timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/workflows/runs/{run_id}").json()
        if r["status"] in target_statuses:
            return r
        time.sleep(0.05)
    return client.get(f"/api/workflows/runs/{run_id}").json()


def test_workflow_multistep_crud_and_schema(client):
    """验证多前序步骤定义与保存、查询以及旧字段兼容性"""
    # 1. 创建多前序步骤引用的工作流
    payload = {
        "name": "多步骤协同推演流",
        "description": "测试步骤 2 同时参考步骤 0 和 1",
        "steps": [
            {
                "title": "步骤0-立项",
                "input_mode": "chapter",
                "context_sources": ["chapter"],
                "ref_step_seqs": [],
                "requires_review": 0
            },
            {
                "title": "步骤1-世界观",
                "input_mode": "prev_output",
                "context_sources": ["triad"],
                "ref_step_seqs": [0],
                "requires_review": 0
            },
            {
                "title": "步骤2-剧情网",
                "input_mode": "merge",
                "context_sources": ["chapter", "triad"],
                "ref_step_seqs": [0, 1],
                "requires_review": 0
            }
        ]
    }
    res = client.post("/api/workflows", json=payload)
    assert res.status_code == 201
    wf_id = res.json()["id"]

    # 2. 查询并验证结构
    detail = client.get(f"/api/workflows/{wf_id}").json()
    assert len(detail["steps"]) == 3
    s0, s1, s2 = detail["steps"]

    assert s0["ref_step_seqs"] == []
    assert "chapter" in s0["context_sources"]

    assert s1["ref_step_seqs"] == [0]
    assert s1["prev_step_seq"] == 0

    assert s2["ref_step_seqs"] == [0, 1]
    assert s2["prev_step_seq"] == 1
    assert "chapter" in s2["context_sources"]
    assert "triad" in s2["context_sources"]


def test_workflow_multistep_execution_and_prompt_injection(client):
    """验证工作流执行时，多前序步骤输出被正确格式化拼装入后续步骤的 AI 上下文中"""
    work, volume, chapter = make_wvc(client, "多步推演测试作品")
    db = get_db()
    db.execute("UPDATE chapters SET content = ? WHERE id = ?", ("章节开篇正文：苍茫大地，风起云涌。", chapter["id"]))
    db.commit()

    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    # 创建工作流：
    # 步骤0：创意立项
    # 步骤1：主要人物
    # 步骤2：联合推演（同时参考步骤 0 和 步骤 1）
    wf = client.post("/api/workflows", json={
        "name": "三步合一推演流",
        "steps": [
            {
                "title": "创意立项",
                "input_mode": "none",
                "context_sources": [],
                "ref_step_seqs": [],
                "instruction": "生成创意：赛博修仙",
                "requires_review": 0
            },
            {
                "title": "主要人物",
                "input_mode": "none",
                "context_sources": [],
                "ref_step_seqs": [],
                "instruction": "生成主角：叶天，机械灵根",
                "requires_review": 0
            },
            {
                "title": "冲突高潮推演",
                "input_mode": "merge",
                "context_sources": ["chapter"],
                "ref_step_seqs": [0, 1],
                "instruction": "结合立项 {{steps.0.output}} 与人物 {{steps.1.output}} 推演冲突",
                "requires_review": 0
            }
        ]
    }).json()

    captured_messages = []

    async def mock_chat(messages, cfg):
        step_idx = len(captured_messages)
        captured_messages.append(messages)
        if step_idx == 0:
            return ("【步骤0产出】：核动力金丹与赛博天劫", 30)
        elif step_idx == 1:
            return ("【步骤1产出】：叶天搭载玄冰散热矩阵", 40)
        else:
            return ("【步骤2产出】：最终融合推演决战完成", 50)

    with patch("app.workflow_engine.chat", side_effect=mock_chat):
        r = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"], "chapter_id": chapter["id"]})
        run_id = r.json()["run_id"]
        final_run = _wait_run_status(client, run_id, target_statuses=("done",))

    assert final_run["status"] == "done"
    assert len(captured_messages) == 3

    # 步骤2的 Prompt 校验：
    step2_all_text = " ".join(m["content"] for m in captured_messages[2])

    # 1. 验证上下文注入中包含步骤 0 和步骤 1 的前序参考块
    assert "【前序参考：步骤 1 (创意立项)】" in step2_all_text
    assert "【步骤0产出】：核动力金丹与赛博天劫" in step2_all_text

    assert "【前序参考：步骤 2 (主要人物)】" in step2_all_text
    assert "【步骤1产出】：叶天搭载玄冰散热矩阵" in step2_all_text

    # 2. 验证章节正文也被成功注入
    assert "苍茫大地，风起云涌" in step2_all_text

    # 3. 验证 instruction 中的 {{steps.0.output}} 和 {{steps.1.output}} 模板变量替换
    assert "结合立项 【步骤0产出】：核动力金丹与赛博天劫 与人物 【步骤1产出】：叶天搭载玄冰散热矩阵 推演冲突" in step2_all_text

    # 4. 验证 run detail 返回字段
    detail = client.get(f"/api/workflows/runs/{run_id}").json()
    assert detail["steps"][2]["ref_step_seqs"] == [0, 1]
    assert "chapter" in detail["steps"][2]["context_sources"]
