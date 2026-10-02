# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""桌面原生窗口入口 (moyu_entry.py) 单元与集成测试。"""
import os
import socket
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import moyu_entry


def test_is_instance_running_false_on_free_port():
    """未监听的端口应返回 False。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    
    assert moyu_entry.is_instance_running("127.0.0.1", free_port) is False


def test_is_instance_running_true_on_active_server():
    """监听中的端口应返回 True。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    try:
        assert moyu_entry.is_instance_running("127.0.0.1", port) is True
    finally:
        sock.close()


def test_wait_for_server_ready_success():
    """在超时时间内端口连通应返回 True。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    try:
        assert moyu_entry.wait_for_server_ready("127.0.0.1", port, timeout=2.0) is True
    finally:
        sock.close()


def test_wait_for_server_ready_timeout():
    """端口持续未连通时应超时返回 False。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    t0 = time.time()
    result = moyu_entry.wait_for_server_ready("127.0.0.1", free_port, timeout=0.3)
    assert result is False
    assert time.time() - t0 >= 0.25


def test_browser_mode_single_instance_activated():
    """在 --browser 模式下，若检测到已有实例在运行，直接激活唤起已有页面并退出。"""
    with patch("moyu_entry.is_instance_running", return_value=True), \
         patch("moyu_entry.webbrowser.open") as mock_open, \
         pytest.raises(SystemExit) as exc_info:
        moyu_entry.run_browser_mode()

    assert exc_info.value.code == 0
    mock_open.assert_called_once_with(moyu_entry.URL)


def test_main_routes_to_browser_mode_via_cli_flag():
    """当命令行包含 --browser 时分流到 run_browser_mode。"""
    with patch.object(sys, "argv", ["moyu_entry.py", "--browser"]), \
         patch("moyu_entry.run_browser_mode") as mock_browser:
        moyu_entry.main()

    mock_browser.assert_called_once()


def test_main_routes_to_browser_mode_via_env_var(monkeypatch):
    """当环境变量设置 MOYU_WEBVIEW=0 时分流到 run_browser_mode。"""
    monkeypatch.setenv("MOYU_WEBVIEW", "0")
    with patch.object(sys, "argv", ["moyu_entry.py"]), \
         patch("moyu_entry.run_browser_mode") as mock_browser:
        moyu_entry.main()

    mock_browser.assert_called_once()


def test_main_routes_to_desktop_window_mode_by_default():
    """默认情况下直接启动原生桌面窗口模式，绝不随意跳出浏览器。"""
    with patch.object(sys, "argv", ["moyu_entry.py"]), \
         patch("moyu_entry.run_desktop_window_mode") as mock_desktop:
        moyu_entry.main()

    mock_desktop.assert_called_once()


def test_run_desktop_window_mode_lifecycle_and_close():
    """测试 WebView2 原生窗口创建、事件绑定及生命周期退出。"""
    mock_window = MagicMock()
    closed_callbacks = []
    mock_window.events.closed.__iadd__.side_effect = lambda cb: closed_callbacks.append(cb)

    with patch("moyu_entry.is_instance_running", return_value=False), \
         patch("moyu_entry.wait_for_server_ready", return_value=True), \
         patch("uvicorn.Server") as mock_server_cls, \
         patch("threading.Thread") as mock_thread_cls, \
         patch("webview.create_window", return_value=mock_window) as mock_create_window, \
         patch("webview.start") as mock_start:

        mock_server = MagicMock()
        mock_server.should_exit = False
        mock_server_cls.return_value = mock_server

        moyu_entry.run_desktop_window_mode()

        mock_create_window.assert_called_once_with(
            title=moyu_entry.WINDOW_TITLE,
            url=moyu_entry.URL,
            width=moyu_entry.WINDOW_WIDTH,
            height=moyu_entry.WINDOW_HEIGHT,
            min_size=(moyu_entry.MIN_WINDOW_WIDTH, moyu_entry.MIN_WINDOW_HEIGHT),
            text_select=True,
        )
        mock_start.assert_called_once()
        assert mock_server.should_exit is True

        assert len(closed_callbacks) == 1
        closed_callbacks[0]()
        assert mock_server.should_exit is True


def test_run_desktop_window_mode_attaches_to_existing_server():
    """如果本地已有服务实例，直接拉起原生窗口连接，不重复启动 uvicorn。"""
    mock_window = MagicMock()
    with patch("moyu_entry.is_instance_running", return_value=True), \
         patch("uvicorn.Server") as mock_server_cls, \
         patch("webview.create_window", return_value=mock_window) as mock_create_window, \
         patch("webview.start") as mock_start:

        moyu_entry.run_desktop_window_mode()

        # 不应创建新的 uvicorn Server 实例
        mock_server_cls.assert_not_called()
        # 应直接创建原生窗口并启动
        mock_create_window.assert_called_once()
        mock_start.assert_called_once()


def test_run_desktop_window_mode_fallback_on_error():
    """当 webview 初始化失败时，应平稳降级至浏览器打开模式，不闪退。"""
    with patch("moyu_entry.is_instance_running", return_value=False), \
         patch("moyu_entry.wait_for_server_ready", return_value=True), \
         patch("uvicorn.Server") as mock_server_cls, \
         patch("threading.Thread"), \
         patch("webview.create_window", side_effect=RuntimeError("WebView2 not available")), \
         patch("webbrowser.open") as mock_open, \
         patch("uvicorn.run") as mock_uvicorn_run:

        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        moyu_entry.run_desktop_window_mode()

        mock_open.assert_called_once_with(moyu_entry.URL)
        mock_uvicorn_run.assert_called_once()
