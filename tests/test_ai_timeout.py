# -*- coding: utf-8 -*-
import pytest
import httpx
from app.db import DEFAULT_SETTINGS, get_db
from app.ai_client import (
    DEFAULT_TIMEOUT,
    TIMEOUT,
    get_ai_timeout,
    _client,
    _friendly,
    AIError,
)


def test_default_timeout_constants():
    """验证全局默认超时时间已提升至 300 秒（5分钟）。"""
    assert DEFAULT_TIMEOUT == 300.0
    assert TIMEOUT == 300.0
    assert DEFAULT_SETTINGS["ai_timeout"] == "300"


def test_get_ai_timeout():
    """验证从配置字典读取超时时间及降级逻辑。"""
    # 默认回落
    assert get_ai_timeout({}) == 300.0
    assert get_ai_timeout({"ai_timeout": ""}) == 300.0
    assert get_ai_timeout({"ai_timeout": "invalid"}) == 300.0
    assert get_ai_timeout({"ai_timeout": "5"}) == 300.0  # < 10 秒过小，回落

    # 有效配置
    assert get_ai_timeout({"ai_timeout": "450"}) == 450.0
    assert get_ai_timeout({"ai_timeout": "600.5"}) == 600.5

    # 自定义 fallback
    assert get_ai_timeout({}, fallback=600.0) == 600.0


def test_client_timeout_setting():
    """验证 httpx client 注入的超时对象正确包含 connect 与总超时。"""
    cfg = {"ai_base_url": "https://api.openai.com/v1", "ai_api_key": "test_key", "ai_timeout": "500"}
    client = _client(cfg)
    assert client.timeout.connect == 30.0
    assert client.timeout.read == 500.0

    # 显式覆盖 timeout
    client_custom = _client(cfg, timeout=750.0)
    assert client_custom.timeout.read == 750.0


def test_friendly_timeout_error():
    """验证超时异常错误文案包含用户指引。"""
    err = httpx.ReadTimeout("read timed out")
    friendly = _friendly(err)
    assert isinstance(friendly, AIError)
    assert "AI 接口响应超时" in str(friendly)
    assert "系统设置" in str(friendly)
