# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队
# Licensed under the MIT License. See LICENSE.
"""AI 模型获取、归一化与缓存机制单元测试"""
import asyncio
import datetime
import json
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.db import get_db
import app.ai_client as ai_client


class MockAsyncClient:
    def __init__(self, handler):
        self.handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, timeout=15.0):
        return self.handler(url, timeout)


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setenv("MOYU_DB_PATH", test_db)
    monkeypatch.setattr("app.db.DB_PATH", test_db)
    app = create_app()
    return TestClient(app)


def test_list_models_normalization(monkeypatch):
    """1. 验证模型去重、格式规整与排序逻辑"""
    raw_response = {
        "data": [
            {"id": "deepseek-chat", "owned_by": "deepseek"},
            {"id": "deepseek-reasoner", "owned_by": "deepseek"},
            {"id": "custom-model", "owned_by": ""},
            {"id": "deepseek-chat", "owned_by": "deepseek"},  # 重复项
            {"id": "text-embedding-v1", "owned_by": "openai"},  # 非对话模型
        ]
    }

    def mock_get(url, timeout):
        request = httpx.Request("GET", "https://api.deepseek.com/v1" + url)
        return httpx.Response(200, json=raw_response, request=request)

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.deepseek.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=True))
    assert res["ok"] is True
    assert res["source"] == "remote"
    assert res["total"] == 3
    # 验证排序：有 owned_by 的优先按字母升序，无 owned_by 排在后
    assert [m["id"] for m in res["models"]] == ["deepseek-chat", "deepseek-reasoner", "custom-model"]


def test_list_models_non_chat_filter(monkeypatch):
    """2. 过滤常见非对话模型（嵌入、语音、重排等）"""
    raw_response = {
        "data": [
            {"id": "gpt-4o", "owned_by": "openai"},
            {"id": "text-embedding-3-small", "owned_by": "openai"},
            {"id": "bge-large-zh", "owned_by": "baichuan"},
            {"id": "whisper-1", "owned_by": "openai"},
            {"id": "tts-1", "owned_by": "openai"},
            {"id": "dall-e-3", "owned_by": "openai"},
            {"id": "rerank-multilingual", "owned_by": "cohere"},
        ]
    }

    def mock_get(url, timeout):
        return httpx.Response(200, json=raw_response, request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.openai.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=True))
    assert res["ok"] is True
    assert len(res["models"]) == 1
    assert res["models"][0]["id"] == "gpt-4o"


def test_list_models_truncation(monkeypatch):
    """3. 超过 500 个模型时进行安全截断并提示"""
    raw_response = {
        "data": [{"id": f"model-{i:04d}", "owned_by": "org"} for i in range(600)]
    }

    def mock_get(url, timeout):
        return httpx.Response(200, json=raw_response, request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.openai.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=True))
    assert res["ok"] is True
    assert len(res["models"]) == 500
    assert res["total"] == 600
    assert "500" in res["message"]


def test_list_models_401_error(monkeypatch):
    """4. 401 认证失败时返回明确错误并保留既有缓存"""
    cache_store = {"ai_models_cache": json.dumps({
        "base_url": "https://api.deepseek.com/v1",
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "models": [{"id": "cached-m", "owned_by": "org"}]
    })}

    def mock_get(url, timeout):
        return httpx.Response(401, text="Unauthorized", request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.deepseek.com/v1", "ai_api_key": "sk-bad"}
    # 强制刷新触发 401 错误
    res = asyncio.run(ai_client.list_models(
        cfg, refresh=True,
        cache_get=lambda k: cache_store.get(k),
        cache_set=lambda k, v: cache_store.__setitem__(k, v)
    ))
    assert res["ok"] is False
    assert res["code"] == "auth"
    # 原缓存不被抹除
    assert "cached-m" in cache_store["ai_models_cache"]


def test_list_models_404_unsupported(monkeypatch):
    """5. 404 服务商不支持接口返回 unsupported"""
    def mock_get(url, timeout):
        return httpx.Response(404, text="Not Found", request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.test.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=True))
    assert res["ok"] is False
    assert res["code"] == "unsupported"


def test_list_models_network_timeout(monkeypatch):
    """6. 网络超时异常处理"""
    def mock_get(url, timeout):
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    cfg = {"ai_base_url": "https://api.test.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=True))
    assert res["ok"] is False
    assert res["code"] == "network"
    assert "timeout" in res["message"].lower() or "超时" in res["message"]


def test_list_models_cache_hit_and_refresh(monkeypatch):
    """7 & 8. 默认命中缓存与 refresh=1 强制远程拉取"""
    call_count = 0

    def mock_get(url, timeout):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"data": [{"id": f"m-{call_count}", "owned_by": "org"}]}, request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    store = {}
    cfg = {"ai_base_url": "https://api.test.com/v1", "ai_api_key": "sk-test"}

    # 第 1 次：无缓存，发起远程请求
    res1 = asyncio.run(ai_client.list_models(cfg, refresh=False, cache_get=lambda k: store.get(k), cache_set=lambda k, v: store.__setitem__(k, v)))
    assert res1["ok"] is True
    assert res1["cached"] is False
    assert call_count == 1

    # 第 2 次：有缓存且未超期，直接返回缓存
    res2 = asyncio.run(ai_client.list_models(cfg, refresh=False, cache_get=lambda k: store.get(k), cache_set=lambda k, v: store.__setitem__(k, v)))
    assert res2["ok"] is True
    assert res2["cached"] is True
    assert res2["source"] == "cache"
    assert call_count == 1

    # 第 3 次：refresh=True 显式强制刷新
    res3 = asyncio.run(ai_client.list_models(cfg, refresh=True, cache_get=lambda k: store.get(k), cache_set=lambda k, v: store.__setitem__(k, v)))
    assert res3["ok"] is True
    assert res3["cached"] is False
    assert call_count == 2


def test_list_models_base_url_change_invalidates_cache(monkeypatch):
    """9. base_url 改变时自动使旧缓存失效并重新拉取"""
    call_count = 0

    def mock_get(url, timeout):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"data": [{"id": "m1", "owned_by": "org"}]}, request=httpx.Request("GET", "http://test" + url))

    monkeypatch.setattr(ai_client, "_client", lambda cfg: MockAsyncClient(mock_get))

    store = {
        "ai_models_cache": json.dumps({
            "base_url": "https://api.old.com/v1",
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "models": [{"id": "old-m", "owned_by": "org"}]
        })
    }
    cfg = {"ai_base_url": "https://api.new.com/v1", "ai_api_key": "sk-test"}
    res = asyncio.run(ai_client.list_models(cfg, refresh=False, cache_get=lambda k: store.get(k), cache_set=lambda k, v: store.__setitem__(k, v)))
    assert res["ok"] is True
    assert res["cached"] is False
    assert call_count == 1
    assert "https://api.new.com/v1" in store["ai_models_cache"]


def test_api_route_models_no_config(client):
    """10. 未配置 Base URL / Key 时返回 no_config 状态"""
    # 空配置测试
    res = client.get("/api/ai/models")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is False
    assert data["code"] == "no_config"
