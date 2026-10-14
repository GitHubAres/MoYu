# 墨语 MoYu · Skill 体系「重构」· 现状梳理与重构蓝图（修订版 v2）

> 目标：让**全部预置 Skill 的输出**都被墨语核心功能**完美识别、零摩擦适配**。
> 本文档是「先列大纲 + 模块分析」阶段产物。**Phase 0–5 已全部落地**（含 Phase 5 回归测试修复的一个由本重构引入的回归 bug），详见各 Phase 状态与第 6 节总结。

---

## 0. 重要更正（基于完整通读 `db.py` 后的修正）

> ⚠️ 本文件 v1 版本基于**未读完 `BUILTIN_SKILLS` 列表**的误判，得出了"仅 7 个内置 skill""`novel-*` 不存在""5 个孤儿手册"等错误结论。通读 `db.py:679-2322` 后核实：**以上结论全部不成立**。本版为权威版。

**真实情况：**
1. 内置技能共 **13 个**，已覆盖"创作 → 规划 → 审校"完整闭环：
   - 正文类：`default-continue` / `default-expand` / `default-shorten` / `default-rewrite`
   - 规划类：`default-outline` / `novel-premise` / `novel-world` / `novel-cast` / `novel-scene` / `novel-forge`
   - 审校类：`default-audit` / `default-analysis` / `de-ai-tone`
2. 14 个参考手册常量（STYLE_FINGERPRINT / PROSE_CRAFT / GENRE_PLAYBOOK / EXPANSION_CRAFT / COMPRESSION_FORMATS / REWRITE_DIMENSIONS / AI_TONE_CATALOG / STRUCTURE_MODELS / CONSISTENCY_TAXONOMY / ANALYSIS_RUBRIC / WORLDBUILDING_CHECKLIST / CHARACTER_ARC_MODELS / SCENE_BEATS / CREATION_PIPELINE）**全部已挂载**，无孤儿。
3. 多数 `novel-*` 技能 body 已**自带"入库"格式设计**——但它们用的是**自定义 `【人物】/【地点】/【伏笔】` 标记 + 散文式"自动入库解析 / asset_hub 100% 互通"声明**。

**真正的缺口不是"技能不存在/内容缺失"，而是"契约识别适配层断裂"**（详见第 2 节）。因此重构重心从"内容重写"调整为"**契约适配式重构**"：保留 13 技能现有逻辑与内容，只把它们的**输出接口**统一到墨语唯一的识别通道 `MOYU:ASSETS`。

---

## 1. 墨语"被识别"的唯一接口（技术本质）

```
技能/工作流/炼丹炉 产出
        │
        ▼
 文末追加 MOYU:ASSETS 契约块（HTML 注释包裹的 JSON）
   <!-- MOYU:ASSETS {...} MOYU:ASSETS -->
        │
        ▼
 app/services/output_normalizer.py
   ├─ extract_assets_block()   解析契约块
   ├─ canonicalize_assets()    归一 8 键 schema（Phase 0 已增强）
   └─ build_contract_clause()  schema 强制版契约提示（Phase 0 已增强）
        │
        ▼
 app/workflow_assets.py → sync_assets_to_database
   → 落库：entities / entity_relations / timeline_events / foreshadows
          / outline_nodes / chapter_synopses / notes / works
        │
        ▼
 墨语核心模块：设定库 · 关系图谱 · 时间线 · 伏笔看板 · 大纲 · 梗概 · 笔记
```

**8 个产物键（权威 schema）：** `work_info` / `entities` / `relations` / `timeline_events` / `foreshadows` / `outline_nodes` / `chapter_synopses` / `notes`

---

## 2. 真实缺口（Gap Analysis，逐条有代码证据）

### G1 — 直接技能路径与 workflow 路径「双轨契约」
- `app/features.py:257-264` 的 `build_skill_system_prompt` 内**自写一段软提示契约**（"请在回答末尾追加合法的 MOYU:ASSETS 契约块…"），它：
  - 未调用 `build_contract_clause`（output_normalizer 里已升级的 schema 强制版）；
  - **没有 per-skill 的产物键声明**，只给了一段通用、弱约束的文字。
