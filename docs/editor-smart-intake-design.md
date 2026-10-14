# 写作工作台「智能收录 + 悖论体检 + 编辑器增强」设计方案

> 目标：把用户在写作过程中「识别新内容→收录进万象谱/关系图谱/伏笔看板/时间线/大纲」「自动检测悖论」「编辑器增强（前后对比 / AI 问题染色）」三件事做成一个连贯的体验。
> 关键结论：**约 80% 基础设施已存在**，本方案以「补齐缺口 + 串起来 + 编辑器内联化」为主，避免重复造轮子。

---

## 1. 现状盘点（已具备 / 缺口）

| 能力 | 现状 | 位置 | 缺口 |
|---|---|---|---|
| 章节实体识别 | ✅ 手动「识别」按钮 | workbench.js:1280 → `POST /entities/detect-unregistered` | 仅实体；不含关系/伏笔/时间线/大纲 |
| 实体批量收录 | ✅ 预览后确认入库 | `POST /entities/batch-intake` (api/entities.py:471) | 仅 entities；不写关系/伏笔等 |
| 前后对比 | ✅ 独立「版本快照」页双栏 diff | versions.js + `diffLines` LCS | 不在编辑器内；需跳页 |
| 悖论/一致性检查 | ✅ 手动 `POST /audit/run` | api/audit.py（返回 type/severity/quote/chapter_title） | 手动；结果不回显到编辑器 |
| 全套资产解析管线 | ✅ `extract_structured_assets_from_text` + `sync_assets_to_database` | workflow_assets.py（覆盖 entities+relations+timeline+foreshadow+outline+notes） | 目前仅工作流路径用，章节未复用 |

**核心洞察**：章节识别接口只用了 `extract_structured_assets_from_text` 的 `entities` 部分，丢掉了它本可产出的 **relations / foreshadows / timeline_events / outline_nodes**。悖论接口已有且返回「原文引用 quote」，正好可用于编辑器染色，但从未被前端可视化。

---

## 2. 用户愿景 → 方案映射

### A. 智能识别与收录（补全 + 自动化）
- **复用** `extract_structured_assets_from_text` 全量抽取（不止实体），经 `canonicalize_assets` 归一后，走 `sync_assets_to_database`（与工作流同一条受信任管线），一次把 人物/地点/关系/道具/伏笔/时间线/大纲 全收。
- **新增** 章节级「收录」端点（或扩展现有 detect-unregistered 返回结构），输出分模块候选清单 + 与已有库的增量（is_new 标记），前端做「预览 → 勾选 → 确认收录」面板。
- **自动触发**：章节保存（saveContent）后闲时（debounce）自动跑一次识别，仅在「确有新增资产」时，在编辑器旁浮出「发现 N 条新设定，点击收录」提示（默认不自动落库，避免污染；可由设置开关切换为「高置信度自动收录」）。
- **关系补全**：识别到的 relations 端点在库中不存在时，先建为对应分类实体（沿用 sync 现有逻辑），再写 entity_relations → 关系图谱自动长出。

### B. 悖论 / 一致性体检（自动 + 编辑器内联）
- **复用** `POST /audit/run`：传入本章 chapter_id（可含前几章作上下文），返回问题数组。
- **自动轻量触发**：保存后可一键/自动跑「本章体检」；成本敏感，默认手动，设置可开「每章保存后自动体检」。
- **结果内联化**：把每条 issue 的 `quote`（原文引用）作为锚点，在编辑器内对对应文本片段做 **彩色高亮**（high=红 / medium=橙 / low=黄），点击高亮弹出问题卡（type/severity/issue/建议）。这是目前**完全缺失**的能力。

### C. 编辑器增强（前后对比 + AI 染色）
- **内联前后对比**：复用现有 `diffLines` LCS（workbench.js:1954 / versions.js:293）。在编辑器内提供「对比上一版」浮层：左=上一版，右=当前，增删行着色（`diff-add` 绿 / `diff-del` 红）。无需跳出版本页。
- **AI 问题染色标注**：见 B。编辑器渲染层需在文本之上叠加高亮层（标准做法：透明 textarea + 背后 mirror div，或在 contenteditable 下直接包 `<mark>` 片段）。高亮可叠加在「对比」与「体检」两种模式下。

---

## 3. 技术实现要点

