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

    created_at TEXT DEFAULT (datetime('now','localtime'))

);

CREATE TABLE IF NOT EXISTS notes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    work_id INTEGER REFERENCES works(id) ON DELETE SET NULL,

    content TEXT NOT NULL,

    tags TEXT DEFAULT '',

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
    "ai_models_cache": "",

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

你是一位长篇小说续写助手。请阅读以下上下文与当前选区，顺着既有文势自然续写，保持人物口吻、叙事节奏与文风一致，不要复述已有内容。

【上下文】
{{context}}

【当前选区】
{{selection}}

【写作要求】
{{instruction}}

续写准则：
1. 提取原文文风指纹：句长、对话密度、叙事距离、用词档次向原文靠拢。
2. 零复述：不重述已有情节，第一句直接是新的动作、对话或感官输入。
3. 有推进：这一段结束时，世界必须与开头不同——关系变了、信息变了、或处境变了。
4. 留钩子：末尾制造一个新问题，而不是把话说完。
5. 控 AI 腔：禁止排比抒情、"仿佛/不禁/五味杂陈"三连、总结式收尾。

请直接输出续写的正文，不要输出解释。""",
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
        "body_md": """---
name: default-expand
description: 为选区内容充实环境描写、人物动作、心理刻画与感官细节，适合粗纲细化或重点高潮场景铺陈时使用。
---

你是一位长篇小说扩写助手。请将选区内容扩写得更丰满：补充环境、动作、心理与感官细节，不改变情节走向，保持原有文风。

【上下文】
{{context}}

【待扩写选区】
{{selection}}

【写作要求】
{{instruction}}

扩写准则：
1. 信息只增不减：原文每一个信息点都必须在扩写稿中保留。
2. 事件不增不减：不新增人物、不新增冲突、不新增转折、不改变结局。
3. 设定不新增：不发明原文没有的规则、道具、地点、亲属关系。
4. 密度可控：加的必须是"原文没写但确实存在的"，不是形容词堆砌。
5. 节奏不塌：扩写会拖慢节奏，要给新内容安排起伏，一处铺开，一处收紧。

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
        "body_md": """---
name: default-shorten
description: 压缩精炼冗余铺陈与拖沓情节，提取核心故事动线并保留有力意象，适合节奏紧凑化与篇幅精简时使用。
---

你是一位长篇小说缩写助手。请将选区内容缩写压缩，保留关键情节信息与最有力的意象，删去冗余铺陈，语言凝练。

【上下文】
{{context}}

【待缩写选区】
{{selection}}

【写作要求】
{{instruction}}

缩写准则：
1. 零新增：不补动机、不补过渡、不补主题。原文没写的，缩写稿也不写。
2. 不改动事实与顺序：主干事件的先后与结局状态必须与原文一致。
3. 人名与称呼一致：与原文完全相同，不改写、不简化、不简称。
4. 不注水凑字数：目标字数超了就继续压，不要用抽象评论填充。
5. 保留最有力意象：优先保留揭示人物或铺垫线索的细节。

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
        "body_md": """---
name: default-rewrite
description: 修正病句错别字、替换平淡俗套表达、优化叙事节奏与文学意蕴，适合草稿定稿前精修打磨时使用。
---

你是一位长篇小说改写助手。请对选区文字进行改写：根据用户要求彻底改造原文的视角、文体、语言或内容，但保留核心事实与人物设定。

【上下文】
{{context}}

【待改写选区】
{{selection}}

【写作要求】
{{instruction}}

改写准则：
1. 改就要改彻底：换人称则全篇指代、内心描写归属、对话自称都要跟着改。
2. 残留清零：改写后任何连续 12 字以上与原文相同的片段都要处理，除非属于关键台词或专有名词。
3. 不合并任务：用户只要换人称，就不要顺手改文风。
4. 不改不该改的：用户没要求改的维度保持原样。
5. 控 AI 腔：无"仿佛/不禁/五味杂陈"、无排比抒情、无总结式升华。

