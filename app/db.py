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

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,          -- 规范名：^[a-z0-9][a-z0-9-]{0,63}$
    title       TEXT NOT NULL,                 -- 展示名
    description TEXT NOT NULL DEFAULT '',      -- 触发依据（L1）
    body_md     TEXT NOT NULL DEFAULT '',      -- SKILL.md 正文（L2）
    version     TEXT NOT NULL DEFAULT '1.0.0',
    enabled     INTEGER NOT NULL DEFAULT 1,
    applies_to  TEXT NOT NULL DEFAULT '',      -- 兼容旧任务类型：continue,expand,... 空=通用
    source      TEXT NOT NULL DEFAULT 'custom',-- builtin|custom|migrated|imported
    icon        TEXT NOT NULL DEFAULT 'auto_awesome',
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    updated_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS skill_files (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    path       TEXT NOT NULL,                  -- 白名单：scripts/ references/ assets/ 前缀
    content    TEXT NOT NULL,
    size       INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(skill_id, path)
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
    "skill_migration_done": "0",

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
    migrate_and_seed_skills(conn)







BUILTIN_SKILLS = [
    {
        "name": "default-continue",
        "title": "续写·顺延文势",
        "description": "在长篇小说写作中顺接既有情节自然续写，保持人物口吻、叙事节奏与文风一致，适合日常推进故事时使用。",
        "applies_to": "continue",
        "icon": "edit_note",
        "body_md": """---
name: default-continue
description: 在长篇小说写作中顺接既有情节自然续写，保持人物口吻、叙事节奏与文风一致，适合日常推进故事时使用。
---

你是一位长篇小说写作助手。请阅读以下上下文，顺着既有文势自然续写，保持人物的口吻与叙事节奏一致，不要复述已有内容。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

请直接输出续写的正文，不要输出解释。""",
    },
    {
        "name": "default-expand",
        "title": "扩写·充实细节",
        "description": "为选区内容充实环境描写、人物动作、心理刻画与感官细节，适合粗纲细化或重点高潮场景铺陈时使用。",
        "applies_to": "expand",
        "icon": "unfold_more",
        "body_md": """---
name: default-expand
description: 为选区内容充实环境描写、人物动作、心理刻画与感官细节，适合粗纲细化或重点高潮场景铺陈时使用。
---

你是一位长篇小说写作助手。请将选区内容扩写得更丰满：补充环境、动作、心理与感官细节，不改变情节走向，保持原有文风。

【上下文】
{{context}}

【待扩写选区】
{{selection}}

【写作要求】
{{instruction}}

请直接输出扩写后的正文，不要输出解释。""",
    },
    {
        "name": "default-shorten",
        "title": "缩写·凝练取舍",
        "description": "压缩精炼冗余铺陈与拖沓情节，提取核心故事动线并保留有力意象，适合节奏紧凑化与篇幅精简时使用。",
        "applies_to": "shorten",
        "icon": "unfold_less",
        "body_md": """---
name: default-shorten
description: 压缩精炼冗余铺陈与拖沓情节，提取核心故事动线并保留有力意象，适合节奏紧凑化与篇幅精简时使用。
---

你是一位长篇小说写作助手。请将选区内容缩写压缩，保留关键情节信息与最有力的意象，删去冗余铺陈，语言凝练。

【上下文】
{{context}}

【待缩写选区】
{{selection}}

【写作要求】
{{instruction}}

请直接输出缩写后的正文，不要输出解释。""",
    },
    {
        "name": "default-rewrite",
        "title": "改写润色·字句打磨",
        "description": "修正病句错别字、替换平淡俗套表达、优化叙事节奏与文学意蕴，适合草稿定稿前精修打磨时使用。",
        "applies_to": "rewrite",
        "icon": "auto_fix_high",
        "body_md": """---
name: default-rewrite
description: 修正病句错别字、替换平淡俗套表达、优化叙事节奏与文学意蕴，适合草稿定稿前精修打磨时使用。
---

你是一位长篇小说写作助手。请对选区文字进行改写润色：修正语病、替换平淡表达、调整句式节奏，但保留原意与叙事视角。

【上下文】
{{context}}

【待润色选区】
{{selection}}

【写作要求】
{{instruction}}

请直接输出润色后的正文，不要输出解释。""",
    },
    {
        "name": "default-outline",
        "title": "大纲生成·纲举目张",
        "description": "基于背景设定与主线构思生成卷章大纲，明确分卷主题、主线冲突与伏笔钩子，适合新篇开局与长线架构时使用。",
        "applies_to": "outline",
        "icon": "account_tree",
        "body_md": """---
name: default-outline
description: 基于背景设定与主线构思生成卷章大纲，明确分卷主题、主线冲突与伏笔钩子，适合新篇开局与长线架构时使用。
---

你是一位长篇小说策划助手。请基于已有上下文与设定，生成结构清晰的故事大纲，按「卷/章」层级列出节点，每个节点给出标题与一句话梗概，注意承接收束已有伏笔。

【上下文】
{{context}}

【相关要求】
{{instruction}}

请直接输出大纲，不要输出解释。""",
    },
    {
        "name": "default-audit",
        "title": "设定检查·脉络稽核",
        "description": "交叉对照全书设定库，严密审校战力体系、人物性格、时间线先后与地理逻辑矛盾，保障长篇逻辑严密无脱节。",
        "applies_to": "audit",
        "icon": "fact_check",
        "body_md": """---
name: default-audit
description: 交叉对照全书设定库，严密审校战力体系、人物性格、时间线先后与地理逻辑矛盾，保障长篇逻辑严密无脱节。
---

你是一位长篇小说的设定一致性审校助手。请对照作品设定库，检查所选章节正文中是否存在与设定矛盾、遗忘前后文、时间线错位等问题。

【作品设定】
{{context}}

【待检查章节】
{{selection}}

【检查要求】
{{instruction}}

请逐条列出问题：问题类型、严重程度、涉及设定、问题描述、原文引用、所在章节。""",
    },
]


def migrate_and_seed_skills(conn: sqlite3.Connection | None = None):
    """首启自动迁移旧 prompts 到 skills 表，并初始化规范内置 Skill 种子。幂等执行。"""
    if conn is None:
        conn = get_db()

    # 1. 检查是否已完成迁移
    migrated_row = conn.execute("SELECT value FROM app_settings WHERE key = 'skill_migration_done'").fetchone()
    already_done = migrated_row and str(migrated_row[0]).strip() == "1"

    # 2. 插入或确保内置 Skill 种子就绪
    for s in BUILTIN_SKILLS:
        conn.execute("""
            INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon)
            VALUES (?, ?, ?, ?, '1.0.0', 1, ?, 'builtin', ?)
            ON CONFLICT(name) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                body_md = excluded.body_md,
                applies_to = excluded.applies_to,
                source = 'builtin',
                icon = excluded.icon
        """, (s["name"], s["title"], s["description"], s["body_md"], s["applies_to"], s["icon"]))

    # 3. 若未完成旧数据迁移，将 prompts 表内容平滑迁移至 skills 表
    if not already_done:
        try:
            has_prompts = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prompts'").fetchone()
            if has_prompts:
                p_rows = conn.execute("SELECT id, name, task_type, template, builtin FROM prompts").fetchall()
                for r in p_rows:
                    pid = r["id"]
                    pname = (r["name"] or "").strip() or f"旧模板{pid}"
                    ptask = r["task_type"] or "continue"
                    ptpl = r["template"] or ""
                    pbuiltin = int(r["builtin"]) if r["builtin"] is not None else 0

                    if pbuiltin == 1:
                        continue

                    cand_name = f"migrated-{pid}"
                    counter = 2
                    while conn.execute("SELECT 1 FROM skills WHERE name=?", (cand_name,)).fetchone():
                        cand_name = f"migrated-{pid}-{counter}"
                        counter += 1

                    desc = f"自旧版提示词「{pname}」迁移而来，任务类型：{ptask}。"
                    body_md = f"---\nname: {cand_name}\ndescription: {desc}\n---\n\n{ptpl}"

                    conn.execute("""
                        INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon)
                        VALUES (?, ?, ?, ?, '1.0.0', 1, ?, 'migrated', 'auto_awesome')
                    """, (cand_name, pname, desc, body_md, ptask))
        except Exception:
            pass

        conn.execute("""
            INSERT INTO app_settings(key, value) VALUES ('skill_migration_done', '1')
            ON CONFLICT(key) DO UPDATE SET value = '1'
        """)

    conn.commit()


def word_count(text: str) -> int:

    """字数口径：去除空白字符后的字符数（含标点，含中英文）。"""

    return len("".join(text.split()))
