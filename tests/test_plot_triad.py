# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""剧情三件套联动与设定关系图谱回归测试 (v1.9.0)"""
import pytest
from app import db as db_module


def test_plot_triad_and_entity_relations(client):
    # 1. 创建测试作品
    res = client.post("/api/works", json={"title": "三道演义", "description": "剧情中枢测试作品"})
    assert res.status_code == 201
    work_id = res.json()["id"]

    # 2. 创建大纲节点
    res_node1 = client.post(f"/api/works/{work_id}/outline", json={"title": "青云立誓", "synopsis": "少年拜山立志"})
    assert res_node1.status_code == 201
    node1_id = res_node1.json()["id"]

    res_node2 = client.post(f"/api/works/{work_id}/outline", json={"title": "试炼夺魁", "synopsis": "宗门大比"})
    assert res_node2.status_code == 201
    node2_id = res_node2.json()["id"]

    # 3. 关联剧情时间线事件至 node1
    res_te = client.post(f"/api/works/{work_id}/timeline", json={
        "time_label": "永泰元年·春",
        "event": "主角于通天峰拜入青云门",
        "characters": "主角、师尊",
        "outline_node_id": node1_id,
    })
    assert res_te.status_code == 201
    te_data = res_te.json()
    assert te_data["outline_node_id"] == node1_id
    assert te_data["outline_title"] == "青云立誓"

    # 4. 关联伏笔至 node1
    res_fs = client.post(f"/api/works/{work_id}/foreshadows", json={
        "title": "师尊腰间的半枚玉佩",
        "content": "玉佩残缺处刻有血色暗纹",
        "status": "planted",
        "outline_node_id": node1_id,
    })
    assert res_fs.status_code == 201
    fs_data = res_fs.json()
    assert fs_data["outline_node_id"] == node1_id
    assert fs_data["outline_title"] == "青云立誓"

    # 5. 检查大纲树聚合统计 (timeline_count, foreshadow_count)
    res_tree = client.get(f"/api/works/{work_id}/outline")
    assert res_tree.status_code == 200
    tree = res_tree.json()
    n1 = next(n for n in tree if n["id"] == node1_id)
    n2 = next(n for n in tree if n["id"] == node2_id)
    assert n1["timeline_count"] == 1
    assert n1["foreshadow_count"] == 1
    assert n2["timeline_count"] == 0
    assert n2["foreshadow_count"] == 0

    # 6. 检查节点名下剧情聚合端点 GET /outline/nodes/{node_id}/plot-items
    res_items = client.get(f"/api/works/{work_id}/outline/nodes/{node1_id}/plot-items")
    assert res_items.status_code == 200
    items = res_items.json()
    assert items["node_id"] == node1_id
    assert len(items["timeline_events"]) == 1
    assert items["timeline_events"][0]["event"] == "主角于通天峰拜入青云门"
    assert len(items["foreshadows"]) == 1
    assert items["foreshadows"][0]["title"] == "师尊腰间的半枚玉佩"

    # 7. 更新伏笔和时间线的大纲归属 (移至 node2)
    fs_id = fs_data["id"]
    te_id = te_data["id"]
    res_fs_patch = client.patch(f"/api/foreshadows/{fs_id}", json={"outline_node_id": node2_id})
    assert res_fs_patch.status_code == 200
    assert res_fs_patch.json()["outline_node_id"] == node2_id

    res_te_patch = client.patch(f"/api/timeline/{te_id}", json={"outline_node_id": node2_id})
    assert res_te_patch.status_code == 200
    assert res_te_patch.json()["outline_node_id"] == node2_id

    # 8. 删除 node2 节点，验证外键置空（SET NULL）保护
    del_node = client.delete(f"/api/outline/{node2_id}")
    assert del_node.status_code == 204

    # 检查数据库中事件和伏笔依然存在，且 outline_node_id 变为 None
    db = db_module.get_db()
    te_row = db.execute("SELECT outline_node_id FROM timeline_events WHERE id=?", (te_id,)).fetchone()
    fs_row = db.execute("SELECT outline_node_id FROM foreshadows WHERE id=?", (fs_id,)).fetchone()
    assert te_row is not None and te_row[0] is None
    assert fs_row is not None and fs_row[0] is None

    # 9. 万象谱实体与人物关系图谱自动同步测试
    res_e1 = client.post(f"/api/works/{work_id}/entities", json={
        "category": "character",
        "name": "林惊羽",
        "content": "惊才绝艳的少年剑客",
        "tags": "同门,天才",
    })
    assert res_e1.status_code == 201
    e1_id = res_e1.json()["id"]

    res_e2 = client.post(f"/api/works/{work_id}/entities", json={
        "category": "character",
        "name": "张小凡",
        "content": "质朴坚韧的少年",
        "tags": "同门,发小",
        "relations": [
            {"to_id": e1_id, "label": "草庙村发小"}
        ],
    })
    assert res_e2.status_code == 201
    e2_id = res_e2.json()["id"]

    # 验证关系图谱 API 是否自动包含该连线
    res_graph = client.get(f"/api/works/{work_id}/graph")
    assert res_graph.status_code == 200
    graph = res_graph.json()
    assert any(ed["from_id"] == e2_id and ed["to_id"] == e1_id and ed["label"] == "草庙村发小" for ed in graph["edges"])

    # 验证获取实体详情时带上 relations
    res_get_e2 = client.get(f"/api/entities/{e2_id}")
    assert res_get_e2.status_code == 200
    assert len(res_get_e2.json().get("relations", [])) == 1
    assert res_get_e2.json()["relations"][0]["to_name"] == "林惊羽"

    # 验证 PATCH 更新关系
    res_patch_e2 = client.patch(f"/api/entities/{e2_id}", json={
        "relations": [
            {"to_id": e1_id, "label": "生死之交"}
        ]
    })
    assert res_patch_e2.status_code == 200
    assert res_patch_e2.json()["relations"][0]["label"] == "生死之交"


def test_plot_triad_frontend_assets():
    """验证前端各页面已实现剧情脉络三位一体与关系网络联动"""
    from pathlib import Path
    
    # outline.js
    outline_js = Path("static/js/pages/outline.js").read_text(encoding="utf-8")
    assert "renderPlotTriadSection" in outline_js
    assert "plot-items" in outline_js
    assert "timeline_count" in outline_js
    assert "foreshadow_count" in outline_js
    assert "addTimelineEventModal" in outline_js
    assert "addForeshadowModal" in outline_js
    
    # timeline.js
    timeline_js = Path("static/js/pages/timeline.js").read_text(encoding="utf-8")
    assert "outlineNodes" in timeline_js
    assert "outline_node_id" in timeline_js
    assert "outlineSelect" in timeline_js
    
    # board.js
    board_js = Path("static/js/pages/board.js").read_text(encoding="utf-8")
    assert "outlineNodes" in board_js
    assert "outline_node_id" in board_js
    assert "outlineSel" in board_js
    
    # entities.js
    entities_js = Path("static/js/pages/entities.js").read_text(encoding="utf-8")
    assert "relationsSection" in entities_js
    assert "currentRelations" in entities_js
    assert "renderRelationsList" in entities_js
