# 墨语 MoYu · Phase B (P1: 层级挂载与子字段 Schema) 交付报告

## 1. 任务背景与目标
依据 `docs/codex-plan-asset-contract-fixes.md` Phase B 规划：
- **B-M2**：在 `app/services/plot_service.py:batch_sync_triad_assets` 补充 `parent_title → parent_id` 解析支持，解决模型输出大纲按字符串卷名挂载时失效、只能依赖脆弱时序推断的问题；并在 `app/workflow_assets.py:AssetOutlineIn` 补充 `parent_title` 字段声明。
- **B-M4 + B-M6**：在 `app/services/output_normalizer.py:build_contract_clause` 为 `relations`、`timeline_events`、`foreshadows` 补充明确的最小子字段 schema 规则，并要求人物卡可通过 `entity.fields_json` 承载欲望/创伤/弧光等高维设定，消除模型因字段猜测偏差导致的丢字段问题。

## 2. 改动文件清单与关键 Diff 说明

1. **`app/services/plot_service.py`**
   - 在 `batch_sync_triad_assets` 的大纲节点循环中增加 `parent_title` 解析与 `parent_map` 缓存机制；当遇到 `is_volume: true` 时记录父卷映射，未提供 `parent_id` 时按 `work_id + parent_title` 查库解析父卷 ID，未查到则回退至 `current_parent_id`。

2. **`app/workflow_assets.py`**
   - 在 `AssetOutlineIn` 模型中显式增加 `parent_title: Optional[str] = None` 字段。

3. **`app/services/output_normalizer.py`**
   - 在 `build_contract_clause` 的“字段规则”中扩展补充：
     - `entity`: 人物实体可用 `fields_json` 承载欲望/创伤/弧光/说话方式等高维设定；
     - `relations`: `{"from_name": "起点角色", "to_name": "终点角色", "label": "关系/冲突说明"}`；
     - `timeline_events`: `{"time_label": "时间点", "event": "事件描述", "characters": "相关角色"}`；
     - `foreshadows`: `{"title": "伏笔标题", "content": "线索内容", "status": "planted/pending/recovered"}`。

4. **`tests/test_skill_contract_adapter.py`**
   - 新增测试用例 `test_outline_parent_title_resolved_and_relations_synced`，验证包含 `parent_title` 的章节成功挂载至对应分卷，且 `relations` 与人物 `fields_json` 均正确解析落库。

## 3. 测试执行命令与结果
- **执行命令**：
  ```bash
  .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
  ```
- **测试结果**：
  `93 passed, 1 warning in 8.42s`（全部通过）。

## 4. 遗留风险与红线遵守
- 未修改 8 个资产主键列表；
- 保持向后兼容（既有未带 `parent_title` 的旧大纲节点依然走 `parent_id` / `current_parent_id` 降级链路）；
- 无 git commit / push。
