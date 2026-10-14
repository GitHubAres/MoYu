# 墨语 MoYu · 运行时端到端验证「智能收录 + 悖论体检 + 编辑器增强」（P0，交给 Codex 执行）

## ⚠️ 执行方式（必须遵守）
- **直接开始执行，禁止长时间分析**。本文件已给出全部所需信息，以此为准即可，不必全文通读其他文件。
- 每完成一步就落实（改代码 + 跑测试），不要攒到最后。
- **不 `git commit` / `push`**，改动留在工作区由用户验收。

## 任务来源
依据 `docs/codex-handoff-smart-intake-audit.md` 的 **P0**：Phase 1+2 的代码改动已完成且**静态回归全绿**（前端 `node --check` 通过、后端 `py_compile` 通过、前后端契约字段已逐一核对），但**从未真机/集成跑过**。本任务目标：用集成测试把新增的 `smart-intake` 端点与 `audit/run` 端到端跑通，并修复测试中发现的一切 bug，把"静态通过"升级为"运行时通过"。

## 范围（本次必须完成）

### A. 新增集成测试 `tests/test_smart_intake.py`
复用 `tests/conftest.py` 的 `client` 夹具与 `make_wvc(client)`（自动建 作品→卷→章，返回 `(work, volume, chapter)`）。以下用例全部用 `client` 发起真实 HTTP 请求：

1. **候选预览（auto_commit=false）**：
   - 用 `make_wvc` 建好章节，正文取一段含「新人物 + 新地点 + 新伏笔」的文本（例如含 `<!-- MOYU:ASSETS ... -->` 契约块，或纯散文，依赖 `extract_structured_assets_from_text` 抽取）。
   - `POST /api/chapters/{chapter.id}/smart-intake`，body `{"content": <正文>, "auto_commit": false}`。
   - 断言：`status_code==200`；响应含 `committed=false` 与 `assets` 对象，且 `assets` 至少含键 `entities / relations / foreshadows / timeline_events / outline_nodes / notes`；库为空时，正文里出现的人物名在 `assets["entities"]` 中存在且 `is_new==True`。

2. **确认落库（auto_commit=true）**：
   - 同一正文，`auto_commit=true` 再发一次。
   - 断言：响应 `summary` 中至少 `entities_added>0`（或对应分类 `>0`）。
   - 关键落库校验：`GET /api/works/{work.id}/entities` 的返回里**确实多出**该人物实体（数量比对：落库前后 +1）。证明走的是 `sync_assets_to_database` 真实写库，而非仅返回候选。

3. **is_new 判定正确性**：
   - 先经 auto_commit=true 落库某个实体；之后再用含该实体的正文跑 auto_commit=false，断言该实体的 `is_new==False`（已存在于库）。

4. **location→place 归一回归（P0 bug 修复验证）**：
   - 构造契约块 `<!-- MOYU:ASSETS {"entities":[{"name":"青云山","category":"location","content":"一座仙山"}]} MOYU:ASSETS -->` 作为正文，`auto_commit=true`。
   - 断言：`GET /api/works/{work.id}/entities` 中名为「青云山」的实体 `category == "place"`（**不是** `"term"`）。
   - 另加一条纯单元断言：`from app.workflow_assets import normalize_category; assert normalize_category("location")=="place"`。

5. **audit/run 字段契约（mock LLM）**：
   - `audit.py:141` 经 `httpx.AsyncClient.post` 调 LLM。用 monkeypatch 让 `httpx.AsyncClient.post` 返回 canned 响应，其 `choices[0].message.content` 为一段 JSON，含数组：
     `[{"type":"矛盾","severity":"high","entity":"李雷","issue":"前后年龄不一致","quote":"李雷今年十八岁……","chapter_title":"第一章"}]`。
   - `POST /api/audit/run`，body `{"work_id": work.id, "chapter_ids":[chapter.id]}`。
   - 断言：`status_code==200`；`issues` 数组非空；`issues[0]` 含 `quote / type / severity / issue`（前端 `applyAuditHighlights` 正是读取这些字段做染色，`audit.py:_normalize` 应已产出）。

### B. 修复测试中发现的一切 bug
- 若 smart-intake 落库字段错、is_new 判定反、location 归一未生效、audit 字段缺失等，直接修 `app/api/works.py` / `app/workflow_assets.py` / `app/services/output_normalizer.py` / `app/api/audit.py`，**不要动前端**（前端静态已通过，留给后续 Phase 3）。
- 若测试本身假设有误（如抽取器对散文人物识别不稳定），可把用例 1/2 改为用**契约块**触发（确定性更强），但必须保留"真实 HTTP + 真实写库"的断言。

## 红线
- 不 `git commit` / `push`。
- 不引入新依赖；不重写已存在能力（detect-unregistered / batch-intake / versions diff / audit 保留复用）。
- 不动 `static/js/` 前端文件、不动 chat / exporter / hotradar / 炼丹炉 等无关模块。
- 不修改 8 产物键 schema（work_info/entities/relations/timeline_events/foreshadows/outline_nodes/chapter_synopses/notes）。

## 完成标准
1. 新增 `tests/test_smart_intake.py` 全部用例通过；并跑全量相关回归（期望全绿）：
   ```bash
   .venv\Scripts\python.exe -m pytest tests/test_smart_intake.py tests/test_works.py tests/test_versions.py tests/test_output_contract.py tests/test_skill_contract_adapter.py tests/test_workflow_contract.py tests/test_workflows.py tests/test_v11_features.py -q
   ```
2. 写交付汇报 `docs/codex-report-runtime-verify.md`，含：① 执行的测试命令与结果摘要；② 改动文件清单与关键 diff 说明；③ 若发现并修复了 bug，说明根因；④ 遗留风险（如散文识别不稳定、audit 仅 mock 未接真 LLM）。
3. 在 stdout 输出 `TASK_DONE` 标记。
