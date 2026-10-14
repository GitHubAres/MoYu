# 模块收录逻辑 vs Skill 输出逻辑 · 对比分析

> 目的：把「墨语核心功能模块的收录逻辑（资产如何被识别并落库）」与「对应 skill 被契约指令产出的输出逻辑」逐模块对齐，找出二者之间的错配（declared ≠ ingested）。
> 分析基于当前工作树代码（v2.2.0 契约适配式重构之后）。涉及文件：`app/services/output_normalizer.py`、`app/workflow_assets.py`、`app/services/plot_service.py`、`app/features.py`、`app/db.py`(BUILTIN_SKILLS)、`static/js/pages/`。

---

## 1. 收录链路总览（资产如何「被墨语识别」）

```
skill / 工作流步骤 的 AI 产出文本
        │
        ▼
extract_assets_block(text)            # 仅解析 <!-- MOYU:ASSETS {...} MOYU:ASSETS --> 契约块
        │  （output_normalizer.py:134）
        ▼
canonicalize_assets(raw)              # 归一到 8 键权威 schema、枚举边界
        │  （output_normalizer.py:326）
        ▼
sync_assets_to_database(db, work_id, body, ...)   # workflow_assets.py:835
        ├─ work_info        → UPDATE works（作品设定）
        ├─ entities[]       → entities 表（category 枚举归一）
        ├─ relations[]      → entity_relations（缺失端点自动建 entity 桩）
        ├─ outline_nodes[] / timeline_events[] / foreshadows[]
        │                   → 委托 plot_service.batch_sync_triad_assets（workflow_assets.py:997）
        ├─ chapter_synopses[] → 匹配已有 outline_nodes.title 后写 synopsis
        └─ notes[]          → 以 category='term' 写入 entities（标签「世界观」）
```

**关键事实**：`extract_assets_block` 的 `valid_keys` 只有 7 个 list 键（output_normalizer.py:162），
**不含 `work_info`**。这是后续 M1 的根因。

---

## 2. 逐模块「收录能力 × Skill 输出逻辑」对照

| 产物键 | 收录去向（模块） | 收录器的硬约束 | 声明该键的 skill | 是否匹配 |
|---|---|---|---|---|
| `work_info` | works（作品设定） | 仅启发式兜底，契约块被丢弃 | default-outline / novel-premise / novel-forge / default-analysis | ❌ M1 |
| `entities` | 设定库 entities | category 归一枚举（character/place/faction/item/term/custom） | 多数 | ✅ |
| `relations` | 关系图谱 entity_relations | 需 `from_name`/`to_name`/`label`；子字段 schema 未声明 | novel-cast / novel-world / novel-forge | ⚠️ M4/M6 |
| `outline_nodes` | 大纲树 outline_nodes | `parent_title` 不被解析，仅认 `parent_id` | default-outline / novel-scene / novel-forge | ⚠️ M2 |
| `timeline_events` | 时间线 timeline_events | 需 `event`+`time_label`；子字段 schema 未声明 | default-continue / default-expand / novel-scene / novel-world / novel-forge | ⚠️ M6 |
| `foreshadows` | 伏笔看板 foreshadows | status 归一枚举（planted/pending/recovered） | default-continue / default-expand / default-outline / novel-scene / novel-forge | ✅(弱) |
| `chapter_synopses` | 大纲节点 synopsis | **必须 match 已有 outline_nodes.title**，否则整条 reject | novel-forge（实际几乎不产出） | ❌ M5 |
| `notes` | entities（term 术语） | title 非套话；实际落「世界观设定」库 | default-shorten / default-rewrite / default-audit / default-analysis / de-ai-tone / novel-world / novel-premise | ⚠️ M3 |

---

## 3. 六处错配详解（按严重度）

### M1 · `work_info` 被收录器静默丢弃（P0，最严重）
- **契约输出逻辑**：`build_contract_clause` 明确指令 4 个技能在文末产出 `"work_info": {"title": "", "genre": "", "intro": ""}`（output_normalizer.py:306、316）。
- **收录逻辑**：`extract_assets_block` 的 `valid_keys` 不含 `work_info`（:162），解析出的字典直接没有该键；`canonicalize_assets` 收到后只用默认空对象（:333）；`extract_structured_assets_from_text` 仅在「契约块存在」分支用**启发式**兜底补 title/genre/intro（workflow_assets.py:762-767），而启发式从正文散文里抽设定，几乎不可靠。
- **结果**：这 4 个技能的「作品设定」几乎无法经契约块入库，与契约承诺完全脱节。

### M2 · `outline_node.parent_title` 不被解析（P1）
- **契约输出逻辑**：`build_contract_clause` 指令 `outline_node.is_volume=true 表示分卷；parent_title 填所属分卷名`（output_normalizer.py:320）——即用**字符串卷名**表达卷-章从属。
- **收录逻辑**：`batch_sync_triad_assets` 只读取 `n.get("parent_id")`（plot_service.py:73），整个收录链路（extract / canonicalize / sync）**都不解析 `parent_title`**。
- **结果**：层级挂载只能依赖「按出现顺序 + 遇到 `is_volume:true` 时更新 `current_parent_id`」的脆弱顺序推断（plot_service.py:97-98）。若 LLM 不严格先卷后章、或分多批输出，章节会挂错父节点甚至挂到根。

