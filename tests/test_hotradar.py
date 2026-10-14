# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""热点雷达单元测试与集成测试：数据层、抓取器契约、服务层 API 与调度器清理。"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.db import get_db
from app.services.hotradar_fetcher import (
    BaseRankFetcher,
    QidianRankFetcher,
    FanqieRankFetcher,
    JjwxRankFetcher,
    save_hot_topics,
    fetch_all_platforms
)
from app.services.hotradar_scheduler import cleanup_expired_topics


def test_hot_topics_table_schema(client):
    """验证 hot_topics 表正确创建且支持增删查改"""
    db = get_db()
    # 插入一条测试榜单条目
    cur = db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected)
           VALUES ('起点', '测试玄幻之王', 1, '["玄幻", "异界大陆"]', 99999.0, '天蚕土豆', 0)"""
    )
    db.commit()
    inserted_id = cur.lastrowid
    assert inserted_id is not None

    row = db.execute("SELECT * FROM hot_topics WHERE id = ?", (inserted_id,)).fetchone()
    assert row["platform"] == "起点"
    assert row["title"] == "测试玄幻之王"
    assert row["rank"] == 1
    assert row["author"] == "天蚕土豆"
    assert row["collected"] == 0


def test_save_hot_topics_upsert(client):
    """验证 save_hot_topics 正确写入与更新已存在数据，且保留用户已收藏状态"""
    db = get_db()
    mock_items = [
        {
            "platform": "番茄",
            "title": "我有一座恐怖屋",
            "rank": 1,
            "genre_tags": ["悬疑", "惊悚"],
            "heat": 500000.0,
            "author": "我会修空调",
        },
        {
            "platform": "晋江",
            "title": "某某",
            "rank": 1,
            "genre_tags": ["纯爱", "校园"],
            "heat": 888888.0,
            "author": "木苏里",
        }
    ]
    saved_count = save_hot_topics(db, mock_items)
    assert saved_count == 2

    # 用户手动收藏某一本
    row = db.execute("SELECT id FROM hot_topics WHERE title = '我有一座恐怖屋'").fetchone()
    db.execute("UPDATE hot_topics SET collected = 1 WHERE id = ?", (row[0],))
    db.commit()

    # 再次刷新并更新数据（排名变化）
    updated_items = [
        {
            "platform": "番茄",
            "title": "我有一座恐怖屋",
            "rank": 2,
            "genre_tags": ["悬疑", "都市"],
            "heat": 520000.0,
            "author": "我会修空调",
        }
    ]
    save_hot_topics(db, updated_items)

    check_row = db.execute("SELECT * FROM hot_topics WHERE id = ?", (row[0],)).fetchone()
    assert check_row["rank"] == 2
    assert check_row["collected"] == 1  # 收藏标记未被覆盖


def test_cleanup_expired_topics(client):
    """验证清理 7 天前过期未收藏的热点，已收藏的不被清理"""
    db = get_db()
    # 插入 10 天前的未收藏热点与已收藏热点
    db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, collected, fetched_at)
           VALUES ('起点', '过期未收藏小说', 10, '[]', 1000.0, 0, datetime('now', 'localtime', '-10 days'))"""
    )
    db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, collected, fetched_at)
           VALUES ('起点', '过期已收藏小说', 11, '[]', 2000.0, 1, datetime('now', 'localtime', '-10 days'))"""
    )
    db.commit()

    deleted = cleanup_expired_topics(db, days=7)
    assert deleted >= 1

    # 未收藏的被清理，已收藏的仍保留
    uncollected = db.execute("SELECT * FROM hot_topics WHERE title = '过期未收藏小说'").fetchone()
    assert uncollected is None

    collected = db.execute("SELECT * FROM hot_topics WHERE title = '过期已收藏小说'").fetchone()
    assert collected is not None


def test_api_hotradar_list_and_filter(client):
    """测试 GET /api/hotradar/list 接口及平台/题材过滤"""
    db = get_db()
    db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected)
           VALUES ('起点', '凡人修仙传', 1, '["仙侠", "凡人流"]', 100000.0, '忘语', 1)"""
    )
    db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected)
           VALUES ('番茄', '开局神级抽卡', 1, '["都市", "系统"]', 80000.0, '作者A', 0)"""
    )
    db.commit()

    # 1. 查询全部
    res = client.get("/api/hotradar/list")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total"] >= 2

    # 2. 平台过滤
    res_qd = client.get("/api/hotradar/list?platform=起点")
    assert res_qd.status_code == 200
    items_qd = res_qd.json()["items"]
    assert all(item["platform"] == "起点" for item in items_qd)

    # 3. 题材过滤
    res_genre = client.get("/api/hotradar/list?genre=仙侠")
    assert res_genre.status_code == 200
    items_genre = res_genre.json()["items"]
    assert any("仙侠" in item["genre_tags"] for item in items_genre)

    # 4. 仅看收藏过滤
    res_coll = client.get("/api/hotradar/list?collected=1")
    assert res_coll.status_code == 200
    items_coll = res_coll.json()["items"]
    assert all(item["collected"] is True for item in items_coll)


def test_api_hotradar_collect(client):
    """测试 POST /api/hotradar/collect 切换收藏状态"""
    db = get_db()
    cur = db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected)
           VALUES ('晋江', '未名之书', 5, '["科幻"]', 5000.0, '作者B', 0)"""
    )
    db.commit()
    topic_id = cur.lastrowid

    # 切换为收藏
    res = client.post("/api/hotradar/collect", json={"topic_id": topic_id})
    assert res.status_code == 200
    assert res.json()["collected"] is True

    # 再次切换为取消收藏
    res2 = client.post("/api/hotradar/collect", json={"topic_id": topic_id})
    assert res2.status_code == 200
    assert res2.json()["collected"] is False


