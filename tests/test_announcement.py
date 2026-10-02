# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""公告模块测试套件：覆盖拉取入库、超时降级、内置兜底、ack幂等、force逻辑、min_app_version过滤、XSS转义与列表排序等。"""
import datetime
import json
import subprocess
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api.announcement import (
    BUILTIN_PATH,
    _is_time_active,
    _load_builtin_announcement,
)
from app.db import get_db
from app.version import APP_VERSION


def test_fetch_remote_and_save_to_db(client):
    """用例 1: 远程拉取成功并持久化落库。"""
    remote_data = {
        "id": "remote-test-001",
        "level": "normal",
        "title": "测试远程公告",
        "body_md": "## 远程特性\n- 欢迎使用墨语",
        "link_url": "https://example.com/details",
        "link_text": "详情链接",
        "version_tag": "1.5.0",
        "starts_at": "2026-01-01T00:00:00Z",
        "ends_at": "",
        "min_app_version": "1.0.0",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = remote_data

    async def fake_get(*args, **kwargs):
        return mock_resp

    with patch.object(httpx.AsyncClient, "get", side_effect=fake_get):
        res = client.get("/api/announcements/latest")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["ok"] is True
        ann = data["announcement"]
        assert ann["id"] == "remote-test-001"
        assert ann["title"] == "测试远程公告"
        assert ann["source"] == "remote"
        assert ann["acked"] is False

    # 查库验证
    db = get_db()
    row = db.execute("SELECT * FROM announcements WHERE id = 'remote-test-001'").fetchone()
    assert row is not None
    assert row["title"] == "测试远程公告"


def test_remote_timeout_falls_back_to_cache(client):
    """用例 2: 远程拉取超时时，静默降级读取本地缓存快照。"""
    db = get_db()
    now_str = (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash)
        VALUES ('cache-001', 'remote', 'normal', '已缓存的公告', '正文内容', ?, 'hash123')
        ON CONFLICT(id) DO UPDATE SET title = excluded.title, fetched_at = excluded.fetched_at
        """,
        (now_str,),
    )
    db.commit()

    async def fake_timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("Connection timeout")

    with patch.object(httpx.AsyncClient, "get", side_effect=fake_timeout):
        res = client.get("/api/announcements/latest")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        ann = data["announcement"]
        assert ann["id"] == "cache-001"
        assert ann["title"] == "已缓存的公告"


def test_empty_remote_and_empty_cache_falls_back_to_builtin(client):
    """用例 3: 远程失败且本地无缓存时，降级使用 static/announcements/builtin.json 兜底。"""
    db = get_db()
    db.execute("DELETE FROM announcement_acks")
    db.execute("DELETE FROM announcements")
    db.commit()

    async def fake_error(*args, **kwargs):
        raise httpx.ConnectError("Network offline")

    with patch.object(httpx.AsyncClient, "get", side_effect=fake_error):
        res = client.get("/api/announcements/latest")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        ann = data["announcement"]
        assert ann is not None
        assert ann["id"] == "builtin-v150-release"
        assert ann["source"] == "builtin"
        assert "V1.5.0" in ann["title"]


def test_ack_idempotency_and_types(client):
    """用例 4: ack 接口幂等性、记录更新及非法类型校验。"""
    db = get_db()
    db.execute(
        """
        INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash)
        VALUES ('ack-test-001', 'builtin', 'normal', '确认测试', '内容', '2026-10-01 10:00:00', 'hash')
        ON CONFLICT(id) DO NOTHING
        """
    )
    db.commit()

    # 1. 首次确认 ack_type=view
    r1 = client.post("/api/announcements/ack-test-001/ack", json={"ack_type": "view"})
    assert r1.status_code == 200
    assert r1.json()["ack_type"] == "view"

    # 2. 幂等再次确认 ack_type=confirm
    r2 = client.post("/api/announcements/ack-test-001/ack", json={"ack_type": "confirm"})
    assert r2.status_code == 200
    assert r2.json()["ack_type"] == "confirm"

    # 3. 验证数据库中仅保留一条记录
    acks = db.execute("SELECT * FROM announcement_acks WHERE announcement_id = 'ack-test-001'").fetchall()
    assert len(acks) == 1
    assert acks[0]["ack_type"] == "confirm"

    # 4. 非法类型校验
    r3 = client.post("/api/announcements/ack-test-001/ack", json={"ack_type": "invalid_type"})
    assert r3.status_code == 422


def test_force_level_logic(client):
    """用例 5: force 级公告字段完整保留，配合 ack 状态返回。"""
    db = get_db()
    future_fetched = (datetime.datetime.now() + datetime.timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash)
        VALUES ('force-test-001', 'remote', 'force', '紧急安全维护公告', '请知悉', ?, 'hashforce')
        ON CONFLICT(id) DO UPDATE SET level = 'force', fetched_at = excluded.fetched_at
        """,
        (future_fetched,),
    )
    db.commit()

    async def fake_error(*args, **kwargs):
        raise httpx.ConnectError("Offline")

    with patch.object(httpx.AsyncClient, "get", side_effect=fake_error):
        res = client.get("/api/announcements/latest")
        assert res.status_code == 200
        ann = res.json()["announcement"]
        assert ann["id"] == "force-test-001"
        assert ann["level"] == "force"
        assert ann["acked"] is False

    # 标记 view 之后，再取仍可取到，但 acked 变为 True
    client.post("/api/announcements/force-test-001/ack", json={"ack_type": "view"})
    with patch.object(httpx.AsyncClient, "get", side_effect=fake_error):
        res2 = client.get("/api/announcements/latest")
        ann2 = res2.json()["announcement"]
        assert ann2["acked"] is True
        assert ann2["ack_type"] == "view"


