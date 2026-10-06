# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""entities / foreshadows(board) / notes / prompts：CRUD 与枚举校验。"""
from conftest import make_work, make_wvc


# ---------- entities ----------

def test_entity_crud_and_category_enum(client):
    w = make_work(client, "设定库测试")

    r = client.post(f"/api/works/{w['id']}/entities", json={
        "category": "character", "name": "叶临渊",
        "fields_json": {"身份": "执剑长老"}, "tags": "主角,剑修"})
    assert r.status_code == 201
    e = r.json()
    assert e["category"] == "character"
    assert e["fields"] == {"身份": "执剑长老"}
    assert e["archived"] == 0

    # 非法分类被拒
    r = client.post(f"/api/works/{w['id']}/entities",
                    json={"category": "wrong", "name": "x"})
    assert r.status_code == 400
    r = client.patch(f"/api/entities/{e['id']}", json={"category": "wrong"})
    assert r.status_code == 400

    # 更新 + 查询过滤
    r = client.patch(f"/api/entities/{e['id']}",
                     json={"content": "幼时满门被灭", "fields_json": {"身份": "长老", "性格": "沉稳"}})
    assert r.status_code == 200
    assert r.json()["fields"]["性格"] == "沉稳"

    lst = client.get(f"/api/works/{w['id']}/entities", params={"category": "character"}).json()
    assert len(lst) == 1
    assert client.get(f"/api/works/{w['id']}/entities",
                      params={"category": "wrong"}).status_code == 400
    assert client.get(f"/api/works/{w['id']}/entities", params={"q": "满门"}).json()[0]["id"] == e["id"]

    # 归档切换：默认列表不再出现，archived=1 可见
    r = client.post(f"/api/entities/{e['id']}/archive")
    assert r.json()["archived"] == 1
    assert client.get(f"/api/works/{w['id']}/entities").json() == []
    assert len(client.get(f"/api/works/{w['id']}/entities", params={"archived": 1}).json()) == 1

    assert client.delete(f"/api/entities/{e['id']}").status_code == 204
    assert client.get(f"/api/entities/{e['id']}").status_code == 404


def test_entity_chapter_link(client):
    w, v, c = make_wvc(client, "章节关联测试")
    e = client.post(f"/api/works/{w['id']}/entities", json={
        "category": "place", "name": "天剑宗"}).json()

    r = client.post(f"/api/entities/{e['id']}/chapters", json={"chapter_id": c["id"]})
    assert r.status_code == 201
    assert r.json()[0]["id"] == c["id"]

    linked = client.get(f"/api/chapters/{c['id']}/entities").json()
    assert [x["name"] for x in linked] == ["天剑宗"]

    # 其他作品的章节不能关联
    w2, _, c2 = make_wvc(client, "别的作品")
    r = client.post(f"/api/entities/{e['id']}/chapters", json={"chapter_id": c2["id"]})
    assert r.status_code == 400

    assert client.delete(f"/api/entities/{e['id']}/chapters/{c['id']}").status_code == 204
    assert client.get(f"/api/chapters/{c['id']}/entities").json() == []


def test_chapter_entities_workbench_link_and_batch(client):
    w, v, c = make_wvc(client, "工作台实体联动测试")
    e1 = client.post(f"/api/works/{w['id']}/entities", json={
        "category": "character", "name": "叶临渊", "fields_json": {"身份": "主角", "性格": "冷静"},
        "content": "天剑宗第九代首座弟子，剑心通明。"}).json()
    e2 = client.post(f"/api/works/{w['id']}/entities", json={
        "category": "item", "name": "太乙玄晶", "fields_json": {"品阶": "天阶"},
        "content": "产自断龙渊深处的极品铸剑灵晶。"}).json()

    # 从章节侧添加关联 POST /chapters/{c_id}/entities
    r = client.post(f"/api/chapters/{c['id']}/entities", json={"entity_id": e1["id"]})
    assert r.status_code == 201
    list1 = r.json()
    assert len(list1) == 1
    assert list1[0]["name"] == "叶临渊"
    assert list1[0]["fields"]["性格"] == "冷静"
    assert "剑心通明" in list1[0]["content"]

    # 跨作品关联受拒
    w2, _, c2 = make_wvc(client, "外部作品")
    bad = client.post(f"/api/chapters/{c2['id']}/entities", json={"entity_id": e1["id"]})
    assert bad.status_code == 400

    # 批量关联 POST /chapters/{c_id}/entities/batch
    r2 = client.post(f"/api/chapters/{c['id']}/entities/batch", json={"entity_ids": [e1["id"], e2["id"]]})
    assert r2.status_code == 200
    names = [x["name"] for x in r2.json()]
    assert "叶临渊" in names and "太乙玄晶" in names

    # 从章节侧移除关联 DELETE /chapters/{c_id}/entities/{entity_id}
    del_res = client.delete(f"/api/chapters/{c['id']}/entities/{e1['id']}")
    assert del_res.status_code == 204
    rem = client.get(f"/api/chapters/{c['id']}/entities").json()
    assert [x["name"] for x in rem] == ["太乙玄晶"]


