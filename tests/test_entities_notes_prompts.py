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


# ---------- prompts ----------

def test_builtin_prompts_seeded(client):
    """create_app 导入 api 模块时自动播种 6 条内置模板。"""
    prompts = client.get("/api/prompts").json()
    builtins = [p for p in prompts if p["builtin"] == 1]
    assert len(builtins) == 6
    assert {p["task_type"] for p in builtins} == {
        "continue", "expand", "shorten", "rewrite", "outline", "audit"}


def test_prompt_crud_and_enum(client):
    r = client.post("/api/prompts", json={
        "name": "我的续写", "task_type": "continue", "template": "请续写 {{selection}}"})
    assert r.status_code == 201
    p = r.json()
    assert p["builtin"] == 0

    assert client.post("/api/prompts", json={
        "name": "x", "task_type": "wrong", "template": "t"}).status_code == 400

    r = client.patch(f"/api/prompts/{p['id']}", json={"template": "新模板 {{instruction}}"})
    assert r.json()["template"] == "新模板 {{instruction}}"

    by_type = client.get("/api/prompts", params={"task_type": "continue"}).json()
    assert all(x["task_type"] == "continue" for x in by_type)

    assert client.delete(f"/api/prompts/{p['id']}").status_code == 204
    assert client.get(f"/api/prompts").json().count(p) == 0


def test_builtin_prompt_protected_and_duplicable(client):
    builtin = [p for p in client.get("/api/prompts").json() if p["builtin"] == 1][0]

    assert client.delete(f"/api/prompts/{builtin['id']}").status_code == 400

    r = client.post(f"/api/prompts/{builtin['id']}/duplicate")
    assert r.status_code == 201
    dup = r.json()
    assert dup["builtin"] == 0
    assert dup["name"] == builtin["name"] + "（副本）"
    assert client.delete(f"/api/prompts/{dup['id']}").status_code == 204
