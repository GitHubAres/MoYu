# 墨语 MoYu 叙事产物写回与全站产物规范任务书（J/K/L 组）

> 版本：v1.0（2026-10-09）
> 执行者：Codex
> 前置状态：I 组已收尾，pytest 基线 **196 全绿**，工作区干净
> 总目标：让工作流/AI 生成的叙事类产物（梗概、正文）能写回功能模块；把 MOYU:ASSETS 契约从“工作流内部约定”升级为全站《墨语产物交付规范》
> 执行顺序：**J（写回通道）→ K（契约扩展）→ L（注入统一）**。通道不通，规范再好产物也落不了地。

---

## 0. 背景与断点（已核验，勿重复排查）

| 断点 | 位置 | 现状 |
|---|---|---|
| 已有大纲节点梗概被去重跳过 | `app/services/plot_service.py:75-91` | dup 命中即 continue，synopsis 永不更新 |
| 绑定节点只读不写 | `app/workflow_engine.py:203`（读侧装配）；`app/services/plot_service.py:68`（仅作新节点父级） | 无写回 synopsis 路径 |
| 章节写回是尸体功能 | `app/workflow_assets.py:1015-1029`（`apply_to_chapter` 已实现） | 前端零调用 |
| 散文无出口 | `static/js/pages/workflows.js:1081` `renderRunStep` | 步骤输出只能回看，无复制按钮 |
| 契约只覆盖台账资产 | `app/services/output_normalizer.py:162` `valid_keys` | 无章节梗概等叙事产物键 |
| 契约注入仅工作流引擎 | `app/workflow_engine.py:288-305` 关键词触发 | 其他 AI 入口无注入 |

---

## 1. 红线（全程有效）

1. **AI 内容先预览后写入**：J-2/J-3 的写回按钮必须有 confirm 二次确认；K-1 的梗概更新必须经同步弹窗人工勾选后才发生。
2. `plot_service.py` 的 dup 更新分支**仅在传入 synopsis 非空时执行**；绝不把已有非空梗概覆盖为空。
3. **正文长文不进契约块**（防大 JSON 写崩）：正文走 J-3 的 `apply_to_chapter` 通道；契约块只放指向性产物（梗概、台账资产）。
4. 契约键**只增不改不删**：`valid_keys` 只追加，既有 6 键与解析行为不得变（`tests/test_output_contract.py`、`tests/test_workflow_contract.py` 全绿不动）。
5. 不新增表/列，不动 `data/`，无需 MIGRATIONS。
6. 测试基线 196 只增不减；每完成一个实现阶段运行 `.venv/Scripts/python.exe -m pytest -q`。
7. 提交信息前缀：J 组 `fix(narrative-Jn)`、K 组 `feat(contract-Kn)`、L 组 `refactor(inject-Ln)`。
8. 断言先行：每组先写断言跑出红，再实现转绿（J-2/J-3/J-4 为纯前端的部分按任务书说明处理）。

---

## 2. 阶段 J：叙事产物写回通道（L3 收口层）

### J-1a 断言（先红）
文件：`tests/test_workflow_auto_intake_triad.py`（追加）
- 用例 1：作品中已存在大纲节点（title="第一章 剑斩云霄"，synopsis="旧梗概"）→ 调 `batch_sync_triad_assets` 传入同名节点 + 新 synopsis="新梗概" → **期望**：节点 synopsis 变为"新梗概"，返回 stats 含 `outline_synopsis_updated == 1`。
- 用例 2：同上但传入 synopsis="" → **期望**：旧梗概原样保留（不被清空），`outline_synopsis_updated == 0`。
- 用例 3：节点不存在 → 维持 INSERT 原行为，`outline_nodes_added == 1` 且 `outline_synopsis_updated == 0`。
- 现状应红：`plot_service.py:75-91` dup 分支直接跳过，无更新、无该统计键。

### J-1 实现
- `app/services/plot_service.py:75-91`：dup 命中且传入 `synopsis` 非空且与现有不同 → `UPDATE outline_nodes SET synopsis = ? WHERE id = ?`；stats 初始化加 `"outline_synopsis_updated": 0` 并累加。空 synopsis 一律不更新（红线 2）。
- `app/workflow_assets.py:808` 附近：summary 初始化加 `"outline_synopsis_updated": 0`；`:972` 后追加 `summary["outline_synopsis_updated"] += triad_stats.get("outline_synopsis_updated", 0)`。
- `static/js/pages/workflows.js:1024` tips 区：追加 `if (sm.outline_synopsis_updated) tips.push("梗概更新+" + sm.outline_synopsis_updated)`。
- `static/js/pages/workflows.js:878` 大纲分组卡片副标题：注明"同名节点将更新其梗概（空梗概不覆盖）"。
- 提交：`fix(narrative-J1): 已存在大纲节点梗概同步更新与统计透出`。

