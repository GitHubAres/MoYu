# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""OpenAI 兼容接口客户端：非流式对话与 SSE 流式对话。"""
import json

import httpx

from .db import get_db

DEFAULT_TIMEOUT = 300.0
TIMEOUT = DEFAULT_TIMEOUT  # 兼容旧代码引用


class AIError(Exception):
    """AI 调用失败，信息友好化后可直接展示给用户。"""


def get_ai_timeout(cfg: dict | None = None, fallback: float = DEFAULT_TIMEOUT) -> float:
    """获取当前配置的 AI 超时秒数（默认 300 秒，最低 10 秒）。"""
    if cfg is None:
        cfg = get_ai_config()
    raw = cfg.get("ai_timeout")
    if raw is not None and str(raw).strip():
        try:
            val = float(raw)
            if val >= 10.0:
                return val
        except (ValueError, TypeError):
            pass
    return fallback


def get_ai_config() -> dict:
    rows = get_db().execute(
        "SELECT key, value FROM app_settings WHERE key LIKE 'ai_%'").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _friendly(e: Exception) -> AIError:
    if isinstance(e, httpx.ConnectError):
        return AIError("无法连接 AI 接口，请检查 Base URL 是否正确，网络是否畅通。")
    if isinstance(e, httpx.TimeoutException):
        return AIError("AI 接口响应超时，请在系统设置中调大超时时间或稍后重试。")
    return AIError(f"AI 接口调用失败：{e}")


def _check_status(resp: httpx.Response):
    if resp.status_code == 401:
        raise AIError("API Key 无效或已过期（401）。")
    if resp.status_code == 404:
        raise AIError("接口路径不存在（404），请确认 Base URL 以 /v1 结尾。")
    if resp.status_code >= 400:
        raise AIError(f"AI 接口返回错误（{resp.status_code}）：{resp.text[:200]}")


def _client(cfg: dict, timeout: float | None = None) -> httpx.AsyncClient:
    t = timeout if timeout is not None else get_ai_timeout(cfg)
    timeout_obj = httpx.Timeout(t, connect=30.0)
    return httpx.AsyncClient(
        base_url=(cfg.get("ai_base_url") or "").rstrip("/"),
        headers={"Authorization": f"Bearer {cfg.get('ai_api_key', '')}"},
        timeout=timeout_obj)


async def chat(messages: list, cfg: dict, max_tokens: int | None = None, timeout: float | None = None, **kwargs):
    """非流式调用，返回 (文本, total_tokens|None)。"""
    payload = {"model": cfg["ai_model"], "messages": messages, "stream": False}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    try:
        async with _client(cfg, timeout=timeout) as c:
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


async def chat_stream(messages: list, cfg: dict, usage_box: dict, timeout: float | None = None):
    """流式调用，异步产生 delta 文本；若有 total_tokens 写入 usage_box；兼容非流式返回兜底。"""
    payload = {
        "model": cfg["ai_model"],
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    try:
        async with _client(cfg, timeout=timeout) as c:
            async with c.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    _check_status(resp)
                # 部分兼容服务端不支持 stream 参数而直接返回 JSON，做兼容降级
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
                        raise AIError("AI 接口返回了无法解析的内容（非 SSE 也非 JSON）。")
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


MODELS_TIMEOUT = 15.0
NON_CHAT_PATTERNS = ("embed", "rerank", "bge-", "whisper", "tts", "moderation",
                     "dall-e", "omni-moderation", "text-moderation", "voice", "realtime")


async def list_models(cfg: dict, *, refresh: bool = False,
                      cache_get=None, cache_set=None) -> dict:
    """返回 {ok, models, total, fetched_at, cached, source, message}。

    cache_get/cache_set 接受可调用对象，避免直接依赖 settings 模块引发循环导入。
    通常由上层注入读取与写入 db 的回调函数。
    """
    import datetime

    base_url = (cfg.get("ai_base_url") or "").rstrip("/")
    api_key = (cfg.get("ai_api_key") or "").strip()

    # 1. 优先读取缓存 (refresh=False)
    cached_data = None
    if not refresh and cache_get:
        try:
            raw_cache = cache_get("ai_models_cache")
            if raw_cache:
                c_json = json.loads(raw_cache) if isinstance(raw_cache, str) else raw_cache
                c_base = c_json.get("base_url")
                c_fetched = c_json.get("fetched_at")
                c_models = c_json.get("models")
                if c_base == base_url and c_fetched and isinstance(c_models, list):
                    # 缓存有效期 24 小时
                    dt = datetime.datetime.fromisoformat(c_fetched)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    if (now - dt).total_seconds() < 86400:
                        return {
                            "ok": True,
                            "models": c_models,
                            "total": len(c_models),
                            "fetched_at": c_fetched,
                            "cached": True,
                            "source": "cache",
                            "message": "",
                        }
                    else:
                        cached_data = c_models
        except Exception:
            pass

    # 2. 请求远程模型列表
    try:
        async with _client(cfg) as c:
            resp = await c.get("/models", timeout=MODELS_TIMEOUT)
            if resp.status_code == 401:
                return {
                    "ok": False,
                    "code": "auth",
                    "message": "API Key 无效或已过期（401）",
                    "models": [],
                    "total": 0,
                    "cached": False,
                    "source": "remote",
                }
            if resp.status_code == 404:
                return {
                    "ok": False,
                    "code": "unsupported",
                    "message": "服务商未提供模型列表接口（404）",
                    "models": [],
                    "total": 0,
                    "cached": False,
                    "source": "remote",
                }
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "code": "network",
                    "message": f"AI 接口请求失败：{resp.status_code}，{resp.text[:200]}",
                    "models": [],
                    "total": 0,
                    "cached": False,
                    "source": "remote",
                }
            raw_json = resp.json()
    except Exception as e:
        friendly = _friendly(e)
        return {
            "ok": False,
            "code": "network",
            "message": str(friendly),
            "models": [],
            "total": 0,
            "cached": False,
            "source": "remote",
        }

    # 3. 解析模型列表
    raw_data = raw_json.get("data")
    if not isinstance(raw_data, list):
        # 部分服务商直接返回列表，兼容两种格式
        if isinstance(raw_json, list):
            raw_data = raw_json
        else:
            raw_data = []

    models = []
    seen_ids = set()
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        mid = item.get("id")
        if not mid or not isinstance(mid, str):
            continue
        if mid in seen_ids:
            continue
        # 过滤非文本对话模型
        low_id = mid.lower()
        if any(pat in low_id for pat in NON_CHAT_PATTERNS):
            continue
        seen_ids.add(mid)
        owned_by = item.get("owned_by") or ""
        if not isinstance(owned_by, str):
            owned_by = ""
        models.append({"id": mid, "owned_by": owned_by})

    # 排序：有 owned_by 优先 -> 按 owned_by 字母升序 -> 按 id 字母升序
    models.sort(key=lambda x: (1 if not x["owned_by"] else 0, x["owned_by"].lower(), x["id"].lower()))

    total = len(models)
    msg = ""
    if total > 500:
        models = models[:500]
        msg = "模型数量过多，已截取前 500 个模型"

    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 4. 写入缓存
    if cache_set:
        try:
            cache_payload = json.dumps({
                "base_url": base_url,
                "fetched_at": fetched_at,
                "models": models
            }, ensure_ascii=False)
            cache_set("ai_models_cache", cache_payload)
        except Exception:
            pass

    return {
        "ok": True,
        "models": models,
        "total": total,
        "fetched_at": fetched_at,
        "cached": False,
        "source": "remote",
        "message": msg,
    }
