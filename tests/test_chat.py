# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""AI 修撰使多轮对话功能单元测试：会话管理、多轮历史检索、消息持久化与采纳更新。"""
import json
from unittest.mock import AsyncMock, patch

from tests.conftest import make_wvc


def test_chat_schema_and_tables(client):
    """测试数据库表结构是否存在且字段符合规范。"""
    from app.db import get_db

    db = get_db()
    tables = [
        r[0]
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert "chat_sessions" in tables
    assert "chat_messages" in tables

    session_cols = {
        r[1] for r in db.execute("PRAGMA table_info(chat_sessions)").fetchall()
    }
    assert {"id", "work_id", "chapter_id", "created_at", "updated_at"}.issubset(
        session_cols
    )

    msg_cols = {
        r[1] for r in db.execute("PRAGMA table_info(chat_messages)").fetchall()
    }
    assert {
        "id",
        "session_id",
        "role",
        "content",
        "task_type",
        "meta_json",
        "adopted",
        "created_at",
    }.issubset(msg_cols)


def test_chat_get_history_empty(client):
    """新章节查询历史时返回空列表。"""
    _, _, chapter = make_wvc(client, "测试对话作品_空历史")
    resp = client.get(f"/api/chat?chapter_id={chapter['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"] is None
    assert data["messages"] == []


def test_chat_new_session(client):
    """测试显式创建新对话会话。"""
    _, _, chapter = make_wvc(client, "测试对话作品_新会话")
    resp = client.post("/api/chat/session/new", json={"chapter_id": chapter["id"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"] is not None
    assert data["session"]["chapter_id"] == chapter["id"]
    assert data["messages"] == []

    # 再次查询历史
    hist_resp = client.get(f"/api/chat?chapter_id={chapter['id']}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["session"]["id"] == data["session"]["id"]


def test_chat_send_message_non_stream_multi_turn(client):
    """测试多轮对话发送（非流式模式验证消息入库与多轮历史累积）。"""
    work, _, chapter = make_wvc(client, "测试多轮对话作品")

    # 预设 AI 连接配置
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    round1_reply = "【第一轮续写】风雪渐急，沈墨按住腰间长刀。"
    round2_reply = "【第二轮推演】风雪中隐现黑影，刀鸣清脆如龙吟。"

    with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
        # 第一轮调用
        mock_chat.return_value = (round1_reply, 150)
        r1 = client.post(
            "/api/chat",
            json={
                "chapter_id": chapter["id"],
                "message": "续写后续情节",
                "task": "continue",
                "stream": False,
            },
        )
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert data1["content"] == round1_reply
        assert data1["message_id"] > 0

        # 校验 mock_chat 接收到的 messages 结构
        sent_messages1 = mock_chat.call_args[0][0]
        assert sent_messages1[0]["role"] == "system"
        assert "续写" in sent_messages1[0]["content"]
        assert sent_messages1[1]["role"] == "user"
        assert "续写后续情节" in sent_messages1[1]["content"]

        # 第二轮调用（测试多轮上下文传递）
        mock_chat.return_value = (round2_reply, 180)
        r2 = client.post(
            "/api/chat",
            json={
                "chapter_id": chapter["id"],
                "message": "敌人现身，描写环境与拔刀动作",
                "task": "expand",
                "stream": False,
            },
        )
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["content"] == round2_reply

        # 校验第二轮 messages 数组必须包含第一轮的问答历史
        sent_messages2 = mock_chat.call_args[0][0]
        roles = [m["role"] for m in sent_messages2]
        # system, user(r1), assistant(r1), user(r2)
        assert roles == ["system", "user", "assistant", "user"]
        assert sent_messages2[2]["content"] == round1_reply
        assert "拔刀动作" in sent_messages2[3]["content"]

    # 检查数据库中的历史记录
    hist_resp = client.get(f"/api/chat?chapter_id={chapter['id']}")
    assert hist_resp.status_code == 200
    msgs = hist_resp.json()["messages"]
    assert len(msgs) == 4  # user1, ai1, user2, ai2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "ai"
    assert msgs[1]["content"] == round1_reply
    assert msgs[2]["role"] == "user"
    assert msgs[3]["role"] == "ai"
    assert msgs[3]["content"] == round2_reply


def test_chat_message_adoption_toggle(client):
    """测试采纳标记更新与撤销采纳。"""
    _, _, chapter = make_wvc(client, "测试采纳作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ("待采纳正文内容", 100)
        r = client.post(
            "/api/chat",
            json={
                "chapter_id": chapter["id"],
                "message": "生成可采纳段落",
                "task": "continue",
                "stream": False,
            },
        )
        msg_id = r.json()["message_id"]

    # 1. 采纳该消息
    patch_res = client.patch(
        f"/api/chat/messages/{msg_id}",
        json={"adopted": 1},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["adopted"] == 1

    # 验证查库确认
    hist_res = client.get(f"/api/chat?chapter_id={chapter['id']}")
    ai_msg = [m for m in hist_res.json()["messages"] if m["id"] == msg_id][0]
    assert ai_msg["adopted"] == 1

    # 2. 撤销采纳
    undo_res = client.patch(
        f"/api/chat/messages/{msg_id}",
        json={"adopted": 0},
    )
    assert undo_res.status_code == 200
    assert undo_res.json()["adopted"] == 0


def test_chat_stream_mode(client):
    """测试流式 SSE 接口能完整产出 delta 并在结束时落库。"""
    _, _, chapter = make_wvc(client, "测试流式作品")
    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    async def mock_stream(messages, cfg, box):
        for token in ["夜", "深", "沉", "。"]:
            yield token

    with patch("app.api.chat.chat_stream", side_effect=mock_stream):
        resp = client.post(
            "/api/chat",
            json={
                "chapter_id": chapter["id"],
                "message": "描写夜色",
                "task": "continue",
                "stream": True,
            },
        )
        assert resp.status_code == 200
        text = resp.text
        assert "data:" in text
        assert "夜" in text
        assert "深" in text
        assert "done" in text

    # 验证落库
    hist = client.get(f"/api/chat?chapter_id={chapter['id']}").json()
    ai_msg = [m for m in hist["messages"] if m["role"] == "ai"][0]
    assert ai_msg["content"] == "夜深沉。"


def test_chat_isolated_between_chapters(client):
    """测试不同章节间会话相互隔离。"""
    work, volume, chap1 = make_wvc(client, "多章节测试作品")
    r2 = client.post(
        "/api/chapters",
        json={"volume_id": volume["id"], "title": "第二章"},
    )
    chap2 = r2.json()

    client.patch(
        "/api/settings",
        json={"values": {"ai_api_key": "test-key-mock", "ai_model": "mock-model"}},
    )

    with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ("第一章专属回复", 80)
        client.post(
            "/api/chat",
            json={"chapter_id": chap1["id"], "message": "第1章问", "stream": False},
        )

        mock_chat.return_value = ("第二章专属回复", 90)
        client.post(
            "/api/chat",
            json={"chapter_id": chap2["id"], "message": "第2章问", "stream": False},
        )

    h1 = client.get(f"/api/chat?chapter_id={chap1['id']}").json()["messages"]
    h2 = client.get(f"/api/chat?chapter_id={chap2['id']}").json()["messages"]

    assert len(h1) == 2
    assert h1[1]["content"] == "第一章专属回复"

    assert len(h2) == 2
    assert h2[1]["content"] == "第二章专属回复"



def test_workbench_chat_frontend_assets():
    """验证 workbench_chat.js 前端文件存在且包含完整的 UI 与响应式结构。"""
    from pathlib import Path
    chat_js = Path('static/js/pages/workbench_chat.js')
    assert chat_js.exists()
    content = chat_js.read_text(encoding='utf-8')

    # 验证核心能力与关键元素
    assert 'window.WorkbenchChat' in content
    assert 'startNewSession' in content
    assert 'min-h-[44px]' in content
    assert 'updateSelectionQuote' in content
    assert 'updateContextCount' in content
    assert 'streaming-caret' in content
    assert 'onAdopt' in content
    assert 'onUndoAdopt' in content

    # 验证 static/index.html 成功引入
    index_html = Path('static/index.html').read_text(encoding='utf-8')
    assert 'workbench_chat.js' in index_html
