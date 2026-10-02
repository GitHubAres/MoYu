# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""OpenAI 兼容接口客户端：非流式调用与 SSE 流式解析。"""
import json

import httpx

from .db import get_db

TIMEOUT = 120.0


class AIError(Exception):
    """AI 调用失败（信息已友好化，可直接展示给用户）。"""


def get_ai_config() -> dict:
    rows = get_db().execute(
        "SELECT key, value FROM app_settings WHERE key LIKE 'ai_%'").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _friendly(e: Exception) -> AIError:
    if isinstance(e, httpx.ConnectError):
        return AIError("无法连接 AI 接口，请检查 Base URL 是否正确、服务是否已启动")
    if isinstance(e, httpx.TimeoutException):
        return AIError("AI 接口请求超时，请稍后重试")
    return AIError(f"AI 接口调用失败：{e}")


def _check_status(resp: httpx.Response):
    if resp.status_code == 401:
        raise AIError("API Key 无效或已过期（401）")
    if resp.status_code == 404:
        raise AIError("接口路径不存在（404），请确认 Base URL 以 /v1 结尾")
    if resp.status_code >= 400:
        raise AIError(f"AI 接口返回错误（{resp.status_code}）：{resp.text[:200]}")


def _client(cfg: dict) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=(cfg.get("ai_base_url") or "").rstrip("/"),
        headers={"Authorization": f"Bearer {cfg.get('ai_api_key', '')}"},
        timeout=TIMEOUT)


async def chat(messages: list, cfg: dict, max_tokens: int | None = None):
    """非流式调用，返回 (文本, total_tokens|None)。"""
    payload = {"model": cfg["ai_model"], "messages": messages, "stream": False}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    try:
        async with _client(cfg) as c:
            resp = await c.post("/chat/completions", json=payload)
            _check_status(resp)
            data = resp.json()
    except AIError:
        raise
    except Exception as e:
        raise _friendly(e)
    text = "".join(ch.get("message", {}).get("content") or ""
                   for ch in data.get("choices", []))
    return text, (data.get("usage") or {}).get("total_tokens")


async def chat_stream(messages: list, cfg: dict, usage_box: dict):
    """流式调用：异步产出 delta 文本；结束后把 total_tokens 写入 usage_box（可能缺省）。"""
    payload = {
        "model": cfg["ai_model"],
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    try:
        async with _client(cfg) as c:
            async with c.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    _check_status(resp)
                # 部分兼容服务忽略 stream 参数直接返回 JSON，做个回退
                if "text/event-stream" not in resp.headers.get("content-type", ""):
                    data = (await resp.aread()).decode("utf-8", "ignore")
                    try:
                        obj = json.loads(data)
                        if obj.get("usage"):
                            usage_box["total_tokens"] = obj["usage"].get("total_tokens")
                        text = "".join(ch.get("message", {}).get("content") or ""
                                       for ch in obj.get("choices", []))
                        if text:
                            yield text
                        return
                    except json.JSONDecodeError:
                        raise AIError("AI 接口返回了无法解析的内容（非 SSE 也非 JSON）")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("usage"):
                        usage_box["total_tokens"] = chunk["usage"].get("total_tokens")
                    for ch in chunk.get("choices", []):
                        delta = (ch.get("delta") or {}).get("content")
                        if delta:
                            yield delta
    except AIError:
        raise
    except Exception as e:
        raise _friendly(e)
