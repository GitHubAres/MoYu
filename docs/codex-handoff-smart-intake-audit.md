# 墨语 MoYu ·「智能收录 + 悖论体检 + 编辑器增强」Codex 接管计划书

> 本文件用于把已完成的 Phase 1+2 代码与剩余工作移交给 Codex。
> **单条启动指令**见同级 `codex-task-runtime-verify.md`（Codex 第一步请先执行它）。
> 本计划书自包含，新会话无需回看对话历史即可接力。

---

## 1. 背景与用户三愿望

用户在小说写作工作台（墨语 MoYu，路径 `D:\KimiCode工作区`）写作时希望：
1. **自动识别并收录**新增的 人物 / 地点 / 关系 / 道具 到「万象谱 / 关系图谱 / 伏笔看板 / 时间线 / 大纲」。
2. **自动识别悖论/矛盾**的故事内容。
3. **编辑器增强**：前后对比、AI 识别到问题处自动标注填充颜色。

经核查，约 80% 基础设施已存在（实体识别、版本 diff、audit 接口、全套资产管线），方案定位为「补齐缺口 + 串起来 + 编辑器内联化」，而非重写。详细方案见 `docs/editor-smart-intake-design.md`，中枢层根因见 `docs/workflow-ingest-diagnosis.md`。

---

## 2. 已完成（Phase 1 + Phase 2，代码层面）

### 2.1 后端
| 改动 | 文件 / 位置 | 说明 |
|---|---|---|
| 新增 `POST /chapters/{id}/smart-intake` | `app/api/works.py:295` `chapter_smart_intake` + `ChapterSmartIntakeIn` | 复用 `extract_structured_assets_from_text` 全量抽取 + `canonicalize_assets` 归一 + 与现有库比对标 `is_new`；`auto_commit=true` 时走 `sync_assets_to_database` 落库并关联本章。覆盖 entities/relations/foreshadows/timeline_events/outline_nodes/notes。 |
| 修复 `location→term` 归一 bug | `app/workflow_assets.py` `CATEGORY_ALIASES`（约 :818）增 `"location":"place"`、`"lore":"term"` | 地点/场景类实体不再被错存为术语（P0 中枢 bug）。 |
| 同步修复契约路径枚举 | `app/services/output_normalizer.py` `canonicalize_assets` 的 `alias`（约 :370）增同样两条 | 契约块解析与 sync 路径枚举一致。 |

### 2.2 前端（`static/js/pages/workbench.js`）
| 新增函数 | 行 | 作用 |
|---|---|---|
| `runSmartIntake` | 1607 | 调 smart-intake（auto_commit=false），有新增则弹面板 |
| `INTAKE_MODULES` + `openSmartIntakeDialog` | 1620 / 1629 | 按模块分组预览 `is_new` 候选、勾选后 `auto_commit=true` 落库 |
| `showInlineDiff` | 1708 | 复用 `lineDiff`/`renderDiffLines`（workbench.js:2199/2218）内联双栏对比上一版本 |
| `runChapterAudit` | 1747 | 调 `POST /audit/run` |
| `clearAuditHighlights` / `applyAuditHighlights` | 1761 / 1768 | 用 `mark[data-issue]` 包裹 issue.quote 染色（high 红 / medium 橙 / low 黄） |
| `onAuditMarkClick` | 1798 | 点击高亮弹问题卡 |
| `scheduleIntakeHint` | 1809 | 保存后 debounce 自动探测，仅在确有新增时浮出提示 |

接线：工具栏新增 3 按钮（智能收录 / 章节体检 / 对比上一版 @1316）；生命周期钩子 `input→scheduleIntakeHint @256`、`click→onAuditMarkClick @264`、`openChapter→clearAuditHighlights @393`。

### 2.3 已做的静态回归（全绿）
- `node --check static/js/pages/workbench.js` → 通过（修复了 1695 行模板字符串以 `"` 收尾导致的未闭合 bug）。
- `python -m py_compile app/api/works.py app/workflow_assets.py app/services/output_normalizer.py app/api/audit.py` → 通过。
- 契约核对：前端 `api.post`（`api.js:15`）自动拼 `/api`；smart-intake 响应字段、audit `_normalize`（`audit.py:85`）字段与前端读取完全一致；URL/路由前缀对齐。

