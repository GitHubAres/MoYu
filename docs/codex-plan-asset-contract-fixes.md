# 墨语 MoYu · 资产契约「收录逻辑 ↔ Skill 输出逻辑」对齐 · 开发计划（交给 Codex 执行）

> 依据：`docs/skill-output-vs-ingest-analysis.md`（模块收录逻辑 vs Skill 输出逻辑 对比分析）。
> 本文是**分阶段开发计划**，明确优先级、改动边界与验收口径；每一步的可执行指令见对应的 `codex-task-*.md`。

## 0. 背景与目标
重构已让 13 个内置 skill + 炼丹炉的输出统一经 `MOYU:ASSETS` 契约块被墨语识别。但分析发现**契约声明与实际收录能力存在 6 处错配**（M1–M6）。本计划按严重度分阶段收敛这些错配，使「契约承诺的内容」真正落库。

## 1. 优先级总览

| 阶段 | 严重度 | 错配 | 一句话修复 |
|---|---|---|---|
| **A** | P0 | **M1** `work_info` 被解析器静默丢弃 | `extract_assets_block` 的 `valid_keys` 补 `work_info` 并对象级解析 |
| **B** | P1 | **M2** `parent_title` 不被解析 | `batch_sync_triad_assets` 增加 `parent_title → parent_id` 解析 |
| **B** | P1 | **M4** `novel-cast` 富人物卡字段丢失 | 契约 clause 显式要求 `entity.fields_json` 结构 |
| **B** | P1 | **M6** `relations/timeline` 子字段 schema 缺失 | `build_contract_clause` 为 relations/timeline/foreshadow 给最小字段模板 |
| **C** | P2 | **M3** `notes` 语义错配（标「笔记」实存「术语」） | 统一 UI 与契约标签，或建独立笔记模块 |
| **C** | P2 | **M5** `novel-forge` 合约键与产出脱钩 | 校正其 `SKILL_ASSET_CONTRACTS` 声明 |

## 2. 分阶段开发计划

### Phase A — P0：`work_info` 收录修复（必做，收益最大）
- **目标**：让 4 个声明 `work_info` 的技能（default-outline / novel-premise / novel-forge / default-analysis）经契约块正确入库作品设定。
- **改动文件**：
  - `app/services/output_normalizer.py`：`extract_assets_block` 的 `valid_keys` 增加 `"work_info"`，并对象级解析（title/genre/intro 去空白）。
  - `app/workflow_assets.py`：`extract_structured_assets_from_text` 在「契约块存在」分支优先读 `block["work_info"]`，仅当缺失时回落启发式。
  - `app/services/output_normalizer.py`：`canonicalize_assets` 已能读 `raw.get("work_info")`，解析器修好后自然贯通，无需改逻辑（仅确认）。
- **验收**：新增/修正测试——构造含 `work_info` 的契约块，断言 `extract_assets_block` 返回非空 `work_info`，且 `sync_assets_to_database` 实际 UPDATE `works` 表。
- **风险**：低。不改 8 键 schema，不触碰其他路径。
- **对应指令**：`docs/codex-task-fix-workinfo.md`（本文附带的一条可执行指令）。

### Phase B — P1：层级挂载 + 子字段 schema
- **B-M2**：在 `app/services/plot_service.py:batch_sync_triad_assets` 增加 `parent_title → parent_id` 解析（参考 `app/features.py:677-695` 的 `parent_map` 做法，按 `work_id` 查重同名卷节点；找不到则回退 `current_parent_id`）。
- **B-M4 + B-M6**：在 `app/services/output_normalizer.py:build_contract_clause` 为 `relations`/`timeline_events`/`foreshadows` 各补最小字段模板，并（针对 novel-cast）要求 `entity.fields_json` 承载欲望/创伤/弧光。
- **验收**：构造含 `parent_title` 的 outline_nodes 契约块，断言节点挂载到正确父卷；构造 relations 契约块，断言按 `from_name/to_name/label` 落库。
- **风险**：中。M2 涉及查库解析，需回归 `plot_service` 既有测试；M6 改 clause 需回归 `test_output_contract.py`（注意 clause 只列所需键的既有约束）。

### Phase C — P2：语义与声明校正
- **C-M3**：统一 `notes` 语义——要么 UI（skills.js `ASSET_KEY_META`、workflows.js 提示）与契约统一称「世界观设定/术语」，要么建独立笔记模块消费该键。
- **C-M5**：修正 `novel-forge` 在 `SKILL_ASSET_CONTRACTS` 的声明（去掉 `chapter_synopses`/`work_info`，或注明「仅路由到子技能时由其产出」），使前端「反哺」标签诚实。
- **验收**：前端反哺标签与落库去向一致；`test_all_builtin_skills_have_contract_mapping` 仍全过。
- **风险**：低，但 C-M3 涉及 UI 文案决策，建议先与用户确认命名。

## 3. 执行纪律（所有阶段通用）
- 直接执行，禁止长时间分析；每步落实即跑测试。
- 不 `git commit` / `push`；改动留工作区验收。
- 不增删 8 个产物键、不引入新依赖、不动 chat/exporter/hotradar 等无关模块。
- 每阶段结束写 `codex-report-*.md` 并在 stdout 输出 `TASK_DONE`。

## 4. 测试基线
全量相关回归（Phase A 修复后期望仍 91 passed，新增 work_info 测试另计）：
```bash
.venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
```
建议新增对账测试 `tests/test_skill_contract_adapter.py::test_work_info_ingested_from_contract_block` 与 `test_outline_parent_title_resolved`。
