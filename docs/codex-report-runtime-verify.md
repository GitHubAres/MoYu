# 墨语 MoYu · P0 运行时端到端验证交付报告

## 一、执行的测试命令与结果摘要

### 1. 核心端到端与回归测试
- **执行命令**：
  `ash
  .venv\Scripts\python.exe -m pytest tests/test_smart_intake.py tests/test_works.py tests/test_versions.py tests/test_output_contract.py tests/test_skill_contract_adapter.py tests/test_workflow_contract.py tests/test_workflows.py tests/test_v11_features.py -q
  `
- **测试结果**：89 passed, 1 warning (8.23s) 全部通过（100% 通过率）。

### 2. 全量回归测试
- **执行命令**：
  `ash
  .venv\Scripts\python.exe -m pytest -q
  `
- **测试结果**：236 passed, 1 warning (20.94s) 全部通过（100% 通过率）。

---

## 二、改动文件清单与关键 Diff 说明

1. **pp/api/works.py**：
   - 修复 chapter_smart_intake SQL 关联查询中的列名错位问题：chapters 表无 work_id，改用 JOIN volumes v ON v.id = c.volume_id 取 .work_id。
   - 规范化模块导入路径：rom ..workflow_assets import extract_structured_assets_from_text 与 rom ..services.output_normalizer import canonicalize_assets。
   - 修复 sync_assets_to_database 入参适配：正确将 chapter_id 作为 SyncAssetsIn 结构体的字段传入，避免多余关键字参数。
2. **	ests/test_smart_intake.py**：
   - 新增 6 项运行时集成与单元测试用例，覆盖：
     - 候选资产预览（uto_commit=false，带 is_new=True，验证未实际落库）；
     - 确认入库（uto_commit=true，验证通过 sync_assets_to_database 真实持久化到 DB）；
     - is_new 判定准确性（入库前 True，入库后二次探测为 False）；
     - location -> place 归一化回归（验证地点资产入库后 category 为 place 而非 	erm）；
     - udit/run 字段契约（使用 monkeypatch mock httpx.AsyncClient.post 返回结构化 JSON，验证 issues 字段健全且类型/严重度/原文字段正确匹配）。
3. **README.md**：
   - 同步更新测试徽标与测试用例计数由 224 项提升至 236 项，满足 	est_doc_integrity.py 严格校验。

---

## 三、测试中发现并修复的 Bug 根因

1. **SQLite 关联查询字段错误**：
   - **根因**：chapters 表结构仅包含 olume_id，作品层级位于 olumes.work_id。原实现直接执行 SELECT c.id, c.work_id FROM chapters c ... 触发 sqlite3.OperationalError: no such column: c.work_id。
   - **修复**：联表 olumes 获取正确的 work_id。
2. **导入与参数错配**：
   - **根因**：extract_structured_assets_from_text 位于 pp/workflow_assets.py，而非 pp/services/output_normalizer.py；sync_assets_to_database 签名仅接收 (db, work_id, data: SyncAssetsIn)，不能直接向函数传递 chapter_id=chapter_id。
   - **修复**：修正导入模块，并将 chapter_id 组装在 SyncAssetsIn 内。

---

## 四、遗留风险与后续规划

1. **散文模式资产识别依赖**：
   - 纯散文正文抽取依赖正则模式与关键词启发式规则，相比携带契约注释块（<!-- MOYU:ASSETS ... -->）其识别精确度略有降低；建议在前端引导作者配合工作流技能块。
2. **LLM 异步审计网络鲁棒性**：
   - 本次测试针对 POST /api/audit/run 采用 monkeypatch 验证字段契约，实测真实大模型输出时需注意长文本分片与超时降级机制（Phase 3 优化项）。
