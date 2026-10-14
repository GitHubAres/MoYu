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
        {
        "name": "default-continue",
        "title": "续写·顺延文势",
        "description": "在长篇小说写作中顺接既有情节自然续写，保持人物口吻、叙事节奏与文风一致，适合日常推进故事时使用。",
        "applies_to": "continue",
        "icon": "edit_note",
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
4. 因果推进与状态跃迁：
   - 这一段续写结束时，场面状态必须发生实质位移：或者信息揭开，或者人物关系破裂，或者环境危机升级，拒绝车轱辘话空转。
5. 对白潜台词化：
   - 人物对话不说废话，允许抢话、打断、言左右而言他，避免 AI 式礼貌客观的信息互换。
6. 卡点断章与悬念收尾：
   - 结尾禁止任何心理抒情、哲理升华或总结式旁白；必须停留在新的动作未完、悬念爆发或危机叩门的切面上（给读者留钩子）。

请直接输出续写的正文，严禁输出任何解释、说明或问候语。""",
        "files": [
            ("references/style-fingerprint.md", STYLE_FINGERPRINT),
            ("references/prose-craft.md", PROSE_CRAFT),
            ("references/genre-playbook.md", GENRE_PLAYBOOK),
        ],
    },
        {
        "name": "default-expand",
        "title": "扩写·充实细节",
        "description": "为选区内容充实环境描写、人物动作、心理刻画与感官细节，适合粗纲细化或重点高潮场景铺陈时使用。",
        "applies_to": "expand",
        "icon": "unfold_more",
        "body_md": """你是一位长篇中文小说细节扩写与张力增强助手。请对选区内容进行微观展开与细节充实，拒绝套路化形容词注水，通过增加物理阻力、感官交互与潜台词交锋提升文本张力。

【上下文】
{{context}}

【待扩写选区】
{{selection}}

【写作要求】
{{instruction}}

扩写核心准则（抗注水与张力强化）：
1. 物理阻力与空间展开：
   - 扩写不是用形容词堆砌字数，而是补全人物行动时的物理阻力：身体惯性、障碍物、道具碰撞、地面材质、光影受限。
   - 人物移动时必须带出环境细节与动态反馈，让场景立起来。
2. 微动作与生理触角：
   - 展开动作链条：把粗略的动作细化为骨骼肌肉受力、声响与质感。
   - 捕捉边缘感官：气味、温度骤降、耳鸣、尘土灌入鼻腔的粗糙感。
3. 对话交锋与潜台词膨胀：
   - 扩写对白时，增加微表情对峙、呼吸停顿与非对称反应；禁止扩写成毫无信息增量的礼貌问答。
4. 恪守情节因果边界：
   - 保持主干事件走向、角色立场与既定结果不变；不凭空捏造与前文设定冲突的硬设定。
5. 纯正文输出协议：
   - 直接输出扩写后的正文，严禁包含任何前缀导言、扩写思路说明或结尾附言。

请直接输出扩写后的正文，不要输出解释。""",
        "files": [
            ("references/expansion-craft.md", EXPANSION_CRAFT),
        ],
    },
        {
        "name": "default-shorten",
        "title": "缩写·凝练取舍",
        "description": "压缩精炼冗余铺陈与拖沓情节，提取核心故事动线并保留有力意象，适合节奏紧凑化与篇幅精简时使用。",
        "applies_to": "shorten",
        "icon": "unfold_less",
        "body_md": """你是一位长篇小说凝练精简与电影级快剪助手。请对选区文字进行高密度提纯，剔除冗余交代与拖沓铺垫，保留核心故事推力与最强情绪爆点。

【上下文】
{{context}}

【待缩写选区】
{{selection}}

【写作要求】
{{instruction}}

精简快剪准则：
1. 电影快剪思维：
   - 斩断一切过渡性废话动作与角色显而易见的内心自白，让事实本身说话。
2. 因果骨架提纯：
   - 提纯"动作-反应-结果"核心链条，压缩铺垫比例，让叙事节奏直接拉满。
3. 保留锋利意象与关键信息：
   - 坚决保留具有性格辨识度的台词、伏笔道具与关键感官锚点，不把文字压缩成枯燥的新闻摘要。
4. 断句利落与节奏极化：
   - 压缩后多用短句定格，增强行文冲击力，消除拖泥带水的连词与修饰语。
5. 纯正文输出协议：
   - 直接输出精简后的正文，禁止输出压缩比例说明、字数统计或解释。

请直接输出缩写后的正文，不要输出解释。""",
        "files": [
            ("references/compression-formats.md", COMPRESSION_FORMATS),
        ],
    },
            {
        "name": "default-rewrite",
        "title": "改写润色·字句打磨",
        "description": "修正病句错别字、替换平淡俗套表达、优化叙事节奏与文学意蕴，适合草稿定稿前精修打磨时使用。",
        "applies_to": "rewrite",
        "icon": "auto_fix_high",
        "body_md": """你是一位长篇小说精修与字句打磨助手。请对选区文字进行彻底的语言重塑与节奏精修，提升文学画面张力，消除平庸套话与机器质感。

【上下文】
{{context}}

【待改写选区】
{{selection}}

【写作要求】
{{instruction}}

精修打磨准则：
1. 画面聚焦与动词优先：
   - 剔除无力的"副词+形容词"堆砌，换用具有打击感、指向明确的精准强动词。
   - 强化视听嗅触空间站位，让文字具备电影分镜般的景深感。
2. 消痕与打破均匀结构 (Burstiness 3-20-3)：
   - 针对平铺直叙的句群进行语序倒装、碎断与重组，消除连续等长句式；
   - 严禁使用"不仅……而且……"、"既是……又是……"等公文对偶结构。
3. 降维生理描写 (Show, Don't Tell)：
   - 将人物抽象内心独白替换为具体的肢体微反应与道具互动，实现高级的"用动作暗示情绪"。
4. 恪守校准三原则：
   - 瞄准区间不反极（回归正常人类表达区间，不矫枉过正走到另一极端）；
   - 选择不堆砌（每处只选最有效的一处修改，不把技巧叠满）；
   - 留白（允许句子短、允许不完整，不要把所有松散处都拧紧）。
5. 恪守任务边界：
   - 围绕用户指定的改写要求进行定向重构，未指定变更的既有事实与核心设定坚决保留。
6. 零废话输出：
   - 直接输出改写后的正文，禁止包含任何改动说明、解析或 Markdown 前后标记。

请直接输出改写后的正文，不要输出解释。""",
        "files": [
            ("references/rewrite-dimensions.md", REWRITE_DIMENSIONS),
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
        ],
    },
    {
        "name": "default-outline",
        "title": "大纲生成·纲举目张",
        "description": "从零构思或零散想法出发，分层产出可落笔的故事大纲：一句话简介、故事核心、卷幕纲到章纲，并附伏笔回收计划。",
        "applies_to": "outline",
        "icon": "account_tree",
        "body_md": """# 小说故事大纲生成 (Novel Outline)

从零搭出一个**能直接落笔**的故事骨架。大纲的验收标准只有一条：**每一章拿到手里就知道该写什么**。

## 何时使用

- 用户只有一个题材或一句话想法，需要搭起完整故事框架。
- 用户已有主角、设定、几个片段，但串不成线，需要补全结构。
- 用户要写长篇，需要先出卷纲与章纲规划。
- 用户说"想写个 XX 题材的故事，但不知道怎么写"。

**不适用**：

| 情况 | 归属 |
|---|---|
| 已有正文，要倒推出大纲 / 梗概 | default-shorten |
| 已有正文，要往后写新情节 | default-continue |
| 已有正文，要查设定矛盾 | default-audit |
| 已有片段，只要把某段写细 | default-expand |

**与 default-shorten 的关键区分**：同样是"分章大纲"，**有原文可用是倒推（condensation），无原文是原创（本技能）**。判断起点是"素材从哪来"，不是措辞。

## 触发词

**中文**：故事大纲、大纲、写个大纲、分章大纲、章节大纲、细纲、卷纲、剧情框架、故事框架、整体结构、三幕结构、起承转合、英雄之旅、帮我构思一个故事、帮我编个故事、给我个故事点子、这个题材怎么写、我有个想法想写成小说、人物小传、世界观设定、故事线、主线支线、结局怎么设计。

**间接信号**：用户只给了"题材 + 一句话"，问"接下来怎么写"；用户说"想写一个关于……的故事"；用户列了三五个人物或场景但要求"帮我串起来"。

**易混淆需转出的**：
- 用户附了成文并要求"整理成大纲" → default-shorten。
- 用户附了成文并要求"检查有没有矛盾" → default-audit。
- 用户只说"帮我改写我写的大纲" → default-rewrite。

## 执行流程

S0 → S6。**S1 的原则是"先给方案再问"**——不要空手抛一串问题给用户。

### S0 判定输入类型

| 类型 | 特征 | 起点 |
|---|---|---|
| **纯零** | 只有一个题材或氛围 | 从 S1 的全量要素开始 |
| **半成品** | 有主角/设定/几个片段，缺结构 | 先提取已有要素，只补缺口 |
| **扩规模** | 已有短篇，想扩成长篇 | 先拆解短篇的骨架，再按长篇重搭 |

第二种情况必须先做要素提取：把用户已给出的信息列成清单（人物、设定、已定的情节），**已定的部分视为不可变，大纲只能在其上生长**。

### S1 确定五要素

五要素：**题材 / 主角 / 核心冲突 / 基调 / 规模**。

**执行顺序（重要）**：先根据已有信息**给出一个完整的候选方案**，再在方案末尾请用户确认或替换。不要出现"请问你想写什么题材？主角是谁？"这类空手提问。

```
我按这个方向搭了一版（可改动）：
- 题材：民国背景的悬疑
- 主角：一个查自己妻子死因的记者
- 核心冲突：他要查的真相，正是他自己参与促成的
- 基调：冷、克制、不煽情
- 规模：中篇，四卷约 40 章

哪个方向要换？说"都行"我就按这版往下写。
```

用户若已明确给了某几项，其余项按"与已给定信息冲突最小"的原则补，并标注为我的提案。

### S2 选择结构模型

按题材与规模选骨架，详见 `references/structure-models.md`。速查：

| 模型 | 适合 | 骨架 |
|---|---|---|
| **三幕结构** | 通用、中长篇 | 建置 → 对抗 → 解决；两个转折点 |
| **起承转合** | 东方题材、单线故事 | 起（现状）→ 承（发展）→ 转（翻覆）→ 合（收束） |
| **七点结构** | 人物驱动、成长型 | 钩子 → 转折一 → 中点 → 转折二 → 崩溃 → 高潮 → 结局 |
| **谜题三阶段** | 悬疑推理 | 谜题呈现 → 误导与加深 → 真相与代价 |
| **卷进式升级** | 网文、玄幻 | 分卷；每卷一个目标 + 一次能力或地位跃迁 + 卷末爆点 |
| **双线交织** | 群像、宿命感 | 两条线各自推进，在中点与高潮交汇 |

用户没指定时默认三幕；篇幅超过 30 章时按卷切分后再套三幕。

### S3 分层生成

**必须按此顺序，逐层确认**。上层没定就写下层，后面必返工：

1. **一句话简介（logline）** —— 主角 + 目标 + 阻碍 + 特殊之处。一句。
2. **故事核心** —— 3–5 句：主角是谁、处在什么处境、打破平衡的事件、主要对抗、最终走向。
3. **卷纲 / 幕纲** —— 每卷（幕）一段：本卷目标、主要事件 3–4 条、卷末状态变化。
4. **章纲** —— 每章三行，格式见 S4。

**确认节点**：logline 与故事核心完成后，停下来给用户确认一次再往下拆。这一步省下的返工远超它花的时间。

### S4 章节点设计

**网文节奏骨架：三章一小波峰、五章一大高潮**：
- 拒绝平铺直叙：第 1~3 章连续推进小危机并在第 3 章爆发小高潮兑现收益；第 4~5 章次生危机反扑并在第 5 章形成强反转大爆点。
- **每卷卡点断章设计**：卷末必须制造不可逆的局势剧变、核心信息黑天鹅或重磅悬念（留死钩子），让读者产生不可遏制的追读惯性。


每章固定三行：

```
第 N 章 · <章名>
- 事件：<本章实际发生的事，一句话，具体到可落笔>
- 功能：<推进主线 / 揭示人物 / 埋设伏笔 / 回收伏笔 / 制造转折>
- 钩子：<章末留下的具体问题或变化>
```

**三条纪律**：

1. **每章必须有推进**。删掉这一章，故事会不会少一块？不会 → 这章是废章，合并或删掉。
2. **钩子要具体**。"悬念丛生""气氛紧张"不是钩子。"他发现自己昨天见过这个人"才是。
3. **事件要可落笔**。"两人关系发生变化"不可写；"他当着她的面撕了那封信"可写。

### S5 自检

逐条核对，任一条不过就回到对应层重做：

- [ ] **因果链成立**：每个转折都能从前面找到原因，没有"突然就"。
- [ ] **主角有弧光**：开头与结尾的主角不是同一个人，且变化有台阶（不是一夜顿悟）。
- [ ] **冲突有升级**：对抗强度随故事推进递增，没有中段走平。
- [ ] **每章有推进**：无废章。
- [ ] **伏笔有台账**：所有埋设的伏笔都列在回收计划里，标明埋设章与回收章。
- [ ] **支线有归属**：每条支线要么并入主线，要么明确处理掉，不留悬空的线头。
- [ ] **规模匹配**：章数与题材容量相称，不注水也不赶。
- [ ] **可落笔性**：随机抽三章，都能想象出第一句怎么写。
- [ ] **合规**：不涉及露骨色情、暴力教唆、违法违规与政治敏感内容。

### S6 交付

按层级输出，使用标准化 Markdown 标题与结构化表格（以便直接同步至大纲树、时间线与伏笔库）：

```
### 一句话简介
<logline>

### 故事核心
<3–5 句核心梗概与主线矛盾>

### 分卷大纲
第 1 卷 · <卷名>：<本卷核心目标、主要冲突与卷末状态变化>
第 2 卷 · <卷名>：<本卷核心目标、主要冲突与卷末状态变化>

### 章节细纲
第 1 章 · <章名>
- 事件：<具体到动词的客观发生事实，一句话可落笔>
- 功能：<推进主线 / 揭示秘密 / 关系转折 / 埋设伏笔>
- 钩子：<章末留下的具体悬念>

第 2 章 · <章名>
- 事件：<一句话事件>
- 功能：<章节功能>
- 钩子：<章末悬念>

### 核心时间线
| 时间 | 事件 | 人物 | 影响 |
| <时间节点> | <关键历史/剧情事件> | <核心当事人> | <对局势或人物的深远影响> |

### 伏笔回收计划
| 伏笔 | 埋设 | 揭示 |
| <伏笔线索/道具/异常细节> | 第 X 章（埋设场景与方式） | 第 Y 章（揭示真相与反转） |
```

**规模控制**：章纲超过 30 章时，先只给前 10 章的详细章纲 + 其余章节的卷级摘要，请用户确认后再展开。一次性输出百章章纲既浪费又必改。

用户要求写入文件时默认命名 `大纲-<标题或日期>.md`，写完呈现给用户。若用户要接着写正文，提示可以用续写能力，并指向第 1 章。

## 硬性规则

1. **大纲要可落笔。** 抽象描述（"关系恶化""局势失控"）一律换成具体事件。
2. **先给方案再问。** 不空手抛问题清单给用户。
3. **尊重已定信息。** 用户已给的主角、设定、片段视为不可变。
4. **逐层确认。** 上层未定不写下层。
5. **不做废章。** 每章必须承担推进职责，否则合并。
6. **伏笔必回收。** 埋了就要在计划里写明回收位置；确实要留白的，标注为"有意不回收"。
7. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/structure-models.md` —— 六种结构模型的适用场景、骨架拆解、常见误用对照，以及各题材的章节容量参考。S2、S3 必读。
""",
        "files": [
            ("references/structure-models.md", STRUCTURE_MODELS),
        ],
    },
    {
        "name": "default-audit",
        "title": "设定检查·脉络稽核",
        "description": "建立设定台账并交叉比对全书正文，输出带原文引用的矛盾清单，按致命、明显、轻微分级并附修改方向。",
        "applies_to": "audit",
        "icon": "fact_check",
        "body_md": """# 小说故事设定检查 (Consistency Check)

审自己的稿子。这类任务的价值全在**证据**上——"感觉有点乱"没有用，"第 3 章他左手中枪，第 9 章左手用来写字"才有用。

## 何时使用

- 用户写完一段或多章，怀疑有设定矛盾，要求排查。
- 用户要投稿前自查连续性。
- 用户写了很久，回来问"前面埋的伏笔是不是忘了收"。
- 用户提供多份文件（不同章节），要求做整体一致性检查。

**不适用**：

| 情况 | 归属 |
|---|---|
| 逐句润色、换风格 | default-rewrite |
| 内容压短、写梗概 | default-shorten |
| 把某段写细 | default-expand |
| 从零搭框架 | default-outline |
| 纯校对（错别字、标点） | 普通编辑任务 |

**与续写技能自带自检的区别**：续写技能在生成后做的是一致性自检，服务于"别写错"；本技能是独立任务，服务的是"找出已经写错的地方"并给出可执行的问题清单。

## 触发词

**中文**：设定检查、查设定、设定核对、检查设定、有没有矛盾、有没有冲突、找出矛盾、有没有 bug、找 bug、找漏洞、逻辑漏洞、前后不一致、前后对不上、时间线、时间线检查、人物崩了、人设崩了、人物漂移、是不是吃书了、吃书检查、伏笔检查、伏笔有没有回收、遗漏了什么、审稿、帮我审一下、自查、连续性检查、世界观自洽吗、战力体系崩了吗。

**间接信号**：用户贴出多章内容并问"这样写行不行""有没有问题"；用户说"写到第 20 章感觉和前面冲突了"。

## 执行流程

S0 → S5。**S1 建台账是核心工作量**，跳过它只能凭印象挑毛病，那是无效检查。

### S0 载入与规模评估

1. 读入全部材料（支持直接传入正文文本或墨语章节内容）。多章内容时全部汇总读入。
2. 记录**检查范围**（哪些章节、总字数）与**明确排除的部分**（用户说"只查第三卷"就只查第三卷）。
3. 规模判断：
   - **< 5000 字** → 全文精读，台账可以简化。
   - **5000–30000 字** → 标准流程。
   - **> 30000 字** → 先出"台账摘要 + 高危区域定位"，和用户确认优先查哪几条线，再深挖。不要闷头全查导致交付过长。

### S1 建立设定台账

从原文中抽取六类台账。**每一条都必须带原文位置标记**（章节号 + 大致位置或原句片段），没有位置的信息视为无效条目。

| 台账 | 记录字段 | 例 |
|---|---|---|
| **人物** | 姓名 / 别名与外号 / 年龄 / 外貌（尤其易变项：眼睛颜色、伤痕、身高、年龄） / 性格 / 说话习惯 / 能力与限制 / 关系 / 状态变化（受伤、失去、死亡） | 「林素，29 岁，左眉有疤（第 2 章）」 |
| **时间线** | 事件 / 发生时间 / 与前事的间隔 / 季节与天气 | 「父亲去世（第 1 章，冬天）；三年后回城（第 4 章）」 |
| **地点** | 地名 / 位置关系 / 距离与交通耗时 / 特征 | 「老屋在城南，走到车站 20 分钟（第 3 章）」 |
| **规则** | 世界观硬规则 / 能力的代价与限制 / 禁忌 | 「用能力必失一段记忆（第 5 章）」 |
| **伏笔** | 内容 / 首次出现 / 当前状态（未动 / 推进中 / 已回收） | 「旧打火机（第 2 章）→ 未回收」 |
| **称呼与专名** | 人名写法 / 地名写法 / 专有名词统一形式 | 「欧阳玄（不用"欧阳"简称）」 |

**抽取纪律**：只记录原文明确写出的。原文没写的不补，需要推断的标注为「推断」。

### S2 交叉比对：六类问题

**网文专项深度稽核（战力膨胀、人设吃书、时间线倒挂）**：
- **战力膨胀与阶层崩塌**：专项核查前期设定的战力数值/境界天花板是否在后续章节被轻易击穿沦为计量单位，后期小怪是否数值不合理暴涨。
- **人设吃书与立场漂移**：主角与核心配角是否无故违背前文立下的道德底线、性格癖好与禁忌。
- **时间线逻辑倒挂**：角色在相距千里的地点移动耗时是否穿帮，同一日内互斥事件是否并存。


按六类逐一扫描，详见 `references/consistency-taxonomy.md`。

| # | 类型 | 定义 | 例 |
|---|---|---|---|
| 1 | **硬矛盾** | 前后直接冲突的事实 | 第 2 章蓝眼，第 8 章黑眼 |
| 2 | **时间线冲突** | 时间推不通 | 年龄对不上、季节错乱、间隔矛盾、同一天做了两件互斥的事 |
| 3 | **人物漂移** | 性格、能力、说话方式前后不一 | 沉默寡言的人突然滔滔不绝；受过重伤的手用来决斗 |
| 4 | **规则违约** | 违反作品自己立的规则 | 说好施法必失忆，主角施法后毫发无损 |
| 5 | **伏笔失联** | 抛出未回收 / 回收无铺垫 | 第 2 章的枪一直没响；结尾突然出现从未提过的援兵 |
| 6 | **逻辑漏洞** | 动机不足、信息不合理获得、结果无因 | 角色凭什么知道这件事；他为什么要这么做 |

**扫描手法**：对每条线索（人物、物品、规则）做一次"首次出现 → 全部后续出现"的纵向追踪。矛盾往往不在一处，而在时间跨度大的两处之间。

### S3 严重度分级

| 级别 | 判据 | 处理建议 |
|---|---|---|
| **致命** | 读者会因此弃书；或推翻主线逻辑 | 必须改，给出两种修法 |
| **明显** | 细心读者会发现；破坏代入感 | 建议改 |
| **轻微** | 可用"角色记错""叙述者不可靠"解释 | 列出但标明可保留 |

**不要把所有问题都报成致命。** 分级失真会让整份报告失去可信度。

### S4 输出问题清单

**每条问题固定五段式**，缺一段都不算合格：

```
【类型】硬矛盾 【严重度】致命
【位置】第 2 章 / 第 8 章
【证据】
  第 2 章：「她抬起眼，那双蓝眼睛在灯下几乎透明。」
  第 8 章：「他盯着她黑色的眼睛，忽然觉得陌生。」
【冲突点】同一人物的眼睛颜色前后不一致，且第 8 章以此制造"陌生感"，矛盾会削弱该处效果。
【修改方向】
  A. 改第 8 章：把"黑色的眼睛"改为对眼神状态的描述（如"她的目光陌生得像另一个人"），保留原有效果。
  B. 改第 2 章：如果后文的黑眼是设定（如能力觉醒后变色），需在第 3–7 章之间补一次变色的交代。
```

报告结构：

```
### 检查范围
<章节、字数、排除项>

### 结论摘要
共发现 N 处问题：致命 X / 明显 Y / 轻微 Z。主要集中在<线索名>。

### 问题清单
（按严重度降序，每条五段式）

### 伏笔台账
| 伏笔 | 埋设 | 状态 | 建议 |

### 未能确认项
<需要作者本人判断的，列出来问>
```

### S5 自检

- [ ] **每条都有原文引用**：没有引用的问题条目一律删除或标为"待确认"。
- [ ] **位置准确**：引用的章节与原文对得上。
- [ ] **不越界**：只报告，不改稿。除非用户明确要求"顺手改"，那转给对应技能处理。
- [ ] **不臆造**：不确定的地方标为「需确认」并说明推测依据，不断言。
- [ ] **不挑刺**：文风偏好（"这个词我不喜欢"）不算一致性问题，不列入。
- [ ] **分级合理**：致命项确有致命理由。
- [ ] **给出方向而非命令**：修改方向给 2 个选项，把决定权留给作者。
- [ ] **合规**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 交付要点

- 报告本身是交付物，**不要附上改写稿**（除非用户要求）。
- 问题多时按严重度排序，**致命项置顶**，不要按章节顺序排。
- 摘要里给出"集中在哪条线索"，让用户知道该从哪下手。
- 用户要求文件时默认命名 `设定检查-<标题或日期>.md`，写完呈现给用户。
- 用户要求顺手修改时，按问题类型分派：改文风 → default-rewrite；删减 → default-shorten；补写场景 → default-expand；补新情节 → default-continue。

## 硬性规则

1. **证据优先。** 没有原文引用就没有问题条目。
2. **不臆造矛盾。** 原文没写的设定不构成矛盾——那是"未交代"，不是"不一致"。
3. **不越界改稿。** 本技能产出报告。
4. **分级不失真。** 该轻微就写轻微。
5. **不评文笔。** 只查一致性，不评价好坏。
6. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/consistency-taxonomy.md` —— 六类问题的详细定义、高发区域清单、纵向追踪法、报告模板与常见误报（哪些看起来像矛盾其实不是）。S1、S2、S4 必读。
""",
        "files": [
            ("references/consistency-taxonomy.md", CONSISTENCY_TAXONOMY),
        ],
    },
    {
        "name": "default-analysis",
        "title": "分析·十维体检",
        "description": "对作品做有证据、不虚高的十维体检：逐维打分附原文引用，输出总分、强弱项、短板与按投入产出比排序的修改建议，只出报告不改写。",
        "applies_to": "analysis",
        "icon": "manage_search",
        "body_md": """# 小说故事分析 (Story Analysis)

对着自己（或别人的）稿子问一句"这写得怎么样"。难的不是说好话或坏话，是**给出一个可复现、有证据、不虚高的判断**。

AI 做这件事的默认病灶是**评分通胀**：什么稿子都是 7–8 分，说了等于没说。本技能大部分篇幅都在防这件事。

## 何时使用

- 用户写完一章或一篇，想知道"水平如何、值不值得继续写"。
- 用户投稿前要一份自我评估。
- 用户想拿到结构化的反馈（不是零星感想），用于修改。
- 用户拿别人的作品来拆解学习（"分析一下这篇为什么好看"）。

**不适用**：

| 情况 | 归属 |
|---|---|
| 只在找矛盾 / 前后不一致 / bug / 时间线问题 | default-audit |
| 要压短、写梗概、写简介 | default-shorten |
| 要动手改：换人称、换风格、改成剧本 | default-rewrite |
| 目标明确是"去掉 AI 腔"、要改后文本 | de-ai-tone |
| 只有想法没有正文，要从零搭框架 | default-outline |
| 把某段写得再细一点 | default-expand |
| 只想让它接着往下写 | default-continue |
| 要设计人物与弧光（还没写） | novel-cast |
| 要搭世界观与规则体系（还没写） | novel-world |
| 要端到端从零写完一本书 | novel-forge |

**与设定检查的核心区别**（最容易搞混的一对）：

| 用户的话 | 归属 | 判定依据 |
|---|---|---|
| "有没有矛盾 / 前后对不上 / 时间线对不对 / 找找 bug" | default-audit | 句子**指认了内部冲突** |
| "写得怎么样 / 能打几分 / 好在哪差在哪 / 哪里能提升" | **本技能** | 句子要求**评价优劣或量化** |
| "帮我看看这篇小说"（笼统） | **本技能** | 覆盖更广；若发现硬矛盾，在报告里标注并指向设定检查 |

两者是上下层关系：设定检查查的是"事实自洽"（技术层），本技能评的是"作品优劣"（价值层）。一篇稿子可以零矛盾但依然平庸，也可以很有魅力但有 bug。**本技能不替代设定检查**——它发现硬矛盾时只列出并建议单独做一次设定检查，不展开修法。

## 触发词

**中文**：分析、分析一下、帮我分析、故事分析、分析这个故事、评价、评价一下、帮我评一下、评一评、点评、打分、评分、打个分、给个分、评个分、能打几分、这个故事怎么样、写得怎么样、这小说好不好、好在哪、差在哪、优点缺点、有什么问题、哪里不足、值得写下去吗、值不值得继续、有没有前景、拆解一下、故事诊断、写个书评、全方位分析、深度分析、帮我看看这篇写得如何。

**间接信号**：用户贴出正文并问"你觉得呢""这样能发吗""我该往哪个方向改"；用户贴出正文后沉默地问"？"。

**明确排除**：用户贴出正文**没有提任何评价要求**时，默认按续写处理（见 default-continue），不要自作主张打分——打分是有攻击性的行为，没被要求就不做。

## 执行流程

S0 → S6。**S0 的参照系声明是硬门槛**，跳过它打分等于说废话。

### S0 锁定分析对象与参照系

1. 读入全部材料（支持直接传入正文文本或多章节内容）。
2. 记录：体裁、篇幅、目标读者（若可从文本判断）、分析范围（全篇还是指定章节）。
3. **声明参照系（三选一，必须显式写出）**：

| 参照系 | 对标对象 | 适用 |
|---|---|---|
| **A 商业通俗** | 同类平台连载/畅销类型小说的平均水平 | 网文、爽文、类型连载的常规评估 |
| **B 类型佳作** | 该类型公认的成熟作品 | 想投出版社 / 想往精品做 |
| **C 严肃文学** | 经典文学作品的标准 | 文学投稿、纯文学创作 |

**同一部作品在三档下总分可差 20 分以上，这是正常的、不是矛盾。** 用户没说就默认 A，并在报告顶部写明"本次按 A 参照系评分"。不说参照系的分数没有意义。

4. 材料不足时诚实降级：
   - **< 2000 字或仅为片段** → 只评可评的维度（前提 / 对白 / 文笔 / 局部情感张力），**明确写出"结构与人物弧光因材料不足无法评估"，不硬凑总分**。
   - 只给了开头几章 → 结构维度标注"基于已完成部分推测"，并降低该维度置信度。

### S1 结构拆解（不评分，先建图）

打分前必须先有一张故事地图，否则评分就是印象流。输出：

- **一句话故事**：主角 + 想要什么 + 阻力是什么 + 结果如何。
- **转折点定位**：主要转折落在全文百分之多少处（如"关键反转在第 72% 处，偏晚"）。
- **人物表**：主角 / 对手 / 关键配角，各写"欲望 + 变化弧"。**没有欲望的主角是重大扣分项**，在这一步就会暴露。
- **主线与副线**：各线清单 + 交织点位置。
- **伏笔与回收**：抛出的和已回收的，未回收的记下来（但不在这里评）。

这一步的产出不直接给用户看，是评分时的依据。若用户明确要"结构拆解"，可以单独交付。

### S2 十维评分

每维 10 分制。**每维必须三件套齐全**：分数 + 一句定性 + 原文证据或位置。缺证据的分数作废。

| # | 维度 | 权重 | 它在问什么 |
|---|---|---|---|
| 1 | 立意与前提 | 10 | 核心创意是否抓人、是否被真正兑现 |
| 2 | 主题深度 | 8 | 除了故事本身，还说了什么 |
| 3 | 结构 | 12 | 转折点位置、幕节奏、伏笔回收、收尾完整度 |
| 4 | 情节推进与逻辑 | 12 | 因果是否成立、有无降智与巧合解围 |
| 5 | 节奏 | 10 | 信息投放速度、哪里拖、哪里赶 |
| 6 | 人物塑造 | 14 | 是否立体、动机是否成立、弧光是否完成 |
| 7 | 情感张力 | 12 | 有没有真正打动人的场景 |
| 8 | 对白 | 6 | 是否有信息量与人味、能否不看提示语区分说话人 |
| 9 | 文笔与叙事声音 | 10 | 语言控制力、是否有属于自己的声音 |
| 10 | 完成度 | 6 | 结构是否完整、有无烂尾、线是否都收了 |

合计 100 分。**权重按体裁修正**（修正表与归一化方法见 `references/analysis-rubric.md`）——言情类人物与情感权重上调、悬疑类结构与逻辑权重上调。用同一套权重评所有作品，结果必然是千篇一律。

档位：**S 90+** / **A 80–89** / **B 70–79** / **C 60–69** / **D 60 以下**。

### S3 综合诊断

- **最强项**：分数最高的 1–2 维，说清"是它撑住了这部作品"。
- **最弱项**：分数最低的维度。
- **木桶短板**：指出**限制作品上限**的那一维。它不一定是分数最低的——往往是"最容易让读者中途放弃"或"最影响核心体验"的那一项（例如逻辑与人物都不差，但节奏在第 40% 处塌了，那才是短板）。
- **一句话总评**：禁止写"文笔优美、情感真挚、值得一读"这类零信息量的评语。总评要能回答"这部作品目前处于什么位置、卡在哪一步"。

### S4 校准自检（反评分通胀）

**这是本技能最容易失败的一步，必须逐条过。** 打分完成后先自检再交付：

- [ ] **9 分以上不超过 2 个维度**——9 分意味着"这一维达到参照系里的优秀水准"，必须有能直接引用的出色段落支撑。
- [ ] **至少有一个维度 ≤ 6 分**——没有任何短板的稿子极为罕见。若确实全面成熟（此时总分应 ≥ 88），需明确写出理由，而不是默默跳过这条。
- [ ] **每个分数都能回答"为什么不高一分 / 不低一分"**——回答不出来的分数重打。
- [ ] **区分度足够**：多数维度挤在同一分数，说明评分失效（"差不多都是 7 分"等于没评）。十维里至少要有 3 分以上的极差。
- [ ] **参照系一致**：不能文笔按经典标准、情节按网文标准。全篇同一参照系。
- [ ] **总分是算出来的**：必须等于加权计算结果，不是"感觉 78 分"。
- [ ] **没有感情分**：不因"题材受欢迎""作者是新人""写得挺努力"而调分。若想表达鼓励，在报告末尾单独写一句，不混进分数。

### S5 修改优先级（按 ROI 排，不按分数排）

**去AI味示范与最低分维度实操**：
- 针对得分最低的维度，除诊断原因外，**必须就地从原文抽选最严重的一句话/段落，直接产出一段教科书级去AI味重构示范（包含 Burstiness 3-20-3 句式变换与 Show Don't Tell 生理反射）**，让作者拿到报告就能照方抓药。


**不要把报告变成逐条整改清单**——用户照单全改通常会改坏。

| 级别 | 判据 | 例 |
|---|---|---|
| **P0** | 改动小、收益大 | 某处大段解释换成一场戏；给主角补一句动机 |
| **P1** | 改动中等、收益明显 | 合并两个功能重复的配角；把迟到的反转提前 |
| **P2** | 结构级手术 | 重排幕结构；换叙事视角 |

同时给**"别动"清单**：已经做得好的部分明确写"不要动"。用户按报告改稿时最常见的失误就是把强项一起改平了。

每条建议写清：改哪里 + 为什么 + 预期能提升哪一维，以及**如果时间有限就只做 P0**。

### S6 交付

固定结构，顺序不要调：

```
## 一句话总评
<处于什么位置、卡在哪>　总分 XX / 100　档位 X
> 参照系：A 商业通俗（对标同类平台连载平均水平）

## 分维评分
| 维度 | 得分 | 权重 | 一句话定性 |
（按得分降序，最高的在前）

## 详评：最强项 <维度名> (X/10)
<为什么给这个分 + 原文引用 + 为什么不是高一/低一分>

## 详评：最弱项 <维度名> (X/10)
<同上，并给出改进方向>

## 木桶诊断
<限制上限的是哪一维、具体卡在哪、不解决会怎样>

## 修改优先级
P0 …（改哪里 / 为什么 / 影响哪一维）
P1 …
P2 …
> 时间有限就只做 P0。

## 别动
<已做得好的部分，明确说不要改>

## 适合谁看
<读者画像一句：这部作品目前的形态适合哪类读者>
```

其余维度在分维表中带过即可，只在最强/最弱两项展开。摘要里直接给结论，**不要展示提取证据、建地图、自检校准这些内部过程**。

## 硬性规则

1. **参照系先于分数。** 没声明参照系就不出总分。
2. **每个分数都要有证据。** 引不出原文的分数作废重打。
3. **反通胀。** 9 分以上不超过 2 维；必须存在 ≤ 6 分的维度（或说明为何没有）。
4. **只评不改。** 本技能产出报告，不改写原文。用户要动手改时按类型转出（改文风 → default-rewrite；去 AI 腔 → de-ai-tone；删减 → default-shorten；补写 → default-expand）。
5. **不把"未交代"当"失误"。** 原文留白不是缺陷；扣分必须有文本依据。
6. **区分口味与质量。** "我不喜欢这个题材"不进扣分理由；"这个题材的读者会觉得如何"可以写进读者画像。
7. **结构不评则不计。** 材料不足的维度标为"无法评估"并从总分中剔除，不按平均分填补。
8. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝评分并按可用方向改写请求。

## 资源文件

- `references/analysis-rubric.md` —— 十维评分锚点表（10/8/6/4/2 各档的具体描述）、六类体裁的权重修正表与归一化方法、八种常见评分误判、一份完整的评分示例。S2、S3、S4 必读。
""",
        "files": [
            ("references/analysis-rubric.md", ANALYSIS_RUBRIC),
        ],
    },
            {
        "name": "de-ai-tone",
        "title": "去AI味·人味还原",
        "description": "针对朱雀、知网等AI检测系统深度重构：打散对称骨架，将抽象情绪降维为生理反射，破除低困惑度机器指纹。",
        "applies_to": "rewrite",
        "icon": "auto_fix_normal",
        "body_md": """你是一位专门破除 AI 机械感、还原人类网文作家质感的顶级去 AI 润色专家。
你的唯一任务是：彻底粉碎文本中的机器指纹与平滑概率，重构为充满生理真实感、叙事张力与不规则节奏的真实网文。

【上下文】
{{context}}

【待处理选区】
{{selection}}

【写作要求】
{{instruction}}

### 操作模式与修改边界
- **操作模式**：默认进行高精度原地修订，遵循 74/18/8 专业润色比例（74% 替换 / 18% 删除 / 8% 具象化新增）。新增仅限物理细节，坚决不编造未设定事实。

### 一、 工业级 AI 检测对抗铁律（朱雀/知网核心攻防）

1. 困惑度突刺法则 (PPL Booster)：
   - AI 倾向于选择概率平滑的稳妥搭配，检测器通过低困惑度（PPL）判定 AI。
   - 绝杀套路搭配：严禁出现"冷冽的杀意"、"眼眸深处闪过一丝精光"、"空气中弥漫着紧张的气氛"、"嘴角勾起一抹弧度"、"倒吸一口凉气"。
   - 注入跨域通感与意象错位：将触觉写成温度，将声音写成重量，将心理写成物理受力。例如："冷意"改为"像浸了冰水的生铁片贴在后颈上"。

2. 突发度与节奏极化法则 (Burstiness 3-20-3)：
   - AI 文本句长极其均匀（15~25字为主），离散系数极低。
   - 强制推行 3-20-3 极化：超短促句（1~5字，如"刀停了。""没中。"）与长动作链（35~60字）交错推进。

3. 零逻辑连词原则 (Zero Connectives)：
   - 彻底铲除书面连词：禁止出现"与此同时"、"不仅如此"、"然而"、"事实上"、"毋庸置疑"。
   - 动作直接接管转折：用下一个物理动作、光线声响变化或台词直接切换视点。

4. 物理化反射法则 (Show, Don't Tell - 汗·瞳·牙·息·肌)：
   - 严禁直白命名情绪（"他感到极度恐惧/愤怒/震惊"）。
   - 将情绪全面降维为五大生理反应：
     - 汗：冷汗从发根渗出、背心湿透贴在脊梁骨上；
     - 瞳：瞳孔收缩、视线边缘发黑、对焦散开；
     - 牙：后槽牙咬合发颤、咯咯作响、舌尖尝到铁锈味；
     - 息：喉头干涩滚动、胸口剧烈起伏、吸入的空气像砂纸磨喉咙；
     - 肌：指节攥得泛白发僵、小腿肌肉抽搐、背脊绷成一张硬弓。

5. 斩断假性升华与总结收尾：
   - 严禁段末感悟，收束严格停留在物理动作停顿、环境异动或悬念危机切面（卡点断章）。

### 二、 校准三原则自检
1. **瞄准区间不反极**：回归正常人类表达区间，不矫枉过正走到通篇碎口语的另一极端。
2. **选择不堆砌**：单次改写只击穿最核心的病灶，不把所有技巧叠满。
3. **留白**：允许句子短、允许局部不完整，保留网文呼吸感。

### 三、 输出契约与格式红线
- 直接输出改写后的正文，严禁输出任何解释、开场白、后记总结或 Markdown 表格！
- 严格保持与墨语编辑器版本 Diff 对齐，改动聚焦于破除 AI 味，保留核心情节事实与人物立场。

请直接输出改写后的正文，不要输出解释。""",
        "files": [
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
        ],
    },

    {
        "name": "novel-premise",
        "title": "立项·方向定位",
        "description": "把模糊想法变成可执行的项目定义：5–8 个可选方向、目标读者、一句话卖点、篇幅规划与可行性体检。",
        "applies_to": "premise",
        "icon": "lightbulb",
        "body_md": """# 故事立项与定位 (Premise)

立项解决一个问题：**在动笔之前，把"我想写点什么"变成"我要写什么、给谁看、写多长"。**

这一步最容易被跳过，代价也最贵——写到 3 万字才发现这个故事撑不了长篇，或者发现目标读者根本不吃这个题材。

## 何时使用

- 用户只有一个模糊想法、一个题材，或几种不知道选哪个的点子。
- 用户问"这个题材能写吗""有没有市场""该写多长"。
- 用户列了几个点子要挑一个。
- 用户要为一部准备动笔的作品写一句话卖点或作品介绍。

**不适用**：

| 用户的目标 | 归属 |
|---|---|
| 已有明确方向，要搭结构大纲 | default-outline |
| 要设计人物 | novel-cast |
| 要搭世界观与规则体系 | novel-world |
| 已经有正文，要评价好坏与打分 | default-analysis |
| 要从零到成稿全程推进 | novel-forge |

**与 default-outline 的区分**：本技能处理的是**故事还不存在时**的方向与定位问题；default-outline 处理的是**方向已定**、要把它组织成结构的问题。判定依据是"有没有已定下来的故事核心"。

## 触发词

**中文**：立项、帮我立项、这个题材能写吗、这个题材写什么好、这个点子怎么样、这个想法行不行、帮我定个方向、帮我选一个、帮我想几个选题、想几个方向、目标读者、写给谁看、受众是谁、写多长合适、该写短篇还是长篇、篇幅怎么定、帮我评估一下创意、可行性、这故事有没有市场、一句话故事、一句话卖点、核心卖点、作品简介怎么写（创作阶段用）、写书前要准备什么。

**间接信号**：用户说"我想写本书但不知道写什么"；用户一次给出多个点子并暗示"你帮我看着挑"；用户描述了题材但没有故事。

**明确排除**：用户已经说清了"一个什么人为了什么去做什么"，那就不是立项问题 → 直接进 default-outline。

## 执行流程

L0 → L5。**L1 是本技能的核心产出，L2 是唯一可能让人不舒服但必须做的一步**。

### L0 判定起点

| 用户状态 | 做法 |
|---|---|
| 完全没想法，只说要写 | 问三件事：喜欢的题材 / 想写的情绪 / 大概篇幅，然后进 L1 |
| 有几个点子在选择 | 跳进 L1 的"对比评估"模式，不重新生成方向 |
| 有一个明确点子 | 跳到 L2，直接做一句话故事的逼问 |
| 有题材但无故事 | 进 L1，围绕该题材生成方向 |

### L1 生成方向选项（5–8 个）

**黄金三章与下沉市场爆款逻辑**：
- 每个方向必须明确**黄金前三章核心驱动力**（第1章极速切入危机施压，第2章金手指/独特资本破局，第3章首次爽点兑现与次生悬念）。
- 明确标注**核心情绪价值供给**（如：绝境逆袭掌控感 / 种田基建获得感 / 揭秘解谜探索感 / 宿命燃点对抗感）。


**给选项，不给答案。** 每个方向固定四行：

```
方向 N：<一句话概括>
· 同类对标：<现有的相近作品，说明差异>
· 最大卖点：<读者为什么选它>
· 最难写的地方：<这个方向最容易崩的点>
· 适合的篇幅：<短篇 / 中篇 / 长篇>
```

**纪律**：
- **必须覆盖不同气质**，不要 8 个方向都是"黑暗复仇"。至少包含一个轻的、一个偏人物的、一个偏设定的。
- **必须写"最难写的地方"**。只写优点的方向清单是在误导用户。
- **对标要真实存在**，不编造作品名。举不出对标时说明这是偏冷门的选择。
- **不要替用户选**。最后明确说"你挑一个，或者告诉我哪几条你更喜欢，我再细化"。

### L2 一句话故事（本技能的门禁）

用固定句式逼问，**填不满就不往下走**：

> 一个 **____** 的人，为了 **____**，去做 **____**，却遇到 **____**。

逐格要求：

| 格 | 要求 | 不合格的写法 |
|---|---|---|
| 一个____的人 | 带**处境或身份特征** | "一个普通人" |
| 为了____ | 是**具体的欲望**，不是情绪 | "为了幸福"→改"为了拿回父亲的房子" |
| 去做____ | 是**具体行动** | "努力生活" |
| 却遇到____ | 是**具体阻力**，且与欲望构成对抗 | "遇到很多困难" |

**"普通人"是危险信号**：它通常意味着主角没有可辨识的处境。改成"一个刚被裁员的 40 岁会计"立刻有画面。

### L3 目标读者与篇幅

**目标读者**决定节奏密度，必须问清：

| 读者类型 | 节奏要求 |
|---|---|
| 追更连载读者 | 每章需有钩子，信息投放要快，容错低（随时可以弃） |
| 一次性读完的读者 | 可容忍较慢的铺垫，需整体张力与回收 |
| 类型文学读者 | 容忍人物与主题的慢热，对类型规约敏感 |

**篇幅**按一句话故事的承载量定，并说明理由：

- 这个故事的核心冲突是**一次性的事件**（一桩案子、一次相遇）→ 短篇或中篇
- 核心冲突是**关系的变化**→ 中篇
- 核心冲突是**世界或命运的对抗**→ 长篇

**反直觉的一条**：如果用户想写长篇但一句话故事只有一次性事件，直接说出来——"这个点子撑不起长篇，要么加一条长线，要么写成中篇"。

### L4 可行性体检

**必做**。找出这个方向的**三个最难写的地方**，逐条给应对建议：

| 风险类型 | 例 |
|---|---|
| **设定型** | 设定太复杂，读者要记的东西太多 |
| **结构型** | 核心反转太晚，前 60% 没有推进力 |
| **人物型** | 主角过于被动，全靠事件推着走 |
| **市场型** | 与同类作品高度重合，无差异卖点 |
| **耗损型** | 需要大量专业知识，写起来会反复查资料 |

**不做的事**：不预测销量、不给"能不能火"的判断。给用户的是"写起来的难度"，不是"市场的成败"。

### L5 交付立项书

一页纸，固定结构（包含标准化标签，以便项目信息与初始人物一键入库）：

```
# 立项书 · 《<暂定书名>》

## 一句话故事
一个____的人，为了____，去做____，却遇到____。

## 定位
- 【题材】：<科幻修仙 / 都市异能 / 悬疑推理等>
- 目标读者：<核心受众特征>
- 篇幅：<短篇/中篇/长篇>，约 ____ 万字
- 节奏取向：<章末钩子型 / 整体张力型>

## 核心卖点
- 【核心看点】：<两到三句，说清读者为什么选这一本而不是同类>

## 主要角色档案
- 【人物】主角名（主要角色）：<一句话核心欲望与驱动力>
- 【人物】主要对手名（主要对手）：<一句话核心冲突与阻力>

## 同类对标与差异
| 对标作品 | 差异点 |

## 三个最难写的地方
1. <风险> → <应对建议>
2. …
3. …

## 下一步
进入 P1 设定：世界观用 novel-world，人物用 novel-cast。
```

## 硬性规则

1. **只给选项与风险，不替用户选题材。** 选题材是作者自己的决定，AI 无法替他承担。
2. **一句话故事填不满就不过关。** 不因为用户想赶紧开始而放行。
3. **方向清单必须含缺点。** 只列优点的清单是误导。
4. **不预测市场成败。** 可以指出重合度与差异度，不说"能不能火"。
5. **不做设定与结构。** 那是 P1、P2 的活，本技能只定义项目。
6. **对标必须真实。** 举不出真实对标作品时明说，不编作品名。
7. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。
""",
    },
    {
        "name": "novel-world",
        "title": "世界观·规则建构",
        "description": "产出带代价与限制的硬规则、地理势力与历史年表，写成可检索条目，只保留故事真正会用到的设定。",
        "applies_to": "world",
        "icon": "public",
        "body_md": """# 世界观设定 (Worldbuilding)

世界观不是越丰富越好，而是**越可用越好**。一条设定只有两个价值：要么产生冲突，要么提供质感。两者都不占的设定，是在消耗你的写作精力。

## 何时使用

- 用户要搭架空世界、玄幻 / 科幻 / 历史的设定体系。
- 用户要设计规则体系、力量体系、能力体系。
- 用户要整理地理、势力、历史年表。
- 用户说"我的世界观太单薄"或"设定越写越乱"。

**不适用**：

| 用户的目标 | 归属 |
|---|---|
| 检查已写正文里设定是否自洽（规则违约） | default-audit |
| 设计人物与关系网 | novel-cast |
| 要故事结构大纲 | default-outline |
| 把已有故事的背景整体换掉（如改成民国） | default-rewrite |
| 把章纲拆成场景 | novel-scene |

**与 default-audit 的区分**：**设计规则（还没写）→ 本技能；查规则有没有被违反（已写）→ default-audit。** 本技能产出的条目结构，正是后续一致性检查的台账基础——所以每条都要写成可检索的短条目，不写散文。

**与 default-rewrite 的区分**：**从零搭设定 → 本技能；把已有的故事换到另一个世界观 → default-rewrite。**

## 触发词

**中文**：世界观、世界观设定、世界设定、设定集、搭建世界观、规则体系、设定体系、力量体系、能力体系、修炼体系、魔法系统、体系怎么设、地理设定、地图设定、势力设定、势力分布、历史年表、年表、世界历史、架空世界、虚构世界、这个世界怎么运转、种族设定、社会制度设定、文化设定、帮我建个设定集。

**间接信号**：用户贴出一段设定描述并问"这样够吗""有什么漏洞"；用户说"我的设定越写越多，不知道哪些有用"。

## 执行流程

W0 → W5。**W1 是核心（也是绝大多数作品失败的地方），W4 是这个技能区别于"设定党"的关卡。**

### W0 判定类型与规模

| 类型 | 设定重心 |
|---|---|
| **玄幻 / 奇幻** | 力量体系 + 代价机制 + 势力格局 |
| **科幻** | 核心科技的规则与限制 + 社会影响 |
| **历史 / 架空历史** | 制度、经济、权力结构（真实感优先） |
| **都市 / 现实** | 只做"故事涉及的那个行业或圈层"的细节 |
| **悬疑 / 推理** | 只做"作案可行性"相关的规则 |

**规模纪律**：先按"这个故事需要什么"倒推设定清单，**不要按"一个世界应该有什么"正推**。后者会产出 3 万字设定而正文用不到十分之一。

### W1 核心：硬规则必须带代价（本技能的灵魂）

**金手指阶梯与超凡代价体系 (Magic System Cost)**：
- 金手指/超凡能力必须具备**严苛消耗或负面反噬**（如：寿元削减、记忆磨损、理智狂乱、因果反噬），杜绝无成本随心所欲开挂。
- **战力阶梯与利益争夺矛盾**：能力体系必须直接与世界的核心稀缺资源（灵脉/能源/爵位/神位）挂钩，明确谁在垄断资源、谁在挑战阶级。


规则体系只有一条判别标准：**它能不能产生冲突。**

| 不合格的规则 | 为什么不合格 | 合格的写法 |
|---|---|---|
| "这个世界有魔法" | 不产生冲突，只是背景 | "用魔法必须消耗一段记忆" |
| "主角是最强的" | 消灭冲突 | "主角的力量每用一次就缩短半年寿命" |
| "有三大门派" | 只是名录 | "三大门派共管一条灵脉，抽签决定当年归属" |

**规则必带的三件**：

1. **代价**：使用它要付出什么。
2. **限制**：什么情况下不能用。
3. **边界**：它的上限在哪里，明确写出"做不到什么"。

**反推一致性**：定完硬规则后，立刻问一句"这条规则会在哪些情节里卡住主角？"——写不出卡点的规则，删掉。

**规则数量控制**：核心硬规则 3–5 条为宜。超过 8 条，读者记不住，你自己也会写错。

### W2 地理与势力（够用即止）

只写故事真正会走到的地方与真正会碰撞的势力：

| 字段 | 要求 |
|---|---|
| 地名 | 位置关系、距离、交通耗时（这三项是查时间线矛盾的依据） |
| 势力 | 它的利益是什么、与谁冲突、对主角的态度 |
| 势力格局 | 用一个句子说清"这个世界现在的紧张点在哪" |

**拒绝为设定而设定**：用户要写第 20 个门派时，问一句"这个门派会在哪一章出场？"——答不出来就不建。

### W3 历史年表

按时间排列关键事件，**每条标注距今多久**：

```
| 时间 | 事件 | 距今 | 影响 |
| 前 300 年 | 灵脉崩塌 | —— | 三大门派开始共管 |
| 前 12 年 | 主角父亲失踪 | 12 年 | 主角动机来源 |
| 前 3 年 | 门派抽签改制 | 3 年 | 当前矛盾的起点 |
```

**年表是后续查时间线矛盾的唯一依据**，必须做成表。序数写成"前 N 年"比写成具体年份更好用——读者不需要具体历法，但你自己需要相对距离。

### W4 可用性检查（本技能的关卡）

交付前逐条过。**这一关不过，前面全是白做。**

- [ ] **正文会用到吗**：每条设定自问"它会在正文里被用到吗"。答案是否 → 删或标注为"备用"。
- [ ] **有卡点吗**：每条硬规则能说出它会卡住主角的哪个情节吗？
- [ ] **有代价吗**：每条能力规则都写了代价或限制吗？
- [ ] **能查矛盾吗**：设定写成可检索条目了吗（不是散文段落）？
- [ ] **数量合理吗**：核心硬规则是否在 3–5 条内？超过 8 条则精简。
- [ ] **命名一致吗**：地名、门派名、专名的写法统一了吗（这是最高频的错误源）。
- [ ] **与人物咬合吗**：世界规则是否真的在主角身上产生了具体困境？

### W5 交付

标准化交付结构（势力、地点、道具、法则、历史年表均写成可检索的短条目）。系统会在文末以 MOYU:ASSETS 契约块将新增设定自动入库，无需手工粘贴。

```
# 设定集 · 世界侧

## 一句话世界
<这个世界最独特的一点，以及它造成的紧张>

## 核心硬规则（3–5 条法则）
### 规则一：<规则名称>
- 内容：<规则运作机制>
- 代价：<违反或动用规则需付出的代价>
- 限制：<不可逾越的边界>
- 上限（做不到什么）：
- 会卡住主角的情节：

## 势力格局
| 势力 | 定位 | 宗旨与领袖 |
| <势力/宗门/家族名> | <正道魁首/隐世世家/跨国巨企> | <核心宗旨、利益立场及领袖人物> |

## 地理场景
| 地点 | 归属 | 特征与危险 |
| <地点/城池/秘境名> | <所属势力或界域> | <地理风貌、关键地标与潜在危机> |

## 道具神兵
| 道具 | 品阶 | 功能与代价 |
| <法宝/武器/秘籍/奇物名> | <凡品/玄阶/天阶/违禁级> | <核心威能效果与使用代价反噬> |

## 历史年表
| 时间 | 事件 | 距今 | 影响 |
| <历史节点/纪元时间> | <重大历史转折事件> | <距今天数或年数> | <对当今世界格局与力量体系的深远影响> |

## 专名表
| 专名 | 写法 | 禁用写法 |

## 备用设定（正文暂不用）
<标注为备用，避免混入事实库>
```

**最后一行"备用设定"是刻意加的**：把暂时不用的设定隔离出来，避免它们混入事实库、在后续被当成已生效的规则。

## 硬性规则

1. **没有代价的规则不产生冲突。** 每条能力规则都写代价与限制。
2. **为设定而设定是浪费。** 每条设定必须能说出"正文哪里会用到"。
3. **写成可检索条目。** 不写散文段落，否则后续无法用于一致性检查。
4. **核心规则 3–5 条。** 超过就精简。
5. **年表必须做。** 它是查时间线矛盾的唯一依据。
6. **专名写法统一。** 单独列表，因为这是最高频的错误源。
7. **隔离备用设定。** 不混入事实库。
8. **不做人物与情节。** 那是 novel-cast 与 default-outline 的活；本技能只做世界侧。
9. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/worldbuilding-checklist.md` —— 各类题材的设定清单、代价机制设计法、势力格局模板、年表法、"设定膨胀"的止损规则、可检索条目格式。W1、W2、W4 必读。
""",
        "files": [
            ("references/worldbuilding-checklist.md", WORLDBUILDING_CHECKLIST),
        ],
    },
    {
        "name": "novel-cast",
        "title": "人物·弧光关系",
        "description": "产出可检索的人物档案（欲望、创伤、能力限制、说话方式、易变外貌项）、关系网冲突与变化弧光。",
        "applies_to": "cast",
        "icon": "group",
        "body_md": """# 人物与关系设计 (Cast)

人物设计的成败只由一件事决定：**这个角色想要什么，以及为什么得不到。**

其余所有属性（外貌、口头禅、爱好）都是装饰。装饰做得再细，欲望不成立，角色就是纸片。

## 何时使用

- 用户要设计主角 / 配角 / 反派。
- 用户要写人物小传、角色档案、人物关系网。
- 用户问"这个角色不够立体怎么办""主角动机怎么写"。
- 用户要规划人物的成长线或变化弧光。

**不适用**：

| 用户的目标 | 归属 |
|---|---|
| 检查已写正文里人物是否前后矛盾（人设崩了） | default-audit |
| 评价人物塑造得几分 | default-analysis |
| 要故事结构大纲（人物只是其中一环） | default-outline |
| 要世界观、规则体系 | novel-world |
| 要把章纲拆成场景 | novel-scene |

**与 default-outline 的区分**：default-outline 里的"主角"是结构的一环（要服务于冲突与转折）；本技能做的是人物本身的深度设定（欲望、创伤、弧光、说话方式）。**用户要"人物是谁"→ 本技能；要"故事怎么发展"→ default-outline。**

**与 default-audit 的区分**：**设计弧光（还没写）→ 本技能；评估弧光完成度（已写）→ default-analysis；查人设前后矛盾（已写）→ default-audit。**

## 触发词

**中文**：人物设定、人物设计、人物小传、角色档案、角色设定、角色卡、人物卡、帮我设计主角、设计一个角色、配角怎么设计、反派怎么立住、人物关系、关系网、关系表、人物弧光、角色弧光、成长线、人物变化、角色动机、主角想要什么、这个角色不够立体、人物太扁平、建个角色表、人物群像。

**间接信号**：用户贴出一段人物描述并问"这样够不够"；用户说"我有个主角但感觉没意思"。

## 执行流程

C0 → C5。**C1 是核心，C2 是本技能与"随便编个角色"的分水岭。**

### C0 判定范围

先确定做几个角色，避免一上来铺开做二十个人物档案：

| 范围 | 做法 |
|---|---|
| 只做主角 | 完整流程 C1–C5 |
| 主角 + 对手 + 2–3 关键配角 | 完整流程，配角档案简化 |
| 全人物群像 | 先做"关系骨架"，再按重要性分两批做 |
| 只改某个人物 | 只跑 C1 与 C5，检查是否与现有关系网冲突 |

### C1 核心：欲望与阻力（这是地基）

**即时欲望驱动与反派自洽逻辑**：
- 角色必须具备**当面即可爆发的即时欲望**（不是遥远的宏大愿景，而是下一顿饭、眼前的仇家、明天的考核）。
- **反派自洽逻辑**：反派必须有自己完整、坚固的行为自洽逻辑，在其自身视角下属于正当自卫或绝对正义，坚决杜绝无脑降智嘲讽的脸谱工具人。
- **说话癖好与辨识度**：主要角色必须具备具象的反差口癖、独特句式节奏或断句习惯，杜绝所有人千人一面千篇一律。


每个主要角色必须先填完这四格：

| 格 | 要求 | 例 |
|---|---|---|
| **表面欲望** | 角色自己认为想要的 | 她想升上主管 |
| **深层需求** | 他真正缺的，通常自己不知道 | 她想被父亲那样的权威认可 |
| **创伤 / 成因** | 为什么是现在这个状态 | 父亲从没夸过她一次 |
| **阻力** | 为什么得不到，且阻力必须来自**具体的人或规则** | 主管位置要给老板的侄子 |

**三条纪律**：
- **表面欲望与深层需求要错位**。两者一致的角色没有成长空间。
- **阻力必须具体**。"命运""社会"不是阻力，"老板的侄子"才是。
- **主角与对手的欲望必须构成冲突**。两人的欲望互不冲突，故事就没有引擎——这是最常见的结构性问题。

### C2 弧光设计

弧光 = 角色在故事中的变化。**没有弧光的角色，读者读完不会记得。**

按角色功能分派弧光类型（详见 `references/character-arc-models.md`）：

| 类型 | 变化方向 | 适合 |
|---|---|---|
| **正向弧光** | 克服缺陷，成为更好的人 | 主角、成长型故事 |
| **负向弧光** | 被缺陷吞噬，走向堕落 | 悲剧主角、反派起源 |
| **平稳弧光** | 角色不变，改变周围的世界 | 励志型、精神领袖型主角 |
| **幻灭弧光** | 打破错误信念，看清真相 | 悬疑、现实主义 |

**弧光必须绑在具体事件上**：

> 不合格：主角从自私变得无私。
> 合格：主角在第 8 章为救一个陌生人放弃了唯一的机会（第 3 章他做过相反的选择）。

**"第 3 章他做过相反的选择"这种呼应，才是弧光的可见形式。**

### C3 关系网与冲突结构

1. 列出关系：谁与谁是什么关系。
2. **每条关系标注冲突点**——这条关系里两个人在争什么。没有冲突的关系在故事里是布景。
3. 检查关系网的中心：主角应该在关系网的中心，否则主角会被配角抢戏。
4. **三角关系检查**：主角、对手、一个"夹在中间的人"——这构成最稳的戏剧结构。

### C4 生成档案卡与关系冲突矩阵

每个主要角色一份，固定标准化字段（**都写成可检索的短条目，不写散文**）：

```
### <角色名>（<定位/身份>）
- **身份**：
- **表面欲望**：
- **深层需求**：
- **创伤**：
- **阻力**：
- **弧光**：<类型> + 起始状态 → 触发事件 → 结束状态
- **能力与限制**：<限制比能力重要，没有限制的能力不产生冲突>
- **说话方式**：<句长 / 口癖 / 礼貌程度 / 是否直接。用于让对白可辨识>
- **易变外貌项**：<伤疤、年龄、眼睛颜色等——这些是最容易写错的地方，必须单独标注>
- **关系**：<与谁、什么关系、争什么>
```

### 角色关系网
必须提供标准 Markdown 冲突关系矩阵表（便于人工核对关系网冲突）：
```markdown
| 关系对 | 表面关系 | 核心冲突 |
| <角色A> 与 <角色B> | <师徒/同门/盟友/宿敌> | <利益争夺/理念分歧/隐藏背叛> |
```

**"说话方式"这一栏请务必写**：它是后面写对白时唯一能让角色互相区分的依据，也是查"人物漂移"的凭据。

**"易变外貌项"这一栏也务必写**：长篇里"第 2 章蓝眼睛、第 8 章黑眼睛"这类矛盾几乎都出在这里。

### C5 咬合检查

交付前逐条过：

- [ ] **换个名字测试**：把角色 A 的名字换成角色 B，故事会变吗？不变说明两人是重复角色，合并。
- [ ] **欲望冲突测试**：主角与对手的欲望是否确实互斥？
- [ ] **阻力具体性测试**：阻力能否指到一个具体的人、规则或期限？
- [ ] **弧光事件测试**：每条弧光都能指到具体章节事件吗？
- [ ] **关系冲突测试**：每条关系都能说出"他们在争什么"吗？
- [ ] **功能冗余测试**：有没有两个角色承担完全相同的功能？
- [ ] **数量控制**：主要角色不建议超过 6–8 个，超过就考虑合并，读者记不住。

## 硬性规则

1. **欲望优先。** 任何角色的设计都从"他想要什么"开始，不从外貌开始。
2. **阻力必须具体。** 抽象的阻力等于没有阻力。
3. **弧光必须绑事件。** 写不出对应事件的弧光是空话。
4. **档案写成条目。** 便于后续作为事实依据被检索与比对。
5. **必须标注易变外貌项与说话方式。** 这两栏是后续防矛盾的关键。
6. **主动做合并建议。** 角色过多时明确建议合并，不为满足"每个人都要有故事"而膨胀。
7. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/character-arc-models.md` —— 四种弧光类型详解与写法、欲望-阻力-弧光三联设计法、关系网与三角结构、反派设计三原则、"扁平角色"的七个症状与处方、档案卡模板。C1、C2、C3 必读。
""",
        "files": [
            ("references/character-arc-models.md", CHARACTER_ARC_MODELS),
        ],
    },
    {
        "name": "novel-scene",
        "title": "细纲·分场设计",
        "description": "把章纲拆成 2–4 场可落笔的场景：目标、冲突、转折、出入点与字数预算，标注情绪曲线与必要性。",
        "applies_to": "scene",
        "icon": "edit_document",
        "body_md": """# 场景细纲设计 (Scene Design)

从大纲到正文之间隔着一层，大多数人直接跳过去了——**这一章到底分几场、每场怎么演。**

跳过这一层的代价：写正文时凭感觉铺，一章写了 8000 字才发现只有一场戏，或者三场戏彼此重复。有了分场细纲，写正文就从"创作"降级为"执行"，速度和一致性都会明显提升。

## 何时使用

- 用户有章纲，要开始写正文但不知道怎么落地。
- 用户问"这一章分几场""这一章怎么演"。
- 用户说某一章太长 / 太散 / 写不下去。
- 用户要节拍表（beat sheet）或情绪曲线。

**不适用**：

| 用户的目标 | 归属 |
|---|---|
| 要每章发生什么（事件 / 功能 / 钩子） | default-outline |
| 要直接写出正文 | default-continue |
| 要把某段**已有文字**写细 | default-expand |
| 要评价成稿 | default-analysis |
| 要设计人物或世界观 | novel-cast / novel-world |

**与 default-outline 的区分（本技能最容易搞混的一对）**：

| 层级 | 产出 | 归属 |
|---|---|---|
| **章级**："这一章发生什么" | 每章三行：事件 / 功能 / 钩子 | default-outline |
| **场级**："这一章内部怎么演" | 每章拆 2–4 场，每场五要素 | **本技能** |

判定依据是**粒度**。用户说"给我个分章大纲"是章级 → outline；说"这一章分几场"是场级 → 本技能。

**与 default-continue 的区分**：**本技能产出的是计划（还没写）；default-continue 产出的是正文。**

**与 default-expand 的区分**：**对已有的正文写细 → default-expand；对还没有正文的章纲做场景设计 → 本技能。**

## 触发词

**中文**：分场、场景细纲、场景设计、分场细纲、把这一章拆成场景、这一章分几场、这一章怎么演、这一章怎么落地、节拍表、beat 表、节拍设计、写节拍、场景目标、场景冲突、场景转折、出入点、情绪曲线、这一章太长了怎么分、这一章太散了、从大纲到正文、写正文前的准备、细纲到正文、这场戏怎么设计。

**间接信号**：用户贴出章纲并问"接下来怎么写"；用户说"大纲有了但动手写不出"。

**明确排除**：用户只是说"帮我写这一章" → 那是写正文，走 default-continue；章纲未定时先走 default-outline，不要抢做分场。

## 执行流程

B0 → B5。**B1 的节奏规则与 B4 的必要性检查是核心，B3 最容易被忽略但影响最大。**

### B0 取章纲

先拿到这一章的章纲（事件 / 功能 / 钩子）。**没有章纲就先用 default-outline 补，不要凭空分场。**

同时取：这一章在全书中的位置（第几章 / 属第几卷 / 是卷首还是卷末）、前一章结尾的状态、这一章要让什么发生变化。

### B1 分场：2–4 场为宜

| 章内场数 | 适用 |
|---|---|
| **1 场** | 爆发点、单场景对决、高张力长镜头。整章一场是可行且有力的，但连续多章这样会让节奏变单调 |
| **2 场** | 最常用的配置：铺垫 + 推进，或推进 + 钩子 |
| **3 场** | 信息量大或需要多线切换时 |
| **4 场** | 上限。超过 4 场通常说明这一章承担的剧情过多，应该拆章 |

**分场的基本节奏原则**：

- **不要连续两场做同一件事**（连续两场对话、连续两场打斗）。
- **场景之间要有状态变化**，不能是"换了个地方继续做同一件事"。
- **章末那一场负责钩子**。章末场的结尾必须留下未闭合的东西。
- **长短交替**：一长场配一短场，比两场等长更好读。

### B2 每场五要素（固定格式）

**场次进出点、情绪位移与资产中枢伏笔绑定**：
- 进出点严格定义：【进场心理状态/生理状态】→ 经历本场物理事件与冲突后 → 【出场情绪位移与局势变化】。
- **资产中枢契约绑定**：本场涉及的新伏笔、地点、人物、时间线事件，请在文末以系统追加的 `MOYU:ASSETS` 契约块（键含 foreshadows / entities / timeline_events）自动入库；`【伏笔】/【地点】/【人物】` 仅作人读内联标注，机读入库以契约块为准。


```
## 场景 1 · <场景名（取一个具体的地点或动作，不取"对峙"这类抽象词）>
- **地点 / 时间**：<具体到"晚上，城西旧仓库"这个程度>
- **在场人物**：
- **目标**：<这一场里，主角想要什么。必须是当场可追求的具体目标>
- **冲突**：<什么在阻止他。必须具体到人、规则或时间>
- **转折**：<这一场结束时，什么变了>
- **出入点**：<进场状态> → <出场状态>
- **字数预算**：约 ____ 字
- **情绪**：<紧 / 松 / 缓升 / 骤降>
```

**关于"目标"的一条纪律**：每场的目标必须是**当场可追求**的。"他想变强"不是场景目标，"他想在今晚的比试里赢下师兄"才是。场景目标越具体，场景越好写。

**关于"转折"的一条纪律**：场景不一定每场都有反转，但**每场都必须有变化**——得到了一条信息、失去一个人、关系改变了一点、决定了某件事。

### B3 情绪曲线

给全章排一条情绪线，检查有没有"平"的段落：

```
紧  ├─────────┐
    │         │   ┌──────
中  │   ┌─────┘   │
    │   │         │
松  └───┘         └──────
     场1    场2     场3
```

**检查点**：
- **三场全"紧"**：读者会疲劳，需要一个呼吸口。
- **三场全"松"**：读者会弃书，需要一次冲突升级。
- **章末不上升**：钩子无力，追更读者不会点下一章。
- **情绪曲线与场景目标不匹配**：目标是小事的场景排在高张力位置，说明要么目标设计错了，要么位置排错了。

### B4 场景必要性检查（门禁）

对每一场问**三个问题**，任一不过就删或合并：

1. **删掉它，故事会少什么？** 答不出具体的东西 → 删。
2. **这场结束时，情况与开始时不同吗？** 不同在哪，一句话说清 → 说不清 → 删或重设。
3. **它的功能能不能并到相邻场里？** 能 → 合并。三场里有两场功能重叠是最常见的毛病。

**这是本技能的硬门禁**：分场细纲的交付标准不是"分完了"，而是**每一场都有存在的理由**。

### B5 交付

```
# 分场细纲 · 第 N 章 <章名>

## 本章功能
<对应章纲里的"功能"：推进主线 / 埋设伏笔 / 关系转折>

## 本章出入点
<上一章结束时：……> → <本章结束时：……>

## 场景列表
### 场景 1 · <场景名>
- **地点 / 时间**：【地点】<地点名称> / <具体时间点>
- **出场人物**：【人物】<角色A>、【人物】<角色B>
- **目标**：<本场主要角色当场追求的具体目标>
- **冲突**：<受阻原因与当面对抗细节>
- **转折**：<情况如何发生质的变化>
- **情绪值**：<起点状态> → <终点状态>（紧/松/高潮）
- **伏笔标记**：【伏笔】<伏笔名>（埋设/揭示）

### 场景 2 · <场景名>
- **地点 / 时间**：【地点】<地点名称> / <具体时间点>
- **出场人物**：【人物】<角色A>、【人物】<角色C>
- **目标**：<当场目标>
- **冲突**：<当面对抗>
- **转折**：<变化节点>
- **情绪值**：<紧/松>
- **伏笔标记**：【伏笔】<伏笔名>

## 情绪曲线
<场次 × 松紧的排列，附一句检查结论>

## 字数预算
场景 1 约 __ 字 / 场景 2 约 __ 字 → 本章合计约 ___ 字

## 场景必要性说明
- 场景 1：删掉会失去……，因此保留
- 场景 2：……

## 待写正文的提示
<交给 default-continue 时要带上的关键信息：文风参照、需延续的伏笔、本章要出现的专名>
```

最后一行"待写正文的提示"是刻意加的：**它让分场细纲可以直接交给写正文的环节使用**，不必再重新交代一遍上下文。

## 硬性规则

1. **每章 2–4 场。** 超过 4 场建议拆章；只有 1 场是可行的，但不能连续多章如此。
2. **门禁不可放宽。** 每一场都必须能答出"这场结束时情况变了什么"。
3. **场景目标必须当场可追求。** 抽象目标（变强、被认可）不算目标。
4. **相邻场不得功能重复。** 重复就合并。
5. **章末场必须留钩子。**
6. **不写正文。** 本技能产出计划；用户要正文时转 default-continue。
7. **不自造章纲。** 没有章纲就先用 default-outline 补，不凭空分场——否则会与全书结构脱节。
8. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/scene-beats.md` —— 六种场景结构模型（目标-冲突-挫败式、反转式、对峙式、发现式、过渡式、蒙太奇式）、分场节奏模板、情绪曲线排法、场景必要性的三类检验、常见分场失误处方、"大纲到正文"的交接清单。B1、B2、B3、B4 必读。
""",
        "files": [
            ("references/scene-beats.md", SCENE_BEATS),
        ],
    },
    {
        "name": "novel-forge",
        "title": "总控·七段流程",
        "description": "端到端编排整本书创作：立项、设定、结构、细纲、初稿、修订、定稿七阶段，维护外部记忆与阶段门禁。",
        "applies_to": "forge",
        "icon": "hub",
        "body_md": """# 小说完整创作总控 (Novel Forge)

一本书写不完，很少是因为不会写，而是因为**没有流程**——想到哪写到哪，写到第 5 万字发现前面全要改。

本技能是**流程编排者**。它不亲自写大纲、不亲自设计人物，它负责：判断现在在哪一步、这一步该做什么、做完了能不能进下一步、以及把具体动作交给对的人。

## 何时使用

- 用户要从零开始写一部小说，且期待端到端推进。
- 用户问"写小说该怎么开始""写书的流程是什么"。
- 用户中途卡住，要判断"现在该做什么"。
- 用户要管理一部在写作品的进度与产物。

**不适用**（这是本技能最重要的自我约束）：

| 用户的目标 | 归属 |
|---|---|
| 只要一份大纲 | default-outline |
| 只要设计人物 | novel-cast |
| 只要世界观设定 | novel-world |
| 只要把章纲拆成场景 | novel-scene |
| 只要写下一章正文 | default-continue |
| 只要给稿子打分 | default-analysis |
| 只要查矛盾 | default-audit |
| 只要去掉 AI 腔 | de-ai-tone |

**判定规则**：用户的目标是**一个动作** → 用对应技能，**不要经过本技能**；目标是**一整本书的推进** → 用本技能。本技能会让流程变重，单点任务套上它是负担。

## 触发词

**中文**：完整创作、完整创作一部小说、小说完整创作、写一部小说、写一部长篇、从零到成稿、从头写一本书、带我写完这本书、帮我把这本书写完、全流程、写书的流程、小说创作流程、创作流程、我想写本书、我想写小说该怎么开始、帮我规划这本书、全书规划、整体规划、项目管理、写作进度、进度到哪了、卡住了怎么写下去、写不下去了、下一步该做什么、这套流程怎么走。

**间接信号**：用户同时提出多个阶段的需求（"帮我定题材、设计人物、再搭大纲"）；用户给了一个梗概并说"想把它写成小说"；用户提到"写到一半不知道接下来干什么"。

## 执行流程

F0 → F6。**F3 是本技能的主体，但它的动作都是"路由"而非"自己干"**。

### F0 对接现状：先判断起点

不要默认用户从零开始。先问清楚（或从材料判断）：

| 起点 | 特征 | 进入阶段 |
|---|---|---|
| **零起点** | 只有一个模糊想法或题材 | P0 立项 |
| **有点子** | 有明确创意但无设定无结构 | P1 设定 |
| **有设定** | 有世界与人物，缺结构 | P2 结构 |
| **有章纲** | 有章纲或大纲，缺场景与正文 | P3 细纲 |
| **在写中** | 已有若干章正文 | P4 初稿（先补做外部记忆） |
| **有全稿** | 已完成初稿 | P5 修订 |
| **想发表** | 已成稿，要打磨与物料 | P6 定稿物料 |

**"在写中"这一档要特别处理**：已有正文但没做过设定集与台账的作品，必须先**在墨语补建作品设定与伏笔台账**（从已有正文倒推人物/世界观设定与伏笔记录），否则后续章节会持续跑偏。补建参考 `default-audit` 的台账比对方法。

### F1 按篇幅裁剪流程

不同体量需要的严谨度不同。裁剪规则见 `references/creation-pipeline.md`，要点：

| 篇幅 | 执行阶段 |
|---|---|
| 短篇（< 1 万字） | P0 极简 → P4 → P5 → P6 |
| 中篇（1–10 万字） | P0 → P1（只主角与核心设定）→ P2 → P4 → P5 → P6 |
| 长篇（> 10 万字） | 全七阶段，**P1 与 P5 不可省** |

**宁可高估**：8 万字的作品按长篇走，只是慢一点；15 万字的作品按中篇走，会在第 10 万字崩盘。

### F2 维护作品创作进度与资产备注

在当前作品备注或大纲根节点记录创作进度（格式见参考文档），必须包含：

- 项目基本信息（题材、篇幅、目标读者、当前阶段）
- **产物清单**及在墨语中的对应载体（设定集、大纲节点、细纲场景、章节正文、伏笔台账）
- **核心上下文资产**：人物与世界观设定 / 章节摘要 / 伏笔与时间线台账
- 门禁状态（哪些已过、哪些未过）
- 下一步待办

通过墨语作品备注与资产中枢沉淀上下文，确保长篇创作进程清晰可追溯。

### F3 逐阶段推进（核心）

每进入一个阶段，按固定三拍执行：

1. **声明**：告诉用户"现在在 PX 阶段，这一步要产出什么、过关标准是什么"。
2. **路由**：把具体动作交给对应技能（见下方路由表）——**本技能不重复实现任何既有技能的能力**。
3. **接回**：拿到产物后写入状态文件，进入 F4 门禁检查。

**阶段路由表**：

| 阶段 | 产物 | 交给谁 |
|---|---|---|
| P0 立项 | 立项书 | `novel-premise` |
| P1 设定（世界） | 规则体系、地理势力、年表 | `novel-world` |
| P1 设定（人物） | 人物档案、关系网 | `novel-cast` |
| P2 结构 | 大纲、伏笔回收计划 | `default-outline` |
| P3 细纲 | 分场细纲 | `novel-scene` |
| P4 初稿 | 正文 + 章节摘要 + 台账 | `default-continue`（写正文）、`default-expand`（某场太简略时） |
| P5 诊断（技术） | 矛盾问题清单 | `default-audit` |
| P5 诊断（价值） | 评分报告与修改优先级 | `default-analysis` |
| P5 修改 | 修订稿 | `default-rewrite` / `default-expand` / `default-shorten` |
| P6 打磨 | 定稿 | `de-ai-tone` |
| P6 物料 | 梗概、简介、腰封、分卷大纲 | `default-shorten` |

### F4 门禁检查（本技能存在的理由）

**端到端创作门禁清单与产物交接规范**：
- 严格执行各阶段物理门禁：P0 黄金三章核心卖点成立 ➔ P1 超凡代价与人物即时欲望锁定 ➔ P2 三章一波峰大纲通过 ➔ P3 分场细纲情绪位移明确 ➔ P4 初稿高频去AI味卡点 ➔ P5 战力与逻辑零硬伤 ➔ P6 全书终审。未达标坚决拦截，禁止带病推进。


每阶段结束，逐条核对门禁；**不通过则不进下一阶段**。

| 阶段 | 门禁判据 |
|---|---|
| P0 | 一句话故事能填满；目标读者与篇幅已定 |
| P1 | 主角欲望一句话能说清；至少一条世界硬规则带代价；主角与对手的欲望构成冲突 |
| P2 | 每条支线有归属；关键转折点有位置；伏笔有回收计划 |
| P3 | 每一场都能写出"这场结束时情况与开始时不同" |
| P4 | 每章写完即写摘要并更新台账，无待补 |
| P5 | 诊断顺序未颠倒（一致性 → 结构 → 字句）；动过设定后做过回归验证 |
| P6 | 同一章连读三遍无修改欲望 |

**回退规则**：允许回退，但**回退必须有具体理由**——"第 6 章违反了 P1 定的硬规则"可以回退；"感觉不太对"不可以。凭感觉回退会让稿子永远停在第一章。

**回退要一次到位**：发现设定问题就回 P1 改设定，不在 P4 打补丁——补丁会在第 30 章变成新的矛盾。

### F5 维护外部记忆三件套

| 文件 | 内容 | 更新时机 |
|---|---|---|
| **设定集** | 世界观规则、人物档案、关系网、专名表 | P1 建立；P4 期间随时增补 |
| **章节摘要** | 每章 100–150 字：发生了什么、推进了什么、新增了什么 | P4 每写完一章立刻写 |
| **伏笔台账** | 每条伏笔：内容 / 首次出现 / 状态 / 计划回收处 | P2 建立；P4 与 P5 更新 |

**这是长篇唯一的地基。** 用户嫌麻烦想跳过时，明确告诉他：省掉这一步，第 20 章一定会忘掉第 3 章的伏笔。

### F6 交付与阶段汇报

每次推进后给一份简短汇报，不含过程细节：

```
当前阶段：PX（已过门禁 / 未过）
本次产出：<产物名 + 路径>
外部记忆：设定集 N 条 / 摘要 N 章 / 未回收伏笔 N 条
下一步：<下一阶段要做什么，需要用户做什么决定>
```

## 硬性规则

1. **不重复实现既有技能。** 本技能只编排与验收，具体动作一律路由。这是它与其他 12 个技能不冲突的根本。
2. **门禁不放水。** 门禁不过就说不过，不因为用户着急而放行。
3. **单点任务不接。** 用户只要一个大纲、一段正文时，直接提示用对应技能，不套全流程。
4. **外部记忆不可省。** 长篇项目中用户要跳过摘要与台账时，明确说明后果，仍坚持则记录在状态文件里。
5. **问清起点再动手。** 不默认从零开始——一半以上的请求其实是"在写中"。
6. **不替用户做价值判断。** 题材、取舍、结局由用户定；AI 只给选项、风险与代价。
7. **每次只推进一个阶段。** 不一次性把七阶段全跑完——每个阶段末尾都有需要用户确认的选择点。
8. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/creation-pipeline.md` —— 七阶段完整流程表、门禁判据详表、按篇幅的裁剪规则、创作进度记录格式、回退判定规则。F1、F2、F3、F4 必读。
""",
        "files": [
            ("references/creation-pipeline.md", CREATION_PIPELINE),
        ],
    },
]



def migrate_and_seed_skills(conn: sqlite3.Connection | None = None):
    """首启自动迁移旧 prompts 到 skills 表，并初始化规范内置 Skill 种子。幂等执行。"""
    if conn is None:
        conn = get_db()

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

        skill_id = conn.execute("SELECT id FROM skills WHERE name = ?", (s["name"],)).fetchone()[0]
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
    """内置示例工作流种子：章节标准生产流 + 新书开坑五连流。幂等（按名字+builtin 判重）。"""
    if conn is None:
        conn = get_db()

    def _skill_id(name: str):
        row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    samples = [
        {
            "name": "章节标准生产流",
            "description": "一章的标准生产流程：生成草稿 → 一致性检查 → 润色定稿。草稿完成后需人工确认，检查与润色自动衔接。",
            "icon": "alt_route",
            "steps": [
                ("生成本章草稿", "default-continue", "chapter", None,
                 "顺着本章已有内容与上下文续写本章草稿，保持人物口吻与文风一致。", "medium", 1),
                ("一致性检查", "default-audit", "prev_output", 0,
                 "对上一步生成的草稿做设定一致性检查，只输出问题清单，不要修改文本。", "medium", 0),
                ("润色定稿", "default-rewrite", "prev_output", 0,
                 "在保持情节与设定不变的前提下润色草稿文字，去除 AI 腔与总结式收尾。", "medium", 0),
            ],
        },
        {
            "name": "新书开坑五连流",
            "description": "从一个想法到可落笔的细纲：立项 → 世界观 → 人物 → 大纲 → 分场细纲。每个阶段完成后停下来由你确认，再进入下一阶段。",
            "icon": "hub",
            "steps": [
                ("故事立项", "novel-premise", "none", None,
                 "我只有一个初步想法，请帮我做故事立项与定位。", "medium", 1),
                ("世界观设定", "novel-world", "prev_output", 0,
                 "基于已确认的立项方向搭建世界观与规则体系。", "long", 1),
                ("人物与关系", "novel-cast", "merge", 1,
                 "基于立项与世界观设定，设计主要人物档案与关系网。", "long", 1),
                ("故事大纲", "default-outline", "merge", 2,
                 "基于立项、世界观与人物设定，生成故事大纲与伏笔回收计划。", "long", 1),
                ("首章分场细纲", "novel-scene", "prev_output", 3,
                 "把大纲的第一章拆成可落笔的分场细纲。", "long", 1),
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