# ---------- foreshadows ----------

def test_foreshadow_crud_and_status_enum(client):
    w, _, c = make_wvc(client, "伏笔测试")

    r = client.post(f"/api/works/{w['id']}/foreshadows", json={
        "title": "传讯符灰烬", "content": "魔道暗影", "chapter_id": c["id"]})
    assert r.status_code == 201
    f = r.json()
    assert f["status"] == "planted"
    assert f["chapter_title"] == c["title"]

    # 非法状态被拒（创建与更新）
    assert client.post(f"/api/works/{w['id']}/foreshadows",
                       json={"title": "x", "status": "wrong"}).status_code == 400
    assert client.patch(f"/api/foreshadows/{f['id']}",
                        json={"status": "wrong"}).status_code == 400

    r = client.patch(f"/api/foreshadows/{f['id']}", json={"status": "resolved"})
    assert r.json()["status"] == "resolved"

    lst = client.get(f"/api/works/{w['id']}/foreshadows").json()
    assert [x["id"] for x in lst] == [f["id"]]

    assert client.delete(f"/api/foreshadows/{f['id']}").status_code == 204
    assert client.get(f"/api/works/{w['id']}/foreshadows").json() == []


# ---------- notes ----------

def test_notes_crud(client):
    w = make_work(client, "便签测试")

    r = client.post("/api/notes", json={"content": "一句高光台词", "tags": "台词", "work_id": w["id"]})
    assert r.status_code == 201
    n = r.json()
    assert n["work_id"] == w["id"]

    g = client.post("/api/notes", json={"content": "全局便签"})  # work_id 为空
    assert g.status_code == 201

    # 按作品过滤：含本作品便签 + 全局便签
    lst = client.get("/api/notes", params={"work_id": w["id"]}).json()
    assert {x["content"] for x in lst} == {"一句高光台词", "全局便签"}

    r = client.patch(f"/api/notes/{n['id']}", json={"content": "改过的台词"})
    assert r.json()["content"] == "改过的台词"
    assert client.patch("/api/notes/99999", json={"content": "x"}).status_code == 404

    assert client.delete(f"/api/notes/{n['id']}").status_code == 204
    remaining = client.get("/api/notes", params={"work_id": w["id"]}).json()
    assert [x["content"] for x in remaining] == ["全局便签"]

    # 测试标签过滤与排除功能
    w_note = client.post("/api/notes", json={"content": "世界观核心规则", "tags": "世界观", "work_id": w["id"]}).json()
    all_notes = client.get("/api/notes").json()
    assert any(x["id"] == w_note["id"] for x in all_notes)
    excluded = client.get("/api/notes", params={"exclude_tag": "世界观"}).json()
    assert not any(x["id"] == w_note["id"] for x in excluded)
    filtered = client.get("/api/notes", params={"tag": "世界观"}).json()
    assert any(x["id"] == w_note["id"] for x in filtered)
    client.delete(f"/api/notes/{w_note['id']}")


# ---------- prompts ----------

def test_old_prompts_api_retired_returns_404(client):
    """根据 V1.6.0 Agent Skills 升级规范，旧版 /api/prompts 接口已正式退役下线，直接返回 404。"""
    assert client.get("/api/prompts").status_code == 404
    assert client.post("/api/prompts", json={"name": "test"}).status_code == 404
    assert client.patch("/api/prompts/1", json={"template": "test"}).status_code == 404
    assert client.delete("/api/prompts/1").status_code == 404
