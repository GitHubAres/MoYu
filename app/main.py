# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""FastAPI 应用入口：API 路由 + 静态文件托管 + 云端访问鉴权门禁。"""
import threading
import webbrowser

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .paths import STATIC_DIR
from .api.auth import is_auth_enabled, is_authenticated

def create_app(open_browser: bool = False) -> FastAPI:
    init_db()
    app = FastAPI(title="墨语MoYu · 本地与云端写作工作台")

    # 全局安全门禁拦截器（当启用登录认证时生效）
    @app.middleware("http")
    async def auth_gate_middleware(request: Request, call_next):
        path = request.url.path

        # 豁免开放路由：静态资源、根首页、健康检查及认证相关 API
        if path == "/" or path.startswith("/static") or path == "/api/health" or path.startswith("/api/auth"):
            return await call_next(request)

        # 检查是否启用了密码认证
        if is_auth_enabled():
            if not is_authenticated(request):
                return JSONResponse(
                    {"detail": "请先登录墨语工作台"},
                    status_code=401
                )

        return await call_next(request)

    from .api import router as api_router
    app.include_router(api_router, prefix="/api")

    from .features import get_prompt_library
    get_prompt_library().seed_builtin()

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8321")).start()
    return app