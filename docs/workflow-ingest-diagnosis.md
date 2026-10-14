# 写作工作流 → 各模块收录问题诊断（万象谱/伏笔看板/关系图谱/时间线/大纲）

> 结论先行：**问题主要来自「中枢收录分发逻辑」（设计 + 代码 bug），skill/工作流输出不规范是次要放大器。**
> 最关键的两点：① 工作流产出**不会自动归档**，必须人工点「收录」；② 启发式分类器的分类词汇（`location`/`lore`）与归一函数（`normalize_category`）对不上，导致**地点/场景类实体被错存为「术语」**。

---

## 1. 数据链路全景（先说清数据怎么流）

```
工作流步骤执行
  workflow_engine.py: finish_task() → workflow_run_steps.output = 文本   ← 仅存文本，不入库
        │
        ▼  （人工操作）前端「收录/全部收录」按钮
  POST /workflows/runs/{id}/steps/{seq}/sync-assets   (api/workflows.py:425)
        │
        ├─ 前端先 GET /summary-assets 或 /extracted-assets
        │     → extract_structured_assets_from_text(output)   (workflow_assets.py:697)
        │         ├─ 有 MOYU:ASSETS 契约块 → 契约路径（分类准确，显式字段）
        │         └─ 无块 → _heuristic_extract_assets() 关键词启发式（粗，易错）
        │
        ▼
  sync_assets_to_database(db, work_id, body)   (workflow_assets.py:843)
        ├─ entities        → entities 表        （万相谱 / 设定库）
        ├─ relations       → entity_relations   （关系图谱）
        ├─ outline/timeline/foreshadow → plot_service.batch_sync_triad_assets （大纲/时间线/伏笔看板）
        ├─ chapter_synopses→ outline_nodes.synopsis
        ├─ notes           → entities 表 category='term'（★没有独立笔记模块）
        └─ work_info       → works 表
```

**关键事实**：`workflow_engine.py` 跑完步骤只是把文本写进 `workflow_run_steps.output`（:338/:347），**全程没有任何自动调用 `sync_assets_to_database`**。归档完全依赖前端 `POST /sync-assets`（workflows.js:1117/1288）的人工触发。

---

## 2. 中枢收录分发逻辑的问题（主因）

### 2.1 不自动归档（最核心，造成「有输出没进模块」）
- 工作流结束后，产出只是聊天文本。用户若**没点「收录」**，万象谱/伏笔看板等模块一条都不会新增。
- 这与「工作流会自动沉淀资产」的直觉相悖，是「工作流有输出类似内容但没归档」的**第一来源**。
- 代码证据：`workflow_engine.py` 全程无 `sync_assets_to_database` 调用；仅 `api/workflows.py` 暴露手动端点。

### 2.2 分类词汇不一致（真实 bug，造成「分类不准确」）★
- 启发式抽取器 `category_map`（workflow_assets.py:108-114）把实体分为：
  `character / item / location / faction / lore`
- 但落库归一函数 `normalize_category`（:826-840）的合法表是：
  `character / place / faction / item / term / custom`，别名表也只有 `地点→place`、`设定→term` 等。
- `location` 既不在合法表、也不在别名表 → **一律回落为 `term`（术语）**。
- 后果：**所有「地点/场景/世界/秘境/城池」类实体被错存进万相谱的「术语/设定」分类**。这正是用户感知的「分类不准确」。
- 同理 `lore`（法则/世界观）虽也回落 `term`，但语义上尚可接受；真正的硬伤是 `location→term`。

### 2.3 双归一器词汇表不同步（设计债）
- `output_normalizer.canonicalize_assets`（契约路径用）与 `workflow_assets.normalize_category`（sync 路径用）各有一套枚举/别名表，互不同步。
- 契约块里若 LLM 误写 `location`（而非约定的 `place`），`canonicalize_assets` 的别名表（人物/地点/势力/道具/术语）同样不认 `location` → 回落 `term`。两套归一器都没兜住 `location`。

### 2.4 过度拒绝导致「该收的没收」（sanitize_asset_item）
- 位于 `output_normalizer.py:181-249`，以下情况整条丢弃：
  - 标题 **> 30 字** 直接拒（:221-222）——小说卷名、长伏笔标题、带修饰的大纲名极易超 30 字 → 静默丢失 → 「没归档」。
  - 标题命中套话前缀（「好的」「以下是」等）拒。
  - 标题属于模块关键词（「世界观设定」「伏笔暗线」「故事大纲」等）拒（:246）。
- 这些被拒条目只进 `rejected_items`，前端若未展示或用户未留意，就等于「丢了」。

### 2.5 notes 没有独立模块（语义错配）
- 契约键 `notes` 在 `sync_assets_to_database` 中（:1048-1077）**落库为 `entities` 表 `category='term'`、`tags='世界观'`**。
- 即：审校批注、术语、设定补充说明、用户笔记全被混进万相谱「术语」一栏，没有真正的「笔记/便签」看板。
- 前端 `notes` 反哺标签（skills.js）也据此误导为「笔记」，但实际无独立模块承载。

