# 墨语 MoYu - Copyright (c) 2026 墨语MoYu开发团队
# Licensed under the MIT License. See LICENSE.
"""全仓代码与静态资源编码完整性与乱码占位符长效回归测试"""
import os


def test_no_corrupted_question_mark_placeholders_in_frontend():
    """断言前端所有非第三方静态资源中不存在连续乱码问号占位符"""
    corrupted_files = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_dir = os.path.join(base_dir, "static")

    for root, dirs, files in os.walk(static_dir):
        if "vendor" in root:
            continue
        for f in files:
            if f.endswith((".js", ".html", ".css")):
                fpath = os.path.join(root, f)
                with open(fpath, "rb") as fh:
                    content = fh.read()
                if b"????" in content:
                    corrupted_files.append((os.path.relpath(fpath, base_dir), content.count(b"????")))

    assert len(corrupted_files) == 0, f"发现前端静态资源中存在问号乱码损毁: {corrupted_files}"


def test_no_corrupted_question_mark_placeholders_in_backend_and_tests():
    """断言后端 Python 代码与自动化测试套件中不存在连续乱码问号占位符"""
    corrupted_files = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    target_dirs = [os.path.join(base_dir, "app"), os.path.join(base_dir, "tests")]

    for target_dir in target_dirs:
        for root, dirs, files in os.walk(target_dir):
            if "__pycache__" in root:
                continue
            for f in files:
                # 排除本测试文件自身包含的断言字符串字面量
                if f == "test_frontend_encoding.py":
                    continue
                if f.endswith(".py"):
                    fpath = os.path.join(root, f)
                    with open(fpath, "rb") as fh:
                        content = fh.read()
                    if b"????" in content:
                        corrupted_files.append((os.path.relpath(fpath, base_dir), content.count(b"????")))

    assert len(corrupted_files) == 0, f"发现后端或测试文件中存在问号乱码损毁: {corrupted_files}"
