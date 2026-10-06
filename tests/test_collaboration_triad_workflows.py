# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）开发团队 · MIT
# Licensed under the MIT License. See LICENSE.
"""端到端跨模块协作验收测试：写作工作流 ↔ 剧情脉络三位一体深度联动 (v1.9.1)"""
import pytest
from app.db import get_db
from app.services.context_service import assemble_workflow_context
from app.services.plot_service import get_node_plot_triad


def test_e2e_triad_workflow_collaboration(client):
    # 1. 建立测试作品
    w_res = client.post("/api/works", json={"title": "太虚证道录", "intro": "凡人修仙长篇宏篇巨制"})
    assert w_res.status_code == 201
    work_id = w_res.json()["id"]

    # 2. 建立大纲节点（第10章·剑冢试炼）
    n_res = client.post(f"/api/works/{work_id}/outline", json={
        "title": "第十章·剑冢试炼",
        "synopsis": "林萧进入上古剑冢核心，参悟无名残剑中的上古剑意，遭遇魔宗暗伏探子。",
    })
    assert n_res.status_code == 201
    node_id = n_res.json()["id"]

    # 3. 为该大纲节点预埋一条时间线事件与一条伏笔
    te_pre = client.post(f"/api/works/{work_id}/timeline", json={
        "time_label": "天启三年·秋分",
        "event": "剑冢石门千年封印开启，各大宗门真传齐聚剑冢山下",
        "characters": "林萧、魔宗探子",
        "outline_node_id": node_id,
    })
    assert te_pre.status_code == 201

    fs_pre = client.post(f"/api/works/{work_id}/foreshadows", json={
        "title": "太虚残剑断刃暗纹",
        "content": "林萧无意中发现残剑剑格处刻有神秘宗门云纹",
        "status": "planted",
        "outline_node_id": node_id,
    })
    assert fs_pre.status_code == 201

    # 4. 验证领域服务层上下文装配契约 (assemble_workflow_context)
    db = get_db()
    ctx = assemble_workflow_context(
        db=db,
        work_id=work_id,
        outline_node_id=node_id,
        chapter_text="剑冢之内阴风怒号，碎剑如林。",
        input_mode="merge",
    )
    assert "【目标大纲节点】" in ctx
    assert "第十章·剑冢试炼" in ctx
    assert "林萧进入上古剑冢核心" in ctx
    assert "【已绑定时间线事件】" in ctx
    assert "剑冢石门千年封印开启" in ctx
    assert "【已布局相关伏笔】" in ctx
    assert "太虚残剑断刃暗纹" in ctx

    # 5. 启动工作流并明确绑定大纲节点
    client.patch("/api/settings", json={"values": {"ai_api_key": "mock-key", "ai_model": "mock-model"}})
    wf_res = client.post("/api/workflows", json={
        "name": "细纲与剧情脉络推演流",
        "steps": [
            {"title": "细纲深化与伏笔推演", "input_mode": "chapter", "requires_review": 1}
        ]
    })
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["id"]

    run_res = client.post(f"/api/workflows/{wf_id}/runs", json={
        "work_id": work_id,
        "outline_node_id": node_id,
    })
    assert run_res.status_code == 201
    run_id = run_res.json()["run_id"]

    # 验证运行详情正确携带大纲信息
    run_detail = client.get(f"/api/workflows/runs/{run_id}").json()
    assert run_detail["outline_node_id"] == node_id
    assert run_detail["outline_node_title"] == "第十章·剑冢试炼"

    # 6. 模拟推演输出，包含新时间线事件、新子大纲、新伏笔
    simulated_step_output = """
    #### 剧情推演方案
    【时间线事件】：时间：天启三年·寒露，事件：林萧在洗剑池力破魔宗暗阵斩杀血煞修士，人物：林萧、血煞道人
    【时间线事件】：时间：天启三年·霜降，事件：掌教亲赐太虚真传玉简，众人心服，人物：林萧、玄天道尊

    * 伏笔线索：血煞道人怀中的血灵玉佩暗含幽冥教总坛密印，指向十年后的北境魔祸。
    * 伏笔线索：洗剑池底沉睡的上古剑魂被惊醒，悄然附身于林萧识海。

    第1节：洗剑池决战
    第2节：玉简赐封
    """
    db.execute(
        "UPDATE workflow_run_steps SET output=?, status='awaiting_review' WHERE run_id=? AND step_seq=0",
        (simulated_step_output, run_id),
    )
    db.commit()

    # 7. 提取结构化资产
    ext_res = client.get(f"/api/workflows/runs/{run_id}/steps/0/extracted-assets")
    assert ext_res.status_code == 200
    assets = ext_res.json()["assets"]

    # 验证提取到时间线、伏笔
    assert len(assets["timeline_events"]) >= 2
    assert any("洗剑池力破魔宗暗阵" in e["event"] for e in assets["timeline_events"])
    assert len(assets["foreshadows"]) >= 1

    # 8. 规范采纳同步到作品库 (sync-assets)
    sync_res = client.post(f"/api/workflows/runs/{run_id}/steps/0/sync-assets", json=assets)
    assert sync_res.status_code == 200
    sm = sync_res.json()["summary"]
    assert sm["timeline_events_added"] >= 2
    assert sm["foreshadows_added"] >= 1

    # 9. 跨模块全闭环断言 (大纲树 ↔ 时间线 ↔ 伏笔看板 ↔ 剧情聚合端点)

    # 9.1 大纲树统计与徽章数据联动更新
    tree_res = client.get(f"/api/works/{work_id}/outline").json()
    target_node = next(n for n in tree_res if n["id"] == node_id)
    # 原来有 1 个时间线事件 + 新增至少 2 个 = >= 3
    assert target_node["timeline_count"] >= 3
    # 原来有 1 条伏笔 + 新增至少 1 条 = >= 2
    assert target_node["foreshadow_count"] >= 2

    # 9.2 时间线列表断言：新事件自动绑定 node_id
    tl_res = client.get(f"/api/works/{work_id}/timeline").json()
    new_te = next(e for e in tl_res if "洗剑池力破魔宗暗阵" in e["event"])
    assert new_te["outline_node_id"] == node_id
    assert new_te["outline_title"] == "第十章·剑冢试炼"

    # 9.3 伏笔看板断言：新伏笔自动绑定 node_id
    fs_res = client.get(f"/api/works/{work_id}/foreshadows").json()
    new_fs = next(f for f in fs_res if "血灵玉佩" in f["title"] or "血灵玉佩" in f["content"])
    assert new_fs["outline_node_id"] == node_id
    assert new_fs["outline_title"] == "第十章·剑冢试炼"

    # 9.4 节点专属剧情聚合端点 (plot-items) 一站式验证
    plot_items = client.get(f"/api/works/{work_id}/outline/nodes/{node_id}/plot-items").json()
    assert plot_items["node_id"] == node_id
    assert len(plot_items["timeline_events"]) >= 3
    assert len(plot_items["foreshadows"]) >= 2