### M3 · `notes` 语义错配：标「笔记」实存「术语」（P2）
- **契约/前端输出逻辑**：`skills.js` 的 `ASSET_KEY_META` 把 `notes` 标为「笔记」（skills.js:90）。
- **收录逻辑**：`sync_assets_to_database` 把每条 note 以 `category='term'` 写入 `entities`，标签「世界观」（workflow_assets.py:1066）；工作流预览 UI 直接标注为「世界观设定 (N条) · 将归入万象谱「术语」」（workflows.js:1049）。
- **结果**：系统**没有独立的「笔记」模块**消费该键。契约承诺「反哺笔记」，实际进入「世界观设定/术语」库，标签自相矛盾。

### M4 · `novel-cast` 关系/人物：正文价值无法被结构化收录（P1）
- **skill body 输出逻辑**：body 明确要求产出「标准 Markdown 冲突关系矩阵表」（db.py:1919）与富人物卡——含 **身份 / 表面欲望 / 深层需求 / 创伤 / 阻力 / 弧光 / 易变外貌项 / 说话方式**（db.py:1904-1916）。
- **契约/收录逻辑**：契约仅捕获 `relations:[{from_name,to_name,label}]` 与薄 `entities:[{name,category,content}]`；通用 clause **未要求 LLM 填 `entity.fields_json`**。
- **结果**：人物卡中「欲望/创伤/弧光/说话方式」等核心字段在契约里无对应位置，关系「争什么」只在 Markdown 矩阵里而 `relations` 只收一个 label。大量分析价值留在 prose，收录丢字段。

### M5 · `novel-forge` 合约键与自身产出脱钩（P2）
- **skill body 输出逻辑**：body 自述「本技能只编排与验收，具体动作一律路由」（db.py:2305），自身产出的是阶段汇报文本，且把「梗概/简介/腰封」路由给 `default-shorten`（db.py:2258）。
- **契约输出逻辑**：`SKILL_ASSET_CONTRACTS["novel-forge"]` 却声明了 `chapter_synopses` 与 `work_info`（output_normalizer.py:279-280）。
- **结果**：路由型技能几乎不会以 MOYU:ASSETS 结构化块产出逐章梗概或作品设定，两键形同虚设；前端「反哺：梗概 · 作品设定」标签误导用户。

### M6 · 通用契约 clause 未给出 relations/timeline 的子字段 schema（P2）
- **契约输出逻辑**：`build_contract_clause` 的字段规则只列了 `entity.category`、`foreshadow.status`、`outline_node.is_volume/parent_title`、以及 title/name/event 长度（output_normalizer.py:317-322）。
- **收录逻辑**：`sync_assets_to_database` 严格按 `rel.from_name/to_name/label`、`ev.event/time_label/characters`、`fs.title/content/status` 读取（workflow_assets.py:953-1002）。
- **结果**：模型若用别的子字段命名（如 `from/to/type`、`character` 单数、`content` 写在错字段），整键落空且无任何提示。relations/timeline 的高识别率依赖模型「恰好猜对」字段名。

---

## 4. 结论

- **收录器对 7 个 list 键的解析是健全的**（entities/relations/timeline/foreshadow/outline/notes/chapter_synopses 都能进库），真正的问题集中在 **(a) `work_info` 被解析器漏掉、(b) outline 层级用 `parent_title` 而非 `parent_id`、(c) 契约 clause 字段级 schema 不完整、(d) 个别技能声明了自身不产出的键、以及 (e) notes 语义标签与实际落库不一致**。
- 这 6 处错配中，**M1（work_info 丢弃）是唯一会令「契约承诺的内容整块丢失」的 P0 问题**，应优先修；其余为字段级/语义级损耗，影响的是「收录质量」而非「能否收录」。

---

## 5. 修复建议（按优先级）

1. **P0 — 补 `work_info` 解析**：在 `extract_assets_block` 的 `valid_keys` 增加 `"work_info"`，并在 `canonicalize_assets` / `extract_structured_assets_from_text` 把 `work_info` 当对象与 list 键同等解析（而非启发式兜底）。改动小、收益最大。
2. **P1 — 解析 `parent_title`**：在 `batch_sync_triad_assets` 增加 `parent_title → parent_id` 解析（参考 `features.py:677-695` 的 `parent_map` 做法，按 work_id 查重同名卷节点），或放到 `canonicalize_assets` 阶段（需传入 work_id）。
3. **P1 — 富化 `novel-cast` 契约**：在 clause 中显式要求 `entity.fields_json` 结构（欲望/创伤/弧光…），或至少在 body 注明「矩阵表仅供人读，结构化入库以契约块为准」，避免用户误以为关系冲突点已入库。
4. **P2 — 完善子字段 schema**：在 `build_contract_clause` 为 `relations`/`timeline_events`/`foreshadows` 各给出最小字段模板（如 `"relations": [{"from_name":"","to_name":"","label":""}]`），提升跨模型识别率。
5. **P2 — 校正 `novel-forge` 合约键**：去掉 `chapter_synopses`/`work_info`（或注明「仅路由到子技能时由其产出，本技能不直接产」），使前端「反哺」标签诚实。
6. **P2 — 统一 `notes` 语义**：要么在 UI 与契约里统一叫「世界观设定/术语」，要么真正建独立笔记模块消费该键。
7. **测试加固**：在 `tests/test_skill_contract_adapter.py` 增加对账测试——「合约声明键 === 收录器真实能落库键」，覆盖 `work_info` 解析与 `chapter_synopses` 的 reject/ingest 断言。
