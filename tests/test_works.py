# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""works 核心链路：作品→卷→章→内容保存→树→级联删除。"""
from conftest import make_chapter, make_volume, make_work, make_wvc


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_work_volume_chapter_flow(client):
    w = make_work(client, "链路测试", intro="简介", genre="玄幻")
    assert w["title"] == "链路测试"
    assert w["status"] == "连载中"

    v = make_volume(client, w["id"], "卷一：启程")
    assert v["work_id"] == w["id"]
    assert v["sort_order"] == 1
    v2 = make_volume(client, w["id"], "卷二：远行")
    assert v2["sort_order"] == 2  # sort_order 自动递增

    c = make_chapter(client, v["id"], "第一章 出山")
    assert c["volume_id"] == v["id"]
    assert c["status"] == "draft"
    assert c["word_count"] == 0

    # PATCH 内容：word_count 按去空白字符数计算，且生成 auto 快照
    r = client.patch(f"/api/chapters/{c['id']}", json={
        "content": "你好 世界\n再见",  # 去空白后 6 字
        "snapshot_source": "auto",
    })
    assert r.status_code == 200
    assert r.json()["word_count"] == 6

    versions = client.get(f"/api/chapters/{c['id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["source"] == "auto"
    assert versions[0]["word_count"] == 6

    # tree 结构正确
    tree = client.get(f"/api/works/{w['id']}/tree").json()
    assert [t["title"] for t in tree] == ["卷一：启程", "卷二：远行"]
    assert [ch["title"] for ch in tree[0]["chapters"]] == ["第一章 出山"]
    assert tree[0]["chapters"][0]["word_count"] == 6
    assert tree[1]["chapters"] == []

    # 列表带总字数
    works = client.get("/api/works", params={"q": "链路测试"}).json()
    assert len(works) == 1
    assert works[0]["total_words"] == 6


def test_update_work_fields(client):
    w = make_work(client, "待改名")
    r = client.patch(f"/api/works/{w['id']}", json={"title": "已改名", "status": "完结"})
    assert r.status_code == 200
    assert r.json()["title"] == "已改名"
    assert r.json()["status"] == "完结"


def test_get_missing_returns_404(client):
    assert client.get("/api/works/99999").status_code == 404
    assert client.get("/api/chapters/99999").status_code == 404


def test_delete_work_cascade(client):
    w, v, c = make_wvc(client, "级联删除测试")
    client.patch(f"/api/chapters/{c['id']}", json={
        "content": "正文", "snapshot_source": "auto"})
    assert len(client.get(f"/api/chapters/{c['id']}/versions").json()) == 1

    r = client.delete(f"/api/works/{w['id']}")
    assert r.status_code == 204

    # 作品、树、章节（经 卷 级联）全部消失
    assert client.get(f"/api/works/{w['id']}").status_code == 404
    assert client.get(f"/api/works/{w['id']}/tree").status_code == 404
    assert client.get(f"/api/chapters/{c['id']}").status_code == 404


def test_delete_volume_cascades_chapters(client):
    w = make_work(client, "删卷测试")
    v = make_volume(client, w["id"])
    c = make_chapter(client, v["id"])
    assert client.delete(f"/api/volumes/{v['id']}").status_code == 204
    assert client.get(f"/api/chapters/{c['id']}").status_code == 404
    assert client.get(f"/api/works/{w['id']}/tree").json() == []


def test_settings_defaults_and_patch(client):
    s = client.get("/api/settings").json()
    assert s["theme"] == "light"
    assert s["version_keep_auto"] == "30"

    r = client.patch("/api/settings", json={"values": {"theme": "dark", "daily_word_goal": "8000"}})
    assert r.status_code == 200
    assert r.json()["theme"] == "dark"
    assert client.get("/api/settings").json()["daily_word_goal"] == "8000"