### J-2a 断言
- 检查 `tests/` 是否已覆盖 `PATCH /outline/{id}` 更新 synopsis（`app/api/outlines.py:79`/`:106` 字段已存在）；未覆盖则在 `tests/test_works.py` 或合适文件补一条：PATCH  synopsis 后 GET 读回一致。**若已覆盖则跳过，任务书注明即可。**

### J-2 实现（纯前端，手动验收）
- `static/js/pages/workflows.js:1081` `renderRunStep` 操作区：当 `run.outline_node_id` 存在时（run 详情已返回该字段与 `outline_node_title`，见 `app/api/workflows.py:212-216`/`:419`）追加按钮「写入目标节点梗概」：
  - 点击 → `ui.confirm` 显示"将把本步骤输出写入节点「{outline_node_title}」的核心剧情梗概，覆盖现有梗概"；
  - 确认后 `api.patch("/outline/" + run.outline_node_id, { synopsis: stripMoyuAssetsBlock(s.output).trim() })`，成功 toast。
  - 输出剥离契约块后为空则禁用该按钮。
- 手动验收：跑一次绑定大纲节点的工作流 → 步骤产出点按钮 → 大纲页梗概卡（`static/js/pages/outline.js:213`）可见新梗概。
- 提交：`fix(narrative-J2): 步骤产出一键写入目标大纲节点梗概`。

### J-3a 断言（保底覆盖）
文件：`tests/test_workflows.py`（追加）
- 建 run（带 chapter_id）→ 调 `sync_assets_to_database`（`apply_to_chapter=True`, `chapter_content="新正文"`，资产全空）→ **期望**：chapters.content 已更新、chapter_versions 新增一条 `source='workflow'`、`summary["chapter_synced"] is True`。覆盖 `app/workflow_assets.py:1015-1029` 既有实现，防回归。

### J-3 实现（纯前端）
- `renderRunStep` 操作区：当 `run.chapter_id` 存在时追加按钮「写入目标章节正文」：
  - `ui.confirm` 文案必须写明"将覆盖章节当前正文，旧稿自动存为版本（可在版本快照中恢复）"；
  - 确认后调 `POST /workflows/runs/{runId}/steps/{seq}/sync-assets`，body：`{ apply_to_chapter: true, chapter_content: stripMoyuAssetsBlock(s.output), 其余资产键全空数组 }`；
  - 成功 toast 含"已写入章节并沉淀版本"。
- 提交：`fix(narrative-J3): 步骤产出一键写入目标章节正文并沉淀版本`。

### J-4 实现（纯前端）
- `renderRunStep` 输出展示区（`static/js/pages/workflows.js:1131` pre 附近）加「复制」按钮：`navigator.clipboard.writeText(stripMoyuAssetsBlock(s.output))`，成功 toast"已复制"。
- 提交：`fix(narrative-J4): 步骤输出增加复制按钮`。

---

## 3. 阶段 K：契约扩展叙事产物键（L1 规范层）

### K-1a 断言（先红）
文件：`tests/test_output_contract.py`（追加）
- 契约块 JSON 含 `"chapter_synopses": [{"node_title": "第一章 剑斩云霄", "synopsis": "……"}]` → `extract_structured_assets_from_text` 结果中该键被保留且条目经 `sanitize_asset_item` 校验（空 node_title/空 synopsis/超长 → 进 `_rejected`）。
- 同步用例（`tests/test_workflows.py` 追加）：chapter_synopses 匹配到同名节点 → synopsis 更新、`summary["chapter_synopses_updated"] == 1`；匹配不到 → `rejected_count` +1、原因含"未找到同名大纲节点"。
- 现状应红：`app/services/output_normalizer.py:162` `valid_keys` 无此键。

### K-1 实现
- `app/services/output_normalizer.py:162`：`valid_keys` 追加 `"chapter_synopses"`（只追加，红线 4）。
- `app/workflow_assets.py`：新增 `AssetChapterSynopsisIn(BaseModel): node_title: str; synopsis: str`；`SyncAssetsIn`（`:65`）加 `chapter_synopses: list[AssetChapterSynopsisIn] = []`；summary 加 `"chapter_synopses_updated": 0`。
- 同步逻辑：按 `work_id + node_title` 精确匹配 `outline_nodes` → 命中且 synopsis 非空 → UPDATE（与 J-1 同语义：空不覆盖）；未命中 → `rejected_count += 1`，`rejected_items` 记原因"未找到同名大纲节点：{node_title}"。
- 抽取/合并链路（`extract_structured_assets_from_text`、`merge_assets`）同步支持该键，去重键 = node_title。
- 前端：`showAssetSyncModal`（`static/js/pages/workflows.js:681`）加「章节梗概」分组卡片（可勾选、可编辑 synopsis）；tips 区加 `梗概更新+N`（复用 J-1 字段，chapter_synopses_updated 并入展示即可）。
- 提交：`feat(contract-K1): 契约新增 chapter_synopses 章节梗概产物键与同步链路`。

