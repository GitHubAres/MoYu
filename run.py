"""开发入口：python run.py"""
import uvicorn

from app.main import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8321, log_level="info")