请直接输出改写后的正文，不要输出解释。""",
        "files": [
            ("references/rewrite-dimensions.md", REWRITE_DIMENSIONS),
        ],
    },
    {
        "name": "default-outline",
        "title": "大纲生成·纲举目张",
        "description": "从零构思或零散想法出发，分层产出可落笔的故事大纲：一句话简介、故事核心、卷幕纲到章纲，并附伏笔回收计划。",
        "applies_to": "outline",
        "icon": "account_tree",
        "body_md": """
---
name: default-outline
description: 从零构思或零散想法出发，分层产出可落笔的故事大纲：一句话简介、故事核心、卷幕纲到章纲，并附伏笔回收计划。
---

# 小说故事大纲生成 (Novel Outline)

从零搭出一个**能直接落笔**的故事骨架。大纲的验收标准只有一条：**每一章拿到手里就知道该写什么**。

## 何时使用

- 用户只有一个题材或一句话想法，需要搭起完整故事框架。
- 用户已有主角、设定、几个片段，但串不成线，需要补全结构。
- 用户要写长篇，需要先出卷纲与章纲规划。
- 用户说"想写个 XX 题材的故事，但不知道怎么写"。

**不适用**：

| 情况 | 归属 |
|---|---|
| 已有正文，要倒推出大纲 / 梗概 | novel-condensation |
| 已有正文，要往后写新情节 | novel-continuation |
| 已有正文，要查设定矛盾 | novel-consistency-check |
| 已有片段，只要把某段写细 | novel-expansion |

**与 novel-condensation 的关键区分**：同样是"分章大纲"，**有原文可用是倒推（condensation），无原文是原创（本技能）**。判断起点是"素材从哪来"，不是措辞。

## 触发词

**中文**：故事大纲、大纲、写个大纲、分章大纲、章节大纲、细纲、卷纲、剧情框架、故事框架、整体结构、三幕结构、起承转合、英雄之旅、帮我构思一个故事、帮我编个故事、给我个故事点子、这个题材怎么写、我有个想法想写成小说、人物小传、世界观设定、故事线、主线支线、结局怎么设计。

**英文**：outline my novel, story outline, plot structure, chapter breakdown, three-act structure, brainstorm a story idea, help me plot this.

**间接信号**：用户只给了"题材 + 一句话"，问"接下来怎么写"；用户说"想写一个关于……的故事"；用户列了三五个人物或场景但要求"帮我串起来"。

**易混淆需转出的**：
- 用户附了成文并要求"整理成大纲" → novel-condensation。
- 用户附了成文并要求"检查有没有矛盾" → novel-consistency-check。
- 用户只说"帮我改写我写的大纲" → novel-rewriting。

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

按层级输出，用 Markdown 标题分节：