- 对比 `app/workflow_engine.py:273-316` 的 workflow 路径，它**正确调用** `build_contract_clause(required_keys)`，但 required_keys 是靠 **instruction 关键词启发式**推导的，不稳定。
- 结果：同一套契约，两条路径口径不一；直接调用技能时模型拿到的约束过弱，导致 `novel-*` 作者不得不在 body 里**自己发明 `【】` 标记**来"补强"。

### G2 — `novel-*` 的 `【人物】/【地点】/【伏笔】` 标记"声称自动入库"但不成立
- `db.py` 中 `novel-premise:1593-1594`、`novel-world:1736`、`novel-cast:1902/1919`、`novel-scene:2039/2100-2115` 等使用 `【人物】…`、`【地点】…`、`【伏笔】…` 标记，并声称"全自动入库解析""与资产中枢 (asset_hub) 契约 100% 互通"。
- **但全局搜索 `app/` 证明：没有任何解析器消费这些 `【】` 标记**（仅 `workflow_engine.py:86` 把它当作 UI 摘要的一行文字，不入库）。
- 唯一真正入库的解析器是 `output_normalizer.extract_assets_block`，它只认 `MOYU:ASSETS` 块。
- **结论："`【】` 标记 → 自动入库"在当前代码下是虚假承诺。** 这是"不被墨语识别"的根因。

### G3 — 炼丹炉走独立 JSON 双轨
- `features.py:545-629` 的 `AlchemyEngine.extract_lore` 要求模型输出**自带 JSON schema**（`entities` + `outline`，键名与 MOYU:ASSETS 不同：`outline` vs `outline_nodes`、无 `relations/foreshadows/timeline_events` 等），返回结构化数据后由前端调用 `import_lore` **直接 INSERT**，完全不经过 `output_normalizer`。
- 这与技能体系的契约/落库通道是**两条平行线**，无法复用归一化、校验、查重逻辑。

### G4 — skills 表无"产出资产键"声明列，前端无法展示「反哺模块」
- `db.py:410-423` 的 `skills` 表字段无"本技能反哺哪些核心模块"的声明。
- 因此技能市场/菜单无法告诉用户"用这个技能会沉淀哪些资产"，与用户设想的"所有 skill 输出完美适配核心功能"的可视化目标脱节。

---

## 3. 重构蓝图（对齐用户已确认的 4 个方向）

用户已拍板：① Skill 内容 + 前端联动；② 扩到完整闭环（已具备）；③ 结构化 JSON 强制；④ 炼丹炉并入统一 MOYU:ASSETS。

### Phase 0（✅ 已完成）契约收敛 — `output_normalizer` 升级为 schema 强制唯一入口
- `build_contract_clause(required_keys)` 升级为 schema 强制版：给出可照抄的 JSON 样例 + 字段规则（category 枚举、status 枚举、is_volume、≤30 字等）。
- 新增 `canonicalize_assets(raw)`：保证 8 键齐全、实体 category 中文别名归一、伏笔 status 归一、fields_json 兜底。
- 已通过 Python 单元验证。

### Phase 1（✅ 已完成）统一契约装配 — 消除 G1 双轨
- 在 `features.py` 新增 **`SKILL_ASSET_CONTRACTS`** 映射：13 技能 → 应产出的资产键列表（见第 4 节）。
- 修改 `build_skill_system_prompt`：删除硬编码软条款，改为调用 `build_contract_clause(required_keys=SKILL_ASSET_CONTRACTS.get(name, []))`。
- `workflow_engine.py` 的 required_keys 推导改为**优先用技能声明键**，关键词启发式作为兜底补充。

### Phase 2（✅ 已完成）修正 13 内置 skill body — 消除 G2 虚假承诺
- 保留每个技能**现有逻辑与格式约定**，仅做"输出接口"手术：
  - 删除"自动入库解析 / asset_hub 100% 互通"等基于 `【】` 标记的不实声明；
  - 在"产出与入库"小节统一写明：**本次产出若含可入库资产，请在文末以系统追加的 `MOYU:ASSETS` 契约块输出**（键见本技能对应的资产键）；`【人物】/【地点】/【伏笔】` 可继续作为人读内联标注，但**机读入库以契约块为准**。
- `BUILTIN_SKILLS` 通过 `INSERT … ON CONFLICT(name) DO UPDATE SET` 幂等更新，body 修改会自动同步到已存在的运行库。

