# 墨语 MoYu · 新增一个"被墨语识别"的技能（交给 Codex 执行）

## ⚠️ 执行方式（必须遵守）
- **直接开始写代码，禁止长时间分析**。下面已给出完整步骤与全部所需信息，以此为准实现即可，不必全文通读其他文件。
- 每完成一个文件就写盘，不要攒到最后。
- **不 `git commit` / `push`**，代码留在工作区由用户验收。

## 任务来源
严格按 `docs/skill-contract-dev-guide.md` 第 4 节「如何新增一个被墨语识别的技能」实现。本文档是权威流程，实现细节以它为准；如实现中发现与现状冲突，在最终汇报中说明冲突点。

## 任务输入（执行前由用户/上游填充，或按下面的默认值）
- **技能名 `SKILL_NAME`**：`default-<动作>` 或 `novel-<领域>`（全局唯一，示例：`novel-lore`）
- **技能标题 `SKILL_TITLE`**：中文展示名（示例：`世界观提炼`）
- **任务类型 `TASK`**：`continue/expand/shorten/rewrite/outline/...`（与 `AIOrchestrator.BASIC_PROMPTS` 对齐）
- **应产出的资产键 `ASSET_KEYS`**：取自 8 个权威键的子集（示例：`["entities","relations","timeline_events","notes"]`）

## 范围（本次必须完成）
1. **登记技能**：在 `app/db.py` 的 `BUILTIN_SKILLS` 新增条目，字段对齐现有技能（`name`/`title`/`version`/`body_md`/`enabled` 等）。`body_md` 写业务逻辑与文风即可，**不得**出现"自动入库解析 / asset_hub 100% 互通"等不实声明；在"产出与入库"小节写明："若本次产出含可入库资产，请在文末以系统追加的 `MOYU:ASSETS` 契约块输出；`【人物】/【地点】/【伏笔】` 仅作人读标注，机读入库以契约块为准"。
2. **声明资产键**：在 `app/services/output_normalizer.py` 的 `SKILL_ASSET_CONTRACTS` 增加 `"<SKILL_NAME>": <ASSET_KEYS>`。键必须全部取自 `{work_info, entities, relations, timeline_events, foreshadows, outline_nodes, chapter_synopses, notes}`。
3. **（可选）挂载参考资源**：在技能下挂 `references/`（内联到提示词）、`scripts/`、`assets/`，与既有技能对齐（无则跳过）。
4. **前端反哺标签（自动）**：`app/api/skills.py` 已自动派生 `asset_keys`，`static/js/pages/skills.js` 已渲染反哺标签——**无需手动改前端**，但需在测试中断言返回的 `asset_keys` 正确。
5. **新增测试**（pytest，对齐现有用例风格，≥3 条）：
   - 该技能在 `SKILL_ASSET_CONTRACTS` 有映射且键全部合法；
   - 其样本输出能被 `extract_assets_block` 识别、`canonicalize_assets` 归一到 8 键；
   - 技能 API `list_skills` / `get_skill_detail` 返回的 `asset_keys` 等于 `ASSET_KEYS`。

## 红线
- 不修改 8 键 schema，不增删键；`SKILL_ASSET_CONTRACTS` 是唯一映射源，禁止在 `workflow_engine.py` 另写一份键推导（只能引用它）。
- 不引入新依赖；不动技能/契约以外的业务代码。
- 不 `git commit` / `push`。

## 完成标准
1. 跑测试全绿：
   ```bash
   .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills.py tests/test_output_contract.py tests/test_workflow_contract.py -q
   ```
2. 抽取一个**最小可运行 sanity**：用 `features.build_skill_system_prompt(skill_id=<新技能id>, task="<TASK>")` 确认其返回的 system prompt 包含 `【结构化产物交付契约 MOYU:ASSETS（强制）】` 且列出 `ASSET_KEYS` 中的键。
3. 写交付汇报 `docs/codex-report-add-skill.md`：改动文件清单、测试结果、sanity 验证结论、遗留风险。
4. 在 stdout 输出 `TASK_DONE` 标记。