### 3.1 后端
- **新增 `POST /chapters/{id}/smart-intake`**（或扩展 detect-unregistered）：
  - 入参：`content`（本章正文）、`auto_commit: bool`。
  - 逻辑：`extract_structured_assets_from_text(content, "chapter")` → `canonicalize_assets` → 与 `entities/relations/foreshadows/timeline/outline` 现有库比对（复用 api/workflows.py:372-386 的 existing_* 查重逻辑）→ 返回结构化候选：`{entities:[{...is_new}], relations:[...], foreshadows:[...], timeline_events:[...], outline_nodes:[...], notes:[...]}`。
  - `auto_commit=true` 时直接调 `sync_assets_to_database(db, work_id, body, chapter_id=id)` 落库；否则仅返回候选供前端确认。
- **复用** `sync_assets_to_database`（workflow_assets.py:843）作为唯一落库入口，保证与万相谱/关系图谱/伏笔看板/时间线/大纲口径一致。**顺带修复已知 bug**：`normalize_category` 的 `location→term` 错配（详见 workflow-ingest-diagnosis.md §2.2）应在本端点落地前一并修。
- **审计内联**：`POST /audit/run` 已满足；新增可选 `return_quotes: true`（默认即返回 quote），前端直接用 quote 做锚点。

### 3.2 前端
- **workbench.js** 新增：
  - `runChapterIntake()`：调 smart-intake，弹「收录面板」（按模块分组、is_new 高亮、可勾选）。
  - 保存后 debounce 自动调用，仅在 `is_new>0` 时浮出提示条。
  - `runChapterAudit()`：调 `/audit/run`，拿到 issues 后调用 `applyIssueHighlights(issues)`。
  - `applyIssueHighlights(issues)`：用 quote 在编辑器高亮层定位并包 `<mark class="audit-high-{severity}">`；点击弹出问题卡。
  - `showInlineDiff()`：复用 `diffLines`，对当前正文 vs 最近一次 chapter_versions 渲染内联双栏/行内 diff。
- **编辑器高亮层**：需确认编辑器 DOM（textarea 或 contenteditable）。textarea 方案用「透明 textarea + 背后同步滚动的 mirror div」叠 `<mark>`；contenteditable 直接内联 `<mark>`。此为唯一需适配的渲染细节。

### 3.3 数据/存储
- 现有表已足够：`entities / entity_relations / foreshadows / timeline_events / outline_nodes / chapter_entities / chapter_versions`。
- 审计问题可选择性落 `notes` 或新增 `chapter_audit_issues` 表（含 quote_offset 以便重新打开时恢复高亮）。建议先不落库，仅会话内展示；后续再决定持久化。

---

## 4. 分阶段实施计划

### Phase 1（高杠杆，建议先做）
1. 后端 `POST /chapters/{id}/smart-intake`（复用 extract+cano+sync），**覆盖关系/伏笔/时间线/大纲**（补全最大缺口）。
2. 修 `normalize_category` 的 `location→place` 错配（P0 bug，顺带）。
3. 前端 workbench「收录面板」+ 保存后自动提示（手动确认落库）。
→ 直接解决用户「关系/伏笔没被识别收录」的核心痛点。

### Phase 2（体验闭环）
4. 编辑器内联「对比上一版」浮层（复用 diffLines）。
5. `runChapterAudit` + `applyIssueHighlights`：把 `/audit/run` 的 quote 染成彩色高亮 + 问题卡。
→ 解决「前后对比」「AI 问题染色标注」。

### Phase 3（自动化与打磨）
6. 设置开关：保存后自动体检 / 高置信度自动收录 / 染色配色。
7. 审计问题可选持久化（chapter_audit_issues）+ 重新打开恢复高亮。
8. 边界：超长章节分片审计；识别置信度阈值；重复实体去抖。

---

## 5. 风险与注意
- **自动落库污染**：默认仅「预览确认」，不做静默自动写库；关系端点未知实体建为 character 的老问题需在 sync 路径一并收敛（diagnosis §2.6）。
- **AI 成本**：每章体检是一次 LLM 调用，需默认手动 + 设置可控；可对长文分片。
- **编辑器高亮层适配**：textarea 高亮需 mirror 层，属于本方案唯一非平凡前端工作，建议 Phase 2 先做最小可用（仅当前可见片段高亮）。
- **不要重写已有能力**：detect-unregistered / batch-intake / versions diff / audit 均保留复用，新端点与之并存，避免回归。

---

## 6. 与既有诊断的关系
- 本方案直接消费并修复 `workflow-ingest-diagnosis.md` 中确认的中枢 bug（`location→term` 错配、关系端点硬建 character）。
- 章节「识别」能力从「仅实体」升级为「全资产」，正好弥补 diagnosis 里「关系/伏笔/时间线未覆盖」的缺口。
- 悖论/一致性检测把早已存在但「藏在独立页、不回显」的 `/audit/run` 能力首次接到写作主场景。
