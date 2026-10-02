# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""SQLite 数据层：连接管理与建表。"""
import os
import sqlite3
import threading
from pathlib import Path

from .paths import DATA_DIR

# 可用环境变量 MOYU_DB 覆盖（测试切库用），默认行为不变
DB_PATH = Path(os.environ.get("MOYU_DB", str(DATA_DIR / "moyu.db")))

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    intro TEXT DEFAULT '',
    genre TEXT DEFAULT '',
    cover_color TEXT DEFAULT '#1B2A38',
    status TEXT DEFAULT '连载中',
    style_profile TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    volume_id INTEGER NOT NULL REFERENCES volumes(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    word_count INTEGER DEFAULT 0,
    cursor_pos INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS chapter_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'auto',
    label TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS outline_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES outline_nodes(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    synopsis TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    category TEXT DEFAULT 'character',
    name TEXT NOT NULL,
    fields_json TEXT DEFAULT '{}',
    content TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    archived INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS chapter_entities (
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (chapter_id, entity_id)
);
CREATE TABLE IF NOT EXISTS foreshadows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'planted',
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER REFERENCES works(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    task_type TEXT DEFAULT 'continue',
    template TEXT NOT NULL,
    builtin INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER REFERENCES works(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    format TEXT NOT NULL,
    scope TEXT DEFAULT '{}',
    path TEXT DEFAULT '',
    status TEXT DEFAULT 'done',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS entity_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    from_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    label TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    time_label TEXT DEFAULT '',
    event TEXT NOT NULL,
    characters TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chapters_volume ON chapters(volume_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_versions_chapter ON chapter_versions(chapter_id, id DESC);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    kind TEXT DEFAULT 'illustration',
    prompt TEXT DEFAULT '',
    path TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_entities_work ON entities(work_id, category);

CREATE TABLE IF NOT EXISTS ai_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER REFERENCES works(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL,
    input_summary TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    output_json TEXT DEFAULT '',
    token_used INTEGER DEFAULT 0,
    elapsed_ms INTEGER DEFAULT 0,
    error_msg TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_work ON ai_tasks(work_id, status, id DESC);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_chap ON chat_sessions(chapter_id, id DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    task_type TEXT DEFAULT '',
    meta_json TEXT DEFAULT '{}',
    adopted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, id ASC);

CREATE TABLE IF NOT EXISTS announcements (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    level         TEXT NOT NULL DEFAULT 'normal',
    title         TEXT NOT NULL,
    body_md       TEXT NOT NULL,
    link_url      TEXT DEFAULT '',
    link_text     TEXT DEFAULT '',
    version_tag   TEXT DEFAULT '',
    starts_at     TEXT DEFAULT '',
    ends_at       TEXT DEFAULT '',
    fetched_at    TEXT NOT NULL,
    content_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcement_acks (
    announcement_id TEXT PRIMARY KEY REFERENCES announcements(id),
    acked_at        TEXT NOT NULL,
    ack_type        TEXT DEFAULT 'view'
);
"""

DEFAULT_SETTINGS = {
    "theme": "light",
    "editor_font_size": "18",
    "editor_line_height": "1.9",
    "autosave_interval": "2",
    "daily_word_goal": "5000",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "",
    "version_keep_auto": "30",
    "token_used": "0",
    "img_base_url": "https://api.siliconflow.cn/v1",
    "img_api_key": "",
    "img_model": "Kwai-Kolors/Kolors",
    "img_size": "1024x1024",
    "update_channel": "stable",
    "update_auto_check": "1",
    "update_last_check": "",
    "update_skipped_ver": "",
    "update_mirror": "",
    "announcement_url": "https://github.com/GitHubAres/MoYu/releases/latest/download/announcement.json",
}


def get_db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return conn


def _reset_conn():
    """关闭并清空当前线程的缓存连接（测试切换数据库路径时用）。"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


# 增量迁移：(列名, 定义) —— 旧库缺列时 ALTER TABLE 补上
MIGRATIONS = {
    "chapters": [("cursor_pos", "INTEGER DEFAULT 0")],
    "works": [("style_profile", "TEXT DEFAULT ''"), ("cover_image", "TEXT DEFAULT ''")],
}


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, ddl in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)", (k, v))
    conn.commit()


def word_count(text: str) -> int:
    """字数口径：去除空白字符后的字符数（含标点，含中英文）。"""
    return len("".join(text.split()))
