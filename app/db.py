import warnings
import re
import json
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者

# Licensed under the MIT License. See LICENSE.

"""SQLite 数据层：连接管理与建表。"""

import os

import sqlite3

import threading

from datetime import datetime

from pathlib import Path



from .paths import DATA_DIR
from .builtin_skill_data import (
    STYLE_FINGERPRINT,
    PROSE_CRAFT,
    GENRE_PLAYBOOK,
    EXPANSION_CRAFT,
    REWRITE_DIMENSIONS,
    COMPRESSION_FORMATS,
    STRUCTURE_MODELS,
    CONSISTENCY_TAXONOMY,
    AI_TONE_CATALOG,
    ANALYSIS_RUBRIC,
    CREATION_PIPELINE,
    CHARACTER_ARC_MODELS,
    WORLDBUILDING_CHECKLIST,
    SCENE_BEATS,
    TIMELINE_ANCHOR_RULES,
    FORESHADOW_CRAFT,
    POWER_SCALING_RULES,
    COMBAT_RHYTHM,
    PREMISE_TEMPLATES,
    FACTION_DYNAMICS,
    HOOK_CATALOG,
    HERO_JOURNEY_CHECK,
    SUBTEXT_DIALOGUE_RULES,
    SENSORY_IMMERSION,
    FORESHADOW_VERIFICATION,
    CAUSALITY_AUDIT,
    RHYTHM_SCORING_RUBRIC,
)



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

    outline_node_id INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL,

    created_at TEXT DEFAULT (datetime('now','localtime'))

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

    outline_node_id INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL,

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
    builtin_version TEXT DEFAULT '1.0.0',
    user_modified   INTEGER DEFAULT 0,
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

-- 写作工作流：可编辑的 Skill 步骤序列，一键编排运行
CREATE TABLE IF NOT EXISTS workflows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    icon        TEXT DEFAULT 'account_tree',
    scope       TEXT DEFAULT 'global',        -- global | work:<work_id>
    enabled     INTEGER DEFAULT 1,
    builtin     INTEGER DEFAULT 0,            -- 内置示例禁删，可复制
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    updated_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id   INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,           -- 执行顺序，从 0 起
    title         TEXT NOT NULL,
    skill_id      INTEGER REFERENCES skills(id),
    input_mode    TEXT DEFAULT 'chapter',     -- chapter | prev_output | merge | none
    prev_step_seq INTEGER,
    ref_step_seqs TEXT DEFAULT '[]',          -- 引用前序步骤序号列表 JSON
    context_sources TEXT DEFAULT '["chapter","triad"]', -- 上下文装配源列表 JSON: chapter, triad
    output_var    TEXT DEFAULT '',
    instruction   TEXT DEFAULT '',            -- 固定补充指令，可引用 {{steps.N.output}}
    length        TEXT DEFAULT 'medium',
    candidates    INTEGER DEFAULT 1,
    requires_review INTEGER DEFAULT 1,        -- 人工确认闸
    enabled       INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    updated_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_wf ON workflow_steps(workflow_id, seq);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  INTEGER NOT NULL REFERENCES workflows(id),
    work_id      INTEGER REFERENCES works(id) ON DELETE CASCADE,
    chapter_id   INTEGER,
    outline_node_id INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL,
    status       TEXT DEFAULT 'pending',      -- pending|running|awaiting_review|done|failed|cancelled
    current_step INTEGER DEFAULT 0,
    error_msg    TEXT DEFAULT '',
    token_used   INTEGER DEFAULT 0,
    started_at   TEXT,
    finished_at  TEXT,
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS workflow_run_steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_seq     INTEGER NOT NULL,
    title        TEXT NOT NULL,
    ai_task_id   INTEGER,
    status       TEXT DEFAULT 'pending',      -- pending|running|awaiting_review|approved|skipped|failed
    output       TEXT DEFAULT '',
    review_note  TEXT DEFAULT '',
    token_used   INTEGER DEFAULT 0,
    elapsed_ms   INTEGER DEFAULT 0,
    updated_at   TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(run_id, step_seq)
);

CREATE TABLE IF NOT EXISTS hot_topics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    platform     TEXT NOT NULL,               -- 起点 / 番茄 / 晋江
    title        TEXT NOT NULL,               -- 作品名/话题名/榜单条目
    rank         INTEGER NOT NULL,            -- 榜单排名
    genre_tags   TEXT DEFAULT '[]',           -- 题材标签 JSON
    heat         REAL DEFAULT 0,              -- 热度数值/追读/月票
    author       TEXT DEFAULT '',             -- 作者名/所属品类
    collected    INTEGER DEFAULT 0,           -- 是否收藏 (0/1)
    fetched_at   TEXT DEFAULT (datetime('now','localtime')) -- 采集时间
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run ON workflow_run_steps(run_id, step_seq);

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
    "ai_timeout": "300",

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
    "ai_models_cache": "",

}