def test_min_app_version_filtering(client):
    """用例 6: 当远程公告要求更高客户端版本时，本地自动忽略该公告。"""
    remote_data = {
        "id": "future-version-ann",
        "level": "normal",
        "title": "未来版本专享公告",
        "body_md": "需要 v99.0.0 客户端",
        "min_app_version": "99.0.0",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = remote_data

    async def fake_get(*args, **kwargs):
        return mock_resp

    with patch.object(httpx.AsyncClient, "get", side_effect=fake_get):
        res = client.get("/api/announcements/latest")
        assert res.status_code == 200
        ann = res.json()["announcement"]
        assert ann["id"] != "future-version-ann"


def test_announcement_list_sorting_and_acked_flags(client):
    """用例 7: 公告列表接口按时间倒序排列，并带出正确已读状态。"""
    db = get_db()
    db.execute("DELETE FROM announcement_acks")
    db.execute("DELETE FROM announcements")

    db.execute(
        "INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash) "
        "VALUES ('a1', 'remote', 'normal', '公告1', '正文', '2026-10-01 10:00:00', 'h1')"
    )
    db.execute(
        "INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash) "
        "VALUES ('a2', 'remote', 'normal', '公告2', '正文', '2026-10-02 12:00:00', 'h2')"
    )
    db.execute(
        "INSERT INTO announcements (id, source, level, title, body_md, fetched_at, content_hash) "
        "VALUES ('a3', 'remote', 'normal', '公告3', '正文', '2026-10-01 08:00:00', 'h3')"
    )
    db.execute("INSERT INTO announcement_acks (announcement_id, acked_at, ack_type) VALUES ('a2', '2026-10-02 12:30:00', 'confirm')")
    db.commit()

    res = client.get("/api/announcements")
    assert res.status_code == 200
    items = res.json()["announcements"]
    assert len(items) == 3
    assert items[0]["id"] == "a2"
    assert items[0]["acked"] is True
    assert items[0]["ack_type"] == "confirm"

    assert items[1]["id"] == "a1"
    assert items[1]["acked"] is False

    assert items[2]["id"] == "a3"
    assert items[2]["acked"] is False


def test_xss_protection_and_markdown_rules():
    """用例 8: 运行 Node 验证前端迷你 Markdown 渲染器与防 XSS 规则。"""
    node_test_script = """
    const fs = require('fs');
    const vm = require('vm');

    const code = fs.readFileSync('static/js/pages/announcement.js', 'utf8');

    const fakeWindow = {};
    const fakeUi = { el: () => ({ append: () => {}, querySelector: () => null }) };
    const context = {
      window: fakeWindow,
      document: { getElementById: () => null, body: { append: () => {} } },
      ui: fakeUi,
      registerPage: () => {},
      api: {},
      localStorage: { getItem: () => null, setItem: () => {} }
    };
    vm.createContext(context);
    vm.runInContext(code, context);

    const { renderMiniMarkdown, sanitizeHttpsUrl } = context.window.announcement;

    // 1. 验证 HTML 转义：<script> 和 <img 标签不能作为可执行 HTML 出现
    const xssPayload = '<script>alert(1)</script><img src=x onerror=alert(2)>';
    const renderedXss = renderMiniMarkdown(xssPayload);
    if (renderedXss.includes('<script>') || renderedXss.includes('<img')) {
      console.error('XSS payload not properly escaped:', renderedXss);
      process.exit(1);
    }
    if (!renderedXss.includes('&lt;script&gt;') || !renderedXss.includes('&lt;img')) {
      console.error('Missing escaped script/img tags:', renderedXss);
      process.exit(1);
    }

    // 2. 验证 javascript: 链接剥除
    const jsLink = '[恶意链接](javascript:alert(1))';
    const renderedLink = renderMiniMarkdown(jsLink);
    if (renderedLink.includes('javascript:')) {
      console.error('javascript: link was not stripped:', renderedLink);
      process.exit(1);
    }

    // 3. 验证仅允许 https: 协议链接
    const httpLink = '[非https链接](http://insecure.com)';
    const renderedHttp = renderMiniMarkdown(httpLink);
    if (renderedHttp.includes('href=')) {
      console.error('http: link was incorrectly allowed:', renderedHttp);
      process.exit(1);
    }

    const httpsLink = '[安全链接](https://safe.example.com)';
    const renderedHttps = renderMiniMarkdown(httpsLink);
    if (!renderedHttps.includes('href="https://safe.example.com"')) {
      console.error('valid https: link was not rendered properly:', renderedHttps);
      process.exit(1);
    }

    // 4. 验证 Markdown 格式（粗体、标题、列表）
    const mdText = '## 标题二\\n- 列表条目\\n这是**粗体文字**';
    const renderedMd = renderMiniMarkdown(mdText);
    if (!renderedMd.includes('<h2') || !renderedMd.includes('<li') || !renderedMd.includes('<strong')) {
      console.error('Markdown tags missing:', renderedMd);
      process.exit(1);
    }

    console.log('MARKDOWN_XSS_VERIFIED_OK');
    """

    res = subprocess.run(["node", "-e", node_test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node test failed: {res.stderr}\n{res.stdout}"
    assert "MARKDOWN_XSS_VERIFIED_OK" in res.stdout


def test_time_window_filtering():
    """用例 9: starts_at / ends_at 生效时间窗口精确判定。"""
    # 1. 过去已过期
    assert _is_time_active("2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z") is False

    # 2. 未来尚未生效
    future_start = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).isoformat()
    assert _is_time_active(future_start, "") is False

    # 3. 当前有效
    past_start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    future_end = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    assert _is_time_active(past_start, future_end) is True
    assert _is_time_active("", "") is True