def test_api_hotradar_to_outline_draft(client):
    """测试 POST /api/hotradar/to-outline 生成立项草稿建议"""
    db = get_db()
    cur = db.execute(
        """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected)
           VALUES ('起点', '万族之劫', 1, '["高武", "玄幻", "诸天"]', 999999.0, '老鹰吃小鸡', 0)"""
    )
    db.commit()
    topic_id = cur.lastrowid

    res = client.post("/api/hotradar/to-outline", json={"topic_id": topic_id})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    draft = data["draft"]
    assert "万族之劫" in draft["reference_work"]
    assert draft["genre"] == "高武"
    assert "direction" in draft
    assert "one_sentence_story" in draft


def test_mock_fetch_all_platforms():
    import asyncio
    """测试聚合拉取 mock 行为，确保无网络外发并遵循数据契约"""
    mock_items = [
        {"platform": "起点", "title": "Mock书名A", "rank": 1, "genre_tags": ["玄幻"], "heat": 100.0, "author": "A"},
        {"platform": "番茄", "title": "Mock书名B", "rank": 1, "genre_tags": ["都市"], "heat": 200.0, "author": "B"},
    ]

    with patch("app.services.hotradar_fetcher.QidianRankFetcher.fetch", new_callable=AsyncMock) as m_qd:
        with patch("app.services.hotradar_fetcher.FanqieRankFetcher.fetch", new_callable=AsyncMock) as m_fq:
            with patch("app.services.hotradar_fetcher.JjwxRankFetcher.fetch", new_callable=AsyncMock) as m_jj:
                m_qd.return_value = [mock_items[0]]
                m_fq.return_value = [mock_items[1]]
                m_jj.return_value = []

                all_res = asyncio.run(fetch_all_platforms(10))
                assert len(all_res) == 2
                assert all_res[0]["title"] == "Mock书名A"
                assert all_res[1]["title"] == "Mock书名B"

def test_db_migration_hot_topics_table():
    """验证 init_db 正确初始化 hot_topics 表及其字段与索引"""
    import sqlite3
    from app.db import SCHEMA, MIGRATIONS
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, ddl in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    cur = conn.cursor()
    # 检查表是否存在
    row = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hot_topics'").fetchone()
    assert row is not None
    # 检查字段
    cols = [col[1] for col in cur.execute("PRAGMA table_info(hot_topics)").fetchall()]
    for expected in ["id", "platform", "title", "rank", "genre_tags", "heat", "author", "collected", "fetched_at"]:
        assert expected in cols
    conn.close()


def test_api_hotradar_refresh_cooldown_and_mock(client):
    """测试 POST /api/hotradar/refresh 手动抓取与防刷冷却机制"""
    with patch("app.api.hotradar.fetch_all_platforms", new_callable=AsyncMock) as m_fetch:
        m_fetch.return_value = [
            {"platform": "起点", "title": "新刷新热门", "rank": 1, "genre_tags": ["科幻"], "heat": 888.0, "author": "某作者"}
        ]
        # 重置冷却时间
        import app.api.hotradar as hr_mod
        hr_mod._LAST_REFRESH_TIMESTAMP = 0.0

        resp = client.post("/api/hotradar/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["synced_count"] >= 1

        # 立即再次刷新，应触发冷却拦截
        resp2 = client.post("/api/hotradar/refresh")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["ok"] is False
        assert "频繁" in data2["message"] or "冷却" in data2["message"]
