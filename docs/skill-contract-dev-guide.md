# 墨语 MoYu · 技能与资产契约 · 开发指引（Developer Guide）

> 适用范围：开发与扩展墨语内置 **Agent Skill** 体系，重点是让任意技能产出都能被墨语核心模块**自动识别、零摩擦入库**。
> 阅读前提：已通读 `docs/skill-rebuild-blueprint.md`（v2，重构结论与架构全图）。
> 本文档假设你要在**不改动技能"业务逻辑/文风"**的前提下，把输出接口接到墨语唯一的识别通道 `MOYU:ASSETS`。

---

## 0. 一句话心智模型

> **"被墨语识别" = 在回答末尾追加一个 `MOYU:ASSETS` 契约块。** 其余一切（设定库、关系图谱、时间线、伏笔看板、大纲、梗概、作品设定、笔记）都从这个契约块自动解析入库。技能正文怎么写、参考手册怎么挂，墨语不管；墨语只认契约块。

---

## 1. 核心接口：MOYU:ASSETS 契约块

```html
<!-- MOYU:ASSETS
{
  "entities": [
    {"category": "character", "name": "宁恪", "tags": "主角", "content": "少年帝王，隐忍而决断"}
  ],
  "foreshadows": [
    {"name": "北境异动", "status": "planted", "bind_entity": "宁恪"}
  ],
  "outline_nodes": [
    {"title": "第一卷·潜龙", "is_volume": true},
    {"title": "第一章·雪夜密诏", "is_volume": false, "parent_title": "第一卷·潜龙"}
  ]
}
MOYU:ASSETS -->
```

- 用 **HTML 注释** 包裹的合法 JSON；正文写在契约块之外。
- **8 个产物键（权威 schema）**，键名不可增删、大小写不可改：

| 键 | 归口模块 | 说明 |
|---|---|---|
| `work_info` | 作品设定 | 对象：`{"title","genre","intro"}` |
| `entities` | 设定库/人物 | 数组，每项含 `category/name/tags/content` |
| `relations` | 关系图谱 | 数组，人物/势力关系 |
| `timeline_events` | 时间线 | 数组，剧情事件 |
| `foreshadows` | 伏笔看板 | 数组，`status` 枚举见下 |
| `outline_nodes` | 大纲 | 数组，`is_volume`/`parent_title` |
| `chapter_synopses` | 梗概 | 数组，章节梗概 |
| `notes` | 笔记 | 数组，问题/评分/改动沉淀 |

- **枚举边界**（越界会被 `canonicalize_assets` 兜底，但应尽量避免）：
  - `entity.category` ∈ `character / place / faction / item / term / custom`（中文别名如「人物→character」「地点→place」会被自动归一）
  - `foreshadow.status` ∈ `planted / pending / recovered`
- `outline_node.is_volume=true` 表示分卷，`false` 表示章节；`parent_title` 填所属分卷名。
- `title/name/event` 须 ≤30 字、非空、非 AI 套话。

---

## 2. 架构链路（两条调用路径，统一口径）

```
技能/工作流/炼丹炉 产出（文末含 MOYU:ASSETS 契约块）
        │
        ▼
app/services/output_normalizer.py
  ├─ extract_assets_block()      解析契约块
  ├─ canonicalize_assets()       归一 8 键 schema（枚举/中文别名/字段兜底）
  └─ build_contract_clause()     schema 强制版契约提示（喂给模型照抄）
        │
        ▼
app/workflow_assets.py → sync_assets_to_database → 落库
```

**两条生产端路径已统一**，都依赖同一份元数据 `SKILL_ASSET_CONTRACTS`：

| 路径 | 入口 | 契约注入方式 |
|---|---|---|
| 直接调用（聊天/创作） | `features.build_skill_system_prompt` | `name` 命中 `SKILL_ASSET_CONTRACTS` 时，注入 `build_contract_clause(required_keys=SKILL_ASSET_CONTRACTS[name])` |
| 工作流 | `app/workflow_engine.py` | `if step["skill_id"]:` 查技能名 → 追加 `SKILL_ASSET_CONTRACTS[name]` 键；关键词启发式（`实体/大纲/伏笔/立项…`）作兜底补充 |

> ⚠️ 两级路径的契约键**必须保持一致**，避免同一技能在"直接跑"和"走工作流"时产出不同结构。新增/修改映射只改 `SKILL_ASSET_CONTRACTS` 一处即可。

---

## 3. SKILL_ASSET_CONTRACTS（权威映射表）

位置：`app/services/output_normalizer.py`，被 `features` / `workflow_engine` / `api/skills` 共用。

```python
SKILL_ASSET_CONTRACTS: dict[str, list[str]] = {
    "default-continue": ["entities", "foreshadows", "timeline_events"],
    "default-expand":   ["entities", "foreshadows", "timeline_events"],
    "default-shorten": ["notes"],
    "default-rewrite": ["notes"],
    "default-outline": ["work_info", "outline_nodes", "entities", "relations", "foreshadows"],
    "novel-premise":    ["work_info", "entities", "notes"],
    "novel-world":      ["entities", "relations", "timeline_events", "notes"],
    "novel-cast":       ["entities", "relations"],
    "novel-scene":      ["outline_nodes", "foreshadows", "entities", "timeline_events"],
    "novel-forge":      ["work_info", "entities", "relations", "timeline_events",
                         "foreshadows", "outline_nodes", "chapter_synopses", "notes"],
    "default-audit":    ["notes"],
    "default-analysis": ["work_info", "notes"],
    "de-ai-tone":       ["notes"],
}
```

