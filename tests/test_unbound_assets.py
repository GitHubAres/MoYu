# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
import pytest
from conftest import make_wvc
import app.db as db_module
from app.services.asset_hub import upsert_foreshadow, upsert_timeline_event


def test_bound_chapter_deleted_retains_outline_aggregation(client):
    """R3-4 断言 1：章节已绑节点，双键写入产物，删章后大纲节点聚合中仍可见产物"""
    w, v, chap = make_wvc(client, "测试已绑节点删章")
    work_id = w["id"]
    node = client.post(f"/api/works/{work_id}/outline", json={"title": "第一章·初入宗门"}).json()
    node_id = node["id"]
    client.post(f"/api/outline/{node_id}/link-chapter", json={"chapter_id": chap["id"]})

    db = db_module.get_db()
    fs = upsert_foreshadow(
        db=db,
        work_id=work_id,
        title="神秘玉佩",
        content="贴身佩戴的玉佩",
        chapter_id=chap["id"],
        outline_node_id=node_id,
    )
    te = upsert_timeline_event(
        db=db,
        work_id=work_id,
        time_label="开元初年",
        event="入门考核",
        chapter_id=chap["id"],
        outline_node_id=node_id,
    )
    assert fs["id"] is not None
    assert te["id"] is not None

    # 删除章节
    del_res = client.delete(f"/api/chapters/{chap['id']}")
    assert del_res.status_code == 200

    # 大纲聚合中仍可见
    items = client.get(f"/api/works/{work_id}/outline/nodes/{node_id}/plot-items").json()
    assert any(f["title"] == "神秘玉佩" for f in items["foreshadows"])
    assert any(e["event"] == "入门考核" for e in items["timeline_events"])


def test_unbound_chapter_deleted_assets_become_unbound(client):
    """R3-4 断言 2：章节未绑节点，删章后产物两键皆空，全量接口仍可见，且 unbound-assets 接口能查到"""
    w, v, chap = make_wvc(client, "测试未绑节点删章")
    work_id = w["id"]

    db = db_module.get_db()
    fs = upsert_foreshadow(
        db=db,
        work_id=work_id,
        title="无归属伏笔",
        content="散落的线索",
        chapter_id=chap["id"],
        outline_node_id=None,
    )
    te = upsert_timeline_event(
        db=db,
        work_id=work_id,
        time_label="无定时间",
        event="无定事件",
        chapter_id=chap["id"],
        outline_node_id=None,
    )

    # 删除章节
    del_res = client.delete(f"/api/chapters/{chap['id']}")
    assert del_res.status_code == 200

    # 全量列表仍可见
    tls = client.get(f"/api/works/{work_id}/timeline").json()
    assert any(e["id"] == te["id"] for e in tls)

    fss = client.get(f"/api/works/{work_id}/foreshadows").json()
    assert any(f["id"] == fs["id"] for f in fss)

    # 未归属查询接口
    unbound_res = client.get(f"/api/works/{work_id}/unbound-assets")
    assert unbound_res.status_code == 200
    unbound_data = unbound_res.json()
    assert any(f["id"] == fs["id"] for f in unbound_data.get("foreshadows", []))
    assert any(e["id"] == te["id"] for e in unbound_data.get("timeline_events", []))


def test_rebind_unbound_assets_to_outline_node(client):
    """R3-4 断言 3：调用 rebind 接口将未归属产物重绑至节点，双键一致并出现在大纲聚合中"""
    w, v, chap = make_wvc(client, "测试重绑产物")
    work_id = w["id"]

    db = db_module.get_db()
    fs = upsert_foreshadow(
        db=db,
        work_id=work_id,
        title="待归位伏笔",
        content="漂泊的伏笔",
        chapter_id=chap["id"],
        outline_node_id=None,
    )
    te = upsert_timeline_event(
        db=db,
        work_id=work_id,
        time_label="待归位年",
        event="待归位事件",
        chapter_id=chap["id"],
        outline_node_id=None,
    )

    # 删章
    client.delete(f"/api/chapters/{chap['id']}")

    # 新放大纲节点
    new_node = client.post(f"/api/works/{work_id}/outline", json={"title": "第二章·归宿"}).json()
    new_node_id = new_node["id"]

    # 重绑
    rebind_res = client.post(f"/api/works/{work_id}/unbound-assets/rebind", json={
        "foreshadow_ids": [fs["id"]],
        "timeline_event_ids": [te["id"]],
        "outline_node_id": new_node_id,
    })
    assert rebind_res.status_code == 200
    r_json = rebind_res.json()
    assert r_json.get("foreshadows_rebound") == 1
    assert r_json.get("timeline_events_rebound") == 1

    # 重绑后在节点聚合中可见
    items = client.get(f"/api/works/{work_id}/outline/nodes/{new_node_id}/plot-items").json()
    assert any(f["id"] == fs["id"] for f in items["foreshadows"])
    assert any(e["id"] == te["id"] for e in items["timeline_events"])
