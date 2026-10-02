# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""pytest 公共夹具：临时库 + TestClient。

关键顺序：必须在导入 app 任何模块之前设置 MOYU_DB，
因为 app.db.DB_PATH 在模块导入时一次性求值。
conftest.py 先于同目录测试模块被 pytest 导入，因此此处顶层设置是安全的。
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根目录，供 import app

_TEST_DIR = Path(tempfile.mkdtemp(prefix="moyu_test_"))
os.environ["MOYU_DB"] = str(_TEST_DIR / "test.db")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """整个测试会话共用一个临时数据库的 TestClient。

    - db 文件在临时目录，不触碰真实 data/moyu.db；
    - 导出/导入目录重定向到临时目录，避免在真实 data/ 下留文件；
    - get_db 是线程局部连接，TestClient 的请求跑在 anyio 工作线程，
      各线程会按需自建连接到同一个测试库文件，无需额外处理。
    """
    from app import db as db_module

    db_module._reset_conn()  # 主线程连接指向测试库前清掉可能的旧连接
    db_module.init_db()

    from app.main import create_app

    app = create_app()  # 内部再次 init_db()，并触发 api 模块导入（含 prompts 内置种子）

    # 导出/导入目录在模块导入时按真实 DATA_DIR 求值，这里重定向到临时目录
    import app.exporter as exporter
    import app.api.io_export as io_export

    exporter.EXPORT_DIR = _TEST_DIR / "exports"
    io_export.EXPORT_DIR = exporter.EXPORT_DIR
    io_export.IMPORT_DIR = _TEST_DIR / "imports"

    yield TestClient(app)

    db_module._reset_conn()


def make_work(client, title="测试作品", **kw):
    r = client.post("/api/works", json={"title": title, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def make_volume(client, work_id, title="卷一"):
    r = client.post("/api/volumes", json={"work_id": work_id, "title": title})
    assert r.status_code == 201, r.text
    return r.json()


def make_chapter(client, volume_id, title="第一章"):
    r = client.post("/api/chapters", json={"volume_id": volume_id, "title": title})
    assert r.status_code == 201, r.text
    return r.json()


def make_wvc(client, title="测试作品"):
    """快捷创建 作品→卷→章，返回 (work, volume, chapter)。"""
    w = make_work(client, title)
    v = make_volume(client, w["id"])
    c = make_chapter(client, v["id"])
    return w, v, c