```
### 一句话简介
<logline>

### 故事核心
<3–5 句>

### 卷纲
卷一卷名 / 本卷目标 / 主要事件 / 卷末状态

### 章纲
第 1 章 …
（逐章）

### 伏笔回收计划
| 伏笔 | 埋设 | 回收 |
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
        "body_md": """
---
name: default-audit
description: 建立设定台账并交叉比对全书正文，输出带原文引用的矛盾清单，按致命、明显、轻微分级并附修改方向。
---

# 小说故事设定检查 (Consistency Check)

审自己的稿子。这类任务的价值全在**证据**上——"感觉有点乱"没有用，"第 3 章他左手中枪，第 9 章左手用来写字"才有用。

## 何时使用

- 用户写完一段或多章，怀疑有设定矛盾，要求排查。
- 用户要投稿前自查连续性。
- 用户写了很久，回来问"前面埋的伏笔是不是忘了收"。
- 用户提供多份文件（不同章节），要求做整体一致性检查。

**不适用**：

| 情况 | 归属 |
|---|---|
| 逐句润色、换风格 | novel-rewriting |
| 内容压短、写梗概 | novel-condensation |
| 把某段写细 | novel-expansion |
| 从零搭框架 | novel-outline |
| 纯校对（错别字、标点） | 普通编辑任务 |

**与续写技能自带自检的区别**：续写技能在生成后做的是一致性自检，服务于"别写错"；本技能是独立任务，服务的是"找出已经写错的地方"并给出可执行的问题清单。

## 触发词

**中文**：设定检查、查设定、设定核对、检查设定、有没有矛盾、有没有冲突、找出矛盾、有没有 bug、找 bug、找漏洞、逻辑漏洞、前后不一致、前后对不上、时间线、时间线检查、人物崩了、人设崩了、人物漂移、是不是吃书了、吃书检查、伏笔检查、伏笔有没有回收、遗漏了什么、审稿、帮我审一下、自查、连续性检查、世界观自洽吗、战力体系崩了吗。

**英文**：consistency check, find plot holes, continuity errors, does this contradict itself, timeline check, check for inconsistencies, beta read for logic.

**间接信号**：用户贴出多章内容并问"这样写行不行""有没有问题"；用户说"写到第 20 章感觉和前面冲突了"。

## 执行流程

S0 → S5。**S1 建台账是核心工作量**，跳过它只能凭印象挑毛病，那是无效检查。

### S0 载入与规模评估

1. 读入全部材料（文件路径用 Read；.docx / .pdf 走 Office 解析链路）。多章多文件时全部读入。
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
- 用户要求顺手修改时，按问题类型分派：改文风 → novel-rewriting；删减 → novel-condensation；补写场景 → novel-expansion；补新情节 → novel-continuation。

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
        "body_md": """
---
name: default-analysis
description: 对作品做有证据、不虚高的十维体检：逐维打分附原文引用，输出总分、强弱项、短板与按投入产出比排序的修改建议，只出报告不改写。
---

# 小说故事分析 (Story Analysis)

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
| 只在找矛盾 / 前后不一致 / bug / 时间线问题 | novel-consistency-check |
| 要压短、写梗概、写简介 | novel-condensation |
| 要动手改：换人称、换风格、改成剧本 | novel-rewriting |
| 目标明确是"去掉 AI 腔"、要改后文本 | de-ai-tone |
| 只有想法没有正文，要从零搭框架 | novel-outline |
| 把某段写得再细一点 | novel-expansion |
| 只想让它接着往下写 | novel-continuation |

**与设定检查的核心区别**（最容易搞混的一对）：

| 用户的话 | 归属 | 判定依据 |
|---|---|---|
| "有没有矛盾 / 前后对不上 / 时间线对不对 / 找找 bug" | novel-consistency-check | 句子**指认了内部冲突** |
| "写得怎么样 / 能打几分 / 好在哪差在哪 / 哪里能提升" | **本技能** | 句子要求**评价优劣或量化** |
| "帮我看看这篇小说"（笼统） | **本技能** | 覆盖更广；若发现硬矛盾，在报告里标注并指向设定检查 |

两者是上下层关系：设定检查查的是"事实自洽"（技术层），本技能评的是"作品优劣"（价值层）。一篇稿子可以零矛盾但依然平庸，也可以很有魅力但有 bug。**本技能不替代设定检查**——它发现硬矛盾时只列出并建议单独做一次设定检查，不展开修法。

## 触发词

**中文**：分析、分析一下、帮我分析、故事分析、分析这个故事、评价、评价一下、帮我评一下、评一评、点评、打分、评分、打个分、给个分、评个分、能打几分、这个故事怎么样、写得怎么样、这小说好不好、好在哪、差在哪、优点缺点、有什么问题、哪里不足、值得写下去吗、值不值得继续、有没有前景、拆解一下、故事诊断、写个书评、全方位分析、深度分析、帮我看看这篇写得如何。

**英文**：analyze my story, critique this, rate this story, give feedback, story assessment, what works and what doesn't, review my novel, how good is this。

**间接信号**：用户贴出正文并问"你觉得呢""这样能发吗""我该往哪个方向改"；用户贴出正文后沉默地问"？"。

**明确排除**：用户贴出正文**没有提任何评价要求**时，默认按续写处理（见 novel-continuation），不要自作主张打分——打分是有攻击性的行为，没被要求就不做。

## 执行流程

S0 → S6。**S0 的参照系声明是硬门槛**，跳过它打分等于说废话。

### S0 锁定分析对象与参照系

1. 读入全部材料（多个文件全部读入；.docx / .pdf 走 Office 解析）。
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
4. **只评不改。** 本技能产出报告，不改写原文。用户要动手改时按类型转出（改文风 → novel-rewriting；去 AI 腔 → de-ai-tone；删减 → novel-condensation；补写 → novel-expansion）。
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
        "description": "诊断并移除六类 AI 痕迹，以提升信息密度与打散对称结构为核心手法，适用于任何文体的去机器味改写润色。",
        "applies_to": "rewrite",
        "icon": "auto_stories",
        "body_md": """
---
name: de-ai-tone
description: 诊断并移除六类 AI 痕迹，以提升信息密度与打散对称结构为核心手法，适用于任何文体的去机器味改写润色。
---

# 文章去 AI 味 (De-AI Tone)

把"像 AI 写的"改成"像人写的"。先说清一件事，它决定了后面所有手法的方向：

> **AI 味的本质不是用词问题，是信息密度低 + 结构过于对称。**
> 只把"赋能"换成"帮忙"、把"仿佛"删掉，改完还是 AI 味——因为骨架没动。

## 何时使用

- 用户说某段文字"太像 AI 写的""一眼假""机器味重"。
- 用户要把 AI 生成的初稿改成自己能用、能交的稿子。
- 用户觉得文字"太工整""太套路""空话太多"，但说不清哪里有问题。

**不适用**：

| 情况 | 归属 |
|---|---|
| 泛泛要求换文风（"更冷一些""像汪曾祺"） | novel-rewriting |
| 要求内容变短 | novel-condensation |
| 要求把某段写细 | novel-expansion |
| 只改错别字、标点 | 普通编辑任务 |
| 只要一份文风评价与打分，不要改后文本 | novel-analysis |

**与改写技能的分工**：目标明确指向"去 AI 痕迹 / 更像人写的" → 本技能；目标是一个具体的风格名或方向 → novel-rewriting。两者同时存在时，先用本技能去味，再按需做风格迁移。

## 触发词

**中文**：去AI味、去AI腔、去AI感、去 AI 味、去 ai 味、去掉 AI 味、去掉AI腔、AI 腔太重、AI 味道太重、AI 痕迹、一眼 AI、一看就是 AI、AI 生成的感觉、机器味、机器翻译腔、模板味、套路味、降 AI 率、降AI感、降低 AI 感、更像人写的、加点人味、有人味一点、自然一点、口语一点、别那么工整、别那么书面、太模板化了、空话太多、套话太多、车轱辘话、别那么像范文、帮我改得像自己写的。

**英文**：remove AI tone, de-AI, humanize this, make it sound human, less robotic, less like ChatGPT wrote it, remove AI clichés, make it sound natural.

**间接信号**：用户贴出一段文字并说"这是我用 AI 写的，帮我改改"；用户说"读起来很流畅但就是假"；用户抱怨"每段都差不多长"。

## 执行流程

S0 → S5。**S1 先诊断再动手**——不诊断直接改，会只改表层词汇。

### S0 载入并判定文体

1. 读入文本（文件路径用 Read；.docx / .pdf 走 Office 解析链路）。
2. **判定文体与使用场景**。这直接决定"人味"该长什么样：

| 文体 | 去味目标 | 不该做的 |
|---|---|---|
| **小说 / 散文** | 增加具体细节、感知与不对称 | 不要加解释性旁白 |
| **公众号 / 自媒体** | 加真实经历、具体数字、个人判断 | 不要为了口语而拆散逻辑 |
| **论文 / 学术** | 删套话与空转，提高论断密度 | **不要加口语和跑题**——学术写作本就要求工整 |
| **报告 / 公文** | 换成具体数据、时间、责任主体 | 不要加第一人称情绪 |
| **邮件 / 商务** | 缩短、直说诉求 | 不要过度口语 |

**关键提醒**：去 AI 味 ≠ 加口语。学术与公文类文本的 AI 味来自"说了一堆正确但无信息量的话"，解药是**提高信息密度**，不是加"说真的""其实吧"。

### S1 六类 AI 痕迹诊断

逐类扫描，记录命中位置。详见 `references/ai-tone-catalog.md`。

| # | 类型 | 症状 | 一眼识别的标记 |
|---|---|---|---|
| 1 | **结构痕迹** | 段落等长、三段式强行对称、总-分-总套模板 | 每段都是 3–4 行；必有结尾总结段 |
| 2 | **词汇痕迹** | 抽象套话密集 | 赋能、闭环、抓手、底层逻辑、维度、生态、价值链、不可否认、值得注意的是、综上所述、深度、极大、显著 |
| 3 | **句式痕迹** | 排比与对偶过密 | "不仅…而且…""不是…而是…""既…又…"、三句同结构连用、破折号后跟解释 |
| 4 | **抒情痕迹** | 情绪词与陈词滥调 | 仿佛、宛如、不禁、五味杂陈、心中泛起涟漪、久久不能平静、令人深思、引发共鸣、值得玩味 |
| 5 | **收尾痕迹** | 每个段落或全文末尾升华 | "总而言之""让我们…""这一刻，他终于明白了""具有重要意义" |
| 6 | **空转痕迹** | **最重要的一类** | 句子语法正确、读着通顺，但删掉后信息量零损失 |

**空转痕迹是 AI 味的真正来源**，也是最难改的一类。识别方法：

> 逐句问：这句话删掉，读者会少知道什么？
> 答"什么都不少" → 空转，删或换成具体内容。

典型空转形态：
- "随着社会的发展，人们对 X 的关注日益增加。"（没有具体时间、具体数据、具体变化）
- "这不仅仅是一个关于 Y 的故事，更是一次对 Z 的探讨。"
- "他在这一过程中不断成长，逐渐明白了许多道理。"
- "面对挑战，我们需要保持理性，同时也要兼顾情感。"

### S2 判定改写强度

| 强度 | 动作 | 适用 |
|---|---|---|
| **轻改** | 只做词句替换与删除 | 原文信息量本身够，只是用词套话 |
| **中改**（默认） | 重组句式与段落结构，打散对称 | 结构痕迹与句式痕迹明显 |
| **深改** | 只保留信息点，重新组织 | 空转严重、整篇需要重写 |

**先说清一件事**：深改会改变原文的措辞与结构，若用户在意"保留我的原话"，改用轻改或中改。

### S3 执行去味

**核心是加，不只是减。** 许多人只会删，删完文本变得干瘪，还是假。五条手法：

#### 手法 1：把抽象换成具体（最重要）

| 原文 | 改后 |
|---|---|
| 这家公司近年来发展迅速 | 这家公司三年里员工从 40 人涨到 300 人 |
| 他感到非常疲惫 | 他连着两天没合眼，端杯子的时候手在抖 |
| 随着行业的发展，竞争日益激烈 | 去年这条街上有 7 家同行，今年剩下 3 家 |
| 该方案具有显著优势 | 这个方案把审批从 11 天压到 2 天 |

**具体化的四个来源**：数字、时间、人名与地名、可观察的动作。

#### 手法 2：打散对称

AI 最爱写对称。人要写不对称。

- 排比三连 → 留两句，第三句换个说法或直接删
- 段落等长 → 故意让某段只有一句话
- "首先/其次/最后" → 改掉顺序词，让内容自己排队
- 每段都 3–4 行 → 插一个一行的短段

#### 手法 3：删掉收尾升华

每个自然段末尾的总结句、全文末尾的升华段，**八成可以直接删**。删完读一遍，通常更利落。

#### 手法 4：加入人的痕迹

人类写作的特征，AI 缺的正是这些：

| 痕迹 | 例 |
|---|---|
| **犹豫与不确定** | "我到现在也不确定当时该不该走。" |
| **跑题与插话** | 讲到一半想起另一件事，插一句再回来 |
| **未完成** | 有些疑问不给答案。人写东西不总是闭环 |
| **个人立场** | "我不喜欢这个说法。"——而不是"这个说法值得商榷" |
| **不完美的比喻** | 比喻可以有偏差，不必精准到位 |
| **口语节律** | 短句、断句、一句独立成段 |

**文体适配**：学术与公文不加前四项，只做"删套话 + 换具体"。小说与自媒体可以全加。

#### 手法 5：减连接词

AI 靠连接词粘句子（因此、然而、此外、与此同时、正因如此）。人靠语序和省略。**删掉一半连接词，语意通常仍然清楚，而且更利落。**

### S4 自检与前后对照

- [ ] **信息密度上升**：改后字数若减少，信息点不能减少。
- [ ] **空转清零**：没有语法正确但零信息量的句子。
- [ ] **对称打散**：无三句以上的同结构排比；段落长度不等。
- [ ] **升华清零**：无段落末尾的总结句、无全文升华段。
- [ ] **黑名单清扫**：抒情词与套话词汇已清理（对照 `references/ai-tone-catalog.md`）。
- [ ] **文体适配**：口语化程度符合文体要求（学术/公文不得口语化）。
- [ ] **不新增事实**：具体化时用的数字与细节必须来自原文或用户提供，**不可以编造**。这一点是硬红线。
- [ ] **原意未变**：改后与原文表达同一件事，只是说得更像人。
- [ ] **合规**：不涉及露骨色情、暴力教唆、违法违规与政治敏感内容。

**关于"不新增事实"的处理方式**：若原文是抽象的"发展迅速"，不能编一个具体数字。正确做法是**在改稿中标出占位符并提示用户填写**：

```
这家公司三年里<请填具体增长数据>
```

或用不含数字的具体化：`这家公司从一条街的小店面做到了整层写字楼`——只使用原文可推得的信息。

### S5 交付

```
### 改后

