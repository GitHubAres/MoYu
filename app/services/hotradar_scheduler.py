# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""热点雷达后台调度器：定时从三大平台抓取热榜并自动清理超过 7 天的旧数据。"""
import asyncio
import logging
import threading
import time
from typing import Optional

from ..db import get_db
from .hotradar_fetcher import fetch_all_platforms, save_hot_topics

logger = logging.getLogger("hotradar_scheduler")

_SCHEDULER_THREAD: Optional[threading.Thread] = None
_RUNNING = False
_INTERVAL_SECONDS = 6 * 3600  # 每 6 小时刷新一次
_CLEANUP_DAYS = 7


def cleanup_expired_topics(db_conn, days: int = _CLEANUP_DAYS) -> int:
    """清理 fetched_at 超过指定天数且未被作者收藏 (collected = 0) 的热点条目"""
    cur = db_conn.cursor()
    cur.execute(
        f"""DELETE FROM hot_topics 
           WHERE collected = 0 
             AND fetched_at < datetime('now', 'localtime', '-{days} days')"""
    )
    deleted = cur.rowcount
    db_conn.commit()
    return deleted


async def run_refresh_cycle():
    """执行一次采集与清理闭环"""
    try:
        topics = await fetch_all_platforms(limit_per_platform=50)
        if topics:
            conn = get_db()
            save_hot_topics(conn, topics)
            cleanup_expired_topics(conn, _CLEANUP_DAYS)
    except Exception as e:
        logger.warning(f"热点雷达定时刷新异常: {e}")


def _scheduler_loop():
    """独立后台线程事件循环"""
    global _RUNNING
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while _RUNNING:
        try:
            loop.run_until_complete(run_refresh_cycle())
        except Exception as e:
            logger.warning(f"调度器运行周期报错: {e}")
        # 轮询睡眠（支持秒级感知停机）
        for _ in range(_INTERVAL_SECONDS):
            if not _RUNNING:
                break
            time.sleep(1)
    loop.close()


def start_scheduler():
    """启动热点雷达后台调度线程（守护线程）"""
    global _SCHEDULER_THREAD, _RUNNING
    if _RUNNING or (_SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive()):
        return
    _RUNNING = True
    _SCHEDULER_THREAD = threading.Thread(target=_scheduler_loop, name="HotradarSchedulerThread", daemon=True)
    _SCHEDULER_THREAD.start()


def stop_scheduler():
    """停止热点雷达调度器"""
    global _RUNNING
    _RUNNING = False