### 2.6 关系端点未知时一律建成「人物」
- `sync_assets_to_database` 关系同步（:960-999）：若 `from_name`/`to_name` 在实体库不存在，**无论实际是势力/地点/物件，都 `INSERT ... 'character'`**（:976/984）。
- 后果：势力×势力、地点×地点 的关系会凭空造出两个「人物」实体，污染万相谱与关系图谱。

---

## 3. skill / 工作流输出不规范（次因 / 放大器）

### 3.1 契约条款并非覆盖所有步骤
- `workflow_engine.py:323` 只在 `required_keys` 非空时才注入 `build_contract_clause`。
- 触发条件：步骤有 `skill_id`（取 `SKILL_ASSET_CONTRACTS` 声明键），或标题命中 `ledger_kws/outline_kws/synopsis_kws`（:306-321）。
- **纯写作/纯推演且无关键词命中的步骤 → 不注入契约 → LLM 自由输出 → 只能靠启发式**（词汇表窄、易错）。

### 3.2 LLM 未必遵守契约
- 即便注入了契约条款，模型可能：不产出 `MOYU:ASSETS` 块 / 块结构残缺 / `category` 用中文或别名 / `title` 超 30 字 / 把正文塞进块。
- 任一情况 → 落入 `rejected` 或启发式误分类，最终「收不全、分不准」。

### 3.3 路由型技能声明了收不到的键
- `novel-forge` 声明 `work_info`/`chapter_synopses`，但它是流程编排总控，自身几乎不直接产出这些结构化块 → 前端「反哺标签」误导，实际收不到对应资产。

### 3.4 契约子字段规则只给了一部分
- `build_contract_clause`（output_normalizer.py:329-335）列了 entity/relations/timeline/foreshadow/outline 子字段，但 `relations`/`timeline` 仅给了示例结构、未像 entity 那样列「允许值枚举」，模型自由发挥易偏差。

---

## 4. 责任划分（量化判断）

| 现象 | 主因 | 说明 |
|---|---|---|
| 工作流产出**完全没进**模块 | 中枢：不自动归档（设计） | 必须人工点「收录」 |
| 该收的条目**丢失** | 中枢：sanitize 过度拒绝 + 人工未留意 rejected | 标题>30字、套话、纯标题词被丢 |
| **地点/场景**被存成「术语」 | 中枢：`location` 归一 bug（代码） | 硬 bug，确定性发生 |
| 笔记/批注混进术语 | 中枢：notes 无独立模块（语义） | 设计债 |
| 势力/地点关系造出「人物」 | 中枢：关系端点未知硬建 character | 代码债 |
| 自由输出步骤分类乱 | skill 输出：契约未覆盖该步骤 | 次因 |
| 块结构不符导致收不全 | skill 输出：LLM 遵从率 | 次因 |

**结论**：约 70% 的「没收录/分不准」根子在中枢（自动归档缺失 + 归一 bug + 过度拒绝 + notes 错配）；约 30% 是 skill 输出规范未覆盖或 LLM 不遵从。

---

## 5. 修复优先级建议

### P0（立即，收益最大）
1. **工作流完成即自动归档**：在 `workflow_engine` 跑完最后一步（或全部步骤完成、run 进入终态）时，自动调用一次 `extract_structured_assets_from_text` + `sync_assets_to_database`；或至少在 UI 强提示「有 N 条待收录资产」。
2. **修 `normalize_category` 词汇不一致**：补 `location→place`、`lore→term`（及 `custom` 兼容）；并让 `canonicalize_assets` 与 `normalize_category` 共用同一枚举/别名表，消除双归一器。

### P1（重要）
3. **放宽 sanitize 阈值**：30 字上限对大纲卷名/伏笔标题过严，改为分级（如大纲/伏笔放宽到 50 字；正文块仍严），并把 `rejected_items` 在 UI 明确展示「未收录原因」，避免静默丢失。
4. **notes 独立承载**：新增 `notes` 表（或明确映射到现有便签模块），不再塞进 `entities` 的 `term`；前端反哺标签对应到真实模块。
5. **关系端点未知时按上下文推断 category**：不要一律 `character`，可据关系文案或先在 `entities` 模糊匹配，匹配不到再默认 `character`。

### P2（完善）
6. **契约条款覆盖所有步骤**：对无 `skill_id` 的纯写作/推演步骤，默认注入与步骤语义匹配的资产键（或最小全集），减少自由输出比例。
7. **提升 LLM 遵从**：契约块改为更不可错的结构（如强制 YAML/紧凑 JSON、显式枚举值下拉），并在工作流结束前做「块校验—补全」兜底。

---

## 6. 对前期分析（M1–M6）的更正
- 前期 `skill-output-vs-ingest-analysis.md` 中 **M2（`parent_title` 未被解析）判断有误**：`plot_service.batch_sync_triad_assets`（:74-86）已正确把 `parent_title` 反查为 `parent_id` 并逐级挂载，**大纲卷-章层级是通的**。该条从待修列表移除。
- 本期新增并确认的中枢 bug：**`location`→`term` 归一错配（§2.2）**、**关系端点硬建 character（§2.6）**、**不自动归档（§2.1）**、**notes 无独立模块（§2.5）** 应进入修复计划。