<改好的全文，可直接复制>

---

### 主要问题
<3–5 条，指出最严重的痕迹类型与位置>

### 改动说明
| 原句 | 改后 | 手法 |
|---|---|---|
| 《随着社会发展…》 | … | 抽象→具体 |

### 需要你补充的
<若有占位符，列出；没有则省略这一节>
```

**篇幅控制**：改动说明只列最典型的 3–5 处，不要逐句罗列——那会让用户读不完。

用户要求文件时默认命名 `去AI味-<原标题或日期>.md`，写完呈现给用户。

## 硬性规则

1. **不编造事实。** 具体化只能使用原文已有的信息，缺数据就用占位符请用户补。这是本技能最重要的红线。
2. **不只是删。** 只删不补会把文本改干瘪，信息密度才是解药。
3. **按文体适配。** 学术与公文不口语化，只提密度。
4. **不用错别字冒充人味。** 不故意写错字、不加无意义的语气词。
5. **不承诺过检测。** 明确告知：AI 检测工具本身不可靠，本技能的目标是读起来自然，不保证任何工具的判定结果。
6. **学术诚信提示**：若用户说明用于学术提交，提示其遵守所在机构关于 AI 使用的规定。
7. **合规红线**：涉及未成年人性内容、教唆犯罪、政治敏感议题时，拒绝并按可用方向改写请求。

## 资源文件

- `references/ai-tone-catalog.md` —— 六类痕迹的完整词表与句式清单、空转句识别法、按文体区分的改法对照、常见误改（改过头反而更假）。S1、S3 必读。
""",
        "files": [
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
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


def word_count(text: str) -> int:

    """字数口径：去除空白字符后的字符数（含标点，含中英文）。"""

    return len("".join(text.split()))
