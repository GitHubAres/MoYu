# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""seed/demo 幂等与 outline 基本链路。"""


def test_seed_demo_idempotent(client):
    r = client.post("/api/seed/demo")
    assert r.status_code == 201
    first = r.json()
    assert first["ok"] is True
    work_id = first["work_id"]

    # 第二次调用幂等返回 ok=false，不产生重复作品
    r = client.post("/api/seed/demo")
    assert r.status_code == 201
    second = r.json()
    assert second["ok"] is False
    assert second["work_id"] == work_id

    works = client.get("/api/works", params={"q": "太虚仙途"}).json()
    assert len(works) == 1

    # 演示数据完整：2 卷 2 章 + 大纲 + 设定 + 伏笔 + 便签
    tree = client.get(f"/api/works/{work_id}/tree").json()
    assert len(tree) == 2
    assert sum(len(v["chapters"]) for v in tree) == 2

    outline = client.get(f"/api/works/{work_id}/outline").json()
    assert len(outline) == 2
    assert outline[0]["children"][0]["chapter_title"] == "第一章 剑斩云霄"

    entities = client.get(f"/api/works/{work_id}/entities").json()
    assert {e["name"] for e in entities} >= {"叶临渊", "陆清雪", "天剑宗", "龙渊剑"}

    foreshadows = client.get(f"/api/works/{work_id}/foreshadows").json()
    assert {f["status"] for f in foreshadows} == {"planted", "pending"}

    notes = client.get("/api/notes", params={"work_id": work_id}).json()
    assert any("文明并不是因为熄灭而寒冷" in n["content"] for n in notes)


def test_outline_crud_and_enum(client):
    from conftest import make_work

    w = make_work(client, "大纲测试")
    r = client.post(f"/api/works/{w['id']}/outline", json={"title": "卷一", "synopsis": "起"})
    assert r.status_code == 201
    root = r.json()
    assert root["status"] == "pending"

    assert client.post(f"/api/works/{w['id']}/outline",
                       json={"title": "x", "status": "wrong"}).status_code == 400

    child = client.post(f"/api/works/{w['id']}/outline", json={
        "title": "第一章", "parent_id": root["id"], "status": "focus"}).json()
    assert child["parent_id"] == root["id"]

    # 从节点建章并自动关联
    r = client.post(f"/api/outline/{child['id']}/create-chapter")
    assert r.status_code == 201
    chapter = r.json()
    assert chapter["title"] == "第一章"
    # 已关联后不可重复建章
    assert client.post(f"/api/outline/{child['id']}/create-chapter").status_code == 400

    tree = client.get(f"/api/works/{w['id']}/outline").json()
    assert tree[0]["children"][0]["chapter_id"] == chapter["id"]

    # 成环校验：父节点不能挂到子孙下
    assert client.patch(f"/api/outline/{root['id']}",
                        json={"parent_id": child["id"]}).status_code == 400
    assert client.patch(f"/api/outline/{child['id']}",
                        json={"parent_id": child["id"]}).status_code == 400

    # 删除根节点级联子节点
    assert client.delete(f"/api/outline/{root['id']}").status_code == 204
    assert client.get(f"/api/works/{w['id']}/outline").json() == []
