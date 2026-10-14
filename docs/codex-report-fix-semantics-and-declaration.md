# 墨语 MoYu · Phase C (P2: 语义与声明校正) 交付报告

## 1. 任务背景与目标
依据 `docs/codex-plan-asset-contract-fixes.md` Phase C 规划：
- **C-M3**：统一 `notes` 语义——收录器实际将其作为 `category='term'` 写入设定库，工作流界面也明确提示「世界观设定 · 将归入万象谱『术语』」，因此将 `skills.js` 中的 `ASSET_KEY_META` 标签由「笔记」校正为「世界观/术语」，保持前端反哺标签与落库去向一致。
- **C-M5**：校正 `novel-forge` 在 `SKILL_ASSET_CONTRACTS` 的合约键声明。移除自身不直接产出的 `chapter_synopses` 和 `work_info`（这两项分别由其编排路由的 `default-shorten` 与 `novel-premise` 等子技能产出），使前端反哺标签真实客观。

## 2. 改动文件清单与关键 Diff 说明

1. **`static/js/pages/skills.js`**
   - 更新 `ASSET_KEY_META` 中 `notes` 的标签文本：
   ```javascript
   notes: { label: "世界观/术语", color: "bg-slate-100 text-slate-600" },
   ```

2. **`app/services/output_normalizer.py`**
   - 调整 `SKILL_ASSET_CONTRACTS["novel-forge"]`：
   ```python
   # novel-forge 为流程编排总控，自身直接沉淀编排与推演产物（实体/关系/时间线/伏笔/大纲/术语），
   # 逐章梗概与细化立项由其路由的对应子技能（default-shorten / novel-premise 等）专项产出
   "novel-forge": ["entities", "relations", "timeline_events",
                    "foreshadows", "outline_nodes", "notes"],
   ```

## 3. 测试执行命令与结果
- **执行命令**：
  ```bash
  .venv\Scripts\python.exe -m pytest tests/test_skill_contract_adapter.py tests/test_skills_refactor_batch1.py tests/test_output_contract.py tests/test_workflow_contract.py tests/test_skills.py tests/test_workflows.py tests/test_workflow_multistep_context.py tests/test_v11_features.py -q
  ```
- **测试结果**：
  `93 passed, 1 warning in 7.76s`（全量回归套件全部通过）。

## 4. 遗留风险与红线遵守
- 未增删 8 个资产主键；
- 前端反哺标签与真实入库语义完全一致；
- 无 git commit / push。
