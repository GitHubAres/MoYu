# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
"""智能收录 (smart-intake) 与设定体检 (audit) 运行时端到端回归测试。

覆盖：
1. 候选预览 (auto_commit=false)：返回 assets 对象，标注 is_new，不入库；
2. 确认落库 (auto_commit=true)：走 sync_assets_to_database 真实写库并关联本章；
3. is_new 判定正确性：入库后再次探测返回 is_new=False；
4. location→place 归一回归：验证地点实体入库分类为 place 而非 term；
5. audit/run 字段契约：mock httpx LLM，验证 quote/type/severity/issue 正常输出。
"""
import pytest
from conftest import make_wvc
from app.workflow_assets import normalize_category


def test_normalize_category_location_to_place():
    """纯单元断言：location 别名正确映射到 place，lore 映射到 term。"""
    assert normalize_category("location") == "place"
    assert normalize_category("地点") == "place"
    assert normalize_category("lore") == "term"


def test_smart_intake_candidate_preview_auto_commit_false(client):
    """用例 1：候选预览（auto_commit=false）返回 assets 并标注 is_new=True，不真正落库。"""
    w, v, c = make_wvc(client, "测试候选预览作品")
    work_id = w["id"]
    chapter_id = c["id"]

    sample_text = (
        "夜幕低垂，青云宗外门弟子萧炎独自走上试炼峰。\n"
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "entities": [\n'
        '    {"name": "萧炎", "category": "character", "content": "外门弟子"},\n'
        '    {"name": "试炼峰", "category": "place", "content": "外门禁地"}\n'
        "  ],\n"
        '  "foreshadows": [\n'
        '    {"title": "黑铁指环异动", "content": "偶得残破指环"}\n'
        "  ]\n"
        "}\n"
        "MOYU:ASSETS -->"
    )

    r = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": False,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["committed"] is False
    assert "assets" in data
    assets = data["assets"]

    # 验证资产键健全
    for expected_key in ["entities", "relations", "foreshadows", "timeline_events", "outline_nodes", "notes"]:
        assert expected_key in assets

    # 库为空时，正文中新实体应存在且 is_new=True
    ent_names = [e["name"] for e in assets["entities"]]
    assert "萧炎" in ent_names
    assert "试炼峰" in ent_names
    xiao = next(e for e in assets["entities"] if e["name"] == "萧炎")
    assert xiao["is_new"] is True

    # 验证此时并未落库
    ent_list_res = client.get(f"/api/works/{work_id}/entities")
    assert ent_list_res.status_code == 200
    ent_db_names = [e["name"] for e in ent_list_res.json()]
    assert "萧炎" not in ent_db_names


def test_smart_intake_confirm_commit_auto_commit_true(client):
    """用例 2：确认落库（auto_commit=true）调用 sync_assets_to_database 真实写库。"""
    w, v, c = make_wvc(client, "测试确认落库作品")
    work_id = w["id"]
    chapter_id = c["id"]

    sample_text = (
        "正文简述...\n"
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "entities": [\n'
        '    {"name": "韩立", "category": "character", "content": "七玄门杂役弟子"}\n'
        "  ],\n"
        '  "foreshadows": [\n'
        '    {"title": "绿玉小瓶", "content": "山崖偶拾异宝"}\n'
        "  ]\n"
        "}\n"
        "MOYU:ASSETS -->"
    )

    # 记录写入前数量
    before_ents = len(client.get(f"/api/works/{work_id}/entities").json())

    r = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": True,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["committed"] is True
    assert "summary" in data
    assert data["summary"]["entities_added"] >= 1

    # 真实落库比对：实体表确实新增条目
    after_ents_res = client.get(f"/api/works/{work_id}/entities")
    after_ents = after_ents_res.json()
    assert len(after_ents) == before_ents + 1
    assert any(e["name"] == "韩立" for e in after_ents)


def test_smart_intake_is_new_flag_determination(client):
    """用例 3：is_new 判定准确性：入库前 is_new=True，入库后再次探测为 is_new=False。"""
    w, v, c = make_wvc(client, "测试is_new判定作品")
    work_id = w["id"]
    chapter_id = c["id"]

    sample_text = (
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "entities": [{"name": "药老", "category": "character", "content": "灵魂体大师"}]\n'
        "}\n"
        "MOYU:ASSETS -->"
    )

    # 1. 首次预览：is_new 为 True
    r1 = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": False,
    })
    assert r1.status_code == 200
    yao1 = next(e for e in r1.json()["assets"]["entities"] if e["name"] == "药老")
    assert yao1["is_new"] is True

    # 2. 确认落库
    r2 = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": True,
    })
    assert r2.status_code == 200
    assert r2.json()["committed"] is True

    # 3. 再次探测预览：此时药老已在库中，is_new 应为 False
    r3 = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": False,
    })
    assert r3.status_code == 200
    yao3 = next(e for e in r3.json()["assets"]["entities"] if e["name"] == "药老")
    assert yao3["is_new"] is False


