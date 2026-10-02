# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""exe / 桌面端启动入口：
- 默认 100% 启动轻量原生 WebView2 独立应用视窗（1366x820，无控制台黑框、点叉即退、关闭连带退出后台服务）
- 防范 --noconsole 模式下 stdout/stderr 为 None 导致的 Uvicorn 'Unable to configure formatter default' 崩溃
- 仅当显式传入 --browser 参数或 MOYU_WEBVIEW=0 环境变量时，才回退至外部浏览器模式
- 包含完善的 WebView 异常降级 fallback：若宿主环境缺失 WebView 运行时，安全降级至浏览器打开保底
"""
import io
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser

# 防范 --noconsole 窗口模式下 sys.stdout / sys.stderr 为 None 导致日志或底层模块抛出异常
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        sys.stdout = io.StringIO()

if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        sys.stderr = io.StringIO()

HOST, PORT = "127.0.0.1", 8321
URL = f"http://{HOST}:{PORT}"
WINDOW_TITLE = "墨语 MoYu - AI长篇小说创作工作台"
WINDOW_WIDTH = 1366
WINDOW_HEIGHT = 820
MIN_WINDOW_WIDTH = 1024
MIN_WINDOW_HEIGHT = 680


def is_instance_running(host: str = HOST, port: int = PORT) -> bool:
    """检测当前端口是否已有服务实例在监听。"""
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def wait_for_server_ready(host: str = HOST, port: int = PORT, timeout: float = 8.0) -> bool:
    """等待本地后端 HTTP 服务完全连通。"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_instance_running(host, port):
            return True
        time.sleep(0.1)
    return False


def run_browser_mode():
    """以传统外部浏览器模式启动墨语。"""
    if is_instance_running():
        webbrowser.open(URL)
        sys.exit(0)

    import uvicorn
    from app.main import create_app

    config = uvicorn.Config(
        create_app(open_browser=True),
        host=HOST,
        port=PORT,
        log_config=None,
    )
    server = uvicorn.Server(config)
    server.run()


def run_desktop_window_mode():
    """以轻量原生窗口（WebView2）模式启动墨语。"""
    already_running = is_instance_running(HOST, PORT)
    server = None
    server_thread = None

    if not already_running:
        import uvicorn
        from app.main import create_app

        app = create_app(open_browser=False)
        # 显式 log_config=None 避免 --noconsole 模式下尝试配置控制台 formatter 导致崩溃
        config = uvicorn.Config(app, host=HOST, port=PORT, log_config=None)
        server = uvicorn.Server(config)

        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        wait_for_server_ready(HOST, PORT, timeout=10.0)

    try:
        import webview

        def on_closed():
            # 窗体关闭时，如果当前进程托管了服务，向 Uvicorn 发送退出信号彻底杀除后台
            if server:
                server.should_exit = True

        window = webview.create_window(
            title=WINDOW_TITLE,
            url=URL,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT),
            text_select=True,
        )
        window.events.closed += on_closed

        # 启动主事件循环（阻塞直至主窗体关闭）
        webview.start()

        if server:
            server.should_exit = True
    except Exception as e:
        if server:
            server.should_exit = True
        err_msg = f"原生窗口初始化异常，回退至浏览器模式: {e}\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        webbrowser.open(URL)
        if server and server_thread:
            server_thread.join(timeout=1.0)
            uvicorn.run(app, host=HOST, port=PORT, log_config=None)


def main():
    use_browser = (
        "--browser" in sys.argv
        or os.environ.get("MOYU_WEBVIEW", "").strip() == "0"
        or os.environ.get("MOYU_BROWSER", "").strip() == "1"
    )

    if use_browser:
        run_browser_mode()
    else:
        run_desktop_window_mode()


if __name__ == "__main__":
    main()