def get_db() -> sqlite3.Connection:

    conn = getattr(_local, "conn", None)

    if conn is None:

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        from . import db as _db_mod
        target_path = getattr(_db_mod, "DB_PATH", DB_PATH)
        conn = sqlite3.connect(target_path, timeout=15.0)

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass

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

    "timeline_events": [("outline_node_id", "INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL")],

    "foreshadows": [("outline_node_id", "INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL")],

    "workflow_runs": [("outline_node_id", "INTEGER REFERENCES outline_nodes(id) ON DELETE SET NULL")],

    "workflow_steps": [
        ("ref_step_seqs", "TEXT DEFAULT '[]'"),
        ("context_sources", "TEXT DEFAULT '[\"chapter\",\"triad\"]'"),
    ],
    "hot_topics": [
        ("author", "TEXT DEFAULT ''"),
        ("collected", "INTEGER DEFAULT 0"),
        ("fetched_at", "TEXT DEFAULT (datetime('now','localtime'))"),
    ],
    "skills": [
        ("builtin_version", "TEXT DEFAULT '1.0.0'"),
        ("user_modified", "INTEGER DEFAULT 0"),
    ],
}





def init_db():

    conn = get_db()

    conn.executescript(SCHEMA)
    conn.execute("DROP TABLE IF EXISTS notes")

    for table, cols in MIGRATIONS.items():

        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

        for col, ddl in cols:

            if col not in existing:

                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_outline_node ON timeline_events(outline_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_foreshadows_outline_node ON foreshadows(outline_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_outline_node ON workflow_runs(outline_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_topics_platform_rank ON hot_topics(platform, rank)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_topics_fetched_at ON hot_topics(fetched_at)")

    for k, v in DEFAULT_SETTINGS.items():

        conn.execute("INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    migrate_and_seed_skills(conn)
    seed_builtin_workflows(conn)







BUILTIN_SKILLS = [
    # =========================================================================
    # 一、立项与世界观体系 (Premise & Worldbuilding)
    # =========================================================================
    {
        "name": "novel-premise",
        "title": "灵感立项·核心金手指定位",
        "description": "从灵感碎片提炼小说核心立意、初始绝境、金手指差异化优势与核心卖点。",
        "applies_to": "premise",
        "icon": "lightbulb",
        "version": "2.0.0",
        "body_md": """# 灵感立项与核心金手指定位 (Novel Premise)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位专精商业网文选题与开篇破局的总编辑。请根据作者提供的灵感片段、题材类型或初步脑洞，梳理提炼小说的核心立项方案。

【执行步骤】：
1. 核心困局 (Setup)：明确主角开篇面临的不可调和的绝境或危机。
2. 金手指与核心爽点 (Hook)：设计运作机制清晰、具备成长性与唯一性的差异化金手指。
3. 主线动力引擎 (Engine)：明确全书主线的根本推动力与长远追求。

【交付契约】：
正文给出结构清晰的立项评估与建议；
文末必须附加 MOYU:ASSETS 契约块，规范交付 work_info、entities 与 notes。
""",
        "files": [
            ("references/premise-templates.md", PREMISE_TEMPLATES),
            ("references/genre-playbook.md", GENRE_PLAYBOOK),
        ],
    },
    {
        "name": "novel-world",
        "title": "世界观·三界九域与底层法则",
        "description": "构筑世界观背景、三界九域地理版图、文明历史底色与不可动摇的底层法则。",
        "applies_to": "world",
        "icon": "public",
        "version": "2.0.0",
        "body_md": """# 世界观体系与底层法则构筑 (Novel World)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位宏观世界观架构师。请为作品搭建自洽、厚重且富有探索欲望的世界观体系。

【核心原则】：
1. 三界九域版图：划分核心势力分布、自然地理与禁区险境。
2. 历史与文明断层：设定前史重大转折事件与上古遗秘。
3. 核心法则与代价：世界观超自然现象必须附带不可违背的法则代价。
4. 契约产出：沉淀地点 (place)、阵营 (faction) 等基础实体与前史 timeline_events。
""",
        "files": [
            ("references/worldbuilding-checklist.md", WORLDBUILDING_CHECKLIST),
        ],
    },
    {
        "name": "novel-magic-system",
        "title": "战力法则·修炼阶梯与代价值构建",
        "description": "设计修炼境界、神通法则阶梯、消耗反噬与战力天花板，防止长篇战力通胀。",
        "applies_to": "system",
        "icon": "military_tech",
        "version": "2.0.0",
        "body_md": """# 修炼体系与战力法则构建 (Novel Magic System)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位专精小说力量体系平衡的数值与法则架构师。请构建阶梯严密、质变清晰且充满代价感的修炼体系。

【核心原则】：
1. 境界质变：每个层级必须具备明确的标志性能力与战力质变感。
2. 代价与反噬：越强大的能力，其付出与反噬惩罚越严苛，严禁无痛爆种。
3. 契约沉淀：所有功法、境界、天材地宝以 category='term' 实体沉淀入库。
""",
        "files": [
            ("references/power-scaling-rules.md", POWER_SCALING_RULES),
        ],
    },
    {
        "name": "novel-cast",
        "title": "万相谱·主要角色群像档案",
        "description": "提炼立体角色卡，包含性格软肋、核心欲望、表面伪装与人际纠缠网络。",
        "applies_to": "cast",
        "icon": "group",
        "version": "2.0.0",
        "body_md": """# 万相谱群像人物档案塑造 (Novel Cast)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位人物塑造专家。请将灵感散点提炼为生动鲜明、充满动机冲突的主要角色群像卡片。

【执行准则】：
1. 核心四要素：【核心欲望】、【致命软肋】、【外在伪装/口癖】、【人物底色】。
2. 关系纠葛：明确角色之间不可调和的利益或情感冲突。
3. 契约交付：输出 category='character' 实体，并在 relations 中交付起点/终点人际关系。
""",
        "files": [
            ("references/character-arc-models.md", CHARACTER_ARC_MODELS),
        ],
    },
    {
        "name": "novel-faction-graph",
        "title": "势力割据·阵营关系网络拓扑",
        "description": "梳理各大宗门、王朝、家族与隐秘势力的利益冲突、盟约借势与对抗拓扑。",
        "applies_to": "faction",
        "icon": "hub",
        "version": "2.0.0",
        "body_md": """# 势力割据与阵营博弈动力学 (Novel Faction Graph)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位精通地缘政治与宗派博弈的架构师。请分析并输出各大势力的利益同盟与敌对拓扑关系。

【交付契约】：
文末附加 MOYU:ASSETS，交付 category='faction' 的实体以及各阵营之间的 relations。
""",
        "files": [
            ("references/faction-dynamics.md", FACTION_DYNAMICS),
        ],
    },

    # =========================================================================
    # 二、大纲拓扑与剧情架构 (Plot Architecture)
    # =========================================================================
    {
        "name": "novel-outline-macro",
        "title": "分卷规划·起承转合与大主线",
        "description": "设计全书宏观分卷、卷主线起承转合、卷末大高潮与阶段性核心矛盾转移。",
        "applies_to": "outline",
        "icon": "schema",
        "version": "2.0.0",
        "body_md": """# 宏观大纲与分卷架构规划 (Novel Outline Macro)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位长篇小说总架构师。请根据核心立项与背景，梳理全书分卷规划、核心节拍与大事件推演。

【执行规范】：
1. 分卷起承转合：每卷具备独立的开端、危机发酵、绝境爆发与收网解决。
2. 契约交付：outline_nodes 数组中，分卷项标记 is_volume=true；章节项标记 is_volume=false，并正确填写 parent_title。
""",
        "files": [
            ("references/structure-models.md", STRUCTURE_MODELS),
        ],
    },
    {
        "name": "novel-scene",
        "title": "分场细纲·微观冲突与节拍表",
        "description": "将单章拆解为 3~4 场紧凑戏剧动作，明确入场目标、危机阻碍、转折与章末钩子。",
        "applies_to": "scene",
        "icon": "view_list",
        "version": "2.0.0",
        "body_md": """# 分场细纲与微观冲突节拍 (Novel Scene)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位分场细纲设计专家。请为目标章节编排紧凑利落的分场节拍表。

【执行准则】：
1. 目标-阻碍-结果 (G-O-D)：每一小场角色都必须带着具体目标进场，并遭遇突发阻碍。
2. 状态变化门禁：一场演完情况必须与开始不同。
3. 章末留钩子：章节最后一小场必须留下未闭合的悬念或动作未完切面。
4. 契约产出：细纲中必须标明伏笔回收或埋设节点，输出 outline_nodes、foreshadows 与 timeline_events。
""",
        "files": [
            ("references/scene-beats.md", SCENE_BEATS),
        ],
    },
    {
        "name": "novel-timeline",
        "title": "编年史·剧情大事件时序编织",
        "description": "梳理宏观年号、前史转折与卷章关键大事记，排查物理位移与因果倒错漏洞。",
        "applies_to": "timeline",
        "icon": "timeline",
        "version": "2.0.0",
        "body_md": """# 剧情大事记与时间线编织 (Novel Timeline)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位长篇时序档案官。请梳理时间锚点清晰、因果严密的剧情大事件流水。

【交付契约】：
文末附加 MOYU:ASSETS 契约块，产出 timeline_events 结构化事件数组。
""",
        "files": [
            ("references/timeline-anchor-rules.md", TIMELINE_ANCHOR_RULES),
        ],
    },
    {
        "name": "novel-foreshadow-matrix",
        "title": "伏笔布网·草蛇灰线暗线规划",
        "description": "围绕核心反转设计全书伏笔网，按埋设、浮现推进、收网引爆三段式设计悬念。",
        "applies_to": "foreshadow",
        "icon": "psychology",
        "version": "2.0.0",
        "body_md": """# 草蛇灰线：伏笔暗线规划 (Novel Foreshadow Matrix)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位精通悬疑与反转布局的故事架构师。请为故事设计精密的草蛇灰线网络。

【交付契约】：
文末附加 MOYU:ASSETS，交付 foreshadows 数组（status 仅限 planted/pending/recovered）。
""",
        "files": [
            ("references/foreshadow-craft.md", FORESHADOW_CRAFT),
        ],
    },
    {
        "name": "novel-hook-engineer",
        "title": "黄金钩子·章末悬念留白设计",
        "description": "专精设计章末卡点悬念、信息差引爆与突发危机，极大提升读者连读期待感。",
        "applies_to": "hook",
        "icon": "link",
        "version": "2.0.0",
        "body_md": """# 黄金章末钩子设计 (Novel Hook Engineer)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位专精提升小说读者追读留存率的卡点断章专家。请为当前章节量身定做 3 个极具吸引力的章末黄金钩子。

【五类强钩子】：
1. 新信息差引爆；2. 突发危机逼近；3. 反常关键决断；4. 悬念式对白留白；5. 胜负底牌逆转。
""",
        "files": [
            ("references/hook-catalog.md", HOOK_CATALOG),
        ],
    },
    {
        "name": "novel-lead-arc",
        "title": "命途演进·主角心境与成长轨迹",
        "description": "规划主角心境蜕变、信念崩塌与重塑弧光，确保长篇人物成长深刻可信。",
        "applies_to": "arc",
        "icon": "trending_up",
        "version": "2.0.0",
        "body_md": """# 主角命途演进与成长弧光 (Novel Lead Arc)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位人物心理与成长轨迹架构师。请为主角梳理各分卷阶段的道心蜕变与成长轨迹。
""",
        "files": [
            ("references/hero-journey-check.md", HERO_JOURNEY_CHECK),
        ],
    },

    # =========================================================================
    # 三、正文撰写与文风修撰 (Drafting & Stylistic Craft)
    # =========================================================================
    {
        "name": "prose-continue",
        "title": "顺流续写·紧扣情境推进正文",
        "description": "严格锁定前文人称时态与文风指纹，以动作起笔顺势推进正文，杜绝AI套话。",
        "applies_to": "continue",
        "icon": "edit_note",
        "version": "2.0.0",
        "body_md": """你是一位高水准的长篇中文小说续写助手。请阅读以下上下文与当前选区，顺着既有文势自然续写，保持人物口吻、叙事节奏与文风一致，彻底杜绝机器感。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

续写执行准则（严控 AI 腔与抗检测规范）：
1. 零复述与动作起笔：
   - 第一句话必须直接是新的物理动作、外界变动或突发对白，绝对严禁承上总结前文，严禁"接上一幕……"、"此时此刻……"。
2. 节奏极化与文风下潜 (Burstiness 3-20-3)：
   - 句长严禁均等平铺！长短句交错推进，短句定调断魂（1~5字），长句铺叙动作（35~60字）。
   - 彻底禁用 AI 高频套话："仿佛"、"不禁"、"五味杂陈"、"嘴角勾起一抹笑意"、"眼底闪过一丝复杂"、"空气骤然降温"。
3. 具象生理反射 (Show, Don't Tell)：
   - 情绪全面降维为【汗、瞳、牙、息、肌】五大生理受力反应，禁止直白命名"他感到愤怒/恐惧"。
4. 结尾留钩子：停留在新的动作未完、悬念爆发或危机叩门的切面上。

【输出协议】：
直接输出正文，严禁输出任何多余的开场白或解释。
若续写自然涌现关键人物、伏笔或事件，文末附 MOYU:ASSETS 沉淀入库。
""",
        "files": [
            ("references/style-fingerprint.md", STYLE_FINGERPRINT),
            ("references/prose-craft.md", PROSE_CRAFT),
            ("references/genre-playbook.md", GENRE_PLAYBOOK),
        ],
    },
    {
        "name": "prose-expand",
        "title": "场景扩写·铺陈细节与微张力",
        "description": "对选区骨架做细节扩充、环境微张力渲染与情绪下潜，保持主线节奏不注水。",
        "applies_to": "expand",
        "icon": "unfold_more",
        "version": "2.0.0",
        "body_md": """你是一位长篇小说细节扩写大师。请对当前选区文本进行具象化细节扩写。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

扩写执行规范：
1. 扩充真实感，绝不注水废话。
2. 增加环境对人物的压迫感与物理交互。
3. 直接输出扩写后的完整文本，严禁输出任何解释或多余说明。
""",
        "files": [
            ("references/expansion-craft.md", EXPANSION_CRAFT),
            ("references/sensory-immersion.md", SENSORY_IMMERSION),
        ],
    },
    {
        "name": "prose-polish",
        "title": "沉香精修·遣词造句去粗取精",
        "description": "精修糙稿文字，剔除啰唆重复，增强句式节奏美感与中文文学质感。",
        "applies_to": "rewrite",
        "icon": "auto_fix_high",
        "version": "2.0.0",
        "body_md": """你是一位专精文笔锤炼的资深小说润色编辑。请对选区文本进行深度精修。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

精修原则：
1. 保留原本剧情事实与人物立场绝对不变。
2. 压缩虚词冗句，重塑铿锵有力的中文动词。
3. 直接输出精修后的正文，严禁输出任何解释、废话或总结。
""",
        "files": [
            ("references/rewrite-dimensions.md", REWRITE_DIMENSIONS),
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
        ],
    },
    {
        "name": "prose-dialogue",
        "title": "机锋对白·潜台词与个性台词",
        "description": "重塑人物对话，言在此而意在彼，融入博弈试探、身份口癖与潜台词交锋。",
        "applies_to": "dialogue",
        "icon": "chat",
        "version": "2.0.0",
        "body_md": """你是一位精通戏剧冲突与台词潜台词化的台词指导大师。请重构本场对白。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

对白戒律：
1. 严禁礼貌客观、毫无信息差的 AI 式聊天。
2. 允许抢话、截断、讽刺与答非所问。
3. 伴随具体肢体微动作推进心理博弈。直接输出对白正文。
""",
        "files": [
            ("references/subtext-dialogue-rules.md", SUBTEXT_DIALOGUE_RULES),
        ],
    },
    {
        "name": "prose-combat",
        "title": "惊险博弈·动作拆解与招式节奏",
        "description": "专精武戏动作碰撞、攻防拆招、空间掩体与生理受力反馈，杜绝无痛假打。",
        "applies_to": "combat",
        "icon": "sports_martial_arts",
        "version": "2.0.0",
        "body_md": """你是一位专精兵刃格杀与法术对决的武戏专家。请撰写高张力动作博弈场面。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

武戏戒律：
1. 空间与掩体交互：严禁站桩对轰，充分利用地形环境。
2. 生理受力与代价：写出肌肉震颤、骨骼受力、兵刃缺口与真气逆行。
3. 节奏极化：进攻用极短句连缀，回气对峙用长句铺陈。直接输出正文。
""",
        "files": [
            ("references/combat-rhythm.md", COMBAT_RHYTHM),
        ],
    },
    {
        "name": "prose-sensory",
        "title": "临场摹写·五感通感环境营造",
        "description": "调动冷热触感、气味、声响留白与视觉光影，打造极强身临其境感。",
        "applies_to": "sensory",
        "icon": "filter_drama",
        "version": "2.0.0",
        "body_md": """你是一位专精环境气氛与五感摹写的文学大师。请渲染沉浸式临场画面。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

摹写规范：
1. 调动触觉温度、空气气味与微弱声响。
2. 以景衬情，不直接抒发抽象感受。直接输出正文。
""",
        "files": [
            ("references/sensory-immersion.md", SENSORY_IMMERSION),
        ],
    },
    {
        "name": "novel-forge",
        "title": "造化烘炉·全自动长篇推演总控",
        "description": "长篇创作全生命周期总控（立项→设定→大纲→细纲→执笔），多阶段编排执行。",
        "applies_to": "forge",
        "icon": "all_inclusive",
        "version": "2.0.0",
        "body_md": """# 小说全流程造化总控 (Novel Forge)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位全流程长篇创作向导与总控中枢。根据用户当前所处的写作阶段，调度并指引各环节的创作推演。
""",
        "files": [
            ("references/creation-pipeline.md", CREATION_PIPELINE),
        ],
    },

    # =========================================================================
    # 四、审校质检与回溯反馈 (Audit & Consistency Quality Gate)
    # =========================================================================
    {
        "name": "audit-consistency",
        "title": "剧情巡检·吃书预警与状态冲突",
        "description": "比对章节正文与设定档案、时间线、伏笔，揪出伤势恢复、修为穿帮等逻辑漏洞。",
        "applies_to": "audit",
        "icon": "verified_user",
        "version": "2.0.0",
        "body_md": """你是一位极其严苛的网文质检专家。请审查章节正文，比对传入的设定集、时间线与伏笔，揪出潜在的“吃书”漏洞与逻辑冲突。

【审查重点】：
1. 人物状态冲突 (character_status)：肢体残疾/伤势突然痊愈、死亡角色复活、性格/修为与档案不符。
2. 道具法则冲突 (item_status)：已损毁法宝突然完整出现、法则代价被无视。
3. 时间线错位 (timeline_error)：先后顺序倒错。
4. 伏笔断裂 (foreshadow_break)：已设定的关键约束条件被无视。

【交付契约】：
正文给出分级诊断卡片；文末 MOYU:ASSETS 契约块以 notes 形式交付具体 quote 原文与 replacement 替换建议。
""",
        "files": [
            ("references/consistency-taxonomy.md", CONSISTENCY_TAXONOMY),
        ],
    },
    {
        "name": "audit-foreshadow",
        "title": "伏笔核验·回收校验与断裂预警",
        "description": "比对正文与全书伏笔池，核验本章伏笔回收是否合理，预警长期遗忘的断裂线索。",
        "applies_to": "audit",
        "icon": "find_in_page",
        "version": "2.0.0",
        "body_md": """你是一位长篇伏笔核验专家。请比对章节正文与已有伏笔清单，排查伏笔回收是否突兀、伏笔是否断裂。
文末以 MOYU:ASSETS 产出 foreshadows 状态变更与 notes 诊断记录。
""",
        "files": [
            ("references/foreshadow-verification.md", FORESHADOW_VERIFICATION),
        ],
    },
    {
        "name": "audit-timeline",
        "title": "时序核对·因果逻辑闭环校对",
        "description": "专项核查位移路途时耗、事件因果先后次序与伤势修养时间窗口矛盾。",
        "applies_to": "audit",
        "icon": "update",
        "version": "2.0.0",
        "body_md": """你是一位时序与因果逻辑校对专家。排查当前章节中的位移超速、因果倒置与时间窗口矛盾。
文末以 MOYU:ASSETS 产出 notes 诊断问题。
""",
        "files": [
            ("references/causality-audit.md", CAUSALITY_AUDIT),
        ],
    },
    {
        "name": "audit-de-aitone",
        "title": "破除假大空·AI 油腻腔重度过滤",
        "description": "专精清洗 AI 高频套话、假大空抒情与总结式升华收尾，还原地道文采。",
        "applies_to": "de-ai-tone",
        "icon": "cleaning_services",
        "version": "2.0.0",
        "body_md": """你是一位无情剔除机器味与 AI 腔的文字净化专家。请对文本进行重度去 AI 味洗稿。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

绝对封杀词表：
- 严禁“仿佛”、“宛如”、“不禁”、“五味杂陈”、“嘴角勾起笑意”、“眼中闪过复杂”。
- 严禁段落末尾的总结式升华。
- 直接输出洗净后的正文，绝不要输出解释。
""",
        "files": [
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
        ],
    },
    {
        "name": "audit-pacing-rhythm",
        "title": "剧情心电图·张弛起伏节奏量化",
        "description": "分析章节情绪张力起伏、高潮密度与尿点缓冲，诊断剧情节奏健康度。",
        "applies_to": "analysis",
        "icon": "analytics",
        "version": "2.0.0",
        "body_md": """你是一位小说叙事节奏与张力心电图评鉴专家。请按松紧维度对正文进行节奏量化诊断。
产出各阶段张力评分与诊断建议。
""",
        "files": [
            ("references/rhythm-scoring-rubric.md", RHYTHM_SCORING_RUBRIC),
            ("references/analysis-rubric.md", ANALYSIS_RUBRIC),
        ],
    },
    {
        "name": "audit-synopsis-distill",
        "title": "卷章提要·梗概提炼与记忆回溯",
        "description": "将数千字章节压缩为百字核心梗概，便于前情回溯与大纲上下文自动装配。",
        "applies_to": "shorten",
        "icon": "compress",
        "version": "2.0.0",
        "body_md": """# 卷章核心剧情梗概提炼 (Audit Synopsis Distill)

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

你是一位精准提炼小说章节梗概的速读专家。请将正文浓缩为 100~200 字的核心剧情梗概。
直接输出提要，严禁输出任何解释。文末以 MOYU:ASSETS 交付 chapter_synopses 数组。
""",
        "files": [
            ("references/compression-formats.md", COMPRESSION_FORMATS),
        ],
    },
]



def migrate_and_seed_skills(conn: sqlite3.Connection | None = None):
    """首启自动迁移旧 prompts 到 skills 表，并初始化规范内置 Skill 种子。幂等执行。"""
    if conn is None:
        conn = get_db()

    # 0. 彻底清理 v2.5.0 前未修改的旧预设 Skill，全面切换至全新 24 项全景 Skill 矩阵
    # 建立旧名称到新名称的安全迁移映射，解绑外键
    migration_map = {
        "default-continue": "prose-continue",
        "default-expand": "prose-expand",
        "default-shorten": "audit-synopsis-distill",
        "default-rewrite": "prose-polish",
        "default-outline": "novel-outline-macro",
        "default-audit": "audit-consistency",
        "default-analysis": "audit-pacing-rhythm",
        "de-ai-tone": "audit-de-aitone",
    }
    for old_n, new_n in migration_map.items():
        old_row = conn.execute("SELECT id FROM skills WHERE name = ?", (old_n,)).fetchone()
        if old_row:
            old_id = old_row[0]
            # 临时置空或更新步骤中的引用，杜绝外键级联阻止
            conn.execute("UPDATE workflow_steps SET skill_id = NULL WHERE skill_id = ?", (old_id,))
            conn.execute("DELETE FROM skill_files WHERE skill_id = ?", (old_id,))
            conn.execute("DELETE FROM skills WHERE id = ? AND user_modified = 0 AND source = 'builtin'", (old_id,))

    # 1. 检查是否已完成迁移
    migrated_row = conn.execute("SELECT value FROM app_settings WHERE key = 'skill_migration_done'").fetchone()
    already_done = migrated_row and str(migrated_row[0]).strip() == "1"

    # 2. 插入或确保内置 Skill 种子就绪（含参考资源文件）
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for s in BUILTIN_SKILLS:
        # 守卫：固化占位符契约为 {context, selection, instruction}
        # 扫描每个技能 body_md，发现非标准 {{...}} 即告警
        placeholders = set(re.findall(r"\{\{([^\{\}\s]+)\}\}", s.get("body_md", "")))
        invalid_placeholders = placeholders - {"context", "selection", "instruction"}
        if invalid_placeholders:
            warnings.warn(
                f"[Skill Contract Guard] Skill '{s.get('name')}' contains non-standard placeholders: {invalid_placeholders}. "
                f"Standard contract only supports {{context}}, {{selection}}, {{instruction}}.",
                UserWarning,
                stacklevel=2,
            )
        seed_ver = s.get("version", "1.0.0")
        existing_skill = conn.execute("SELECT id, user_modified, builtin_version FROM skills WHERE name = ?", (s["name"],)).fetchone()
        if not existing_skill:
            conn.execute("""
                INSERT INTO skills(name, title, description, body_md, version, enabled, applies_to, source, icon, builtin_version, user_modified)
                VALUES (?, ?, ?, ?, ?, 1, ?, 'builtin', ?, ?, 0)
            """, (s["name"], s["title"], s["description"], s["body_md"], seed_ver, s.get("applies_to", ""), s.get("icon", "auto_awesome"), seed_ver))
            skill_id = conn.execute("SELECT id FROM skills WHERE name = ?", (s["name"],)).fetchone()[0]
            for fpath, fcontent in s.get("files", []):
                fsize = len(fcontent.encode("utf-8"))
                conn.execute("""
                    INSERT INTO skill_files(skill_id, path, content, size, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (skill_id, fpath, fcontent, fsize, now))
        else:
            skill_id = existing_skill[0]
            is_user_modified = int(existing_skill[1] or 0)
            cur_builtin_ver = str(existing_skill[2] or "1.0.0")
            if not is_user_modified and cur_builtin_ver != seed_ver:
                conn.execute("""
                    UPDATE skills SET
                        title = ?,
                        description = ?,
                        body_md = ?,
                        version = ?,
                        applies_to = ?,
                        icon = ?,
                        builtin_version = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (s["title"], s["description"], s["body_md"], seed_ver, s.get("applies_to", ""), s.get("icon", "auto_awesome"), seed_ver, now, skill_id))
                for fpath, fcontent in s.get("files", []):
                    fsize = len(fcontent.encode("utf-8"))
                    conn.execute("""
                        INSERT INTO skill_files(skill_id, path, content, size, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(skill_id, path) DO UPDATE SET
                            content = excluded.content,
                            size = excluded.size,
                            updated_at = excluded.updated_at
                    """, (skill_id, fpath, fcontent, fsize, now))
            else:
                conn.execute("""
                    UPDATE skills SET
                        title = ?,
                        icon = ?,
                        applies_to = ?
                    WHERE id = ?
                """, (s["title"], s.get("icon", "auto_awesome"), s.get("applies_to", ""), skill_id))

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


def seed_builtin_workflows(conn: sqlite3.Connection | None = None):
    """基于 v2.5.0 最新 24 项全景 Skill 矩阵，构建 5 大高价值工业级预设工作流：
    1. 单章极致研磨流 (5步)：细纲节拍 -> 顺流续写 -> 潜台词对白精炼 -> 剧情一致性巡检 -> 沉香精修定稿
    2. 新书全景开炉孵化流 (6步)：灵感立项 -> 世界观法则 -> 万相谱群像 -> 势力割据拓扑 -> 分卷宏观总纲 -> 首章分场细纲
    3. 惊险博弈高潮戏精雕流 (4步)：武戏动作拆解 -> 五感通感临场摹写 -> 伏笔反转收网核验 -> 黄金章末卡点断章
    4. 剧情时序与逻辑质检流 (3步)：剧情大事件时序编织 -> 剧情吃书与状态巡检 -> 剧情心电图张弛诊断
    5. 全书核心设定推演流 (4步)：修炼战力法则与代价 -> 阵营割据博弈动力学 -> 草蛇灰线伏笔布网 -> 主角命途蜕变轨迹
    """
    if conn is None:
        conn = get_db()

    def _skill_id(name: str):
        row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    # 清理所有旧版 builtin 工作流定义，确保全面刷新为 5 大新工作流
    old_builtin_wf_ids = [r[0] for r in conn.execute("SELECT id FROM workflows WHERE builtin = 1").fetchall()]
    for old_wfid in old_builtin_wf_ids:
        conn.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (old_wfid,))
        conn.execute("DELETE FROM workflows WHERE id = ?", (old_wfid,))

    samples = [
        {
            "name": "单章极致研磨流",
            "description": "单章工业级闭环：分场细纲节拍 → 顺流执笔推进 → 机锋对白雕琢 → 剧情吃书冲突巡检 → 沉香去AI腔精修定稿。关键生成与质检设确认闸。",
            "icon": "edit_note",
            "steps": [
                ("分场节拍排布", "novel-scene", "chapter", None,
                 "结合当前章节目标，梳理3~4场戏剧冲突动作与出入点。", "medium", 1),
                ("顺流执笔正文", "prose-continue", "prev_output", 0,
                 "依据上一步分场细纲顺承文势撰写正文，保持人物文风，杜绝AI套话。", "long", 1),
                ("机锋对白雕琢", "prose-dialogue", "prev_output", 1,
                 "精炼本章人物对话，注入潜台词交锋与身份口癖，强化心理博弈。", "long", 0),
                ("吃书漏洞巡检", "audit-consistency", "prev_output", 2,
                 "比对设定集与伏笔池，严格排查本章是否存在人物状态矛盾或设定吃书穿帮。", "medium", 1),
                ("沉香精修定稿", "prose-polish", "prev_output", 2,
                 "在保持剧情不变前提下剔除AI假大空虚词，增强动词与行文质感完成定稿。", "long", 0),
            ],
        },
        {
            "name": "新书全景开炉孵化流",
            "description": "从灵感碎片到万字细纲闭环孵化：核心立项与金手指 → 世界观法则 → 万相谱群像 → 势力割据拓扑 → 分卷宏观总纲 → 首章分场细纲。",
            "icon": "hub",
            "steps": [
                ("核心立项与卖点", "novel-premise", "none", None,
                 "基于灵感碎片提炼核心困局、金手指差异化优势与全书主线引擎。", "medium", 1),
                ("世界观底层法则", "novel-world", "prev_output", 0,
                 "构筑三界九域地理版图、文明历史底色与不可动摇的超自然法则代价。", "long", 1),
                ("万相谱群像档案", "novel-cast", "merge", 1,
                 "设计主角、核心配角与宿敌的欲望、软肋与人物纠缠关系。", "long", 1),
                ("势力割据博弈网", "novel-faction-graph", "merge", 2,
                 "梳理各大宗门、王朝与隐秘势力的地盘利益、表面盟约与暗中宿怨。", "long", 1),
                ("分卷宏观大主线", "novel-outline-macro", "merge", 3,
                 "规划全书分卷起承转合、阶段性波峰危机与大高潮节拍。", "long", 1),
                ("首章分场微细纲", "novel-scene", "prev_output", 4,
                 "拆解第一卷首章的3场入场动作、悬念阻碍与章末黄金钩子。", "long", 1),
            ],
        },
        {
            "name": "惊险博弈高潮戏精雕流",
            "description": "专打硬仗的高潮戏重度研磨：武戏拆招与博弈 → 五感通感临场摹写 → 伏笔反转收网核验 → 黄金章末卡点断章留钩子。",
            "icon": "sports_martial_arts",
            "steps": [
                ("武戏拆招与攻防", "prose-combat", "chapter", None,
                 "充分利用环境掩体展开刀兵法术碰撞，写出受力反馈与内息代价，拒绝无痛假打。", "long", 1),
                ("五感通感临场感", "prose-sensory", "prev_output", 0,
                 "调动冷热触觉、气味与声响留白，大幅提升高潮大战的临场压迫感。", "long", 0),
                ("伏笔反转收网核验", "audit-foreshadow", "prev_output", 1,
                 "核对本场大战中揭开的伏笔线索是否逻辑自洽、有据可循。", "medium", 1),
                ("章末黄金钩子设计", "novel-hook-engineer", "prev_output", 1,
                 "在高潮余波处提炼最具悬念的卡点断章钩子，引爆读者强烈追读期待。", "short", 0),
            ],
        },
        {
            "name": "剧情时序与逻辑质检流",
            "description": "防吃书防崩坏安全网：剧情大事件时序编织 → 剧情吃书与状态巡检 → 剧情心电图张弛诊断。",
            "icon": "verified_user",
            "steps": [
                ("剧情时序大事件编织", "novel-timeline", "chapter", None,
                 "提取本卷或本章关键剧情节点与时间锚点，校验位移时耗与因果先后。", "medium", 1),
                ("吃书与逻辑矛盾排查", "audit-consistency", "chapter", None,
                 "严格比对万相谱设定集与伏笔池，列出所有伤势、境界或道具状态冲突。", "medium", 1),
                ("剧情心电图张弛诊断", "audit-pacing-rhythm", "chapter", None,
                 "按松紧维度对正文进行节奏量化诊断，指出平淡尿点与高潮密度。", "medium", 0),
            ],
        },
        {
            "name": "全书核心设定推演流",
            "description": "长篇小说骨架硬核设定推演：战力阶梯与代价平衡 → 阵营割据博弈动力学 → 草蛇灰线伏笔布网 → 主角命途心境轨迹。",
            "icon": "military_tech",
            "steps": [
                ("战力法则与代价平衡", "novel-magic-system", "none", None,
                 "设计修炼大境界阶梯、质变标志与严苛的反噬代价值，防御战力通胀。", "long", 1),
                ("阵营割据与利益对抗", "novel-faction-graph", "prev_output", 0,
                 "推演宗派与势力格局的利益分配、核威慑力量与敌友转换触发点。", "long", 1),
                ("草蛇灰线暗线布网", "novel-foreshadow-matrix", "merge", 1,
                 "围绕核心世界观秘密编织贯穿全书的伏笔暗线，规划三段式回收节拍。", "long", 1),
                ("主角道心蜕变轨迹", "novel-lead-arc", "merge", 2,
                 "梳理主角从初始信念到崩溃至暗时刻、再到道心重塑的成长弧光。", "long", 1),
            ],
        },
    ]

    for wf in samples:
        row = conn.execute(
            "SELECT id FROM workflows WHERE name = ? AND builtin = 1", (wf["name"],)
        ).fetchone()
        if row:
            continue
        cur = conn.execute(
            "INSERT INTO workflows(name, description, icon, scope, enabled, builtin) VALUES (?, ?, ?, 'global', 1, 1)",
            (wf["name"], wf["description"], wf["icon"]),
        )
        wf_id = cur.lastrowid
        for seq, step_tuple in enumerate(wf["steps"]):
            title = step_tuple[0]
            skill_name = step_tuple[1]
            input_mode = step_tuple[2]
            prev_seq = step_tuple[3]
            instruction = step_tuple[4]
            length = step_tuple[5]
            review = step_tuple[6]
            ref_seqs = [prev_seq] if prev_seq is not None else []
            ctx_sources = ["chapter", "triad"] if input_mode in ("chapter", "merge") else []
            conn.execute(
                """INSERT INTO workflow_steps(
                       workflow_id, seq, title, skill_id, input_mode, prev_step_seq,
                       ref_step_seqs, context_sources,
                       output_var, instruction, length, candidates, requires_review, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 1)""",
                (wf_id, seq, title, _skill_id(skill_name), input_mode, prev_seq,
                 json.dumps(ref_seqs), json.dumps(ctx_sources),
                 f"step{seq}", instruction, length, review),
            )
    conn.commit()


def word_count(text: str) -> int:

    """字数口径：去除空白字符后的字符数（含标点，含中英文）。"""

    return len("".join(text.split()))