### Phase 3（✅ 已完成）炼丹炉并入统一契约 — 消除 G3 双轨
- `extract_lore` 改为：在 system prompt 中改用 `MOYU:ASSETS` 契约（复用 `build_contract_clause`），产出经 `extract_assets_block` → `canonicalize_assets` → `sync_assets_to_database` 落库，与技能体系共用同一通道。
- 字段映射：`outline` → `outline_nodes`（含 `parent_title`→`parent_id`）；其余实体/关系等原生对齐。

### Phase 4（✅ 已完成）前端技能市场/菜单展示「反哺模块」— 消除 G4
- 基于 `SKILL_ASSET_CONTRACTS`，将资产键映射为中文模块名：
  `work_info→作品设定`、`entities→设定库/人物`、`relations→关系图谱`、`timeline_events→时间线`、`foreshadows→伏笔看板`、`outline_nodes→大纲`、`chapter_synopses→梗概`、`notes→笔记`。
- 技能卡片展示"本技能将反哺：设定库 · 关系图谱 · 伏笔看板 …"。
- 后端 `api/skills.py` 的 `list_skills` / `get_skill_detail` 已附加 `asset_keys` 字段，前端 `static/js/pages/skills.js` 渲染反哺标签。

### Phase 5（✅ 已完成）回归测试 + 修复一个回归 bug
- 新增 `tests/test_skill_contract_adapter.py`（4 测试）：13 技能映射齐全且键合法、直接路径注入强制契约、炼丹炉 `import_lore` 经 `canonicalize_assets` 归一（人物→character、大纲父子解析）。
- 既有契约/技能/工作流测试全过（共 91 passed）。
- **修复 bug**：本重构在 `workflow_engine.py` 误用 `step.get("skill_id")`，而 `step` 是 `sqlite3.Row`（仅支持下标 `step["skill_id"]`，无 `.get` 方法），导致所有带 `skill_id` 的工作流步骤执行时抛 `AttributeError` 被吞入 `error_msg`、运行态卡 `failed`。已改为 `step["skill_id"]` 下标访问。验证手法：`git stash` 仅回退 5 个生产文件 → 46 个 workflow 测试全过；加回改动 → 12 失败（即本 bug）；修复后 46 全过。

---

## 4. 每技能资产键映射表（SKILL_ASSET_CONTRACTS，Phase 1 落地依据）

| # | 技能 | 反哺的核心模块（资产键） |
|---|---|---|
| 1 | `default-continue` 续写 | entities, foreshadows, timeline_events |
| 2 | `default-expand` 扩写 | entities, foreshadows, timeline_events |
| 3 | `default-shorten` 缩写 | notes |
| 4 | `default-rewrite` 改写 | notes |
| 5 | `default-outline` 大纲 | work_info, outline_nodes, entities, relations, foreshadows |
| 6 | `default-audit` 设定检查 | notes |
| 7 | `default-analysis` 十维分析 | work_info, notes |
| 8 | `de-ai-tone` 去 AI 味 | notes |
| 9 | `novel-premise` 立项 | work_info, entities, notes |
| 10 | `novel-world` 世界观 | entities, relations, timeline_events, notes |
| 11 | `novel-cast` 人物 | entities, relations |
| 12 | `novel-scene` 细纲 | outline_nodes, foreshadows, entities, timeline_events |
| 13 | `novel-forge` 总控七段 | work_info, entities, relations, timeline_events, foreshadows, outline_nodes, chapter_synopses, notes（全量） |

> 说明：正文类（1-4）的契约以" emergent 资产"为主（续写/扩写时新出现的人物、埋下的伏笔、发生的时间线事件）；纯审校类（6-8）主要沉淀 `notes`（问题/评分/改动说明）。

---

## 5. 风险与回滚
- 改动集中在 `features.py` / `db.py(BUILTIN_SKILLS)` / `workflow_engine.py` / `AlchemyEngine`，均为幂等或向后兼容；契约块解析器 `output_normalizer` 已验证回归正常。
- 若某技能契约过严导致模型不产出，可将该技能映射键置空（`build_contract_clause` 对空键返回 `""`，退化为无契约）。
- 炼丹炉改动保留旧 `import_lore` 作为兜底入口，避免前端未同步时数据丢失。