- 每个**技能名**映射到它"应当产出"的资产键；消费端据此高识别率解析。
- 空列表 `[]` 表示不强制任何结构化资产（如纯正文润色且无产出，可不入表）。

---

## 4. 如何新增一个"被墨语识别"的技能（标准流程）

> 红色步骤为契约相关，必须做；其余为常规技能登记。

1. **登记技能**：在 `app/db.py` 的 `BUILTIN_SKILLS` 中新增条目（`name` 全局唯一，建议 `default-<动作>` 或 `novel-<领域>`）。
   - `body_md` 写业务逻辑/文风/参考结构即可，**不要**再写"自动入库解析 / asset_hub 100% 互通"等不实声明。
   - 在"产出与入库"小节写明：**若本次产出含可入库资产，请在文末以系统追加的 `MOYU:ASSETS` 契约块输出**；`【人物】/【地点】/【伏笔】` 可继续作为人读内联标注，但**机读入库以契约块为准**。
2. **声明资产键**：在 `app/services/output_normalizer.py` 的 `SKILL_ASSET_CONTRACTS` 增加 `"你的技能名": ["entities", ...]`，键必须取自 8 个权威键。
3. **（可选）挂载参考资源**：在技能下挂 `references/`（内联到提示词）、`scripts/`、`assets/`，与既有技能对齐。
4. **前端反哺标签（自动）**：`app/api/skills.py` 的 `list_skills` / `get_skill_detail` 已自动带上 `asset_keys`；`static/js/pages/skills.js` 据此渲染"本技能将反哺：设定库 · 关系图谱 …"。**无需手动改前端**。
5. **写测试**：在 `tests/test_skill_contract_adapter.py` 或新建文件，断言① 该技能在 `SKILL_ASSET_CONTRACTS` 有映射且键合法；② 其样本输出能被 `extract_assets_block` 识别、`canonicalize_assets` 归一到 8 键；③ 落库字段正确。

---

## 5. 炼丹炉（AlchemyEngine）并入契约的注意点

- `extract_lore`：system prompt 注入 `build_contract_clause(["entities","outline_nodes"])`，产出优先走 `extract_assets_block(raw_text) → canonicalize_assets`；缺失则回退旧 JSON 解析（兼容历史）。输出形状 `{"entities":..., "outline":...}` 保持前端兼容。
- `import_lore`：先把 `body.entities` / `body.outline` 经 `canonicalize_assets` 归一（人物→character 中文别名归一、大纲 `parent_title` 解析），再落库。与技能体系**同一口径**，不要另写 INSERT。

---

## 6. 测试与回归

依赖项目自带 `.venv`（pytest 9.1.1）：

```bash
# 契约 / 技能 / 工作流 相关回归（推荐日常跑这一组）
.venv/Scripts/python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q

# 全量（含无关模块，较慢）
.venv/Scripts/python.exe -m pytest -q
```

关键测试文件：

| 文件 | 覆盖 |
|---|---|
| `tests/test_skill_contract_adapter.py` | 13 技能映射齐全、直接路径注入强制契约、炼丹炉 `import_lore` 归一与大纲父子解析 |
| `tests/test_output_contract.py` | `build_contract_clause` / `canonicalize_assets` / `extract_assets_block` 行为 |
| `tests/test_workflow_contract.py` | 工作流路径契约键推导 |
| `tests/test_skills.py` | 技能 API 与 `asset_keys` 字段 |

---

## 7. 红线（Red Lines）

- **不改 8 键 schema**：键名、枚举不可增删；新增资产类型先提方案，不要偷偷加键。
- **不再写"自动入库"虚假声明**：技能 body 不得再承诺"asset_hub 100% 互通 / 自动入库解析"等基于 `【】` 标记的能力。
- **映射只在一处**：新增/修改技能资产键只改 `SKILL_ASSET_CONTRACTS`，不要让两条路径各写一份。
- **不引入新依赖**（vendor 不引新包）；不动技能/契约以外的业务代码。
- **不 `git commit` / `push`**（改动留在工作区由用户验收）。

---

## 8. 已知坑（踩过的）

1. **`sqlite3.Row` 没有 `.get()`**：`workflow_engine.py` 中 `step` 是 `sqlite3.Row`（来自 `fetchall()`），只能用 `step["skill_id"]` 下标访问，**不能** `step.get("skill_id")`，否则运行态整体卡 `failed`（异常被 `except` 吞进 `error_msg`）。
2. **`build_contract_clause` 只列所需键**：既有测试 `tests/test_output_contract.py::test_l1a_build_contract_clause` 断言"只列 required 键、空数组占位"。不要把全部 8 键都塞进示例。
3. **契约块外才是正文**：模型容易把大段章节正文塞进契约块。契约块只放结构化元数据；超长字段会被 `canonicalize_assets` 视为噪声丢弃。

---

## 9. 配套 Codex 执行指令

本目录下已提供可直接交给 Codex 执行的任务指令文件（遵循仓库 `codex-task-*.md` 约定）：

- `docs/codex-task-verify-contract.md` —— 验证 MOYU:ASSETS 契约适配回归（最常用："我改了技能/契约，跑一遍确认没破"）。
- `docs/codex-task-add-skill.md` —— 端到端新增一个"被墨语识别"的技能（本指引第 4 节的标准流程封装为可执行任务）。
