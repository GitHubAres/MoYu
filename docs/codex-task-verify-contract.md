# 墨语 MoYu · 技能/资产契约适配 · 回归验证任务（交给 Codex 执行）

## ⚠️ 执行方式（必须遵守）
- **直接开始执行，禁止长时间分析**。下面已给出全部所需信息，以此为准即可，不必全文通读其他文件。
- 每完成一步就落实（跑测试/改代码），不要攒到最后。
- **不 `git commit` / `push`**，改动留在工作区由用户验收。

## 任务来源
严格按 `docs/skill-contract-dev-guide.md` 与 `docs/skill-rebuild-blueprint.md` 验证「技能输出 → MOYU:ASSETS 契约 → 核心模块入库」链路未被破坏。计划书是权威背景，实现细节以本任务为准。

## 范围（本次必须完成）
1. **跑契约/技能/工作流相关回归 suite**（在仓库根目录 `D:\KimiCode工作区` 执行）：
   ```bash
   .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
   ```
2. 若**全绿（91 passed）**：直接进入完成标准第 2 步，写汇报并输出 `TASK_DONE`。
3. 若**有失败**：只在下列文件范围内诊断并修复（禁止动无关模块）：
   - `app/services/output_normalizer.py`（契约解析/归一/提示）
   - `app/features.py`（`build_skill_system_prompt` 契约注入）
   - `app/workflow_engine.py`（契约键推导；注意 `step` 是 `sqlite3.Row`，用 `step["skill_id"]` 下标，**不可用 `.get()`**）
   - `app/db.py` 中与技能 body 相关的 `BUILTIN_SKILLS` 条目
   - `app/api/skills.py` 的 `asset_keys` 派生
   修复后重跑，直到全绿。

## 红线
- 不修改 8 个产物键的 schema（`work_info/entities/relations/timeline_events/foreshadows/outline_nodes/chapter_synopses/notes`），不增删键。
- 不引入新依赖；不动技能/契约以外的业务代码（如 chat、exporter、hotradar 等）。
- 不 `git commit` / `push`。

## 完成标准
1. 上述 pytest 命令 **100% 绿灯**（期望 `91 passed`）。
2. 写交付汇报 `docs/codex-report-verify-contract.md`，含：① 执行的测试命令与结果；② 若曾失败，列出失败项、根因、修复点（改动文件清单）；③ 遗留风险（若有）。
3. 在 stdout 输出 `TASK_DONE` 标记。