### K-2 实现（规范单一真源 + 手册归口）
- 新建 `docs/墨语产物交付规范.md`，内容：
  1. MOYU:ASSETS 契约块完整格式与全部键清单（含新增 chapter_synopses）；
  2. **归宿映射表**：entities→万相谱、relations→关系图谱、timeline_events→时间线、foreshadows→伏笔看板、outline_nodes→大纲树（新建/梗概更新）、notes→万相谱术语、work_info→作品信息、chapter_synopses→大纲节点梗概卡；
  3. **边界规则**：正文长文不进契约块（走 apply_to_chapter）；简介 = `work_info.intro`（不新增 blurb 键）；每个任务只交付声明的产物键，其余留空数组。
- `app/workflow_engine.py:291-305` 契约模板：键清单补 `chapter_synopses` 及一句话说明。
- `app/builtin_skill_data.py`（14 处 MOYU:ASSETS 段）：统一改为"按《墨语产物交付规范》交付与本手册相关的产物键"的简述 + 该手册相关键清单，措辞全手册一致。
- 提交：`feat(contract-K2): 墨语产物交付规范单一真源与14份手册归口`。

---

## 4. 阶段 L：注入统一（L2 注入层）

### L-1a 断言（先红）
文件：`tests/test_output_contract.py`（追加）
- 新函数 `build_contract_clause(required_keys: list[str]) -> str`（建议放 `app/services/output_normalizer.py`）：
  - 传入 `["outline_nodes", "chapter_synopses"]` → 返回文本含契约块模板且只列这两个键；
  - 传入全量 7 键 → 模板含全部键；
  - 模板必须含开闭标记 `<!-- MOYU:ASSETS` 与 `MOYU:ASSETS -->`（闭合格式与 `extract_assets_block` 正则兼容，注意单标记 `-->` 容错已在 H-2 支持）。

### L-1 实现
- `app/services/output_normalizer.py` 新增 `build_contract_clause`。
- `app/workflow_engine.py:288-305`：改调 `build_contract_clause`；关键词映射扩展——instruction/sys_prompt 含"梗概"→ required_keys 加 `chapter_synopses`；含"大纲/细纲/分卷"→ 加 `outline_nodes`；既有台账关键词维持映射到原 6 键。无任何命中时不注入（现状行为不变）。
- 提交：`refactor(inject-L1): 契约注入模板函数化并按任务声明产物键`。

### L-2 实现（范围收敛，含明确排除项）
- 本轮**只**做：注入函数统一 + 引擎切换 + 关键词映射扩展（L-1 内容）。
- **明确不注入**：修撰使多轮对话（`app/api/chat.py`）与划词/一键生成（`app/features.py:374`）——前者是自由对话、后者是纯文本改写，强制契约块会破坏体验且产物无结构化归宿；其产物采纳路径单独立项（记入本文档第 5 节 R-4）。
- 大纲页 AI 推演（`static/js/pages/outline.js:460-530`）维持局部"并入梗概"通道不变。
- 提交：并入 L-1 提交即可，不单独提交。

### L-3 回归
- `.venv/Scripts/python.exe -m pytest -q` 全绿，总数 ≥ 196 + 本轮新增断言数；`tests/test_doc_integrity.py` 不得因新增 `docs/墨语产物交付规范.md` 而失败（文档无控制字符）。

---

## 5. 遗留议题（本轮不做）

- **R-4**：修撰使对话/划词生成的产物采纳路径（"采纳到章节/梗概"动作化设计）——需产品层决策，另行立项。

## 6. 验收清单

- [ ] J-1a 三用例先红后绿；已有节点梗概可更新、空梗概不覆盖
- [ ] J-2 手动验收通过（梗概卡可见写入结果）
- [ ] J-3a 覆盖 apply_to_chapter；J-3 手动验收章节写入+版本沉淀
- [ ] J-4 复制按钮可用
- [ ] K-1a 先红后绿；chapter_synopses 解析/合并/同步/拒绝全链路
- [ ] K-2 规范文档落库，14 份手册措辞统一
- [ ] L-1a 先红后绿；引擎改用注入函数；含"梗概"的 instruction 触发 chapter_synopses 键
- [ ] pytest 全绿且总数增加；工作区无任务书外文件改动
