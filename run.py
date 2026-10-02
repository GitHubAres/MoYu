# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""开发与部署入口：python run.py"""
import os
import uvicorn

from app.main import create_app

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8321"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")