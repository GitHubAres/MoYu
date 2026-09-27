"""FastAPI 应用入口：API 路由 + 静态文件托管。"""
import threading
import webbrowser

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .paths import STATIC_DIR


def create_app(open_browser: bool = False) -> FastAPI:
    init_db()
    app = FastAPI(title="墨语MoYu · 本地版")

    from .api import router as api_router
    app.include_router(api_router, prefix="/api")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8321")).start()
    return app
