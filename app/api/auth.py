# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""身份认证与登录控制 API：严格区分原生桌面版与云端 VPS 部署版。"""
import os
import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..db import get_db
from ..paths import IS_DESKTOP_EXE

router = APIRouter(prefix="/auth", tags=["auth"])

_ACTIVE_SESSIONS = set()

def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, hashed = stored_hash.split(":", 1)
    computed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(computed, hashed)

def is_auth_enabled() -> bool:
    """
    判断当前运行环境是否需要开启身份登录鉴权：
    1. 若为 Windows PyInstaller 原生打包桌面应用（exe），由于运行在用户本机专属 WebView2 环境中，绝对不启用登录页；
    2. 若为云端公开部署模式（环境变量设置了 HOST=0.0.0.0 或 MOYU_CLOUD=1，或数据库设置了 auth_enabled=1），强制启用登录与初始化。
    """
    if IS_DESKTOP_EXE:
        return False

    host = os.environ.get("HOST", "")
    cloud_env = os.environ.get("MOYU_CLOUD", "")
    if host == "0.0.0.0" or cloud_env in ("1", "true", "True"):
        return True

    conn = get_db()
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'auth_enabled'").fetchone()
    if row and row["value"] == "1":
        return True
    return False

def is_initialized() -> bool:
    conn = get_db()
    pw_row = conn.execute("SELECT value FROM app_settings WHERE key = 'auth_password'").fetchone()
    return bool(pw_row and pw_row["value"])

def is_authenticated(request: Request) -> bool:
    if not is_auth_enabled():
        return True
    if not is_initialized():
        return False
    token = request.cookies.get("moyu_session") or request.headers.get("X-Moyu-Token")
    if token and token in _ACTIVE_SESSIONS:
        return True
    return False

class InitRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.get("/status")
def auth_status(request: Request):
    """查询认证状态：桌面版自动免鉴权；云端版根据初始化和登录状态响应。"""
    enabled = is_auth_enabled()
    initialized = is_initialized() if enabled else True
    conn = get_db()
    user_row = conn.execute("SELECT value FROM app_settings WHERE key = 'auth_username'").fetchone()
    username = user_row["value"] if user_row and user_row["value"] else "admin"

    authenticated = is_authenticated(request)
    return {
        "ok": True,
        "is_desktop": IS_DESKTOP_EXE,
        "enabled": enabled,
        "initialized": initialized,
        "authenticated": authenticated,
        "username": username if authenticated else ""
    }

@router.post("/init")
def auth_init(body: InitRequest, response: Response):
    """云端部署首次设置管理员用户名和密码。"""
    if IS_DESKTOP_EXE:
        return {"ok": True, "message": "桌面版无需设置密码"}
    if is_initialized():
        raise HTTPException(400, "系统已完成初始化，禁止重复设置。")
    if not body.username.strip() or len(body.password.strip()) < 4:
        raise HTTPException(400, "用户名不能为空，且密码长度至少为 4 位。")

    conn = get_db()
    hashed = hash_password(body.password.strip())
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('auth_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('auth_username', ?)", (body.username.strip(),))
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('auth_password', ?)", (hashed,))
    conn.commit()

    token = secrets.token_urlsafe(32)
    _ACTIVE_SESSIONS.add(token)
    response.set_cookie(
        "moyu_session",
        token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {"ok": True, "message": "管理员账号初始化成功", "username": body.username.strip()}

@router.post("/login")
def auth_login(body: LoginRequest, response: Response):
    """云端部署管理员登录。"""
    if IS_DESKTOP_EXE:
        return {"ok": True, "message": "桌面版无需登录"}
    if not is_initialized():
        raise HTTPException(400, "系统尚未初始化，请先设置管理员账号与密码。")

    conn = get_db()
    user_row = conn.execute("SELECT value FROM app_settings WHERE key = 'auth_username'").fetchone()
    pw_row = conn.execute("SELECT value FROM app_settings WHERE key = 'auth_password'").fetchone()

    expected_user = user_row["value"] if user_row else "admin"
    stored_hash = pw_row["value"] if pw_row else ""

    if body.username.strip() != expected_user or not verify_password(body.password.strip(), stored_hash):
        raise HTTPException(401, "用户名或密码错误，请重新输入。")

    token = secrets.token_urlsafe(32)
    _ACTIVE_SESSIONS.add(token)
    response.set_cookie(
        "moyu_session",
        token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {"ok": True, "message": "登录成功", "username": expected_user}

@router.post("/logout")
def auth_logout(request: Request, response: Response):
    """登出当前会话。"""
    token = request.cookies.get("moyu_session") or request.headers.get("X-Moyu-Token")
    if token and token in _ACTIVE_SESSIONS:
        _ACTIVE_SESSIONS.remove(token)
    response.delete_cookie("moyu_session", path="/")
    return {"ok": True, "message": "已成功退出登录"}