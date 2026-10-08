# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""写作工作流自动化测试套件：
- 覆盖工作流定义与内置示例保护（CRUD）
- 步骤编排与约束校验
- 运行引擎、上下文注入与前序输出引用（mock AI）
- 人工确认闸（approve / edit / skip / abort）
- 失败处理与恢复（retry / cancel）
- 台账与 token 汇总
"""
import time
from unittest.mock import AsyncMock, patch
import pytest
from app.db import get_db
from tests.conftest import make_wvc, make_work, make_volume, make_chapter


def _wait_run_status(client, run_id: int, target_statuses=("awaiting_review", "done", "failed", "cancelled"), timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/workflows/runs/{run_id}").json()
        if r["status"] in target_statuses:
            return r
        time.sleep(0.05)
    return client.get(f"/api/workflows/runs/{run_id}").json()


# ==================== 1. CRUD 测试 ====================

def test_workflow_seed_builtins(client):
    """测试系统内置的两个示例工作流自动播种就绪且不可删除。"""
    res = client.get("/api/workflows")
    assert res.status_code == 200
    wfs = res.json()
    builtins = [w for w in wfs if w["builtin"] == 1]
    assert len(builtins) >= 2
    names = {w["name"] for w in builtins}
    assert "章节标准生产流" in names
    assert "新书开坑五连流" in names

    # 内置工作流 steps 结构检查
    std_wf = next(w for w in builtins if w["name"] == "章节标准生产流")
    detail = client.get(f"/api/workflows/{std_wf['id']}").json()
    assert len(detail["steps"]) == 3
    # 步骤0 开启确认闸，后续步骤不设确认闸
    assert detail["steps"][0]["requires_review"] == 1
    assert detail["steps"][1]["requires_review"] == 0
    assert detail["steps"][2]["requires_review"] == 0


def test_workflow_create_and_validation(client):
    """测试自定义工作流创建与参数合法性校验。"""
    # 1. 名称不能为空
    bad1 = client.post("/api/workflows", json={"name": "   ", "steps": []})
    assert bad1.status_code == 400
    assert "名称不能为空" in bad1.json()["detail"]

    # 2. 步骤展示名不能为空
    bad2 = client.post("/api/workflows", json={
        "name": "测试流",
        "steps": [{"title": "  ", "input_mode": "chapter"}]
    })
    assert bad2.status_code == 400
    assert "步骤展示名不能为空" in bad2.json()["detail"]

    # 3. 非法 input_mode
    bad3 = client.post("/api/workflows", json={
        "name": "测试流",
        "steps": [{"title": "第一步", "input_mode": "invalid_mode"}]
    })
    assert bad3.status_code == 400

    # 4. 正常创建
    res = client.post("/api/workflows", json={
        "name": "自定义小说流水线",
        "description": "专用于测试的流水线",
        "icon": "alt_route",
        "scope": "global",
        "steps": [
            {"title": "生成初稿", "input_mode": "chapter", "length": "short", "requires_review": 1},
            {"title": "精修润色", "input_mode": "prev_output", "length": "medium", "requires_review": 0}
        ]
    })
    assert res.status_code == 201
    wf = res.json()
    assert wf["name"] == "自定义小说流水线"
    assert wf["builtin"] == 0
    assert wf["enabled"] == 1
    assert len(wf["steps"]) == 2
    assert wf["steps"][0]["output_var"] == "step0"
    assert wf["steps"][1]["output_var"] == "step1"


def test_workflow_get_and_patch(client):
    """测试获取详情与 PATCH 修改属性。"""
    create_res = client.post("/api/workflows", json={
        "name": "待修改工作流",
        "description": "原描述",
        "steps": [{"title": "步1", "input_mode": "none"}]
    }).json()
    wf_id = create_res["id"]

    # PATCH 修改
    patch_res = client.patch(f"/api/workflows/{wf_id}", json={
        "name": "已修改工作流",
        "description": "新描述",
        "enabled": 0,
        "icon": "hub"
    })
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["name"] == "已修改工作流"
    assert data["description"] == "新描述"
    assert data["enabled"] == 0
    assert data["icon"] == "hub"

    # 验证 GET
    get_res = client.get(f"/api/workflows/{wf_id}").json()
    assert get_res["enabled"] == 0


def test_workflow_delete_custom_and_builtin_forbidden(client):
    """测试自定义工作流删除与内置工作流禁止删除。"""
    # 1. 内置工作流尝试删除被 403 拦截
    res = client.get("/api/workflows").json()
    builtin = next(w for w in res if w["builtin"] == 1)
    del_builtin = client.delete(f"/api/workflows/{builtin['id']}")
    assert del_builtin.status_code == 403
    assert "内置" in del_builtin.json()["detail"]

    # 2. 自定义工作流可正常删除
    c = client.post("/api/workflows", json={"name": "即将删除", "steps": []}).json()
    del_custom = client.delete(f"/api/workflows/{c['id']}")
    assert del_custom.status_code == 204
    assert client.get(f"/api/workflows/{c['id']}").status_code == 404


def test_workflow_duplicate(client):
    """测试创建副本（自动追加副本后缀并完整拷贝步骤）。"""
    res = client.get("/api/workflows").json()
    std = next(w for w in res if w["name"] == "章节标准生产流")

    dup_res = client.post(f"/api/workflows/{std['id']}/duplicate")
    assert dup_res.status_code == 200
    dup = dup_res.json()
    assert dup["name"] == "章节标准生产流（副本）"
    assert dup["builtin"] == 0
    assert len(dup["steps"]) == 3
    assert dup["steps"][0]["title"] == "生成本章草稿"


# ==================== 2. 步骤编排测试 ====================

def test_replace_steps_success_and_validation(client):
    """测试 PUT /workflows/{id}/steps 全量替换步骤及顺序。"""
    c = client.post("/api/workflows", json={"name": "替换测试", "steps": []}).json()
    wf_id = c["id"]

    replace_res = client.put(f"/api/workflows/{wf_id}/steps", json={
        "steps": [
            {"title": "新第一步", "input_mode": "chapter", "length": "short", "requires_review": 1},
            {"title": "新第二步", "input_mode": "prev_output", "prev_step_seq": 0, "length": "long", "requires_review": 0}
        ]
    })
    assert replace_res.status_code == 200
    steps = replace_res.json()["steps"]
    assert len(steps) == 2
    assert steps[0]["seq"] == 0 and steps[0]["title"] == "新第一步"
    assert steps[1]["seq"] == 1 and steps[1]["title"] == "新第二步"


def test_step_binding_skill_validation(client):
    """测试步骤绑定不存在的 Skill 或禁用的 Skill 时报错。"""
    c = client.post("/api/workflows", json={"name": "绑定校验", "steps": []}).json()
    wf_id = c["id"]

    # 1. 绑定不存在的 Skill
    bad1 = client.put(f"/api/workflows/{wf_id}/steps", json={
        "steps": [{"title": "步骤A", "skill_id": 999999, "input_mode": "chapter"}]
    })
    assert bad1.status_code == 400
    assert "不存在" in bad1.json()["detail"]

    # 2. 绑定已禁用的 Skill
    sk = client.post("/api/skills", json={
        "name": "disabled-for-wf", "title": "禁用技能", "description": "描述"
    }).json()
    client.patch(f"/api/skills/{sk['id']}", json={"enabled": 0})

    bad2 = client.put(f"/api/workflows/{wf_id}/steps", json={
        "steps": [{"title": "步骤B", "skill_id": sk["id"], "input_mode": "chapter"}]
    })
    assert bad2.status_code == 400
    assert "禁用" in bad2.json()["detail"]


# ==================== 3. 运行预检与执行引擎测试 ====================

def test_start_run_preflight_checks(client):
    """测试启动运行前的前置拦截（停用工作流、空步骤、未配 AI、无效作品章节）。"""
    work, volume, chapter = make_wvc(client, "预检作品")

    # 1. 未配置 AI 接口
    client.patch("/api/settings", json={"values": {"ai_api_key": "", "ai_model": ""}})
    r1 = client.post("/api/workflows/1/runs", json={"work_id": work["id"], "chapter_id": chapter["id"]})
    assert r1.status_code == 400
    assert "未配置 AI" in r1.json()["detail"]

    # 配上 AI
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    # 2. 停用工作流不可运行
    wf_dis = client.post("/api/workflows", json={
        "name": "已停用流", "steps": [{"title": "步1", "input_mode": "chapter"}]
    }).json()
    client.patch(f"/api/workflows/{wf_dis['id']}", json={"enabled": 0})
    r2 = client.post(f"/api/workflows/{wf_dis['id']}/runs", json={"work_id": work["id"], "chapter_id": chapter["id"]})
    assert r2.status_code == 400
    assert "已停用" in r2.json()["detail"]

    # 3. 空步骤工作流不可运行
    wf_empty = client.post("/api/workflows", json={"name": "空流", "steps": []}).json()
    r3 = client.post(f"/api/workflows/{wf_empty['id']}/runs", json={"work_id": work["id"]})
    assert r3.status_code == 400
    assert "没有可执行的步骤" in r3.json()["detail"]

    # 4. 不存在的作品
    r4 = client.post("/api/workflows/1/runs", json={"work_id": 999999})
    assert r4.status_code == 404

    # 5. 章节不属于该作品
    other_work = make_work(client, "另一部作品")
    r5 = client.post("/api/workflows/1/runs", json={"work_id": other_work["id"], "chapter_id": chapter["id"]})
    assert r5.status_code == 400
    assert "不属于" in r5.json()["detail"]


def test_run_auto_execution_three_steps_done(client):
    """3 步全不设确认闸（requires_review=0）时，自动顺序执行至 done 状态。"""
    work, volume, chapter = make_wvc(client, "自动执行测试作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    # 创建一个 3 步都不需要人工确认的工作流
    wf = client.post("/api/workflows", json={
        "name": "全自动三步流",
        "steps": [
            {"title": "生成大纲", "input_mode": "none", "requires_review": 0},
            {"title": "细化冲突", "input_mode": "prev_output", "requires_review": 0},
            {"title": "风格润色", "input_mode": "prev_output", "requires_review": 0}
        ]
    }).json()

    replies = [
        ("【大纲】主角潜入古城探秘。", 80),
        ("【冲突】守门人拔刀，气机锁定。", 120),
        ("【润色】秋风掠过城堞，刀芒如电。", 150),
    ]
    call_idx = 0

    async def mock_chat(messages, cfg):
        nonlocal call_idx
        res = replies[call_idx]
        call_idx += 1
        return res

    with patch("app.workflow_engine.chat", side_effect=mock_chat):
        start_res = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]})
        assert start_res.status_code == 201
        run_id = start_res.json()["run_id"]

        detail = _wait_run_status(client, run_id, target_statuses=("done", "failed"))
        assert detail["status"] == "done"
        assert detail["finished_steps"] == 3
        assert detail["total_steps"] == 3
        assert detail["token_used"] == 350
        assert "主角潜入古城" in detail["steps"][0]["output"]
        assert "守门人拔刀" in detail["steps"][1]["output"]
        assert "秋风掠过城堞" in detail["steps"][2]["output"]


def test_run_context_injection_and_template_sub(client):
    """测试上下文输入模式（chapter/prev_output/merge）与 instruction 模板变量 {{steps.0.output}} 替换。"""
    work, volume, chapter = make_wvc(client, "上下文注入作品")
    # 写入章节正文
    db = get_db()
    db.execute("UPDATE chapters SET content = ? WHERE id = ?", ("原章节第一段内容：大雪封山。", chapter["id"]))
    db.commit()

    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "模板与上下文测试流",
        "steps": [
            {"title": "步0续写", "input_mode": "chapter", "instruction": "基于正文续写", "requires_review": 0},
            {"title": "步1引用", "input_mode": "none", "instruction": "引用第0步：{{steps.0.output}}，请检查", "requires_review": 0}
        ]
    }).json()

    captured_messages = []

    async def mock_chat(messages, cfg):
        captured_messages.append(messages)
        return (f"回复{len(captured_messages)}", 50)

    with patch("app.workflow_engine.chat", side_effect=mock_chat):
        r = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"], "chapter_id": chapter["id"]})
        run_id = r.json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("done",))

    assert len(captured_messages) == 2
    # 校验第 0 步包含章节正文（在 system prompt 或 user content 中）
    step0_all_text = " ".join(m["content"] for m in captured_messages[0])
    assert "大雪封山" in step0_all_text
    # 校验第 1 步的 instruction 中 {{steps.0.output}} 被正确替换为步 0 的产出 "回复1"
    step1_all_text = " ".join(m["content"] for m in captured_messages[1])
    assert "引用第0步：回复1，请检查" in step1_all_text


def test_run_context_truncation(client):
    """测试长链路上下文膨胀对策：长文本前序引用时截断并标记「[中段内容已截断]」。"""
    from app.workflow_engine import _truncate_prev
    short_text = "这是一段很短的文本"
    assert _truncate_prev(short_text) == short_text

    long_text = "头部" + ("A" * 5000) + "尾部"
    truncated = _truncate_prev(long_text)
    assert "[中段内容已截断]" in truncated
    assert truncated.startswith("头部")
    assert truncated.endswith("尾部")


# ==================== 4. 人工确认闸测试 ====================

def test_review_gate_pauses_and_approve(client):
    """步骤 requires_review=1 时暂停挂起（awaiting_review），approve 后继续推进。"""
    work, volume, chapter = make_wvc(client, "确认闸作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    # 使用内置的「章节标准生产流」（步 0 requires_review=1，步 1、2 不设确认闸）
    res = client.get("/api/workflows").json()
    std_wf = next(w for w in res if w["name"] == "章节标准生产流")

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("草稿第1版内容", 100)
        start_res = client.post(f"/api/workflows/{std_wf['id']}/runs", json={"work_id": work["id"], "chapter_id": chapter["id"]})
        run_id = start_res.json()["run_id"]

        # 等待步 0 跑完进入 awaiting_review
        d1 = _wait_run_status(client, run_id, target_statuses=("awaiting_review", "done"))
        assert d1["status"] == "awaiting_review"
        assert d1["steps"][0]["status"] == "awaiting_review"
        assert d1["steps"][1]["status"] == "pending"

        # 触发 approve 采纳并继续
        m.return_value = ("后续步骤产出", 80)
        rev_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={"action": "approve", "note": "满意"})
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "running"

        # 等待全流程跑完
        d2 = _wait_run_status(client, run_id, target_statuses=("done",))
        assert d2["status"] == "done"
        assert d2["steps"][0]["status"] == "approved"
        assert d2["steps"][0]["review_note"] == "满意"
        assert d2["steps"][1]["status"] == "approved"
        assert d2["steps"][2]["status"] == "approved"
        time.sleep(0.05)


def test_review_gate_edit_replaces_output(client):
    """以修改稿继续（action=edit）：产出内容被用户修改稿替换，并带入后续步骤。"""
    work, volume, chapter = make_wvc(client, "修改稿作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "修改稿测试流",
        "steps": [
            {"title": "生成草稿", "input_mode": "none", "requires_review": 1},
            {"title": "润色", "input_mode": "prev_output", "requires_review": 0}
        ]
    }).json()

    captured_prompts = []

    async def mock_chat(messages, cfg):
        captured_prompts.append(messages)
        if len(captured_prompts) == 1:
            return ("AI原本写的草稿", 60)
        return ("定稿", 60)

    with patch("app.workflow_engine.chat", side_effect=mock_chat):
        r = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]})
        run_id = r.json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("awaiting_review",))

        # edit 缺少 content 必须报错 400
        bad_edit = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={"action": "edit"})
        assert bad_edit.status_code == 400

        # 提供修改稿继续
        edit_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={
            "action": "edit",
            "content": "作者亲手修改后的精炼草稿",
            "note": "精简了废话"
        })
        assert edit_res.status_code == 200

        d = _wait_run_status(client, run_id, target_statuses=("done",))
        assert d["status"] == "done"
        assert d["steps"][0]["output"] == "作者亲手修改后的精炼草稿"
        # 验证第二步接收到的是用户修改后的稿件，而非 AI 原本的
        step1_text = " ".join(m["content"] for m in captured_prompts[1])
        assert "作者亲手修改后的精炼草稿" in step1_text


def test_review_gate_skip_and_abort(client):
    """测试确认闸 skip 跳过与 abort 中止。"""
    work, volume, chapter = make_wvc(client, "跳过与中止作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "跳过测试流",
        "steps": [
            {"title": "步0", "input_mode": "none", "requires_review": 1},
            {"title": "步1", "input_mode": "none", "requires_review": 1}
        ]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("产出内容", 50)
        # 1. 测试 skip
        r1 = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()
        run_id1 = r1["run_id"]
        _wait_run_status(client, run_id1, target_statuses=("awaiting_review",))

        skip_res = client.post(f"/api/workflows/runs/{run_id1}/steps/0/review", json={"action": "skip", "note": "不想要此步"})
        assert skip_res.status_code == 200
        # 推进到步 1，由于步 1 也是 requires_review=1，会在步 1 挂起
        d1 = _wait_run_status(client, run_id1, target_statuses=("awaiting_review", "done"))
        assert d1["steps"][0]["status"] == "skipped"

        # 2. 测试 abort 中止
        abort_res = client.post(f"/api/workflows/runs/{run_id1}/steps/1/review", json={"action": "abort"})
        assert abort_res.status_code == 200
        d1_end = client.get(f"/api/workflows/runs/{run_id1}").json()
        assert d1_end["status"] == "cancelled"


def test_review_gate_illegal_state_validation(client):
    """不在 awaiting_review 状态下调用 review 接口必须抛出 400。"""
    work, volume, chapter = make_wvc(client, "非法状态测试作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "直通流", "steps": [{"title": "步0", "input_mode": "none", "requires_review": 0}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("直通完成", 50)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("done",))

        # 当前已完成，调 review 应报 400
        res = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={"action": "approve"})
        assert res.status_code == 400
        assert "未处于待确认状态" in res.json()["detail"]


# ==================== 5. 失败处理与恢复测试 ====================

def test_run_step_failure_and_retry(client):
    """步骤失败（AI 抛出异常）记录错误，通过 retry 从失败处恢复重跑。"""
    work, volume, chapter = make_wvc(client, "失败恢复作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "重试测试流",
        "steps": [
            {"title": "第一步正常", "input_mode": "none", "requires_review": 0},
            {"title": "第二步先失败后成功", "input_mode": "none", "requires_review": 0}
        ]
    }).json()

    fail_counter = 0

    async def mock_chat(messages, cfg):
        nonlocal fail_counter
        fail_counter += 1
        if fail_counter == 2:
            raise RuntimeError("模拟模型超时连接断开")
        return (f"成功回复{fail_counter}", 70)

    with patch("app.workflow_engine.chat", side_effect=mock_chat):
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        d = _wait_run_status(client, run_id, target_statuses=("failed",))
        assert d["status"] == "failed"
        assert "模拟模型超时连接断开" in d["error_msg"]
        assert d["steps"][0]["status"] == "approved"
        assert d["steps"][1]["status"] == "failed"

        # 重跑 retry
        retry_res = client.post(f"/api/workflows/runs/{run_id}/retry")
        assert retry_res.status_code == 200
        assert retry_res.json()["from_step"] == 1

        d2 = _wait_run_status(client, run_id, target_statuses=("done",))
        assert d2["status"] == "done"
        assert d2["steps"][1]["status"] == "approved"
        assert d2["steps"][1]["output"] == "成功回复3"


def test_cancel_running_workflow(client):
    """手动取消工作流置 cancelled。"""
    work, volume, chapter = make_wvc(client, "取消测试作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "待取消流",
        "steps": [{"title": "步0", "input_mode": "none", "requires_review": 1}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("产出", 50)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("awaiting_review",))

        cancel_res = client.post(f"/api/workflows/runs/{run_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # 已完成或已取消的不能重跑
        r_retry = client.post(f"/api/workflows/runs/{run_id}/cancel")
        assert r_retry.json()["status"] == "cancelled"


# ==================== 6. 台账与运行历史测试 ====================

def test_ai_tasks_ledger_and_runs_list(client):
    """验证工作流步骤执行时自动记录至 ai_tasks 台账，且 GET /workflows/runs 可分页检索。"""
    work, volume, chapter = make_wvc(client, "台账验证作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "台账记录流",
        "steps": [{"title": "台账测试步", "input_mode": "none", "requires_review": 0}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("台账测试文本", 123)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("done",))

    # 查库校验 ai_tasks
    db = get_db()
    task = db.execute("SELECT * FROM ai_tasks WHERE work_id=? AND task_type='workflow_step' ORDER BY id DESC", (work["id"],)).fetchone()
    assert task is not None
    assert "工作流步骤 · 台账测试步" in task["input_summary"]
    assert task["status"] == "done"
    assert task["token_used"] == 123

    # 验证 GET /workflows/runs 历史列表
    hist = client.get("/api/workflows/runs", params={"workflow_id": wf["id"]}).json()
    assert len(hist) >= 1
    assert hist[0]["id"] == run_id
    assert hist[0]["workflow_name"] == "台账记录流"


def test_workflow_list_filters(client):
    """测试工作流列表 scope 与 enabled 过滤。"""
    c = client.post("/api/workflows", json={"name": "项目局部流", "scope": "work", "steps": []}).json()
    wf_id = c["id"]

    all_wfs = client.get("/api/workflows").json()
    assert any(w["id"] == wf_id for w in all_wfs)

    work_wfs = client.get("/api/workflows", params={"scope": "work"}).json()
    assert all(w["scope"] == "work" for w in work_wfs)
    assert any(w["id"] == wf_id for w in work_wfs)

    global_wfs = client.get("/api/workflows", params={"scope": "global"}).json()
    assert not any(w["id"] == wf_id for w in global_wfs)

    # 禁用后按 enabled=0 过滤
    client.patch(f"/api/workflows/{wf_id}", json={"enabled": 0})
    disabled_wfs = client.get("/api/workflows", params={"enabled": 0}).json()
    assert any(w["id"] == wf_id for w in disabled_wfs)
    enabled_wfs = client.get("/api/workflows", params={"enabled": 1}).json()
    assert not any(w["id"] == wf_id for w in enabled_wfs)


def test_workflow_get_404(client):
    """不存在的工作流查询返回 404。"""
    res = client.get("/api/workflows/999999")
    assert res.status_code == 404
    assert "不存在" in res.json()["detail"]


def test_workflow_patch_empty_name_error(client):
    """工作流重命名为空时抛出 400。"""
    c = client.post("/api/workflows", json={"name": "原名", "steps": []}).json()
    res = client.patch(f"/api/workflows/{c['id']}", json={"name": "   "})
    assert res.status_code == 400
    assert "不能为空" in res.json()["detail"]


def test_replace_steps_empty_steps(client):
    """全量清空步骤支持清空至 0 步。"""
    c = client.post("/api/workflows", json={
        "name": "步骤清空测试",
        "steps": [{"title": "原步骤", "input_mode": "none"}]
    }).json()
    res = client.put(f"/api/workflows/{c['id']}/steps", json={"steps": []})
    assert res.status_code == 200
    assert len(res.json()["steps"]) == 0


def test_start_run_with_disabled_step_skill(client):
    """启动运行时，若包含已禁用的 Skill，拦截报错 400。"""
    work, volume, chapter = make_wvc(client, "禁用技能拦截作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    sk = client.post("/api/skills", json={
        "name": "will-disable-skill", "title": "即将禁用", "description": "说明"
    }).json()
    wf = client.post("/api/workflows", json={
        "name": "含禁用技能工作流",
        "steps": [{"title": "执行技能", "skill_id": sk["id"], "input_mode": "none"}]
    }).json()

    # 禁用 Skill
    client.patch(f"/api/skills/{sk['id']}", json={"enabled": 0})
    res = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]})
    assert res.status_code == 400
    assert "已被禁用" in res.json()["detail"]


def test_run_detail_404(client):
    """不存在的运行实例返回 404。"""
    res = client.get("/api/workflows/runs/999999")
    assert res.status_code == 404
    assert "不存在" in res.json()["detail"]


def test_review_gate_invalid_action(client):
    """人工确认闸非法 action 拦截 400。"""
    work, volume, chapter = make_wvc(client, "非法动作作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "非法动作流",
        "steps": [{"title": "步0", "input_mode": "none", "requires_review": 1}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("内容", 10)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("awaiting_review",))

        res = client.post(f"/api/workflows/runs/{run_id}/steps/0/review", json={"action": "invalid_action"})
        assert res.status_code == 400
        assert "非法的确认操作" in res.json()["detail"]


def test_review_gate_step_not_awaiting(client):
    """对尚未开始或已经完成的步骤调用 review 拦截 400。"""
    work, volume, chapter = make_wvc(client, "未待确认步骤作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "多步待确认流",
        "steps": [
            {"title": "步0", "input_mode": "none", "requires_review": 1},
            {"title": "步1", "input_mode": "none", "requires_review": 1}
        ]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("内容", 10)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("awaiting_review",))

        # 尝试 review 第 1 步（目前还是 pending 状态）
        res = client.post(f"/api/workflows/runs/{run_id}/steps/1/review", json={"action": "approve"})
        assert res.status_code == 400
        assert "不在待确认状态" in res.json()["detail"]


def test_run_retry_non_failed_error(client):
    """仅 failed 或 cancelled 状态可重试，对已完成或运行中重试拦截 400。"""
    work, volume, chapter = make_wvc(client, "非失败重试作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "顺畅流",
        "steps": [{"title": "步0", "input_mode": "none", "requires_review": 0}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("内容", 10)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("done",))

        res = client.post(f"/api/workflows/runs/{run_id}/retry")
        assert res.status_code == 400
        assert "仅失败或已中止" in res.json()["detail"]


def test_cancel_completed_run_idempotent(client):
    """对已完成的 run 调用 cancel 幂等返回其原有状态。"""
    work, volume, chapter = make_wvc(client, "已完成取消作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "已完成取消流",
        "steps": [{"title": "步0", "input_mode": "none", "requires_review": 0}]
    }).json()

    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = ("内容", 10)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        _wait_run_status(client, run_id, target_statuses=("done",))

        res = client.post(f"/api/workflows/runs/{run_id}/cancel")
        assert res.status_code == 200
        assert res.json()["status"] == "done"


def test_step_output_chars_cap(client):
    """单步输出超长时截断至 MAX_OUTPUT_CHARS（32000字）。"""
    from app.workflow_engine import MAX_OUTPUT_CHARS
    work, volume, chapter = make_wvc(client, "超长输出作品")
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})

    wf = client.post("/api/workflows", json={
        "name": "超长输出流",
        "steps": [{"title": "超长步", "input_mode": "none", "requires_review": 0}]
    }).json()

    huge_text = "字" * 40000
    with patch("app.workflow_engine.chat", new_callable=AsyncMock) as m:
        m.return_value = (huge_text, 1000)
        run_id = client.post(f"/api/workflows/{wf['id']}/runs", json={"work_id": work["id"]}).json()["run_id"]
        d = _wait_run_status(client, run_id, target_statuses=("done",))
        assert len(d["steps"][0]["output"]) == MAX_OUTPUT_CHARS


def test_builtin_workflows_skill_ids_resolved(client):
    """验证所有内置工作流中的步骤都已正确解析绑定到内置 Skill。"""
    res = client.get("/api/workflows").json()
    for wf in res:
        if wf["builtin"]:
            detail = client.get(f"/api/workflows/{wf['id']}").json()
            for s in detail["steps"]:
                assert s["skill_id"] is not None
                assert s["skill_title"] != ""


# -*- coding: utf-8 -*-
def test_sync_workflow_assets(client):
    # 1. 创建一部测试作品
    resp = client.post("/api/works", json={"title": "资产同步测试作品"})
    assert resp.status_code == 201
    work_id = resp.json()["id"]

    # 2. 模拟一个运行中的工作流
    # 创建工作流
    wf_res = client.post("/api/workflows", json={
        "name": "资产同步工作流",
        "steps": [
            {"title": "立项与设定", "input_mode": "none", "requires_review": 1}
        ]
    })
    wf_id = wf_res.json()["id"]

    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})
    run_res = client.post(f"/api/workflows/{wf_id}/runs", json={"work_id": work_id})
    assert run_res.status_code == 201, run_res.text
    run_id = run_res.json()["run_id"]

    # 模拟步骤输出文本
    step_output = """
    #### 方向 1：【古典仙侠】《逆命天尊》林渊（性格孤僻）
    * 核心看点：夺天地造化，掌生死因果
    * 【道具】断渊残剑（品阶残缺）
    * 【势力】青云宗：领袖宗门
    * 林渊 -> 青云宗 (叛出宗门)
    * 【伏笔】青铜残片的真实来历：牵扯上古仙魔大战隐秘

    ### 规则一：死者因果律
    因果代偿不可避免。

    第1卷：绝处逢生
    第1章：江上捞尸
    """
    from app.db import get_db
    db = get_db()
    db.execute("UPDATE workflow_run_steps SET output=?, status='awaiting_review' WHERE run_id=? AND step_seq=0", (step_output, run_id))
    db.commit()

    # 3. 测试自动提取接口
    ext_res = client.get(f"/api/workflows/runs/{run_id}/steps/0/extracted-assets")
    assert ext_res.status_code == 200
    assets = ext_res.json()["assets"]
    assert len(assets["entities"]) >= 3
    assert len(assets["relations"]) >= 1
    assert len(assets["outline_nodes"]) >= 2
    assert len(assets["notes"]) >= 1
    assert assets["work_info"]["title"] == "逆命天尊"
    assert "古典仙侠" in assets["work_info"]["genre"]
    assert len(assets["foreshadows"]) >= 1

    # 4. 测试同步入库接口
    sync_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/sync-assets", json=assets)
    assert sync_res.status_code == 200
    summary = sync_res.json()["summary"]
    assert summary["work_info_updated"] is True
    assert summary["entities_added"] >= 3
    assert summary["relations_added"] >= 1
    assert summary["outlines_added"] >= 2
    assert summary["foreshadows_added"] >= 1
    assert summary["notes_added"] == 0

    # 5. 校验数据库各表是否真正写入！
    ents = db.execute("SELECT name, category FROM entities WHERE work_id=?", (work_id,)).fetchall()
    ent_names = [e["name"] for e in ents]
    assert "林渊" in ent_names
    assert "断渊残剑" in ent_names
    assert "青云宗" in ent_names

    rels = db.execute("SELECT label FROM entity_relations WHERE work_id=?", (work_id,)).fetchall()
    assert len(rels) >= 1
    assert rels[0]["label"] == "叛出宗门"

    outlines = db.execute("SELECT title, parent_id FROM outline_nodes WHERE work_id=?", (work_id,)).fetchall()
    out_titles = [o["title"] for o in outlines]
    assert "第1卷 绝处逢生" in out_titles
    assert "第1章 江上捞尸" in out_titles

    # 验证灵感便签功能彻底清除，notes 表已物理移除且绝不污染写入
    notes_table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'").fetchone()
    assert notes_table is None

    # 校验作品立项信息与伏笔库
    w = db.execute("SELECT title, genre FROM works WHERE id=?", (work_id,)).fetchone()
    assert w["title"] == "逆命天尊"
    assert "古典仙侠" in w["genre"]

    fs = db.execute("SELECT title FROM foreshadows WHERE work_id=?", (work_id,)).fetchall()
    assert len(fs) >= 1
    assert any("青铜残片" in r["title"] for r in fs)

    print("ALL 7 ASSET SYNC INVARIANTS VERIFIED!")