def test_smart_intake_location_to_place_normalization_and_intake(client):
    """用例 4：location 归一为 place 回归验证，确保地点实体入库 category 为 place（不是 term）。"""
    w, v, c = make_wvc(client, "测试地点归一作品")
    work_id = w["id"]
    chapter_id = c["id"]

    sample_text = (
        "<!-- MOYU:ASSETS\n"
        "{\n"
        '  "entities": [\n'
        '    {"name": "青云山", "category": "location", "content": "一座仙山"}\n'
        "  ]\n"
        "}\n"
        "MOYU:ASSETS -->"
    )

    r = client.post(f"/api/chapters/{chapter_id}/smart-intake", json={
        "content": sample_text,
        "auto_commit": True,
    })
    assert r.status_code == 200, r.text

    ent_res = client.get(f"/api/works/{work_id}/entities")
    assert ent_res.status_code == 200
    ents = ent_res.json()
    qingyun = next((e for e in ents if e["name"] == "青云山"), None)
    assert qingyun is not None, "青云山未成功入库"
    assert qingyun["category"] == "place", f"预期 category 为 place，实际为 {qingyun['category']}"


def test_audit_run_field_contract_with_mocked_llm(client, monkeypatch):
    """用例 5：audit/run 字段契约回归，mock httpx 响应验证 quote/type/severity/issue 正常结构化输出。"""
    w, v, c = make_wvc(client, "测试审计字段契约作品")
    work_id = w["id"]
    chapter_id = c["id"]

    # 设定库里预置一个李雷角色
    ent_res = client.post(f"/api/works/{work_id}/entities", json={
        "name": "李雷",
        "category": "character",
        "content": "十九岁剑客",
    })
    assert ent_res.status_code == 201

    # 配置临时 app_settings
    import app.db as db_module
    db = db_module.get_db()
    db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('ai_base_url', 'http://fake-llm/v1')")
    db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('ai_api_key', 'fake-key')")
    db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('ai_model', 'fake-model')")
    db.commit()

    canned_issues = [
        {
            "type": "矛盾",
            "severity": "high",
            "entity": "李雷",
            "issue": "前后年龄不一致",
            "quote": "李雷今年十八岁……",
            "chapter_title": "第一章",
        }
    ]

    import httpx

    class MockResponse:
        status_code = 200

        def json(self):
            import json
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(canned_issues, ensure_ascii=False)
                        }
                    }
                ]
            }

        def raise_for_status(self):
            pass

    async def mock_post(self, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    resp = client.post("/api/audit/run", json={
        "work_id": work_id,
        "chapter_ids": [chapter_id],
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "issues" in data
    assert len(data["issues"]) >= 1

    first = data["issues"][0]
    assert first["type"] == "矛盾"
    assert first["severity"] == "high"
    assert first["entity"] == "李雷"
    assert first["issue"] == "前后年龄不一致"
    assert first["quote"] == "李雷今年十八岁……"
