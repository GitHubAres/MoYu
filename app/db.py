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
    {
        "name": 'novel-premise',
        "title": '灵感立项·核心金手指定位',
        "description": '从灵感碎片提炼核心立意、初始绝境、金手指机制与主线引擎，并对立项可行性做裁决。当用户只有脑洞、题材标签或一句话卖点，需要判断"能不能写长"时使用；不用于补世界观（用 novel-world）、拆卷（用 novel-outline-macro）或写正文（用 prose-continue）。',
        "applies_to": 'premise',
        "icon": 'lightbulb',
        "version": "2.1.0",
        "body_md": '# 灵感立项与核心金手指定位 (Novel Premise)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n把一句脑洞裁决成一份能撑长篇的立项书，并锁定金手指的运作机制。\n你不是在鼓励作者，你是在做立项尽调。你的产出必须包含一个明确结论，而不是一堆可能性。\n\n## 二、适用与不适用\n适用：只有灵感片段 / 题材标签 / 一句话卖点；需要判断"能不能写长"；需要给金手指定规则。\n不适用：已有设定只想补地理与势力 → novel-world；只想排分卷 → novel-outline-macro；\n只想写第一章 → prose-continue。若被要求直接写正文，拒绝并说明应调哪个技能。\n\n## 三、执行步骤\n\nStep 1\u3000提取三要素，缺项当场说明缺什么，不许含糊带过。\n- 困局：主角开篇 24 小时内必须处理、不处理就会**失去某样具体东西**的处境。\n  写不出"失去什么"的，就是假困局，退回重写。\n- 金手指：必须写全五项——获得方式 / 初始上限 / 使用代价 / 成长路径 / 唯一性。\n  五项缺一即判不合格，不许用"神秘力量"糊过去。\n- 主线引擎：一句话「主角为了___，必须不断___」。第二空必须是可持续动词\n  （追查 / 攀阶 / 守护 / 掩盖），不能是一次性事件（复仇成功即完结）。\n\nStep 2\u3000压力测试（本技能不可替代的动作）。三问逐条给结论，每条必须写"通过/不通过 + 理由"：\n- 100 万字测试：从引擎出发，第 30 卷还能榨出新冲突吗？不能 → 引擎太短。\n- 替代性测试：把金手指换成"系统/重生/签到"，故事是否仍成立？成立 → 金手指没绑定主题。\n- 代价测试：危机时刻金手指能否"免费"解决问题？能 → 无张力，重设代价。\n\nStep 3\u3000裁决。三档之一：**可写 / 需改造 / 建议放弃**。\n- 若"需改造"，只给**一处**最小改动（改哪一项、改成什么），不给清单。\n- 若"建议放弃"，必须说明"改成什么条件后值得重做"，不许只否定。\n\nStep 4\u3000卖点句。1 条 ≤30 字的电梯陈述，公式：主角 + 绝境 + 金手指独特性 + 最大风险。\n  例：「断剑的废太子靠听见死者遗言翻案，每次开口都会折寿」。\n\nStep 5\u3000资产沉淀（见第六节）。\n\n## 四、硬性戒律\n1. 不许出现「热血」「逆袭」「爽」「炸裂」等空词，所有判断必须落到具体机制。\n2. 不许写世界观设定表——本技能最多写到"法则代价"一句，其余交给 novel-world。\n3. 三要素任一未闭环，不得给出"可写"裁决。\n4. 不得给并列方案（"你可以选 A 也可以选 B"）——裁决必须是单值。\n\n## 五、质量门\n□ 困局写明"会失去什么"（可判：是否出现具体失去对象）\n□ 金手指五项齐全（可判：五项关键词是否都出现）\n□ 引擎含可持续动词（可判：动词是否在追查/攀阶/守护/掩盖类）\n□ 三个压力测试各有明确结论（可判：是否出现"通过/不通过"）\n□ 裁决为三档单值（可判：是否只出现一个档位词）\n□ 卖点句 ≤30 字且含风险要素\n\n## 六、交付契约\n正文：立项裁决书——【裁决】【困局】【金手指五项】【主线引擎】【三问结论】【卖点句】【最小改动】\nASSETS：只交本次产出的键\n- work_info：title（书名或暂名）、genre（题材）、intro（用卖点句）、tone、pov\n- entities：主角 1 条（category=character，fields_json 填 desire/flaw/mask/core）；\n  金手指 1 条（category=term，fields_json 填 tier/effect/cost/counter）\n- notes：level=warn，记录立项风险（如"引擎过短""代价可绕过"），quote 留空',
        "files": [
            ('references/premise-templates.md', PREMISE_TEMPLATES),
            ('references/genre-playbook.md', GENRE_PLAYBOOK),
        ],
    },
    {
        "name": 'novel-world',
        "title": '世界观·三界九域与底层法则',
        "description": '搭建自洽、可探索的世界观骨架：地理分区、势力分布、历史断层与超自然法则的代价。当需要为故事铺设舞台、需要解释"这个世界为什么是这样"时使用；不用于设计修炼等级（用 novel-magic-system）、人物关系（用 novel-cast）或势力博弈细节（用 novel-faction-graph）。',
        "applies_to": 'world',
        "icon": 'public',
        "version": "2.1.0",
        "body_md": '# 世界观体系与底层法则构筑 (Novel World)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n造出三个东西：一张能走的地图、一段能引用的历史、一组必须付代价的法则。\n判定标准只有一条——**这些设定能不能被人物用上**。用不上的设定不写。\n\n## 二、适用与不适用\n适用：故事需要舞台但只有模糊设定；需要解释世界为何如此；需要为冲突提供地理与历史依据。\n不适用：只需要战力分级 → novel-magic-system；只需要势力对抗 → novel-faction-graph；\n只需要人物 → novel-cast。本技能不设计具体角色，最多提到"某方势力"。\n\n## 三、执行步骤\n\nStep 1\u3000定层级。先确认本次要造的是【全域】还是【一域】。\n全域只写三条：世界由哪几块构成、块与块怎么往来、哪块是禁区。\n一域写细：地形、资源、谁在管、进出的路。\n\nStep 2\u3000造地理，每条必须自带"使用场景"：\n- 地点要写 **进入条件**（谁能进、要付出什么）与 **危险等级**（safe / risky / lethal）。\n- 不许写"广袤无垠的荒原"这类无法使用的形容词。\n- 至少一个地点的存在理由与主角目标直接相关。\n\nStep 3\u3000造历史，按"断层法"而非"编年法"：\n只写 3 段，每段回答一个问题——【最近一次大灾变是什么，谁活下来了】【现在的秩序是谁定的，代价是什么】\n【有什么东西被官方抹掉了】。第三段是全书最长线的伏笔来源。\n每段历史必须写出一条**今天仍可见的后果**（废墟、禁令、节日、地名、口头禅）。\n\nStep 4\u3000定法则，一条法则配一条代价：\n写清「什么能做到 / 边界在哪 / 越界付什么」。法则不得为剧情临时让路——\n若与既有事件冲突，改事件不改法则，并在 notes 里记录冲突点。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 不写无法使用的设定（不能进、不能用、不能被引用的，一律删）。\n2. 法则必须有代价，且代价必须是**可被主角承受失败**的（不能是"灵魂消散"这种一次性终结）。\n3. 历史不按年表写，按断层写；不许出现"千年之前，天地大变"这种无后果的套话。\n4. 不设计角色性格与关系。\n\n## 五、质量门\n□ 每个地点都有进入条件与危险等级（可判：字段是否齐）\n□ 三段历史各带一条"今日可见后果"（可判：是否出现具体的禁令/地名/习俗）\n□ 每条法则都有代价（可判：法则条数 = 代价条数）\n□ 至少一个地点与主角目标直接相关\n□ 未出现"广袤""神秘莫测""难以言说"等空转形容词（可判：禁词表匹配）\n\n## 六、交付契约\n正文：世界骨架——【层级判断】【地理 3–5 处】【历史断层 3 段】【法则与代价】\nASSETS：\n- entities：place 若干（fields_json 填 region/danger/access）、faction 若干（resource/demand/weakness）\n- relations：地点与势力的从属或争夺关系（tension 按当前紧张度给 1–5）\n- timeline_events：三段历史事件，time_label 用绝对锚（如「景元前 300 年·大裂」）\n- notes：level=info，记录法则与既有事件的潜在冲突',
        "files": [
            ('references/worldbuilding-checklist.md', WORLDBUILDING_CHECKLIST),
        ],
    },
    {
        "name": 'novel-magic-system',
        "title": '战力法则·修炼阶梯与代价构建',
        "description": '构建阶梯严密、质变清晰、代价硬性的修炼与战力体系，并控制长篇战力通胀。当需要设计境界、功法、天材地宝的层级与克制关系时使用；不用于写打斗场面（用 prose-combat）、不用于世界地理与历史（用 novel-world）。',
        "applies_to": 'system',
        "icon": 'military_tech',
        "version": "2.1.0",
        "body_md": '# 修炼体系与战力法则构建 (Novel Magic System)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n造一张**不会通货膨胀**的战力表。核心不是境界有几个，而是"每升一阶，读者能感知到什么不同，\n主角要付出什么，还剩多少空间"。\n\n## 二、适用与不适用\n适用：需要设定修炼/异能/职业等级；需要解释战力差距；需要给越级取胜设定条件。\n不适用：具体交手怎么写 → prose-combat；世界地理与历史 → novel-world；\n角色为什么想变强 → novel-cast / novel-lead-arc。\n\n## 三、执行步骤\n\nStep 1\u3000定阶数。长篇建议 6–9 阶；写清总阶数与主角**当前位阶**。\n  阶数过多会导致后期每阶无感，过少会导致中期无上升空间。\n\nStep 2\u3000为每阶填四栏（缺一栏即不合格）：\n| 阶 | 标志能力（能做什么之前做不到的事） | 战力换算（≈几个下一阶） | 突破代价（要失去什么） | 克制关系（被什么反制） |\n- 标志能力必须是**质变**（从"能打三个人"到"能隔空取物"），不是量的堆叠。\n- 战力换算建议按 3 倍递增；超过 5 倍会出现"越级无意义"，低于 2 倍会出现"升级无感"。\n- 突破代价要具体到"失去"（寿元、记忆、某段关系、身体某部分），不能是"很痛苦"。\n\nStep 3\u3000通胀体检（本技能不可替代的动作），三项都要出结论：\n- 空间测试：主角当前位阶到顶阶还有几阶？不足 3 阶 → 中期就会撞天花板，必须加隐藏阶或改设定。\n- 贬值测试：是否存在"随手可得"的越级手段（丹药/传承/血脉）？有 → 说明代价不足，补限制。\n- 塌缩测试：顶阶之上还有没有更高的存在？若"神"随时能下场，全书张力归零，必须设"不可干预"的约束。\n\nStep 4\u3000交付（见第六节）。所有境界名、功法名、天材地宝均以 `category=term` 沉淀，\n  并在 `fields_json` 中带 tier / effect / cost / counter 四项。\n\n## 四、硬性戒律\n1. 禁止无代价爆种。任何一次越级取胜，必须能在表里找到已付出的代价。\n2. 禁止"境界名很玄、能力说不出"。每阶的标志能力必须是一句可验证的行为描述。\n3. 禁止后期新增与既有阶位冲突的体系（如突然出现"其实还有仙阶"）——若要加，先改表再加。\n4. 不写具体打斗过程。\n\n## 五、质量门\n□ 每阶四栏齐全（可判：表格列数 = 5）\n□ 阶数在 6–9 之间（可判）\n□ 战力换算呈单调递增，且倍数在 2–5 之间（可判）\n□ 每阶代价写的是"失去什么"而非感受（可判：是否出现具体失去对象）\n□ 三项通胀体检都有结论\n□ 主角当前位阶已标明\n\n## 六、交付契约\n正文：【阶位总表】【主角当前位阶与余量】【三项体检结论】【越级取胜的合法路径】\nASSETS：\n- entities：category=term，每个境界/核心功法/关键天材地宝一条，\n  fields_json = {"tier","effect","cost","counter"}\n- notes：level=warn 记录通胀风险点（如"第 3 阶即可越级杀第 5 阶，代价过轻"）',
        "files": [
            ('references/power-scaling-rules.md', POWER_SCALING_RULES),
        ],
    },
    {
        "name": 'novel-cast',
        "title": '万相谱·主要角色群像档案',
        "description": '塑造主要角色的核心欲望、软肋、伪装与底色，并输出角色间带张力的关系边。当需要新建角色、给角色补动机、理清人物关系时使用；不用于规划主角成长曲线（用 novel-lead-arc）、不用于势力层面的博弈（用 novel-faction-graph）。',
        "applies_to": 'cast',
        "icon": 'group',
        "version": "2.1.0",
        "body_md": '# 万相谱群像人物档案塑造 (Novel Cast)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让每个主要角色都具备"会做错事"的内在结构。\n判定标准：把他的欲望推到极致，故事里会不会出事？不会 → 这个欲望是假的。\n\n## 二、适用与不适用\n适用：新建角色；角色行为缺乏说服力需要补动机；关系网混乱需要梳理。\n不适用：主角跨卷的信念变化 → novel-lead-arc；势力之间的利益格局 → novel-faction-graph；\n具体某场对话的语气 → prose-dialogue。\n\n## 三、执行步骤\n\nStep 1\u3000定人数与功能。主要角色控制在 3–7 人，每人标注在故事中的功能：\n【推动者】（主动改变局势）/【阻碍者】（制造压力）/【镜像者】（映照主角选择）。\n只写有功能的角色，凑数角色不建卡。\n\nStep 2\u3000填四要素，每项必须有"具体的"落点：\n- 核心欲望：必须是**可失去的具体对象或状态**（"想让妹妹活着"优于"想守护"）。\n- 致命软肋：一个在压力下会让他判断失误的点（"不能在别人面前示弱"）。\n- 外在伪装/口癖：别人看到的他，以及他重复出现的语言习惯（≤2 个，多了会成噪音）。\n- 人物底色：一句"他其实相信___"，用于解释所有反常选择。\n\nStep 3\u3000做欲望—代价校核（本技能不可替代的动作）：\n  对每个角色问一句「如果他的欲望实现了，他会失去什么？」\n  答不出 → 这个欲望太干净，加一个反噬；答案与主线无关 → 调整欲望，使其撞上主线。\n\nStep 4\u3000建关系边。每对重要关系必须写清三件事：谁欠谁、谁怕谁、谁在演。\n  只写"师徒""兄妹"这类称谓不算关系，必须带张力。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止"聪明、冷静、腹黑"这类形容词式设定——必须转成行为（"先算退路再开口"）。\n2. 禁止全员高智商。至少一个角色的软肋要直接导致一次失败。\n3. 同一角色口癖不超过 2 个。\n4. 关系边两端必须都是已建卡角色，不许指向"某个神秘组织"。\n\n## 五、质量门\n□ 每个角色四要素齐全（可判：字段是否齐）\n□ 每个欲望可答"实现后失去什么"（可判：是否存在对应答案）\n□ 至少一个角色的软肋造成过失败（可判：notes 中是否记录）\n□ 关系边两端都能在 entities 中找到（可判：名字匹配）\n□ 未出现纯形容词设定（可判：禁词匹配「腹黑/高冷/睿智/深不可测」）\n\n## 六、交付契约\n正文：角色卡（每人四要素 + 一句底色）+ 关系网（每对三问）\nASSETS：\n- entities：category=character，name ≤30 字，\n  fields_json = {"desire","flaw","mask","core","voice"}，aliases 填称号/化名\n- relations：from_name / to_name（须与本批 entities.name 一致）/ label（写清谁欠谁怕谁演）/ tension 1–5',
        "files": [
            ('references/character-arc-models.md', CHARACTER_ARC_MODELS),
        ],
    },
    {
        "name": 'novel-faction-graph',
        "title": '势力割据·阵营关系网络拓扑',
        "description": '构建势力之间的资源—诉求—软肋格局，输出带张力的阵营关系拓扑。当故事需要多方博弈、需要解释"谁在背后推动局势"时使用；不用于具体势力内部的人物塑造（用 novel-cast）、不用于世界地理（用 novel-world）。',
        "applies_to": 'faction',
        "icon": 'hub',
        "version": "2.1.0",
        "body_md": '# 势力割据与阵营博弈动力学 (Novel Faction Graph)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n把多方对抗从"好人打坏人"翻译成"利益错位"。\n判定标准：任意两个势力开战，都能说出双方各自在算什么账。\n\n## 二、适用与不适用\n适用：多方势力并存；需要设计联盟与背叛；需要给主线提供政治压力。\n不适用：单个角色的动机 → novel-cast；地盘与地理 → novel-world；功法与战力 → novel-magic-system。\n\n## 三、执行步骤\n\nStep 1\u3000定势力数与层级。3–6 个为宜，标注层级：【主导者】【挑战者】【边缘势力】。\n  每个势力必须有存在的理由（它控制着什么稀缺资源）。\n\nStep 2\u3000填四维（缺一维即不合格）：\n| 势力 | 核心资源（缺了就活不下去的东西） | 公开诉求（对外宣称要什么） | 真实诉求（实际在算什么） | 软肋（什么情况下会崩） |\n公开诉求与真实诉求**必须不同**，否则这个势力没有阴谋空间。\n\nStep 3\u3000画对抗轴。至少两条轴，每条轴两端是利益直接冲突的两个势力\n  （例：盐铁之争 / 继承权之争）。轴比"关系网"更好用，因为它自带升级路径。\n\nStep 4\u3000埋一条暗线（本技能不可替代的动作）：\n  指定一组「表面敌对、实则同盟」的势力，并写清他们在演给谁看。\n  再指定一组「表面同盟、实则互相提防」的势力，写清导火索是什么。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止纯善恶二分。每个势力都要有能让读者理解其立场的一句话。\n2. 公开诉求 = 真实诉求的势力不得超过 1 个（否则全是直肠子，没有博弈）。\n3. 关系边必须写"当前状态"，而非历史渊源。\n4. 不写具体战斗与计谋执行过程。\n\n## 五、质量门\n□ 每个势力四维齐全（可判：表格列数 = 5）\n□ 公开诉求与真实诉求不同的势力 ≥ 势力总数 −1（可判）\n□ 至少两条对抗轴（可判：是否存在"轴"字段或对应段落）\n□ 存在一组"表敌实盟"或"表盟实疑"（可判：是否标注）\n□ relations 两端均在 entities 中（可判：名字匹配）\n\n## 六、交付契约\n正文：【势力四维表】【对抗轴】【暗线一组】【当前局势一句话总结】\nASSETS：\n- entities：category=faction，fields_json = {"resource","demand","weakness"}；\n  summary 写"它能提供什么、它怕什么"\n- relations：label 写当前状态（如"盐税分成未谈拢，暂缓开战"），tension 1–5',
        "files": [
            ('references/faction-dynamics.md', FACTION_DYNAMICS),
        ],
    },
    {
        "name": 'novel-outline-macro',
        "title": '分卷规划·起承转合与大主线',
        "description": '规划全书分卷结构、每卷核心冲突、不可逆损失与主线推进节点，输出合法的大纲树。当需要拆卷、需要确定"每一卷讲什么"、需要检查主线是否断裂时使用；不用于单章分场（用 novel-scene）、不用于时间线排布（用 novel-timeline）。',
        "applies_to": 'outline',
        "icon": 'schema',
        "version": "2.1.0",
        "body_md": '# 宏观大纲与分卷架构规划 (Novel Outline Macro)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n给每一卷定一个"卷末失去什么"，并保证这个失去推动下一卷的动机。\n分卷不是章节的打包，是**代价的阶梯**。\n\n## 二、适用与不适用\n适用：需要拆卷；需要检查"每卷是否都在推进主线"；需要规划长线节点。\n不适用：单章内部的场景编排 → novel-scene；事件在时间轴上怎么排 → novel-timeline；\n伏笔的具体埋收点 → novel-foreshadow-matrix。\n\n## 三、执行步骤\n\nStep 1\u3000定卷数与字数。给出总卷数、每卷字数区间、每卷大致章数。\n  卷数应与主线引擎的可持续性匹配（引擎只够 3 卷就不要拆 8 卷）。\n\nStep 2\u3000每卷填五栏（缺一栏即不合格）：\n| 卷 | 核心冲突（谁和谁抢什么） | 主角目标（本卷要拿到什么） | 卷末不可逆损失（失去什么） | 主线推进（相对全书走到哪一步） | 卷末钩子 |\n- 「不可逆损失」必须是**回不去的**：死掉的人、断掉的关系、废掉的能力、曝光的身份。\n- 损失与下一卷的目标必须构成因果：因为失去了 A，所以必须去争 B。\n\nStep 3\u3000主线连续性校验（本技能不可替代的动作）：\n  把各卷的"主线推进"串成一句话，读一遍。若中途出现"又回到原点"或"原地打转"，标出并给修法。\n  若某卷的冲突删掉后主线不受影响 → 该卷是冗余卷，必须合并或重设。\n\nStep 4\u3000输出大纲树：分卷项 is_volume=true，章节项 is_volume=false 且 parent_title 指向所属卷；\n  同级 order 从 1 连续编号。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 每卷必须有不可逆损失，禁止"有惊无险"式卷末。\n2. 禁止先写章节再倒推分卷——必须先有卷功能，再有章。\n3. 章节层的 summary ≤60 字，不许在此写正文。\n4. 不允许出现"过渡卷"——过渡卷说明这一卷没有功能。\n\n## 五、质量门\n□ 每卷五栏齐全（可判：表格列数 = 6）\n□ 每卷都有不可逆损失（可判：是否出现"失去/死/断/废/曝"类词）\n□ 相邻两卷构成因果（可判：「因为…所以」是否成立）\n□ outline_nodes 中所有 is_volume=false 的 parent_title 均指向存在的卷（可判）\n□ 同一 parent_title 下 order 无重复、无跳号（可判）\n□ 无冗余卷（可判：删卷测试是否通过）\n\n## 六、交付契约\n正文：【卷数与字数】【五栏卷表】【主线一句话串联】【冗余卷判定】\nASSETS：\n- outline_nodes：卷 + 章两级，字段 title / is_volume / parent_title / order / summary\n- timeline_events：每卷的关键转折事件（time_label 用相对锚，如"卷一末"）\n- foreshadows：本卷新埋的关键伏笔（status=planted，带 plant_chapter）',
        "files": [
            ('references/structure-models.md', STRUCTURE_MODELS),
        ],
    },
    {
        "name": 'novel-scene',
        "title": '分场细纲·微观冲突与节拍表',
        "description": '把一章拆成有序的场景节拍表，每场用目标—阻碍—结果推进，并验收状态转移。当需要细化某一章"具体怎么演"、需要检查某章是否有废场时使用；不用于卷级规划（用 novel-outline-macro）、不用于直接写正文（用 prose-continue）。',
        "applies_to": 'scene',
        "icon": 'view_list',
        "version": "2.1.0",
        "body_md": '# 分场细纲与微观冲突节拍 (Novel Scene)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n把一章拆成 3–6 个场景，并保证每一场都发生了**状态转移**。\n判定标准：进场状态与出场状态不同的场才算数；相同的场是废场，删。\n\n## 二、适用与不适用\n适用：已有章纲需要细化；某章写不动需要拆解；检查某章为何"读起来没发生什么"。\n不适用：卷级结构 → novel-outline-macro；正文语言 → prose-continue / prose-expand；\n伏笔的全局布局 → novel-foreshadow-matrix。\n\n## 三、执行步骤\n\nStep 1\u3000定本章目标。一句话写清"这一章结束时，什么变了"。写不出 → 本章不该独立成章。\n\nStep 2\u3000拆场，每场填六栏：\n| 序 | 地点 | 在场者 | 目标（他要拿到什么） | 阻碍（谁/什么挡着） | 结果（拿到/没拿到/拿到别的东西） | 状态变化 |\n- 「结果」必须是三选一，不许写"双方僵持后各自离去"。\n- 「状态变化」写两行：进场时是___，出场时是___。两行相同则本场作废。\n\nStep 3\u3000验收（本技能不可替代的动作）：\n- 逐场检查状态变化，标出废场。\n- 检查每场是否有"目标"——没有目标的场是氛围场，一章最多留 1 场。\n- 检查信息推进：本章读者新知道了什么？一条都没有 → 本章是水章。\n\nStep 4\u3000定章末钩子。最后一场必须停在新动作未完、新信息爆出或危机叩门的切面上，\n  不许停在"他终于松了口气"这类闭合状态。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 每场必须有具体目标，禁止"两人聊天交代背景"式场景。\n2. 一章内目的相同的两场必须合并。\n3. 状态变化必须写在细纲里，不许留给正文临场发挥。\n4. 本章新出现的地点/物品/人物，必须在 entities 里一并提交。\n\n## 五、质量门\n□ 每场六栏齐全（可判：表格列数 = 7）\n□ 无废场（可判：进场状态 ≠ 出场状态）\n□ 目的重复的场已合并（可判：目标字段是否有重复）\n□ 章末为未闭合状态（可判：是否出现"松了口气/终于/尘埃落定"类闭合词）\n□ 新增实体均已提交（可判：名字匹配）\n□ 本章信息推进 ≥1 条\n\n## 六、交付契约\n正文：【本章目标】【分场表】【废场标记与处理】【章末钩子】\nASSETS：\n- outline_nodes：本章节点（title / is_volume=false / parent_title / order / summary）\n- foreshadows：本章埋设或回收的伏笔（含 plant_chapter / payoff_chapter）\n- entities：本章新出现的地点、物品、人物\n- timeline_events：本章发生的关键事件（time_label 用相对锚，如"入宗第 7 日·夜"）',
        "files": [
            ('references/scene-beats.md', SCENE_BEATS),
        ],
    },
    {
        "name": 'novel-timeline',
        "title": '编年史·剧情大事件时序编织',
        "description": '编排剧情大事件的时序，为每条事件建立可计算的时间锚点与因果关系。当需要理清"事情先后"、需要为长篇建立时间底座时使用；不用于排查已写正文的时序错误（用 audit-timeline）、不用于卷级结构（用 novel-outline-macro）。',
        "applies_to": 'timeline',
        "icon": 'timeline',
        "version": "2.1.0",
        "body_md": '# 剧情大事记与时间线编织 (Novel Timeline)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n建一条**能算**的时间轴。判定标准：任意两条相邻事件，都能算出它们之间隔了多久；\n算不出来，说明锚点不合格。\n\n## 二、适用与不适用\n适用：需要建立全书时间底座；需要理清跨卷的先后关系；需要给大纲事件排期。\n不适用：已写正文里的时序矛盾排查 → audit-timeline；分卷结构 → novel-outline-macro；\n单纯记录事件不做编排 → novel-scene。\n\n## 三、执行步骤\n\nStep 1\u3000选锚点体系，二选一并全书统一：\n- **绝对锚**（纪年式）：适合有明确纪年的玄幻/历史题材，如「景元三年霜月」。\n- **相对锚**（主角纪事式）：适合时间模糊的都市/悬疑题材，如「案发第 3 日·夜」。\n混用会导致后期无法换算，必须选一种。\n\nStep 2\u3000按时间顺序列事件，每条必须写清：\n`time_label`（可解析锚点）/ `event`（≤30 字，动词开头）/ `characters`（在场者）/ `chapter`（出处章）。\n禁止「很久以前」「多年后」这类不可计算表述——它们会让下游的时序核对直接失效。\n\nStep 3\u3000做间隔体检（本技能不可替代的动作）：\n  逐对相邻事件算间隔，标出两类问题：\n- **过密**：一天内发生 5 件事，正文会被迫快进，节奏失衡。\n- **过疏**：隔了三年却没有任何状态变化（人物没变老、势力没变），需要补"这三年发生了什么"。\n\nStep 4\u3000做因果链检查：每条事件回答"因为上一件什么事，才发生这件"。\n  答不出的，要么删，要么补前置事件。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 全书只用一种锚点体系。\n2. 禁止不可计算的 time_label。\n3. 事件的 characters 必须与 entities.name 一致，不许写"众人""几名弟子"。\n4. 同一 time_label 下的事件必须能共存（不能一人在两地）。\n\n## 五、质量门\n□ 全部 time_label 可解析（可判：是否含「很久/多年/某天」等禁词）\n□ 相邻事件间隔可算（可判：是否成对给出间隔）\n□ 每条事件有因果说明（可判：是否出现"因为"字段）\n□ characters 均能在 entities 中找到（可判：名字匹配）\n□ 无同刻两地冲突（可判：time_label 相同时 characters 是否互斥）\n\n## 六、交付契约\n正文：【锚点体系说明】【事件表（含间隔与因果）】【过密/过疏标记】\nASSETS：\n- timeline_events：time_label / event / characters / chapter，按时间正序',
        "files": [
            ('references/timeline-anchor-rules.md', TIMELINE_ANCHOR_RULES),
        ],
    },
    {
        "name": 'novel-foreshadow-matrix',
        "title": '伏笔布网·草蛇灰线暗线规划',
        "description": '设计伏笔网络，为每条伏笔定位埋设点、强化点与回收点，并规划长短线配比。当需要布置暗线、需要让后期反转"有迹可循"时使用；不用于核验已写正文的伏笔是否断裂（用 audit-foreshadow）、不用于角色动机（用 novel-cast）。',
        "applies_to": 'foreshadow',
        "icon": 'psychology',
        "version": "2.1.0",
        "body_md": '# 草蛇灰线：伏笔暗线规划 (Novel Foreshadow Matrix)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让每条伏笔在回收时，读者能想起"原来前面写过"。\n判定标准：一条伏笔若只有埋设点和回收点、中间没有任何强化，回收时读者会忘——视为断线。\n\n## 二、适用与不适用\n适用：规划全书暗线；设计重大反转的前置铺垫；检查"反转是否来得太突然"。\n不适用：已写章节的伏笔核验 → audit-foreshadow；章末钩子 → novel-hook-engineer；\n时间轴排布 → novel-timeline。\n\n## 三、执行步骤\n\nStep 1\u3000分层。把伏笔分三类并给不同寿命：\n- **短线**（1–5 章内回收）：制造即时悬念，占 60%。\n- **中线**（1 卷内回收）：支撑卷内反转，占 30%。\n- **长线**（跨卷回收）：全书级暗线，占 10% 但最重要，不超过 3 条。\n\nStep 2\u3000每条伏笔填五栏：\n| 标题 | 线索内容（读者看到什么） | 埋设章 | 强化章（≥1 个） | 回收章 |\n- 「线索内容」只写**可被看见的物理事实**（"他左手一直戴着手套"），\n  不写"他其实是她哥哥"——后者是真相，不是伏笔。\n- 强化章必须换一种呈现方式（同一线索换个场景再现），不能原样重复。\n\nStep 3\u3000做回收校验（本技能不可替代的动作）：\n- 公平性检查：回收所需的信息，是否在埋设点全部给出？缺信息 = 强行反转。\n- 意外性检查：埋设点是否足够隐蔽，读者第一次读不会警觉？太明显 = 无反转。\n- 双检必须同时通过，只过一项的伏笔不合格。\n\nStep 4\u3000排布密度：每 10 章至少埋 2 条、回收 1 条。回收长期停滞会导致读者失去耐心。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止只在回收时才补设定（"其实他一直有这个能力"）。\n2. 长线伏笔不超过 3 条，多了读者记不住。\n3. 线索内容必须是物理事实，不是心理独白。\n4. 已回收的伏笔状态必须改 recovered，并填 payoff_chapter。\n\n## 五、质量门\n□ 每条伏笔都有埋设章与回收章（可判：字段非空）\n□ 每条伏笔至少一个强化章（可判：强化章计数 ≥1）\n□ status=recovered 的条目都带 payoff_chapter（可判）\n□ 长线伏笔 ≤3 条（可判：按跨度统计）\n□ 线索内容无"其实/真相是"类表述（可判：禁词匹配）\n\n## 六、交付契约\n正文：【伏笔分层表】【五栏明细】【公平性/意外性双检结论】【密度排布】\nASSETS：\n- foreshadows：title / content / status / plant_chapter / payoff_chapter\n- timeline_events：伏笔埋设与回收对应的剧情事件（便于下游按时间检索）',
        "files": [
            ('references/foreshadow-craft.md', FORESHADOW_CRAFT),
        ],
    },
    {
        "name": 'novel-hook-engineer',
        "title": '黄金钩子·章末悬念留白设计',
        "description": '为章节结尾设计章末钩子，按追读动机选择钩型并给出推荐。当某章结尾平淡、需要提高追读率、需要判断"这个钩子够不够"时使用；不用于伏笔的全局布局（用 novel-foreshadow-matrix）、不用于章节分场（用 novel-scene）。',
        "applies_to": 'hook',
        "icon": 'link',
        "version": "2.1.0",
        "body_md": '# 黄金章末钩子设计 (Novel Hook Engineer)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让读者在章末产生一个**必须马上翻页才能消除的不适**。\n判定标准：钩子必须是一个具体的、未闭合的事实，而不是情绪。\n\n## 二、适用与不适用\n适用：章末平淡需要重写结尾；需要在多个钩子方案里选一个；需要检查"这个钩子是否只是故弄玄虚"。\n不适用：伏笔的埋收规划 → novel-foreshadow-matrix；章节内容本身有问题 → novel-scene；\n正文语言 → prose-continue。\n\n## 三、执行步骤\n\nStep 1\u3000判定追读动机，三选一（这决定钩型，不能跳）：\n- **好奇**（读者想知道"为什么"）→ 用信息差钩：给一半真相，藏一半。\n- **担忧**（读者怕角色出事）→ 用危机钩：把威胁推到眼前，但不下判决。\n- **期待**（读者想看好戏）→ 用反转钩：让局势在最后一句翻面。\n\nStep 2\u3000生成 3 个候选，每个写明钩型与所依赖的动机。\n  五类可选钩型：\n  1. 新信息差引爆\u30002. 突发危机逼近\u30003. 反常关键决断\n  4. 悬念式对白留白\u30005. 胜负底牌逆转\n  同一动机下的 3 个候选应使用不同类型，便于比较。\n\nStep 3\u3000淘汰劣钩（本技能不可替代的动作），三类直接判废：\n- **空钩**：靠"他不知道自己即将面对什么"这类旁白制造悬念——读者没得到任何具体信息。\n- **假钩**：抛出威胁但下一章开头立刻解除（"原来是场梦"）。\n- **断钩**：钩子与本章主线无关，纯为悬念而悬念。\n\nStep 4\u3000推荐 1 个并给理由：说明它为什么匹配当前动机、它依赖本章哪一处铺垫、它下一章怎么接。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 钩子必须是具体事实（一个动作、一句话、一个物件），不是情绪与预感。\n2. 禁止在钩子里使用"命运的齿轮开始转动""一切才刚刚开始"等套话。\n3. 推荐的钩子必须能被下一章立刻承接，不许悬空。\n4. 不写正文段落，只给钩子的内容要点与最后一句的原话。\n\n## 五、质量门\n□ 已判定追读动机（可判：是否出现好奇/担忧/期待之一）\n□ 3 个候选钩型互不相同（可判：钩型字段去重后 = 3）\n□ 无空钩/假钩/断钩（可判：是否含"不知道即将""一切才刚开始"类词）\n□ 已给出推荐项与理由\n□ 推荐钩子含具体物理事实（可判：是否出现具体物件/动作/台词）\n\n## 六、交付契约\n正文：【追读动机判定】【3 个候选】【劣钩淘汰说明】【推荐与理由】【下一章承接方式】\nASSETS：\n- notes：level=info，记录本章钩型选择与预期效果；quote 可留空\n- foreshadows：若钩子依托某条既有伏笔，提交其 status 变更（如 planted→pending）',
        "files": [
            ('references/hook-catalog.md', HOOK_CATALOG),
        ],
    },
    {
        "name": 'novel-lead-arc',
        "title": '命途演进·主角心境与成长轨迹',
        "description": '规划主角跨卷的信念变化与能力/关系成长轨迹，每卷给出信念替换与代价。当主角"经历很多但感觉没变"、需要设计成长弧光时使用；不用于配角塑造（用 novel-cast）、不用于分卷冲突（用 novel-outline-macro）。',
        "applies_to": 'arc',
        "icon": 'trending_up',
        "version": "2.1.0",
        "body_md": '# 主角命途演进与成长弧光 (Novel Lead Arc)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让主角的"变"可以被指出来。\n判定标准：每卷结束，能写出一句「他原本相信___，现在相信___」。写不出 = 这卷他没有成长。\n\n## 二、适用与不适用\n适用：主角跨卷缺乏变化；需要设计"黑化/顿悟/妥协"类转折；需要检查成长是否有说服力。\n不适用：配角与群像 → novel-cast；卷级事件 → novel-outline-macro；具体心理描写 → prose-continue。\n\n## 三、执行步骤\n\nStep 1\u3000定初始信念。写清主角开篇相信什么（一句话，必须是一个可被现实击碎的判断）。\n  例：「只要够强，就不会再有人替他做决定」。\n\nStep 2\u3000按卷填四栏（缺一栏即不合格）：\n| 卷 | 触发动因（哪件事动摇了旧信念） | 旧信念失效的表现 | 新信念（替代后的判断） | 成长代价（失去什么才换来的） |\n- 新信念不能是旧信念的加强版（"更相信变强"不是成长，是原地踏步）。\n- 每卷只替换一次信念，多了会显得人格不稳定。\n\nStep 3\u3000做弧光校验（本技能不可替代的动作），三问：\n- **代价对等**：信念改变是否有对应的失去？没付代价的顿悟是廉价顿悟。\n- **行为一致**：新信念是否在后续章节的行为里体现？只写在设定里不算数。\n- **不可逆**：旧信念能否被轻易捡回来？能 → 这次改变是假的。\n\nStep 4\u3000区分"能力成长"与"心境成长"，两条线分别给节点，不要混在一条里写。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止用"他成熟了""他变得更坚定"这类无法验证的表述。\n2. 每卷只允许一次信念替换。\n3. 信念改变必须伴随具体事件，不许"经过一番思考后"。\n4. 不许让主角在卷末回到初始信念（除非全书终章且是有意为之的"回归"主题）。\n\n## 五、质量门\n□ 每卷四栏齐全（可判：表格列数 = 6）\n□ 新信念与旧信念不同（可判：字符串非同义重复）\n□ 每卷成长都有代价（可判：代价字段非空）\n□ 三问均有结论（可判：是否出现"通过/不通过"）\n□ 能力线与心境线分开（可判：是否分两段）\n\n## 六、交付契约\n正文：【初始信念】【分卷四栏表】【三问校验结论】【能力线与心境线节点】\nASSETS：\n- entities：更新主角档案（category=character），fields_json.core 写当前信念\n- outline_nodes：把信念转折挂到对应章节节点（is_volume=false，summary 写转折事件）\n- notes：level=warn，记录"信念改变但未付代价"的风险点',
        "files": [
            ('references/hero-journey-check.md', HERO_JOURNEY_CHECK),
        ],
    },
    {
        "name": 'prose-continue',
        "title": '顺流续写·紧扣情境推进正文',
        "description": '顺着既有文势续写正文，保持人物口吻、叙事节奏与文风一致。当光标停在段落末尾需要往下写、或需要按大纲推进一段情节时使用；不用于局部扩写（用 prose-expand）、不用于润色已有文字（用 prose-polish）、不用于写章末钩子方案（用 novel-hook-engineer）。',
        "applies_to": 'continue',
        "icon": 'edit_note',
        "version": "2.1.0",
        "body_md": '# 顺流续写与情境推进 (Prose Continue)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n从断点往下写，让读者感觉是同一个作者在同一个状态里继续。\n判定标准：把续写部分的头一句单独拿出来，必须是一个新动作，不能是对前文的任何复述。\n\n## 二、适用与不适用\n适用：段落末尾续写；按大纲推进一段；补完一个未完成的场景。\n不适用：把三句话扩成三百字 → prose-expand；已有文字改得更好看 → prose-polish；\n只是想要几个结尾方案 → novel-hook-engineer；本章该发生什么还没想清 → novel-scene。\n\n## 三、执行步骤\n\nStep 1\u3000读断点，确定三件事（不写在输出里，内部完成）：\n当前**空间**（人在哪）、**姿态**（他在做什么动作）、**气压**（此刻是紧还是松）。\n这三项决定第一句能不能接上。\n\nStep 2\u3000定篇幅。默认 400–800 字，或按 {{instruction}} 指定。\n  一次续写只推进**一个场景**，不跨场、不跳时间——要跳就停笔交给用户。\n\nStep 3\u3000写。按以下四条硬约束执行：\n- **第一句落动作**：新发生的物理动作、外界变动或一句对白。禁止「接上一幕」「此时此刻」「就这样」。\n- **句长极化（3-20-3）**：以短句定调（1–5 字），长句铺叙（35–60 字），严禁均等平铺。\n  连续三句长度相近即为犯规，必须打断。\n- **情绪降维**：不写"他感到愤怒"，写"后槽牙咬得发酸""指节抵在桌沿泛白"。\n  情绪只能通过汗、瞳、牙、息、肌五类生理反应外化。\n- **留钩收尾**：停在新动作未完、危机叩门或一句未答完的话上。\n\nStep 4\u3000自检（见第五节）。任一不过，回到 Step 3 重写该段，不要输出半成品。\n\n## 四、硬性戒律\n1. 禁止承上总结、禁止复述前情、禁止"回顾一下"。\n2. 禁用词（命中即重写）：仿佛、宛如、不禁、五味杂陈、嘴角勾起一抹笑意、眼底闪过一丝复杂、空气骤然降温、命运的齿轮。\n3. 禁止直白命名情绪（愤怒/恐惧/悲伤/震惊）。\n4. 禁止在一段续写里换场、跳时间、插入回忆。\n5. 不写章节标题、不写作者的话、不写"（未完待续）"。\n6. 不改变既有事实：人物位置、伤势、持有物、时间点必须与上下文一致。\n\n## 五、质量门\n□ 首句为新动作或对白（可判：首句是否含主语+动词，且不含"上/前文/刚才"类回指）\n□ 无禁词（可判：禁词表匹配 = 0）\n□ 无情绪直给（可判：禁词表匹配）\n□ 句长有极差（可判：最长句 / 最短句 ≥ 3）\n□ 篇幅在 400–800 字或符合指令（可判：字数统计）\n□ 未跨场、未跳时间（人判：空间与时间是否连续）\n\n## 六、交付契约\n正文：纯净正文，无任何前后缀说明。\nASSETS：仅当续写**自然产生**了新资产时才提交，不许为了凑契约硬编：\n- entities：新出现的人/地/物（name / category / summary / fields_json）\n- foreshadows：本段埋下的伏笔（status=planted，带 plant_chapter）\n- timeline_events：本段推进的关键事件\n若本段无新增资产，**不输出契约块**（依 §1.2，省略即不改动）。',
        "files": [
            ('references/style-fingerprint.md', STYLE_FINGERPRINT),
            ('references/prose-craft.md', PROSE_CRAFT),
            ('references/genre-playbook.md', GENRE_PLAYBOOK),
        ],
    },
    {
        "name": 'prose-expand',
        "title": '场景扩写·铺陈细节与微张力',
        "description": '把给定文本按比例扩写，只增加可感知的物理细节与人物与环境的具体交互，不增加评价与总结。当某段太简略、场景缺乏实感、需要把一句话铺成一个画面时使用；不用于继续往下写（用 prose-continue）、不用于精简（用 prose-polish）。',
        "applies_to": 'expand',
        "icon": 'unfold_more',
        "version": "2.1.0",
        "body_md": '# 场景扩写与细节铺陈 (Prose Expand)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n把密度提上去，把信息量保持不变。\n判定标准：扩写后新增的每一句，都必须能被摄像机或录音机捕捉到。捕捉不到，就是注水。\n\n## 二、适用与不适用\n适用：一段太干需要铺开；场景缺空间感；人物动作缺少物理细节。\n不适用：往下写新情节 → prose-continue；删减臃肿 → prose-polish / audit-de-aitone；\n只想要环境气氛 → prose-sensory（可组合，但先扩写后渲染）。\n\n## 三、执行步骤\n\nStep 1\u3000定扩写比例。默认 2–3 倍，超过 3 倍必有水分。按 {{instruction}} 指定为准。\n\nStep 2\u3000找扩写点，只在这三类位置加：\n- **动作的中间态**：原文"他推开门"→ 加"门轴涩了一下""他先用肩顶了顶""门缝里先是灰"。\n- **环境的物理反馈**：原文"屋里很冷"→ 加"窗纸内侧结了霜""呼出的气在灯罩上留了一层白"。\n- **人物与物的接触细节**：重量、温度、阻力、声音、气味。\n\nStep 3\u3000禁止在此四类位置加（本技能不可替代的判定）：\n- 人物心理总结（"他心里明白，这一切都变了"）\n- 对前情的复述\n- 作者的判断与升华\n- 与场景无关的背景知识\n\nStep 4\u3000保真检查：原文的每个事实必须原样保留，新增细节不得与后文冲突\n  （如原文后文说他手是干净的，这里就不能写他满手泥）。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 不新增情节事件，只增加密度。\n2. 不新增人物动机与内心独白。\n3. 不改变原文顺序与因果。\n4. 不越 3 倍。超了删。\n5. 直接输出扩写后的完整文本，不加任何说明。\n\n## 五、质量门\n□ 字数为原文 2–3 倍（可判：字数比）\n□ 原文事实全部保留（可判：原文关键名词是否仍在）\n□ 新增内容可被感官捕捉（人判：逐句过一遍"摄像机测试"）\n□ 无心理总结与升华（可判：禁词匹配「他明白/他知道/一切都/终于」）\n□ 无与后文冲突的新增细节（人判）\n\n## 六、交付契约\n正文：扩写后的完整文本。\nASSETS：仅当新增了原文没有的实体时提交 entities；\n  若发现原文存在与设定冲突的细节，用 notes 记录（level=warn，quote 引原文，replacement 给修法）。',
        "files": [
            ('references/expansion-craft.md', EXPANSION_CRAFT),
            ('references/sensory-immersion.md', SENSORY_IMMERSION),
        ],
    },
    {
        "name": 'prose-polish',
        "title": '沉香精修·遣词造句去粗取精',
        "description": '精修已有文字的句法、动词与节奏，保留全部事实、立场与信息量。当文字啰嗦、动词疲软、句式单调需要打磨时使用；不用于删减内容与去 AI 腔（用 audit-de-aitone）、不用于扩写（用 prose-expand）、不用于重写剧情（用 prose-continue）。',
        "applies_to": 'rewrite',
        "icon": 'auto_fix_high',
        "version": "2.1.0",
        "body_md": '# 遣词造句与句式精修 (Prose Polish)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让同样的内容读起来更有力。\n判定标准：精修前后**信息清单必须完全一致**——多了是扩写，少了是删改，都不算精修。\n\n## 二、适用与不适用\n适用：句式单调、虚词过多、动词疲软（"进行了一次攻击"→"劈了一刀"）、节奏拖沓。\n不适用：要删掉整句整段 → audit-de-aitone；要加细节 → prose-expand；\n要改剧情走向 → 不是本技能能做的事，直接告知用户。\n\n## 三、执行步骤\n\nStep 1\u3000先列信息清单：把原文的**事实、动作、对白、结论**逐条摘出。\n  这份清单是精修后的验收基准，少一条即为越权。\n\nStep 2\u3000按四个维度改（只改这四类，不碰内容）：\n- **动词**：把"进行/作出/给予/有着"类虚动词换成具体动词；\n  把"走/看/说"这类通用动词换成带方式与力度的动词。\n- **虚词**：删"的、了、着、很、非常、其实、似乎、仿佛"中可删的部分，\n  一句里"的"不超过 2 个。\n- **句式**：长句拆短，连续三个同长句必须打断；倒装与短句用于重音位置。\n- **冗余**：同一意思说两遍的，留一遍（只删重复表述，不删信息）。\n\nStep 3\u3000对齐信息清单：逐条比对，任何一条丢失都要补回。\n\nStep 4\u3000交付（见第六节）。改动超过 5 处时，用 notes 记录**关键改动理由**（不必逐条）。\n\n## 四、硬性戒律\n1. 不改人物立场、不改事件结果、不改对白的信息内容。\n2. 不删整句（删句是 audit-de-aitone 的权限）。\n3. 不新增任何原文没有的细节。\n4. 不改人名、地名、专有名词的写法（须与 entities 一致）。\n5. 直接输出精修后全文，不加说明、不加批注。\n\n## 五、质量门\n□ 信息清单前后一致（可判：关键名词集合是否相同）\n□ 字数变化在 ±15% 内（可判：超过说明发生了增删）\n□ 单句"的"≤2 个（可判：正则统计）\n□ 无连续三个同长句（可判：句长序列检测）\n□ 无新增专有名词（可判：与 entities 比对）\n\n## 六、交付契约\n正文：精修后的完整文本。\nASSETS：\n- notes：level=info，记录关键改动与理由（title 写改动类型，content 写为什么改，\n  quote 引原句，replacement 给改后句，target_key="prose"）；\n  改动少于 5 处时可不提交契约块。',
        "files": [
            ('references/rewrite-dimensions.md', REWRITE_DIMENSIONS),
            ('references/ai-tone-catalog.md', AI_TONE_CATALOG),
        ],
    },
    {
        "name": 'prose-dialogue',
        "title": '机锋对白·潜台词与个性台词',
        "description": '重构场景对白，为每句台词建立字面与意图的落差，并赋予角色可辨识的语言习惯。当对白平淡、像信息播报、角色说话没区别时使用；不用于叙述性描写（用 prose-continue）、不用于扩写场景（用 prose-expand）。',
        "applies_to": 'dialogue',
        "icon": 'chat',
        "version": "2.1.0",
        "body_md": '# 机锋对白与潜台词重构 (Prose Dialogue)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让台词承担两个功能：推进博弈 + 暴露人物。\n判定标准：把任意一句台词的字面意思直接说出来，如果和原句效果一样，这句就没有潜台词。\n\n## 二、适用与不适用\n适用：对白像念稿；两个角色说话分不出谁是谁；对话没有信息差。\n不适用：整段叙述重写 → prose-continue；只要环境气氛 → prose-sensory；\n改动会牵涉剧情结果 → 先与用户确认，本技能不改剧情。\n\n## 三、执行步骤\n\nStep 1\u3000标定三人：**说话人此刻想要什么**（一句话）、**他不敢直接要什么**（一句话）、\n  **对方手里有什么筹码**。三项不清不动笔。\n\nStep 2\u3000删寒暄。所有"你好""你来了""最近怎么样""我知道了"一律删或改，\n  除非寒暄本身在演戏（表面客气实则试探）。\n\nStep 3\u3000给每句台词设落差，四选一：\n- **答非所问**：问 A 答 B，B 暴露他更在意的事。\n- **抢话截断**：一方没说完被打断，被打断的那半句才是真话。\n- **说反话**：字面是关心，语气是威胁。\n- **具体化回避**：被问到关键，转而谈一个极具体的细节（"你袖口有血"）。\n\nStep 4\u3000分配语言习惯，每个角色一套且互不重叠：\n句长（短促/绵长）、称呼方式（直呼/敬称/外号）、口头禅（≤1 个）、\n脏话或文言的使用与否。两个角色的语言习惯不得雷同。\n\nStep 5\u3000插动作。每 3–4 句台词插一个肢体微动作，动作要反驳或补充台词\n  （嘴上说"没事"，手在收桌上的刀）。\n\nStep 6\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止礼貌的问答式对白（一问一答、信息完整、情绪平稳）。\n2. 禁止用台词直接交代背景（"你知道的，三十年前那场大战……"）。\n3. 每个角色口头禅 ≤1 个，全书统一。\n4. 不改变对白推动的剧情结果。\n5. 直接输出对白正文，不加"（停顿）""（冷笑）"这类舞台提示——用动作写。\n\n## 五、质量门\n□ 无寒暄句（可判：禁词匹配「你好/你来了/最近/知道了」）\n□ 有落差的台词占比 ≥50%（人判，但可抽查 3 句）\n□ 两个主要角色的语言习惯可区分（人判：遮住名字能否分辨）\n□ 无背景交代式台词（可判：单句字数 >60 且含"你知道/当年/从前"则命中）\n□ 每 3–4 句有一个动作（可判：动作句计数）\n\n## 六、交付契约\n正文：重构后的对白正文。\nASSETS：\n- notes：level=info，记录本次为各角色确立的语言习惯（title=「角色语言习惯」，\n  content 写句长/称呼/口癖，target_key="entities"），供后续章节保持一致',
        "files": [
            ('references/subtext-dialogue-rules.md', SUBTEXT_DIALOGUE_RULES),
        ],
    },
    {
        "name": 'prose-combat',
        "title": '惊险博弈·动作拆解与招式节奏',
        "description": '撰写高张力的动作与对决场面，用空间距离、生理代价与胜负判据组织交手。当需要写打斗、追逐、对峙等动作场面时使用；不用于设计战力等级（用 novel-magic-system）、不用于写战斗之外的对白（用 prose-dialogue）。',
        "applies_to": 'combat',
        "icon": 'sports_martial_arts',
        "version": "2.1.0",
        "body_md": '# 动作博弈与交手节奏 (Prose Combat)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让读者在脑中能画出这场打斗的走位。\n判定标准：任意一次交手结束，双方距离或某一方的筹码必须发生变化。没变化 = 无效回合。\n\n## 二、适用与不适用\n适用：武戏、法术对决、追逐、近身搏杀、多人混战。\n不适用：战力体系设定 → novel-magic-system；战前谈判 → prose-dialogue；\n战斗结果需要改剧情 → 先确认，本技能不改胜负。\n\n## 三、执行步骤\n\nStep 1\u3000先定四要素（不写进正文，内部完成）：\n- **空间**：场地多大、有什么掩体、地面材质、光线。\n- **初始距离**：几丈/几步，谁在内圈谁在外圈。\n- **双方筹码**：各自还剩什么（体力、真气、兵器、援手、时间）。\n- **胜负判据**：这场怎么算赢？（杀掉/逼退/拖到援军到/抢到东西）——不写这个，打斗没有终点。\n\nStep 2\u3000把交手拆成动作单元，每次交手最多 5 个单元：\n`起手（谁先动）→ 试探（一次接触）→ 变招（一方改策略）→ 代价（一方受伤或失位）→ 收束（距离拉开或一方占位）`\n超过 5 个单元就再切一次交手，中间插一句喘息。\n\nStep 3\u3000写。按四条硬约束：\n- **空间交互**：每次移动都说明与掩体的关系（贴墙、绕过柱子、踩上碎瓦）；严禁站桩对轰。\n- **生理代价**：写肌肉震颤、骨骼受力、呼吸节奏、兵刃缺口、真气逆行；不写"他很累"。\n- **距离可见**：用具体距离词（三尺、半步、一臂），不用"很近""瞬间"。\n- **节奏极化**：进攻用 3–8 字短句连缀（三句以上），回气对峙用 30–50 字长句铺陈。\n\nStep 4\u3000收束。按 Step 1 定的胜负判据结束，不许"两人各退一步"含糊收场。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止无空间定位的招式描写（"他使出一招……"而不说人在哪）。\n2. 禁止零代价取胜——赢了必须付出体力、伤势、装备或时间。\n3. 禁止在打斗中插入大段回忆与抒情（最多一句，且必须被下一个动作打断）。\n4. 禁止战力与 novel-magic-system 的设定冲突；若必须越级，写明代价来源。\n5. 直接输出正文，不加解说。\n\n## 五、质量门\n□ 有明确的胜负判据（可判：是否出现判据句）\n□ 每次交手 ≤5 个动作单元（人判）\n□ 出现具体距离词 ≥3 处（可判：正则匹配「尺/步/臂/丈」）\n□ 有生理代价描写（可判：禁词「累/疲惫/筋疲力尽」是否出现，且是否含具体生理词）\n□ 短句与长句交替（可判：句长极差 ≥3 倍）\n□ 无设定冲突（人判：比对 entities 中 term 的 tier/effect）\n\n## 六、交付契约\n正文：打斗正文。\nASSETS：\n- timeline_events：本场战斗作为事件入档（time_label 用相对锚，event ≤30 字写"谁在哪赢/输"）\n- notes：level=info，记录本场造成的持续状态（伤势、装备损毁、暴露的能力），\n  quote 引对应原句，replacement 留空，target_key="entities"',
        "files": [
            ('references/combat-rhythm.md', COMBAT_RHYTHM),
        ],
    },
    {
        "name": 'prose-sensory',
        "title": '临场摹写·五感通感环境营造',
        "description": '用五感（重点是非视觉感官）渲染一个具体空间，让读者产生在场感。当场景缺乏实感、环境像布景板、需要在一段开头建立氛围时使用；不用于扩写情节（用 prose-expand）、不用于写对白（用 prose-dialogue）。',
        "applies_to": 'sensory',
        "icon": 'filter_drama',
        "version": "2.1.0",
        "body_md": '# 五感摹写与临场氛围 (Prose Sensory)\n\n【上下文】\n{{context}}\n\n【评审对象】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n让读者用身体进入这个空间，而不是用眼睛看一张照片。\n判定标准：一段 200 字的描写里，非视觉感官（触/嗅/听/味/体感）必须占到一半以上。\n\n## 二、适用与不适用\n适用：场景开头需要立住氛围；转场后需要快速建立空间；某段"读起来像大纲"需要长肉。\n不适用：要推进情节 → prose-continue / prose-expand；要写对话 → prose-dialogue；\n整段润色 → prose-polish。\n\n## 三、执行步骤\n\nStep 1\u3000选定**一个感官主角**。每段只突出一种非视觉感官\n  （这段以"冷"为主，那段以"腥"为主），其余作为辅。全段并列五种感官会失焦。\n\nStep 2\u3000按配比写：每 100 字至少 2 种非视觉感官，视觉描写不超过 40%。\n\nStep 3\u3000把抽象换成受力（本技能不可替代的判定）：\n- "很冷" → "铁栏杆粘住掌心，一扯带下一层皮"\n- "很臭" → "腥味压在舌根，咽口水都是咸的"\n- "很安静" → "听见自己耳膜里的血流声"\n凡是能用"很 + 形容词"改写回去的句子，都不合格。\n\nStep 4\u3000景要衬情，但不许点破。人物情绪只能通过他**注意到什么**来体现\n  （愤怒的人只看见对方的牙；恐惧的人只听见自己的呼吸）。禁止出现"仿佛在诉说他的悲伤"。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 禁止"很 + 形容词"式直给。\n2. 禁止通感套话（"夜色浓稠如墨""空气仿佛凝固""时间静止"）。\n3. 禁止比喻超过 2 个/100 字，且比喻须来自本场景可见之物。\n4. 不写人物心理活动，只写感官与动作。\n5. 直接输出正文。\n\n## 五、质量门\n□ 非视觉感官 ≥2 种/100 字（可判：感官词表统计）\n□ 视觉描写 ≤40%（可判：视觉词占比）\n□ 无"很+形容词"（可判：正则匹配）\n□ 无通感套话（可判：禁词表）\n□ 比喻 ≤2 个/100 字（可判：计数）\n\n## 六、交付契约\n正文：环境描写正文。\nASSETS：\n- notes：level=info，记录本段确立的空间特征（温度/气味/光源/声音），\n  target_key="entities"，供后续同场景复用，避免前后感官不一致',
        "files": [
            ('references/sensory-immersion.md', SENSORY_IMMERSION),
        ],
    },
    {
        "name": 'novel-forge',
        "title": '造化烘炉·全自动长篇推演总控',
        "description": '判定当前创作阶段，给出下一步唯一可执行指令并指明应调用的技能。当用户不知道下一步做什么、需要一键推进长篇流程时使用；不用于替代任何专项技能的具体产出（写正文用 prose-continue，拆卷用 novel-outline-macro）。',
        "applies_to": 'forge',
        "icon": 'all_inclusive',
        "version": "2.1.0",
        "body_md": '# 全流程推演总控 (Novel Forge)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n回答一个问题：**现在这一步该做什么，交给谁做。**\n判定标准：输出必须包含一条可以直接执行的指令，且只能有一条。给三条建议等于没给建议。\n\n## 二、适用与不适用\n适用：用户不知道下一步；需要检查当前进度卡在哪；需要把长篇流程串起来。\n不适用：任何具体的创作产出。被要求"直接写一章"时，应拒绝并给出调度指令。\n\n## 三、执行步骤\n\nStep 1\u3000读上下文，判定当前阶段，六选一：\n① 无立项 → ② 有立项无世界观 → ③ 有世界观无大纲 → ④ 有大纲无细纲 →\n⑤ 有细纲无正文 → ⑥ 有正文待审校。\n判定依据只能是**资产库里已有什么**，不是用户说自己做到哪了。\n\nStep 2\u3000做缺口诊断：列出"这一阶段必须有一项还缺失"的东西，最多 3 条，按阻塞程度排序。\n  只列真正阻塞下一步的，不列"可以更好"的。\n\nStep 3\u3000给唯一指令（本技能不可替代的动作）：\n  格式固定为：**「调用 `<skill-name>` + 动词短语 + 具体对象」**\n  例：「调用 `novel-scene`，把卷二的第 41–44 章拆成分场表」。\n  必须带具体对象（第几卷/第几章/哪个角色），不许写"完善一下大纲"。\n\nStep 4\u3000写验收标准：这一步做完，什么变了就算完成？一条，可判断。\n\nStep 5\u3000交付（见第六节）。**不写正文。**\n\n## 四、硬性戒律\n1. 不产出小说正文。任何情况下都不写情节段落。\n2. 指令只能有一条。可以给"完成后的下一条"，但不能并列两个当前动作。\n3. 不重复用户已完成的步骤。\n4. 不评价作品好坏（那是 audit-* 的职责）。\n5. 不虚构资产：诊断必须基于 {{context}} 中实际存在的内容。\n\n## 五、质量门\n□ 已判定阶段（可判：是否出现六个阶段之一）\n□ 指令唯一（可判：是否只出现一个"调用"）\n□ 指令含具体对象（可判：是否含卷/章/角色等限定词）\n□ 含一条验收标准（可判）\n□ 未产出正文（可判：输出中是否含对话引号与场景描写）\n\n## 六、交付契约\n正文：【当前阶段】【缺口 1–3 条】【唯一指令】【验收标准】\nASSETS：\n- notes：level=info，一条记录本次阶段判定与调度（title=「阶段：③ 有世界观无大纲」，\n  content 写缺口与指令，target_key=""）',
        "files": [
            ('references/creation-pipeline.md', CREATION_PIPELINE),
        ],
    },
    {
        "name": 'audit-consistency',
        "title": '剧情巡检·吃书预警与状态冲突',
        "description": '比对正文与设定档案，找出人物状态、道具状态与世界规则上的硬矛盾。当怀疑"吃书"、角色前后不一致、关键道具突然复原时使用；不用于排查时间顺序矛盾（用 audit-timeline）、不用于伏笔回收核验（用 audit-foreshadow）。',
        "applies_to": 'audit',
        "icon": 'verified_user',
        "version": "2.1.0",
        "body_md": '# 剧情状态一致性巡检 (Audit Consistency)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n找出**不能同时为真**的两处陈述。\n判定标准：两处陈述若能找到一个合理解释（如"伤好了""换了新的"），就不算矛盾，不许报。\n\n## 二、适用与不适用\n适用：人物伤势/修为/身份前后不一致；关键道具状态冲突；世界规则被违背。\n不适用：时间顺序错乱 → audit-timeline；伏笔没回收 → audit-foreshadow；\n文字风格问题 → prose-polish / audit-de-aitone。\n\n## 三、执行步骤\n\nStep 1\u3000提取正文中的状态断言，只抓三类：\n- 人物状态：伤势、修为、身份、所在地、持有物、生死。\n- 道具状态：存在与否、完好与否、归属、能力是否可用。\n- 规则遵守：是否违反 {{context}} 中已确立的法则及其代价。\n\nStep 2\u3000与档案比对。逐条查 `entities` 的 `fields_json` 与 `summary`，\n  以及 `timeline_events` 中已发生的事件。\n\nStep 3\u3000做"合理解释测试"（本技能不可替代的动作）：\n  对每一个疑似矛盾，先假设它是对的，找一个解释。\n  - 找得到解释 → 不是矛盾，最多记 `level=info` 提示"建议补一句交代"。\n  - 找不到解释 → 才是矛盾，记 `level=error`。\n  这一步是防止误报的关键，跳过它会让报告变成噪音。\n\nStep 4\u3000分级：\n- `error`：硬矛盾，必须改。\n- `warn`：可疑，需作者确认（如"伤势痊愈但未写治疗过程"）。\n- `info`：建议补充说明。\n\nStep 5\u3000交付（见第六节）。每条 `error` 必须给出 `quote`（原文原句）与 `replacement`（改法）。\n\n## 四、硬性戒律\n1. 不报时间顺序与伏笔问题——发现后只在 notes 里留一条 `info`，\n   并在 `target_key` 写 `timeline_events` 或 `foreshadows`，提示调用对应技能。\n2. 不做"合理解释测试"不许报 error。\n3. `quote` 必须是原文连续片段，不许改写、不许拼接。\n4. 不改正文，只给诊断与替换建议。\n\n## 五、质量门\n□ 每条 error 都有 quote 且能在原文 grep 到（可判：字符串匹配）\n□ 每条 error 都有 replacement（可判：非空）\n□ 无时间线/伏笔类 error（可判：title 是否含"时间/伏笔"）\n□ level 仅用 info/warn/error（可判：枚举校验）\n□ 已对每条 error 完成解释测试（人判：content 是否写了"未找到解释"）\n\n## 六、交付契约\n正文：分级诊断卡片（按 error → warn → info 排序，每条一张）\nASSETS：\n- notes：title（≤30 字问题标题）/ content（哪里错、为什么错）/ level /\n  quote（原文原句）/ replacement（改法）/\n  target_key（仅作引用标注，填 `entities` 表示问题落在该键上，**不产生该键的产出**；无则 `""`）',
        "files": [
            ('references/consistency-taxonomy.md', CONSISTENCY_TAXONOMY),
        ],
    },
    {
        "name": 'audit-foreshadow',
        "title": '伏笔核验·回收校验与断裂预警',
        "description": '核验现有伏笔在本章是否被妥善埋设、强化或回收，预警断裂与强行回收。当某章涉及伏笔回收、或怀疑"反转来得太突然"时使用；不用于规划新伏笔（用 novel-foreshadow-matrix）、不用于人物状态矛盾（用 audit-consistency）。',
        "applies_to": 'audit',
        "icon": 'find_in_page',
        "version": "2.1.0",
        "body_md": '# 伏笔回收核验 (Audit Foreshadow)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n判断本章对每条伏笔做了什么，以及做得够不够。\n判定标准：每条伏笔必须落到三种状态之一——本章埋了 / 本章强化了 / 本章回收了。\n三者都不是，就是"本章与这条伏笔无关"，不必报。\n\n## 二、适用与不适用\n适用：章节涉及回收；怀疑反转铺垫不足；需要检查长期未回收的线。\n不适用：设计新伏笔 → novel-foreshadow-matrix；人物/道具状态 → audit-consistency；\n时间顺序 → audit-timeline。\n\n## 三、执行步骤\n\nStep 1\u3000取伏笔清单（来自 `foreshadows`），只关注 `status=planted` 或 `pending` 的条目。\n\nStep 2\u3000逐条做三点核验（本技能不可替代的动作）：\n- **埋设核验**：若本章声称是首次埋设，检查线索是否为**物理事实**。\n  若写成"他隐约觉得不对劲"，判为无效埋设。\n- **强化核验**：若为强化，检查呈现方式是否与上次不同。原样重复不算强化。\n- **回收核验**：若为回收，检查两件事——\n  ① 回收所需信息是否在埋设点已给全（缺 → 强行反转）；\n  ② 回收是否在本章得到明确交代（含糊其辞 → 假回收）。\n\nStep 3\u3000断裂预警：列出超过 15 章未强化的 `planted` 伏笔，标为 `warn`（读者已遗忘）。\n\nStep 4\u3000给出状态变更：本章实际发生的变化才写入 `foreshadows`，\n  并补齐 `plant_chapter` / `payoff_chapter`（依 §1.4 C3）。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 只为本章实际涉及的伏笔产出记录，不批量改写全部伏笔状态。\n2. `status=recovered` 必须带 `payoff_chapter`。\n3. 不对"是否好看"做评价，只判"是否成立"。\n4. 不改正文。\n\n## 五、质量门\n□ 每条核验都有三点结论（可判：是否出现"埋设/强化/回收"三项）\n□ recovered 条目均带 payoff_chapter（可判）\n□ 断裂预警条目有章号差（可判：数值 ≥15）\n□ 未改动无关伏笔（可判：输出条数 ≤ 输入条数）\n□ 每处问题都有 quote（可判：grep 校验）\n\n## 六、交付契约\n正文：【本章伏笔处置表（埋/强/收）】【断裂预警】【强行回收风险】\nASSETS：\n- foreshadows：仅提交本章发生状态变化的条目，含 title / content / status /\n  plant_chapter / payoff_chapter\n- notes：level=warn 或 error，记录问题，quote 引原文，replacement 给补铺垫建议',
        "files": [
            ('references/foreshadow-verification.md', FORESHADOW_VERIFICATION),
        ],
    },
    {
        "name": 'audit-timeline',
        "title": '时序核对·因果逻辑闭环校对',
        "description": '核对章节内外的时序与因果，定位位移超速、因果倒置、时间窗口冲突与同刻两地。当需要检查"这段的时间对不对"、情节推进速度存疑时使用；不用于编排新时间线（用 novel-timeline）、不用于人物状态矛盾（用 audit-consistency）。',
        "applies_to": 'audit',
        "icon": 'update',
        "version": "2.1.0",
        "body_md": '# 时序与因果逻辑校对 (Audit Timeline)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n用可计算的比较找出时间错误。\n判定标准：每一条报出的问题，都必须能写出「A 到 B 用了多少时间、走了多少距离、这合不合理」。\n写不出这个算式，不许报。\n\n## 二、适用与不适用\n适用：长途移动后时间对不上；一件事的起因发生在结果之后；同一时刻人物出现在两地。\n不适用：建立时间底座 → novel-timeline；人物伤势与道具 → audit-consistency；\n伏笔 → audit-foreshadow。\n\n## 三、执行步骤\n\nStep 1\u3000抽锚点。把本章所有时间标记抽出来（"次日""两个时辰后""三日后""入夜"），\n  与 `timeline_events` 中的 `time_label` 合并成一条轴。\n\nStep 2\u3000做四类检查，每类给"命中/未命中"：\n- **位移超速**：距离 ÷ 时间 > 常规速度的 3 倍 → 报。\n  常规速度须按本作设定取值（步行约 40 里/日，快马约 200 里/日，飞行另计）。\n- **因果倒置**：某事件的信息来源出现在该事件之后 → 报。\n  （例：第 8 章他知道第 12 章才发生的事）\n- **时间窗口冲突**：某事件有明确时限（"三日内赶到"），但推算耗时超出 → 报。\n- **同刻两地**：同一 `time_label` 下，同一角色出现在两个地点 → 报。\n\nStep 3\u3000对每条命中，写出算式：\n  `「A（第 5 章·辰时）到 B（第 5 章·午时）共 2 时辰，路程约 300 里，需 1.5 日 → 超速」`\n  算式写不出，说明证据不足，降级为 `warn`。\n\nStep 4\u3000给修法。三选一并写明选哪个：改时间锚 / 改距离描述 / 改事件顺序。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 每条 `error` 必须带算式。无算式只能记 `warn`。\n2. 不改正文，只给建议。\n3. 时间标记不可计算的（"很久以后"），本身就是问题，记 `warn`。\n4. 不评价节奏快慢（那是 audit-pacing-rhythm 的职责）。\n\n## 五、质量门\n□ 四类检查都有结论（可判：四类关键词是否都出现）\n□ 每条 error 含算式（可判：是否含数字与单位）\n□ error 的 quote 能在原文 grep 到（可判）\n□ 每条 error 有 replacement（可判）\n□ 未越界评价节奏（可判：是否含"节奏/拖沓"）\n\n## 六、交付契约\n正文：【时间轴摘要】【四类检查结论】【问题清单（含算式）】【修法建议】\nASSETS：\n- timeline_events：若本章确立了新的事件时间，提交修正后的条目\n  （time_label / event / characters / chapter）\n- notes：level=error 或 warn，title 写类型（如「位移超速」），content 写算式与结论，\n  quote 引原文，replacement 给改法，target_key="timeline_events"',
        "files": [
            ('references/causality-audit.md', CAUSALITY_AUDIT),
        ],
    },
    {
        "name": 'audit-de-aitone',
        "title": '破除假大空·AI 油腻腔重度过滤',
        "description": '删除 AI 套话、空转抒情与段落末尾的总结升华，允许缩短篇幅。当文字有机器味、读起来"正确但无聊"时使用；不用于在保留全部内容的前提下打磨句子（用 prose-polish）、不用于扩写（用 prose-expand）。',
        "applies_to": 'de-ai-tone',
        "icon": 'cleaning_services',
        "version": "2.1.0",
        "body_md": '# AI 腔重度过滤 (Audit De-AITone)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n删掉不承载信息的句子，让密度上升。\n判定标准：删完之后，读者理解的故事与人物关系**一点没少**，但字数少了。\n\n## 二、适用与不适用\n适用：整段读起来像范文；每段结尾都有感悟；形容词密度过高。\n不适用：只想让句子更好听而不删内容 → prose-polish；\n内容不够要加细节 → prose-expand；判"好不好看" → 不是本技能，本技能只判"有没有信息"。\n\n## 三、执行步骤\n\nStep 1\u3000病灶词扫描。命中即替换或删：\n仿佛 / 宛如 / 犹如 / 不禁 / 不由自主 / 五味杂陈 / 嘴角勾起一抹笑意 /\n眼底闪过一丝复杂 / 空气骤然凝固 / 命运的齿轮 / 心中五味杂陈 / 说不出的滋味 /\n时间仿佛静止 / 这一刻，他明白了\n\nStep 2\u3000病灶句式扫描（比词表更重要，本技能不可替代的动作）：\n- **段末升华**：段落最后一句是抽象感悟（"原来，有些路只能一个人走"）→ 删。\n- **动作配抒情**：一个物理动作后紧跟一句心理注解 → 删注解，留动作。\n- **同义重复**：相邻两句说同一件事，只是换了词 → 留信息更具体的那句。\n- **形容词堆叠**：三个以上形容词修饰同一名词 → 留最不可替代的一个。\n- **虚化主语**：以"有一种……""所谓……"开头的句子 → 改具体或删。\n\nStep 3\u3000段落功能判定：逐段问"删掉这段，故事少什么？"\n  答不出 → 整段删；答得出 → 保留并只修病灶句。\n\nStep 4\u3000复检：删完后通读，检查是否出现断裂（前一句与后一句接不上）。\n  断裂处补一个最短的过渡动作，不许补解释。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 不改变剧情事实、人物关系与关键信息。\n2. 允许字数下降，通常降 10%–30%；降超过 40% 说明删过头，回退重来。\n3. 不把具体描写改成抽象概括（方向必须相反）。\n4. 直接输出洗净后的正文，不列删改清单、不解释。\n\n## 五、质量门\n□ 病灶词命中数 = 0（可判：词表匹配）\n□ 字数下降 10%–30%（可判：字数比）\n□ 无段末抽象升华（可判：段落末句是否含感悟类词）\n□ 无断裂（人判：通读检查）\n□ 关键事实未丢（人判：故事要素核对）\n\n## 六、交付契约\n正文：洗净后的完整正文。\nASSETS：\n- notes：level=info，仅记录"整段删除"的位置与理由（title=「删除段落」，\n  quote 引被删段首句，replacement 留空）；未整段删除时不提交契约块。',
        "files": [
            ('references/ai-tone-catalog.md', AI_TONE_CATALOG),
        ],
    },
    {
        "name": 'audit-pacing-rhythm',
        "title": '剧情心电图·张弛起伏节奏量化',
        "description": '按场景切分正文，为每段打张力分并画出节奏曲线，定位平段与过载段。当读者反馈"读不下去""太赶"、或需要判断一章的张弛是否合理时使用；不用于排查逻辑矛盾（用 audit-consistency / audit-timeline）、不用于提炼梗概（用 audit-synopsis-distill）。',
        "applies_to": 'analysis',
        "icon": 'analytics',
        "version": "2.1.0",
        "body_md": '# 叙事节奏量化诊断 (Audit Pacing Rhythm)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n把"这一章闷"变成一个可核对的数字与位置。\n判定标准：必须给出曲线、平段定位、以及至少一条可执行的调整建议。\n\n## 二、适用与不适用\n适用：章内节奏失衡；连续多章平淡；高潮段不够猛。\n不适用：文字风格 → prose-polish；事件先后错误 → audit-timeline；\n只想要梗概 → audit-synopsis-distill。\n\n## 三、执行步骤\n\nStep 1\u3000切段。按场景或自然段把正文切成 4–10 个单元，每单元标注大致内容（≤10 字）。\n\nStep 2\u3000四维打分（每维 1–5 分，本技能不可替代的动作）：\n| 维度 | 1 分 | 3 分 | 5 分 |\n|---|---|---|---|\n| 冲突强度 | 无对抗 | 有分歧 | 生死相搏 |\n| 信息增量 | 全在重复 | 推进一小步 | 颠覆认知 |\n| 情绪压强 | 平铺直叙 | 有起伏 | 强冲击 |\n| 进展速度 | 停滞 | 匀速 | 突进 |\n综合张力 = 四维之和 ÷ 4（保留一位小数）。\n\nStep 3\u3000画曲线并诊断：\n- **平段**：连续 2 个单元 ≤2.0 → 标"拖沓"，给删/并/加速建议。\n- **过载**：连续 2 个单元 ≥4.5 → 标"疲劳"，建议插一个喘息单元。\n- **断层**：相邻单元落差 ≥2.5 → 标"跳跃"，建议补过渡。\n\nStep 4\u3000给 1–3 条**可执行**调整（不许写"加强冲突"这类空话）：\n  格式：「第 N 段：把 X 事件提前到 Y 之前」/「删掉第 N 段的 A，合并进第 N+1 段」。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 必须切段打分，不许只给整体印象。\n2. 每条建议必须指向具体段落编号。\n3. 不评价文笔，不评价逻辑对错。\n4. 不改正文。\n\n## 五、质量门\n□ 单元数在 4–10 之间（可判：表格行数）\n□ 每单元四维分数齐全（可判：列数 = 6）\n□ 综合分 = 四维平均（可判：数值验算）\n□ 已标出平段/过载/断层（可判：关键词出现）\n□ 建议含段落编号（可判：是否含"第 N 段"）\n\n## 六、交付契约\n正文：【分段表（四维分 + 综合分）】【曲线描述】【问题段标记】【1–3 条调整建议】\nASSETS：\n- notes：level=info 或 warn，每个问题段一条（title 写"平段/过载/断层"，\n  content 写分数与建议，quote 引该段首句，replacement 写调整方式，target_key=""）',
        "files": [
            ('references/rhythm-scoring-rubric.md', RHYTHM_SCORING_RUBRIC),
            ('references/analysis-rubric.md', ANALYSIS_RUBRIC),
        ],
    },
    {
        "name": 'audit-synopsis-distill',
        "title": '卷章提要·梗概提炼与记忆回溯',
        "description": '把章节正文压缩成 100–200 字的核心剧情梗概，附章末钩子与关键要素。当需要为资产库建立章节记忆、供后续前情召回时使用；不用于缩写整卷（按章逐次调用）、不用于评价好坏（用 audit-pacing-rhythm）。',
        "applies_to": 'shorten',
        "icon": 'compress',
        "version": "2.1.0",
        "body_md": '# 章回梗概提炼 (Audit Synopsis Distill)\n\n【上下文】\n{{context}}\n\n【当前选区】\n{{selection}}\n\n【写作要求】\n{{instruction}}\n\n## 一、唯一职责\n产出一条**将来能被检索到、且不会误导下游**的章节记忆。\n判定标准：只看这条梗概，读者能准确说出"这章谁做了什么、结果如何、留下了什么"。\n\n## 二、适用与不适用\n适用：每章写完入库；补录历史章节；需要为长文建立可召回的记忆。\n不适用：评价章节质量；提炼全书大纲 → novel-outline-macro；\n要保留原文风味 → 那不该压缩，那该摘抄。\n\n## 三、执行步骤\n\nStep 1\u3000抽四要素（缺一不可）：\n- **谁**：本章有实际戏份的角色（只写推动情节的，不写路过的）。\n- **做了什么**：主动动作，不用被动句（"他被袭击"→"X 袭击了他"）。\n- **结果**：本章结束时的状态变化（得到/失去/暴露/决裂）。\n- **留下什么**：未解决的悬念或新埋的线。\n\nStep 2\u3000写 summary，100–200 字，三段式：\n`开场处境（≤40 字）→ 核心冲突与转折（≤100 字）→ 结束状态（≤60 字）`\n禁止出现：评价词（精彩/震撼）、心理描写、比喻、"本章讲述了"这类元叙述。\n\nStep 3\u3000抽 hook：本章最后留下的未闭合事实，≤40 字。无钩子填 `""`。\n\nStep 4\u3000抽 keywords：3–5 个检索词，须是具体名词（人名、地名、物件、事件），\n  不许用"成长""抉择""危机"这类抽象词。\n\nStep 5\u3000交付（见第六节）。\n\n## 四、硬性戒律\n1. 只叙事实。梗概中每一句都要能在原文找到依据。\n2. 不写评价、不写感受、不写"这章很精彩"。\n3. `characters` 只列有戏份的，且名字须与 `entities.name` 一致。\n4. summary 严格 100–200 字。\n5. 直接输出提要，不加说明。\n\n## 五、质量门\n□ summary 100–200 字（可判：字数统计）\n□ 四要素齐全（可判：是否含动作、结果、悬念）\n□ 无评价词（可判：禁词表「精彩/震撼/引人入胜/巧妙」）\n□ 无元叙述（可判：「本章/本回/讲述了」匹配）\n□ keywords 3–5 个且均为具体名词（可判：数量 + 抽象词黑名单）\n□ characters 均能在 entities 中找到（可判：名字匹配）\n\n## 六、交付契约\n正文：梗概正文（即 summary 内容），或四要素 + summary 的结构化展示。\nASSETS：\n- chapter_synopses：chapter_title / summary（100–200 字）/ hook（≤40 字）/\n  characters（string[]）/ keywords（3–5 个）\n- notes：仅当本章无法提炼（信息不足或正文残缺）时提交，level=warn 说明原因',
        "files": [
            ('references/compression-formats.md', COMPRESSION_FORMATS),
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
        has_runs = conn.execute("SELECT 1 FROM workflow_runs WHERE workflow_id = ?", (old_wfid,)).fetchone()
        if has_runs:
            # 若历史运行记录存在外键依赖，取消其内置标志并停用，保留历史追溯
            conn.execute("UPDATE workflows SET builtin = 0, enabled = 0, name = name || ' [已废弃]' WHERE id = ?", (old_wfid,))
        else:
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
