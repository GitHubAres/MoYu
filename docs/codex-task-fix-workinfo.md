# 墨语 MoYu · 修复 `work_info` 被收录器静默丢弃（P0，交给 Codex 执行）

## ⚠️ 执行方式（必须遵守）
- **直接开始执行，禁止长时间分析**。下面已给出全部所需信息，以此为准即可，不必全文通读其他文件。
- 每完成一步就落实（改代码 + 跑测试），不要攒到最后。
- **不 `git commit` / `push`**，改动留在工作区由用户验收。

## 任务来源
依据 `docs/skill-output-vs-ingest-analysis.md` 的 **M1（P0）**：`build_contract_clause` 已指令 4 个技能（default-outline / novel-premise / novel-forge / default-analysis）在文末产出 `"work_info": {"title": "", "genre": "", "intro": ""}`，但 `extract_assets_block` 的 `valid_keys` 不含 `work_info`，导致契约块里的 `work_info` 被**静默丢弃**，作品设定几乎无法经契约块入库。
目标：让 `work_info` 与 7 个 list 键一样被正确解析、归一并落库。

## 范围（本次必须完成）
1. **改 `app/services/output_normalizer.py` → `extract_assets_block`（约 134–169 行）**：
   - 在 `valid_keys` 列表（当前 7 个 list 键）中增加 `"work_info"`。
   - 解析逻辑原为「对 valid_keys 取 list」，需对 `work_info` 做**对象级**特殊处理：
     ```python
     # work_info 是对象，单独解析（不能当作 list）
     wi = data.get("work_info")
     if isinstance(wi, dict):
         res["work_info"] = {
             "title": str(wi.get("title") or "").strip(),
             "genre": str(wi.get("genre") or "").strip(),
             "intro": str(wi.get("intro") or "").strip(),
         }
     else:
         res["work_info"] = {"title": "", "genre": "", "intro": ""}
     ```
   - 注意：`res` 不能只是 `dict[str, list]`，现需允许 `work_info` 为 dict。
2. **改 `app/workflow_assets.py` → `extract_structured_assets_from_text`（约 721–787 行）**：
   - 当前「契约块存在」分支只遍历 7 个 list 字段，`work_info` 仅靠 762–767 行的**启发式兜底**。
   - 改为：优先读取 `block.get("work_info")`，当其中 `title/genre/intro` 任一非空时直接采用；仅当契约块未提供时才回落到现有启发式（保留 762–767 逻辑）。
3. **确认 `canonicalize_assets`（output_normalizer.py:326+）无需改逻辑**：它已读 `raw.get("work_info")` 并归一，只要上游 `extract_assets_block` 返回了 `work_info`，即可贯通。仅做确认，不改动。
4. **加一条回归测试**：在 `tests/test_skill_contract_adapter.py` 新增 `test_work_info_ingested_from_contract_block`，断言：
   - 给定含 `"work_info":{"title":"X","genre":"Y","intro":"Z"}` 的 `<!-- MOYU:ASSETS ... MOYU:ASSETS -->` 文本，
   - `extract_assets_block(text)["work_info"]` 返回 `{"title":"X","genre":"Y","intro":"Z"}`（**不再为空**）；
   - （可选）经 `canonicalize_assets` 后 `work_info` 仍保留。

## 红线
- 不修改 8 个产物键的 schema，不增删键；`work_info` 的字段固定为 `title/genre/intro`。
- 不引入新依赖；不动 `chat` / `exporter` / `hotradar` / 炼丹炉 / 前端 等无关模块。
- 不 `git commit` / `push`。

## 完成标准
1. 单测新增用例通过；并跑全量相关回归（期望 **91 passed** + 新增用例全过）：
   ```bash
   .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
   ```
2. 写交付汇报 `docs/codex-report-fix-workinfo.md`，含：① 执行的测试命令与结果；② 改动文件清单与关键 diff 说明；③ 遗留风险（若有）。
3. 在 stdout 输出 `TASK_DONE` 标记。
