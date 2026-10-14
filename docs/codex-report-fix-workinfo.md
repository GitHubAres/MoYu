# 墨语 MoYu · Phase A (P0: work_info) 交付报告

## 1. 任务背景与目标
依据 `docs/skill-output-vs-ingest-analysis.md` 与 `docs/codex-plan-asset-contract-fixes.md`：
修复 M1 (P0) 缺陷——契约块中的 `work_info` 被 `extract_assets_block` 忽视与静默丢弃的问题，实现从契约块解析、对象字段提取、规范化归一到落库的全链路贯通。

## 2. 改动文件清单与关键 Diff 说明

1. **`app/services/output_normalizer.py`**
   - 在 `extract_assets_block` 中对 `work_info` 进行对象级安全提取与去空白：
   ```python
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
   - 保证契约块解析结果包含规范化的 `work_info` 对象。

2. **`app/workflow_assets.py`**
   - 在 `extract_structured_assets_from_text` 的契约块分支中，优先读取并采纳契约块已解析的 `work_info`；仅在契约块未提供或字段为空时，才回落到后文的启发式提取兜底：
   ```python
   b_wi = block.get("work_info") or {}
   if isinstance(b_wi, dict):
       for f_key in ("title", "genre", "intro"):
           val = str(b_wi.get(f_key) or "").strip()
           if val:
               assets["work_info"][f_key] = val
   ```

3. **`tests/test_skill_contract_adapter.py`**
   - 新增回归测试 `test_work_info_ingested_from_contract_block`，断言：
     - `extract_assets_block` 能正确提取 `work_info`（非空）；
     - `canonicalize_assets` 保留 `work_info`；
     - `extract_structured_assets_from_text` 优先采纳契约块 `work_info`；
     - `sync_assets_to_database` 成功更新 `works` 数据表。

## 3. 测试执行命令与结果
- **执行命令**：
  ```bash
  .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
  ```
- **测试结果**：
  `92 passed, 1 warning in 8.49s`（在基线 91 条测试基础上，新增 1 条测试全部通过，无回归破坏）。

## 4. 遗留风险与红线遵守
- 未增删 8 个资产键 schema；
- 未引入任何第三方依赖或触碰不相关模块；
- 无 git commit / push。
