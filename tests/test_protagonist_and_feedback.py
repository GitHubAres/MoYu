# -*- coding: utf-8 -*-
import json
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db import get_db
from app.workflow_assets import (
    extract_structured_assets_from_text,
    sync_assets_to_database,
    SyncAssetsIn,
    normalize_title
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_protagonist.db")
    monkeypatch.setenv("MOYU_DB_PATH", test_db_path)
    app = create_app()
    return TestClient(app)


def test_normalize_title():
    assert normalize_title("第一卷：魔狱潜龙") == normalize_title("第一卷 魔狱潜龙**")
    assert normalize_title("第1章：血祭死牢") == normalize_title("第1章 血祭死牢")


def test_outline_dedup_and_title_cleaning():
    text = """
### 分卷大纲
**第一卷 · 魔狱潜龙**
- **本卷核心目标**：从任人宰割的黑铁狱卒攀升至掌事。

### 章节列表
- 第1章：血祭死牢反吞魔果 (苏醒与吞噬)
- 第2章：仙风魔骨熔炉初威 (借魔炼骨)

MOYU:ASSETS
{
  "outline_nodes": [
    {"title": "第一卷：魔狱潜龙", "synopsis": "卷一核心", "is_volume": true},
    {"title": "第1章：血祭死牢反吞魔果", "synopsis": "第1章概要", "is_volume": false}
  ]
}
"""
    extracted = extract_structured_assets_from_text(text)
    outlines = extracted.get("outline_nodes", [])
    titles = [o["title"] for o in outlines]
    # 验证卷没有被重复添加（不会同时存在 第一卷：魔狱潜龙 和 第一卷 魔狱潜龙**）
    vol_titles = [t for t in titles if "第一卷" in t]
    assert len(vol_titles) == 1, f"Expected 1 volume title, got: {vol_titles}"


def test_methodology_note_filtering_on_sync(client):
    db = get_db()
    cur = db.execute("INSERT INTO works (title) VALUES ('测试作品')")
    work_id = cur.lastrowid
    db.commit()

    payload = SyncAssetsIn(
        selected_types=["term", "world_rule"],
        notes=[
            {"title": "规则一 · 魔煞逆炼律", "content": "熔炉逆炼法则", "tags": "世界观"},
            {"title": "前三章节奏控制", "content": "第一章极限反差爆破", "tags": "方法论"},
            {"title": "立项核心设定", "content": "快节奏升级爽文", "tags": "世界观"}
        ]
    )

    summary = sync_assets_to_database(db, work_id, payload)
    db.commit()

    ents = db.execute("SELECT name, category FROM entities WHERE work_id = ?", (work_id,)).fetchall()
    ent_names = [e["name"] for e in ents]

    assert "规则一 · 魔煞逆炼律" in ent_names
    assert "前三章节奏控制" not in ent_names
    assert "立项核心设定" not in ent_names
    assert summary["rejected_count"] >= 2


def test_protagonist_state_api(client):
    # 1. 创建作品
    res = client.post("/api/works", json={"title": "吞噬星空测试"})
    work_id = res.json()["id"]

    # 2. 查询主角状态（初始为空）
    res = client.get(f"/api/works/{work_id}/protagonist")
    assert res.status_code == 200
    data = res.json()
    assert data["has_protagonist"] is False

    # 3. 设置主角状态与金手指看板
    payload = {
        "name": "罗峰",
        "cultivation_level": "学徒九阶",
        "cheat_name": "金色圆球识海外挂",
        "cheat_progress": "精神念师觉醒度 95%",
        "current_resources": "暗劲巅峰身法、飞刀九把",
        "core_goals": "通过准武者考核，击杀张昊白",
        "key_items": ["江年赠送的血影战刀", "九重雷刀第一重"],
        "notes": "极度坚韧沉稳，重视家人"
    }
    put_res = client.put(f"/api/works/{work_id}/protagonist", json=payload)
    assert put_res.status_code == 200
    assert put_res.json()["ok"] is True

    # 4. 再次获取主角看板
    get_res = client.get(f"/api/works/{work_id}/protagonist")
    assert get_res.status_code == 200
    p_data = get_res.json()
    assert p_data["has_protagonist"] is True
    assert p_data["name"] == "罗峰"
    assert p_data["cultivation_level"] == "学徒九阶"
    assert p_data["cheat_name"] == "金色圆球识海外挂"
    assert "九重雷刀第一重" in p_data["key_items"]

    # 5. 验证 context_service 装配包含主角状态
    from app.services.context_service import assemble_writing_context
    db = get_db()
    ctx = assemble_writing_context(db, work_id)
    assert "【主角战力与金手指状态板】罗峰" in ctx
    assert "金色圆球识海外挂" in ctx
    assert "学徒九阶" in ctx
