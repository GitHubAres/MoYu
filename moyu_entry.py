"""exe 打包入口：双击启动服务并自动打开浏览器；已有实例运行时直接打开页面。"""
import socket
import webbrowser

HOST, PORT = "127.0.0.1", 8321
URL = f"http://{HOST}:{PORT}"


def _instance_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    if _instance_running():
        # 已有墨语实例在运行：直接打开页面，避免端口冲突报错
        webbrowser.open(URL)
    else:
        import uvicorn

        from app.main import create_app

        uvicorn.run(create_app(open_browser=True), host=HOST, port=PORT, log_level="warning")
