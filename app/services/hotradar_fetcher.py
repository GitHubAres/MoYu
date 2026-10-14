# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
# Licensed under the MIT License. See LICENSE.
"""热点雷达采集服务：仅抓取起点、番茄、晋江三平台公开热榜元数据（书名/排名/题材/热度）。"""
import asyncio
import json
import random
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

# 常见客户端 User-Agent 池，用于避免单固定指纹
USER_AGENTS_DESKTOP = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

USER_AGENTS_MOBILE = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
]

def get_random_ua(mobile: bool = False) -> str:
    pool = USER_AGENTS_MOBILE if mobile else USER_AGENTS_DESKTOP
    return random.choice(pool)


class BaseRankFetcher(ABC):
    """平台排行榜抓取抽象基类"""
    platform_name: str = ""

    @abstractmethod
    async def fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        抓取并返回标准格式作品列表：
        [
            {
                "platform": str,      # 起点 / 番茄 / 晋江
                "title": str,         # 书名
                "rank": int,          # 排名 (1-based)
                "genre_tags": list,   # 题材标签数组
                "heat": float,        # 热度值
                "author": str,       # 原作者
            }
        ]
        """
        pass


class QidianRankFetcher(BaseRankFetcher):
    """起点中文网热销榜/畅销榜抓取器（优先走 M 站 SSR 内联 JSON，稳定且无需登录/无WAF）"""
    platform_name = "起点"
    URL = "https://m.qidian.com/rank/hotsales/"

    async def fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        headers = {
            "User-Agent": get_random_ua(mobile=True),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(self.URL, headers=headers)
                if resp.status_code != 200:
                    return results

                html = resp.text
                m = re.search(r'\{"pageContext":.*?"pageProps":.*?\}\s*</script>', html, re.DOTALL)
                if not m:
                    # 尝试非闭合正则
                    m = re.search(r'\{"pageContext":[\s\S]*?\}\s*</script>', html)
                if m:
                    raw_json = m.group(0).replace('</script>', '').strip()
                    data = json.loads(raw_json)
                    records = data.get("pageContext", {}).get("pageProps", {}).get("pageData", {}).get("records", [])
                    for i, r in enumerate(records[:limit]):
                        b_name = (r.get("bName") or "").strip()
                        if not b_name:
                            continue
                        rank = int(r.get("rankNum") or (i + 1))
                        cat = (r.get("cat") or "").strip()
                        sub_cat = (r.get("subCat") or "").strip()
                        author = (r.get("bAuth") or "").strip()
                        tags = [t for t in [cat, sub_cat] if t]
                        # 热度估计（基于排名递减归一化）
                        heat = max(10000.0, 1000000.0 - (rank - 1) * 35000.0)
                        results.append({
                            "platform": self.platform_name,
                            "title": b_name,
                            "rank": rank,
                            "genre_tags": tags,
                            "heat": heat,
                            "author": author,
                        })
        except Exception:
            pass
        return results


class FanqieRankFetcher(BaseRankFetcher):
    """番茄小说热榜抓取器（从官方公开 rank 页面 window.__INITIAL_STATE__ 获取）"""
    platform_name = "番茄"
    URL = "https://fanqienovel.com/rank"

    async def fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        headers = {
            "User-Agent": get_random_ua(mobile=False),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(self.URL, headers=headers)
                if resp.status_code != 200:
                    return results

                html = resp.text
                m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*(?:\(|<)', html, re.DOTALL)
                if not m:
                    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
                if not m:
                    return results

                state = json.loads(m.group(1))
                book_list = state.get("rank", {}).get("book_list", [])
                
                # 遍历前 N 本书
                for i, b in enumerate(book_list[:limit]):
                    rank = i + 1
                    read_count = float(b.get("read_count") or 0)
                    author = (b.get("author") or "").strip()
                    book_id = str(b.get("bookId") or "")
                    # 若书名包含加密字体字符或缺失，从单书页 SEO title 反查
                    book_name = (b.get("bookName") or "").strip()
                    tags = []
                    cat = b.get("category") or ""
                    if cat:
                        tags.append(str(cat))
                    
                    # 若书名包含私用区 unicode（如 \ue491 等）或过短，尝试从单书详情页读取真实纯明文
                    need_clean = any(ord(c) >= 0xE000 and ord(c) <= 0xF8FF for c in book_name) or not book_name
                    if need_clean and book_id:
                        try:
                            # 轻量请求详情页抓取 title
                            book_url = f"https://fanqienovel.com/page/{book_id}"
                            b_resp = await client.get(book_url, headers=headers, timeout=5.0)
                            if b_resp.status_code == 200:
                                tm = re.search(r'<title>(.*?)_.*?番茄小说', b_resp.text)
                                if not tm:
                                    tm = re.search(r'<title>(.*?)(?:在线免费阅读|小说|番茄小说)', b_resp.text)
                                if tm:
                                    cleaned = tm.group(1).replace("完整版", "").strip()
                                    if cleaned:
                                        book_name = cleaned
                        except Exception:
                            pass

                    if not book_name:
                        book_name = f"热榜作品-{book_id}" if book_id else f"番茄作品第{rank}名"

                    results.append({
                        "platform": self.platform_name,
                        "title": book_name,
                        "rank": rank,
                        "genre_tags": tags if tags else ["热门连载"],
                        "heat": read_count if read_count > 0 else (500000.0 - rank * 15000.0),
                        "author": author,
                    })
        except Exception:
            pass
        return results


class JjwxRankFetcher(BaseRankFetcher):
    """晋江文学城榜单抓取器（经典纯 HTML 表格，GB18030 编码）"""
    platform_name = "晋江"
    URL = "https://www.jjwxc.net/topten.php?orderstr=3"

    async def fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        headers = {
            "User-Agent": get_random_ua(mobile=False),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(self.URL, headers=headers)
                if resp.status_code != 200:
                    return results

                raw_bytes = resp.content
                text = raw_bytes.decode("gb18030", errors="ignore")

                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.DOTALL)
                for r in rows:
                    if "onebook.php?novelid=" not in r:
                        continue
                    tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
                    if len(tds) < 7:
                        continue

                    # 提取排名
                    m_rank = re.search(r'>(\d+)<', tds[0])
                    rank = int(m_rank.group(1)) if m_rank else len(results) + 1

                    # 提取作者
                    m_auth = re.search(r'>([^<]+)</a>', tds[1])
                    author = m_auth.group(1).strip() if m_auth else ""

                    # 提取书名
                    m_title = re.search(r'<a[^>]+title="([^"]+)"', tds[2])
                    if not m_title:
                        m_title = re.search(r'<a[^>]+href="onebook\.php\?novelid=\d+"[^>]*>([^<]+)</a>', tds[2])
                    title = m_title.group(1).strip() if m_title else ""
                    if not title:
                        continue

                    # 提取题材
                    genre_str = re.sub(r'<[^>]+>', '', tds[3]).strip()
                    tags = [g.strip() for g in genre_str.split('-') if g.strip()]

                    # 提取积分热度
                    score_str = re.sub(r'<[^>]+>', '', tds[6]).replace('&nbsp;', '').replace(',', '').strip()
                    try:
                        heat = float(score_str)
                    except ValueError:
                        heat = 0.0

                    results.append({
                        "platform": self.platform_name,
                        "title": title,
                        "rank": rank,
                        "genre_tags": tags,
                        "heat": heat,
                        "author": author,
                    })

                    if len(results) >= limit:
                        break
        except Exception:
            pass
        return results


ALL_FETCHERS = [QidianRankFetcher(), FanqieRankFetcher(), JjwxRankFetcher()]


async def fetch_all_platforms(limit_per_platform: int = 50) -> List[Dict[str, Any]]:
    """聚合抓取三大平台热榜"""
    tasks = [fetcher.fetch(limit=limit_per_platform) for fetcher in ALL_FETCHERS]
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    all_books = []
    for res in results_nested:
        if isinstance(res, list):
            all_books.extend(res)
    return all_books


def save_hot_topics(db_conn, topics: List[Dict[str, Any]]) -> int:
    """将抓取到的热榜数据写入 hot_topics 表（保留既有 collected 标记）"""
    if not topics:
        return 0

    inserted_or_updated = 0
    cur = db_conn.cursor()

    for item in topics:
        platform = item.get("platform") or ""
        title = (item.get("title") or "").strip()
        rank = int(item.get("rank") or 0)
        genre_tags = json.dumps(item.get("genre_tags") or [], ensure_ascii=False)
        heat = float(item.get("heat") or 0)
        author = (item.get("author") or "").strip()

        if not platform or not title:
            continue

        # 检查是否已存在同平台同名作品
        existing = cur.execute(
            "SELECT id, collected FROM hot_topics WHERE platform = ? AND title = ?",
            (platform, title)
        ).fetchone()

        if existing:
            # 更新排名、热度与最新抓取时间，保持 collected 不变
            cur.execute(
                """UPDATE hot_topics 
                   SET rank = ?, genre_tags = ?, heat = ?, author = ?, fetched_at = datetime('now','localtime')
                   WHERE id = ?""",
                (rank, genre_tags, heat, author, existing[0])
            )
        else:
            cur.execute(
                """INSERT INTO hot_topics (platform, title, rank, genre_tags, heat, author, collected, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now','localtime'))""",
                (platform, title, rank, genre_tags, heat, author)
            )
        inserted_or_updated += 1

    db_conn.commit()
    return inserted_or_updated