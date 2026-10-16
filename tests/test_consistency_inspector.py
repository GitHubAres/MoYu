# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch, AsyncMock
from conftest import make_wvc
from app.db import get_db
from app.services.consistency_service import (
    build_consistency_context,
    format_consistency_dossier,
    inspect_chapter_consistency,
)


def test_build_consistency_context_and_format(client):
    """验证巡检上下文装配：万相谱实体、时间线事件、伏笔及大纲梗概正确聚集。"""
    w, v, c = make_wvc(client, "一致性巡检作品")
    work_id = w["id"]
    chapter_id = c["id"]
    db = get_db()

    # 1. 插入实体并绑定本章
    cur_e = db.execute(
        """INSERT INTO entities (work_id, category, name, content, fields_json, tags)
           VALUES (?, 'character', '楚残阳', '断臂剑客', '{"identity":"独行剑客","background":"三年前断了左臂"}', '主角')""",
        (work_id,)
    )
    ent_id = cur_e.lastrowid
    db.execute("INSERT INTO chapter_entities (chapter_id, entity_id) VALUES (?, ?)", (chapter_id, ent_id))

    # 2. 插入时间线
    db.execute(
        """INSERT INTO timeline_events (work_id, time_label, event, characters, sort_order)
           VALUES (?, '三年前', '楚残阳于落霞峰折断左臂', '楚残阳', 1)""",
        (work_id,)
    )

    # 3. 插入伏笔
    db.execute(
        """INSERT INTO foreshadows (work_id, title, content, status)
           VALUES (?, '断剑之誓', '发誓不再拔双剑', 'planted')""",
        (work_id,)
    )
    db.commit()

    bundle = build_consistency_context(db, work_id, chapter_id)
    assert len(bundle["entities"]) >= 1
    assert bundle["entities"][0]["name"] == "楚残阳"
    assert "断了左臂" in str(bundle["entities"][0]["fields"])

    assert len(bundle["timeline"]) >= 1
    assert "落霞峰" in bundle["timeline"][0]["event"]

    assert len(bundle["foreshadows"]) >= 1
    assert bundle["foreshadows"][0]["title"] == "断剑之誓"

    # 验证档案字符串格式化
    dossier = format_consistency_dossier(bundle)
    assert "楚残阳" in dossier
    assert "落霞峰" in dossier
    assert "断剑之誓" in dossier


@pytest.mark.anyio
async def test_inspect_chapter_consistency_mock_ai():
    """验证巡检服务调用 AI 并正确解析结构化吃书预警结果。"""
    from app.db import get_db
    db = get_db()

    mock_reply = """[
  {
    "type": "character_status",
    "entity_name": "楚残阳",
    "severity": "warn",
    "description": "楚残阳三年前已断左臂，正文中双手挽起剑花存在前后设定冲突",
    "quote": "双手挽起剑花",
    "suggestion": "改为单手抖出剑花或以独臂御剑",
    "replacement": "单手抖出剑花"
  }
]"""

    # 预先插入 volume 与 chapter
    v_cur = db.execute("INSERT INTO volumes (work_id, title, sort_order) VALUES (1, '第一卷', 1)")
    vol_id = v_cur.lastrowid
    c_cur = db.execute("INSERT INTO chapters (volume_id, title, content, sort_order) VALUES (?, '第一章 剑出落霞', '正文', 1)", (vol_id,))
    chap_id = c_cur.lastrowid
    db.commit()

    with patch("app.services.consistency_service.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = (mock_reply, 80)
        conflicts = await inspect_chapter_consistency(
            db=db,
            work_id=1,
            chapter_id=chap_id,
            content="楚残阳双手挽起剑花，剑光凌厉。",
            cfg={"ai_api_key": "fake_key", "ai_model": "gpt-4"}
        )
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["type"] == "character_status"
        assert c["entity_name"] == "楚残阳"
        assert c["quote"] == "双手挽起剑花"
        assert "断左臂" in c["description"]
        assert c.get("replacement") == "单手抖出剑花"


def test_consistency_check_api_endpoint(client):
    """验证 POST /api/chapters/{chapter_id}/consistency-check 接口连通性与兜底响应。"""
    w, v, c = make_wvc(client, "巡检接口测试作品")
    chapter_id = c["id"]

    # 当未配置 AI 或传入空正文时，应返回 ok: True 且 conflicts 为空列表，不抛异常
    res = client.post(f"/api/chapters/{chapter_id}/consistency-check", json={"content": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["conflicts"] == []

    # 404 测试
    res404 = client.post("/api/chapters/999999/consistency-check", json={"content": "test"})
    assert res404.status_code == 404
