# -*- coding: utf-8 -*-
"""P0 阶段止血回归测试：大纲事件、双键补全、聚合读侧放宽、回流幂等、删除知情"""
import pytest
from app import db as db_module
from app.services.plot_service import batch_sync_triad_assets
from app.services.asset_hub import aggregate_for_node
from conftest import make_wvc


def test_import_events_derives_outline_node_id(client):
    """P0-2 断言 ②：整书导入事件自动通过 chapter_id 反查并补齐 outline_node_id"""
    w, v, chap = make_wvc(client, "导入测试作品")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "第一章"}).json()
    client.post(f"/api/outline/{node['id']}/link-chapter", json={"chapter_id": chap["id"]})

    # 导入事件仅传 chapter_id
    res = client.post("/api/timeline/import", json={
        "work_id": work_id,
        "events": [
            {"time_label": "年初", "event": "宗门大选", "characters": "主角", "chapter_id": chap["id"]}
        ]
    })
    assert res.status_code == 201
    events = res.json()
    assert len(events) == 1
    assert events[0]["outline_node_id"] == node["id"]
    assert events[0]["outline_title"] == "第一章"


def test_plot_triad_aggregate_includes_chapter_only_assets(client):
    """P0-3 断言 ③：聚合读侧放宽，直接绑定节点 OR 绑定该节点所属章节的数据均能查出"""
    w, v, chap = make_wvc(client, "放宽聚合测试作品")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "第一章"}).json()
    client.post(f"/api/outline/{node['id']}/link-chapter", json={"chapter_id": chap["id"]})

    db = db_module.get_db()
    # 模拟历史数据：只绑定了 chapter_id，outline_node_id 为 NULL
    db.execute(
        "INSERT INTO timeline_events(work_id, chapter_id, outline_node_id, time_label, event, characters, sort_order) VALUES (?, ?, NULL, ?, ?, ?, 1)",
        (work_id, chap["id"], "往昔", "仅绑章节的旧事件", "路人")
    )
    db.execute(
        "INSERT INTO foreshadows(work_id, chapter_id, outline_node_id, title, content, status) VALUES (?, ?, NULL, ?, ?, 'planted')",
        (work_id, chap["id"], "仅绑章节的旧伏笔", "古旧密卷")
    )
    db.commit()

    # 1. API 读侧：GET /works/{work_id}/outline/nodes/{node_id}/plot-items
    items = client.get(f"/api/works/{work_id}/outline/nodes/{node['id']}/plot-items").json()
    assert any(e["event"] == "仅绑章节的旧事件" for e in items["timeline_events"])
    assert any(f["title"] == "仅绑章节的旧伏笔" for f in items["foreshadows"])

    # 2. 领域服务读侧：get_node_plot_triad
    triad = aggregate_for_node(db, work_id, node["id"])
    assert any(e["event"] == "仅绑章节的旧事件" for e in triad["timeline_events"])
    assert any(f["title"] == "仅绑章节的旧伏笔" for f in triad["foreshadows"])


def test_batch_sync_triad_assets_idempotent(client):
    """P0-4 断言 ④：工作流资产回流幂等，重复同步不复制时间线事件与伏笔"""
    w, v, chap = make_wvc(client, "幂等回流测试作品")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "第一章"}).json()
    client.post(f"/api/outline/{node['id']}/link-chapter", json={"chapter_id": chap["id"]})

    db = db_module.get_db()
    assets = {
        "timeline_events": [
            {"time_label": "正午", "event": "秘境开启夺宝", "characters": "林天", "chapter_id": chap["id"], "outline_node_id": node["id"]}
        ],
        "foreshadows": [
            {"title": "残缺古符", "content": "符文蕴含雷电", "status": "planted", "chapter_id": chap["id"], "outline_node_id": node["id"]}
        ],
        "outline_nodes": [
            {"title": "子节点·探秘", "synopsis": "探索洞府", "parent_id": node["id"]}
        ]
    }

    # 第一次同步
    stats1 = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=assets["timeline_events"],
        foreshadows=assets["foreshadows"],
        outline_nodes=assets["outline_nodes"],
    )
    assert stats1["timeline_events_added"] == 1
    assert stats1["foreshadows_added"] == 1
    assert stats1["outline_nodes_added"] == 1

    # 第二次重复同步完全相同的资产
    stats2 = batch_sync_triad_assets(
        db=db,
        work_id=work_id,
        timeline_events=assets["timeline_events"],
        foreshadows=assets["foreshadows"],
        outline_nodes=assets["outline_nodes"],
    )
    assert stats2["timeline_events_added"] == 0
    assert stats2["foreshadows_added"] == 0
    assert stats2["outline_nodes_added"] == 0


def test_delete_chapter_returns_impact_and_detaches(client):
    """P0-5 断言 ⑤：删除章节返回影响面统计，且原本挂在该章节的伏笔/事件/节点被安全解绑而非孤儿化"""
    w, v, chap = make_wvc(client, "删除影响面测试作品")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "大纲节点"}).json()
    client.post(f"/api/outline/{node['id']}/link-chapter", json={"chapter_id": chap["id"]})
    te = client.post(f"/api/works/{work_id}/timeline", json={"event": "章节事件", "chapter_id": chap["id"]}).json()
    fs = client.post(f"/api/works/{work_id}/foreshadows", json={"title": "章节伏笔", "chapter_id": chap["id"]}).json()

    # 查询影响面 API
    impact = client.get(f"/api/chapters/{chap['id']}/delete-impact").json()
    assert impact["total"] >= 3
    assert impact["foreshadows"] >= 1
    assert impact["timeline_events"] >= 1
    assert impact["outline_nodes"] >= 1

    # 执行删除，响应体包含影响面
    del_res = client.delete(f"/api/chapters/{chap['id']}")
    assert del_res.status_code == 200
    res_data = del_res.json()
    assert res_data["ok"] is True
    assert res_data["impact"]["total"] >= 3

    # 验证数据库中章节已删除，但产物已脱绑（chapter_id 为 NULL）
    db = db_module.get_db()
    assert db.execute("SELECT id FROM chapters WHERE id=?", (chap["id"],)).fetchone() is None
    te_row = db.execute("SELECT chapter_id FROM timeline_events WHERE id=?", (te["id"],)).fetchone()
    fs_row = db.execute("SELECT chapter_id FROM foreshadows WHERE id=?", (fs["id"],)).fetchone()
    node_row = db.execute("SELECT chapter_id FROM outline_nodes WHERE id=?", (node["id"],)).fetchone()
    assert te_row[0] is None
    assert fs_row[0] is None
    assert node_row[0] is None


def test_p0_1_outline_timeline_events_endpoint(client):
    """P0-1 断言：outline.js 修复 404，调用 POST /works/{work_id}/timeline 可成功写入事件并回显大纲节点"""
    from pathlib import Path
    outline_js = Path("static/js/pages/outline.js").read_text(encoding="utf-8")
    assert "/works/${workId}/timeline/events" not in outline_js
    assert "/works/${workId}/timeline" in outline_js

    w, v, chap = make_wvc(client, "大纲事件端点测试作品")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "事件挂接节点"}).json()

    # outline.js 的 payload
    res = client.post(f"/api/works/{work_id}/timeline", json={
        "time_label": "正月初五",
        "event": "仙门比武",
        "characters": "主角、宿敌",
        "chapter_id": chap["id"],
        "outline_node_id": node["id"],
    })
    assert res.status_code == 201
    ev = res.json()
    assert ev["outline_node_id"] == node["id"]
    assert ev["chapter_id"] == chap["id"]
    assert ev["outline_title"] == "事件挂接节点"
