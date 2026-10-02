# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""版本快照：auto 节流、带标签强制新写、手动快照与恢复。"""
from conftest import make_wvc


def _versions(client, chapter_id):
    return client.get(f"/api/chapters/{chapter_id}/versions").json()


def test_auto_snapshot_throttled_within_5min(client):
    _, _, c = make_wvc(client, "节流测试")
    cid = c["id"]

    client.patch(f"/api/chapters/{cid}", json={"content": "第一版", "snapshot_source": "auto"})
    client.patch(f"/api/chapters/{cid}", json={"content": "第二版内容更多", "snapshot_source": "auto"})

    autos = [v for v in _versions(client, cid) if v["source"] == "auto"]
    assert len(autos) == 1  # 5 分钟内不新增，原地更新

    full = client.get(f"/api/versions/{autos[0]['id']}").json()
    assert full["content"] == "第二版内容更多"  # 内容已就地更新为最新


def test_labeled_auto_snapshot_always_new(client):
    _, _, c = make_wvc(client, "标签快照测试")
    cid = c["id"]

    client.patch(f"/api/chapters/{cid}", json={
        "content": "甲", "snapshot_source": "auto", "snapshot_label": "采纳前自动留存"})
    client.patch(f"/api/chapters/{cid}", json={
        "content": "乙", "snapshot_source": "auto", "snapshot_label": "采纳前自动留存"})

    labeled = [v for v in _versions(client, cid)
               if v["source"] == "auto" and v["label"] == "采纳前自动留存"]
    assert len(labeled) == 2  # 带标签的 auto 始终新写一份


def test_manual_snapshot_and_restore(client):
    _, _, c = make_wvc(client, "恢复测试")
    cid = c["id"]

    client.patch(f"/api/chapters/{cid}", json={"content": "原始手稿内容"})
    r = client.post(f"/api/chapters/{cid}/snapshot", json={"label": "手稿"})
    assert r.status_code == 201
    snap = r.json()
    assert snap["source"] == "manual"
    assert snap["label"] == "手稿"

    client.patch(f"/api/chapters/{cid}", json={"content": "改写后的内容"})
    assert client.get(f"/api/chapters/{cid}").json()["content"] == "改写后的内容"

    # 恢复：内容回退到手稿，且生成 restore_backup 留存恢复前的正文
    r = client.post(f"/api/versions/{snap['id']}/restore")
    assert r.status_code == 200
    assert r.json()["content"] == "原始手稿内容"

    backups = [v for v in _versions(client, cid) if v["source"] == "restore_backup"]
    assert len(backups) == 1
    assert backups[0]["label"] == "恢复前自动留存"
    full = client.get(f"/api/versions/{backups[0]['id']}").json()
    assert full["content"] == "改写后的内容"


def test_restore_backup_makes_restore_undoable(client):
    """连续恢复：先恢复手稿，再恢复 restore_backup，能回到改写后内容。"""
    _, _, c = make_wvc(client, "撤销恢复测试")
    cid = c["id"]
    client.patch(f"/api/chapters/{cid}", json={"content": "A"})
    snap = client.post(f"/api/chapters/{cid}/snapshot", json={"label": ""}).json()
    client.patch(f"/api/chapters/{cid}", json={"content": "B"})
    client.post(f"/api/versions/{snap['id']}/restore")
    assert client.get(f"/api/chapters/{cid}").json()["content"] == "A"

    backup = [v for v in _versions(client, cid) if v["source"] == "restore_backup"][0]
    client.post(f"/api/versions/{backup['id']}/restore")
    assert client.get(f"/api/chapters/{cid}").json()["content"] == "B"


def test_versions_prune_keeps_manual(client):
    _, _, c = make_wvc(client, "清理测试")
    cid = c["id"]
    # version_keep_auto=30，造 32 份带标签 auto（标签强制新写）
    for i in range(32):
        client.patch(f"/api/chapters/{cid}", json={
            "content": f"第{i}版", "snapshot_source": "auto", "snapshot_label": f"L{i}"})
    client.post(f"/api/chapters/{cid}/snapshot", json={"label": "手动"})

    r = client.post(f"/api/chapters/{cid}/versions/prune")
    assert r.status_code == 200
    assert r.json() == {"deleted": 2, "keep": 30}

    versions = _versions(client, cid)
    assert len([v for v in versions if v["source"] == "auto"]) == 30
    assert len([v for v in versions if v["source"] == "manual"]) == 1  # 手动快照不动


def test_version_diff_against_current(client):
    _, _, c = make_wvc(client, "对比测试")
    cid = c["id"]
    client.patch(f"/api/chapters/{cid}", json={"content": "旧内容"})
    snap = client.post(f"/api/chapters/{cid}/snapshot", json={}).json()
    client.patch(f"/api/chapters/{cid}", json={"content": "新内容"})

    r = client.get(f"/api/versions/{snap['id']}/diff")
    assert r.status_code == 200
    d = r.json()
    assert d["base"]["content"] == "旧内容"
    assert d["against"]["content"] == "新内容"
    assert d["against"]["id"] == "current"

    assert client.get(f"/api/versions/{snap['id']}/diff", params={"against": "abc"}).status_code == 400
