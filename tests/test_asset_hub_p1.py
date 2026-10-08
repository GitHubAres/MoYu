# -*- coding: utf-8 -*-
"""P1 阶段收口验收测试：AssetHub 契约、裸 INSERT 禁令守护、聚合唯一性、多对一预警、notes 清除"""
from pathlib import Path
import pytest
from app import db as db_module
from app.services.asset_hub import (
    resolve_binding,
    upsert_foreshadow,
    upsert_timeline_event,
    aggregate_for_node,
    aggregate_for_chapter,
    detach_chapter,
)
from conftest import make_wvc


def test_asset_hub_single_insert_entry_guard():
    """P3-3 ⑥：全库 INSERT INTO foreshadows / timeline_events 只存在于 asset_hub.py"""
    app_dir = Path("app")
    violations = []
    for py_path in app_dir.rglob("*.py"):
        if py_path.name == "asset_hub.py":
            continue
        content = py_path.read_text(encoding="utf-8")
        if "INSERT INTO foreshadows" in content or "INSERT INTO timeline_events" in content:
            violations.append(str(py_path))
    assert not violations, f"发现非 AssetHub 的裸 INSERT: {violations}"


def test_plot_service_no_duplicate_get_node_plot_triad():
    """P1-3 读侧收口：plot_service.py 中重复的 get_node_plot_triad 已被删除"""
    ps_content = Path("app/services/plot_service.py").read_text(encoding="utf-8")
    assert "def get_node_plot_triad" not in ps_content


def test_notes_table_is_completely_dropped():
    """C-4 清洗验证：数据库中 notes 表已被彻底移除"""
    db = db_module.get_db()
    row = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'").fetchone()
    assert row is None


def test_workflows_js_no_dead_notes_field():
    """C-5 清洗验证：workflows.js 中死字段 notes: [] 已被删除"""
    wf_js = Path("static/js/pages/workflows.js").read_text(encoding="utf-8")
    assert "notes: []" not in wf_js


def test_asset_hub_binding_derivation_and_upsert(client):
    """P1-1 & P1-2：AssetHub 双键互派生与幂等写入"""
    w, v, c = make_wvc(client, "中枢契约测试作品")
    work_id = w["id"]
    n = client.post(f"/api/works/{work_id}/outline", json={"title": "核心主线"}).json()
    client.post(f"/api/outline/{n['id']}/link-chapter", json={"chapter_id": c["id"]})

    db = db_module.get_db()

    # 1. 仅传 outline_node_id，自动补齐 chapter_id
    chap_id, node_id = resolve_binding(db, work_id, outline_node_id=n["id"])
    assert chap_id == c["id"]
    assert node_id == n["id"]

    # 2. 仅传 chapter_id，自动补齐 outline_node_id
    chap_id2, node_id2 = resolve_binding(db, work_id, chapter_id=c["id"])
    assert chap_id2 == c["id"]
    assert node_id2 == n["id"]

    # 3. 幂等写入时间线事件
    ev1 = upsert_timeline_event(db, work_id, "宿命对决", time_label="月圆之夜", outline_node_id=n["id"])
    assert ev1["_is_new"] is True
    assert ev1["chapter_id"] == c["id"]

    # 重复写入相同事件 -> 幂等复用，不生成新行
    ev2 = upsert_timeline_event(db, work_id, "宿命对决", time_label="月圆之夜", outline_node_id=n["id"])
    assert ev2["_is_new"] is False
    assert ev2["id"] == ev1["id"]

    # 4. 幂等写入伏笔
    fs1 = upsert_foreshadow(db, work_id, "幽冥古令", content="令牌微烫", outline_node_id=n["id"])
    assert fs1["_is_new"] is True
    assert fs1["chapter_id"] == c["id"]

    # 重复写入相同伏笔 -> 幂等复用
    fs2 = upsert_foreshadow(db, work_id, "幽冥古令", content="令牌微烫", outline_node_id=n["id"])
    assert fs2["_is_new"] is False
    assert fs2["id"] == fs1["id"]


def test_link_chapter_warning_on_duplicate_binding(client):
    """P1-5：同章节重复绑定时返回警告信息"""
    w, v, c = make_wvc(client, "多对一警告测试作品")
    work_id = w["id"]
    n1 = client.post(f"/api/works/{work_id}/outline", json={"title": "第一回"}).json()
    n2 = client.post(f"/api/works/{work_id}/outline", json={"title": "第二回"}).json()

    # 第一次绑定 -> 成功且无 warning
    r1 = client.post(f"/api/outline/{n1['id']}/link-chapter", json={"chapter_id": c["id"]}).json()
    assert r1.get("warning") is None

    # 第二次将同一章节绑定到另一节点 -> 成功但携带 warning
    r2 = client.post(f"/api/outline/{n2['id']}/link-chapter", json={"chapter_id": c["id"]}).json()
    assert "warning" in r2
    assert "已绑定到大纲节点" in r2["warning"]


def test_aggregate_for_chapter_and_detach(client):
    """P1-1：aggregate_for_chapter 与 detach_chapter"""
    w, v, c = make_wvc(client, "章节聚合与解绑测试作品")
    work_id = w["id"]
    n = client.post(f"/api/works/{work_id}/outline", json={"title": "章节关联节点"}).json()
    client.post(f"/api/outline/{n['id']}/link-chapter", json={"chapter_id": c["id"]})

    db = db_module.get_db()
    upsert_timeline_event(db, work_id, "章节专属事件", outline_node_id=n["id"])
    upsert_foreshadow(db, work_id, "章节专属伏笔", outline_node_id=n["id"])

    # 章节聚合读
    res = aggregate_for_chapter(db, work_id, c["id"])
    assert any(e["event"] == "章节专属事件" for e in res["timeline_events"])
    assert any(f["title"] == "章节专属伏笔" for f in res["foreshadows"])

    # 解绑
    impact = detach_chapter(db, c["id"])
    assert impact["total"] >= 3
    assert impact["timeline_events"] >= 1
    assert impact["foreshadows"] >= 1
    assert impact["outline_nodes"] >= 1