---

## 3. 待办路线图（优先级排序）

### P0 — 运行时端到端验证（**Codex 第一步，见 `codex-task-runtime-verify.md`**）
- 写集成测试覆盖 `smart-intake`（auto_commit 两态）、`is_new` 判定、`location→place` 归一落库、`audit/run` 的 quote/字段（mock LLM）。
- 跑全量相关回归；修复测试中发现的一切 bug。
- 这是唯一尚未覆盖的验证环节（代码静态全绿，但从未真机/集成跑过）。

### P1 — Phase 3 自动化与持久化（`editor-smart-intake-design.md` §4 Phase 3）
- 设置开关：保存后自动体检 / 高置信度自动收录 / 染色配色（目前默认手动 + 仅提示不静默落库）。
- 审计问题可选持久化：新增 `chapter_audit_issues` 表（含 quote_offset），重新打开章节时恢复高亮。
- 边界：超长章节分片审计；识别置信度阈值；重复实体去抖（保存后提示用 `intakeHintShownFor` 已做简单去抖）。

### P1 — 编辑器高亮 / diff 边界打磨
- `applyAuditHighlights` 用 `range.surroundContents` 包裹 quote，跨 DOM 节点（如 quote 被 `<b>` 等拆分）时当前 `try/catch` 跳过——需更稳健的「逐文本节点切片」定位，避免长 quote 染不上。
- `showInlineDiff` 当前对比「最近一次版本」；确认 `GET /chapters/{id}/versions` 与 `GET /versions/{vid}` 的返回字段与 `renderDiffLines` 入参一致（已代码核对，需运行确认）。

### P2 — 中枢深层修复（来自 `workflow-ingest-diagnosis.md`，独立于本特性）
- notes 独立模块：目前 sync 时 notes→entities `category='term'` tag='世界观'，与术语混在一起；建议独立表/模块。
- 关系端点未知时不再一律建 `character`（`workflow_assets.py` 约 :976/984），按上下文推断 category。
- `sanitize_asset_item`（`output_normalizer.py:221`）标题>30 字直接丢 → 放宽阈值并展示 rejected。
- 工作流完成自动归档：`workflow_engine` 跑完应自动调 `sync_assets_to_database`，而非仅靠前端 `POST /sync-assets` 人工触发。

> P2 属于既有中枢重构，可单独排期，不在本特性的阻塞路径上。

---

## 4. 验收口径 / 测试基线
- 集成测试建议落 `tests/test_smart_intake.py`，复用 `tests/conftest.py` 的 `client` 夹具与 `make_wvc()` 快捷建 作品→卷→章。
- audit 端点经 `httpx.AsyncClient.post` 调 LLM（`audit.py:141`），测试用 monkeypatch 返回带 `issues` 的假响应。
- 全量相关回归基线（含历史契约测试）：
  ```bash
  .venv\Scripts\python.exe -m pytest tests/test_smart_intake.py tests/test_works.py tests/test_versions.py tests/test_output_contract.py tests/test_skill_contract_adapter.py tests/test_workflow_contract.py tests/test_workflows.py tests/test_v11_features.py -q
  ```

## 5. 红线（交接约束）
- 不 `git commit` / `push`，改动留工作区由用户验收。
- 不引入新依赖；不重写已存在能力（detect-unregistered / batch-intake / versions diff / audit 保留复用）。
- 不动无关模块（chat / exporter / hotradar / 炼丹炉）。

## 6. 参考文件清单
- `docs/editor-smart-intake-design.md` — 总体方案与 Phase 计划
- `docs/workflow-ingest-diagnosis.md` — 中枢 vs skill 责任划分、P0 归一 bug
- `docs/codex-task-runtime-verify.md` — **Codex 启动指令（第一步）**
- 代码：`app/api/works.py`、`app/workflow_assets.py`、`app/services/output_normalizer.py`、`app/api/audit.py`、`static/js/pages/workbench.js`、`static/js/api.js`、`tests/conftest.py`
