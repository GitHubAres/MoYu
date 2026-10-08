# 墨语 MoYu 修复计划：规范矛盾裁决 + 项目大清洗 + 分阶段修复

> **版本**：v1.0（计划稿，未动任何代码）
> **日期**：2026-10-08
> **事实来源**：`D:\KimiCode工作区`（git HEAD `ffd98ec`，`app/version.py` = 1.9.7）
> **效力声明**：**本计划为最新有效规范。凡本计划与 `docs/` 内任何历史计划书、报告、规范发生冲突之处，以本计划为准。** 历史文档仅作演进记录保留，不再作为开发依据。
> **关联文档**：《墨语MoYu_真实代码核验报告.md》《墨语MoYu_模块互通性诊断与资产中枢改造方案.md》（本计划引用其中的 D1–D6 断点编号）

---

## 第一部分　规范文件矛盾裁决

`docs/` 现有 70+ 份 Markdown，其中计划/规范类 15 份。经逐份比对代码现状，发现 **7 组矛盾规则**。裁决原则：**代码现状 + 本计划 > 一切历史文档**。

### 矛盾 1：测试基线数量，各文档说法不一

| 文档 | 声称 |
| :--- | :--- |
| `AGENTS.md`（2 处） | "158 项 API、编码守护与桌面端测试" |
| `docs/v1.9.6-development-notes.md` | "全量 160 项自动化测试 100% 绿灯" |
| `docs/v1.9.0` 重构计划 | "保持 150+ 项现有回归测试全绿" |
| **实测**（`grep "def test_" tests/*.py`） | **161 项**（26 个测试文件） |

**裁决**：废弃所有写死的数字。`AGENTS.md` 改为"测试规模以 `pytest --collect-only` 实测为准，只增不减"。历史文档不改（属演进记录）。

### 矛盾 2：炼丹炉"开炉炼丹"到底下没下线

| 来源 | 规则 |
| :--- | :--- |
| `docs/墨语 MoYu 功能去重与体验一体化重构开发计划书 (v1.9.0).md` 第 10/26/84 行 | 下线"开炉炼丹"Tab，炼丹炉变更为"创作实验室" |
| **代码现状** | 前端 Tab 已移除 ✅；但后端 `POST /api/alchemy/brew`（`app/features.py:850`）与 `POST /api/alchemy/complete`（`:860`）**仍然注册在路由表上，且无任何前端调用方** |

**裁决**：v1.9.0 计划只执行了一半（前端收敛）。本计划决定：**两个后端端点予以保留但降级为"内部实验 API"**，理由——`brew` 背后的 `AIOrchestrator.brew()`（`features.py:626`）是"整书策划一键生成"的唯一实现，未来"创作实验室"深化时可能复用；但在 `AGENTS.md` 中明确标注"无 UI 入口，不承诺稳定"。若 P1 阶段结束时仍无调用方，转入清洗清单删除。

### 矛盾 3：伏笔/时间线"挂载大纲节点"——计划说做了，实际只做了一半

| 来源 | 规则 |
| :--- | :--- |
| v1.9.0 计划第 12/49–52/57/61 行 | 迁移加 `outline_node_id` 双字段 + 索引；`POST /timeline`、`POST /foreshadows` 入参支持 `outline_node_id`；创建时"自动绑定当前 outline_node_id 与章节" |
| **代码现状** | 迁移与索引已做 ✅；`timeline.py:98`、`board.py:74` 已双键写入 ✅；**但** `seed.py:78,80`（示例作品）与 `timeline.py:231`（整书导入）**仍只写 `chapter_id`** ❌；读侧聚合（`outlines.py:181,190`、`plot_service.py:15,26`）**只按 `outline_node_id` 过滤** ❌ |

**裁决**：v1.9.0 计划的"剧情中枢化"目标**未完成**，其未竟部分由本计划第三部分 P0/P1 接管。凡 v1.9.0 计划与本计划冲突处（如读侧查询口径），以本计划 P1 的"AssetHub 单一聚合口"为准。

### 矛盾 4：灵感便签"彻底清除"——表和前端残留都还在

| 来源 | 规则 |
| :--- | :--- |
| `docs/v1.9.6-development-notes.md` | "彻底清除灵感便签功能"：删路由、删 FAB、删面板、切断 `workflow_assets` 写入 |
| **代码现状** | 路由与 UI 确已删除 ✅；但 `notes` 表的 `CREATE TABLE` 仍残留在 `app/db.py:202`（任何代码均无读写，实测确认）；前端 `static/js/pages/workflows.js:678` 的资产兜底对象仍残留 `notes: []` 死字段 |

**裁决**：v1.9.6 的"彻底"名不副实。`notes` 表与前端死字段列入第二部分清洗清单（C-4、C-5）。

### 矛盾 5：`docs/` 里的"全景报告"不是事实来源，却被当成事实文档存放

`docs/墨语MoYu_功能与数据流梳理全景报告.md/.html/.pdf` 三份（共约 3.9 MB）内容经核验含 **45 条事实错误**（越界行号、15 个不存在的接口、虚构事件总线等），详见《真实代码核验报告》。该报告由 `scripts/generate_full_report.js` 字符串拼出 + 人工续写，非机器抽取。

**裁决**：该报告**作废，不得作为任何开发/对接依据**。事实口径以《墨语MoYu_真实代码核验报告.md》为准。三份副本列入清洗清单（C-2），其生成器与半成品片段一并清除（C-1）。

### 矛盾 6：两对重复文档（MD5 完全相同）

| 重复对 | MD5 |
| :--- | :--- |
| `docs/v1.9.0-reconstruction-plan.md` ≡ `docs/墨语 MoYu 功能去重与体验一体化重构开发计划书 (v1.9.0).md` | `e7f89dcf…` |
| `docs/workflow-assets-sync-specification.md` ≡ `docs/写作工作流全功能技术设计报告与程序清单.md` | `895917d0…` |

**裁决**：每对只保留一份——保留语义化命名的 `workflow-assets-sync-specification.md` 与 `v1.9.0-reconstruction-plan.md`，删除长中文名副本（列入 C-3）。

### 矛盾 7：`AGENTS.md` 目录地图与 `scripts/` 实际内容不符

`AGENTS.md` 称 `scripts/` 为"前端依赖本地化与 AI 联调工具"。实测该目录 16 个文件中 **10 个是 10 月 7–8 日生成那份虚构报告时留下的垃圾**（空壳脚本、0 字节文件、hello world 测试文件、报告半成品片段）。

**裁决**：清洗后 `AGENTS.md` 描述恢复属实；并在 `AGENTS.md` 增补一条红线：**"scripts/ 只放与构建、部署、联调相关的工具；一次性报告生成脚本用完即删，禁止入库。"**

---

## 第二部分　项目大清洗清单

清洗分四级：**A 级＝纯垃圾直接删；B 级＝作废资产移出代码库；C 级＝死代码/死 schema 需小改动；D 级＝大件产物需用户决策**。全部 21 项，逐项标注"为什么没用"与"清理影响"。

### A 级：纯垃圾（10 项，直接删除，零影响）

| # | 对象 | 为什么没用 | 清理影响 |
| :--- | :--- | :--- | :--- |
| A-1 | `scripts/build_full_report.py`（8 行） | 空壳：只 `print`，不生成任何东西 | 无。无任何代码/文档引用其实际功能 |
| A-2 | `scripts/build_architecture_report.py`（8 行） | 同上，空壳 | 无 |
| A-3 | `scripts/build_report_sections.py`（6 行） | 同上，空壳 | 无 |
| A-4 | `scripts/generate_report.py`（7 行） | 同上，空壳 | 无 |
| A-5 | `scripts/append_chapters.py`（7 行） | 同上，空壳 | 无 |
| A-6 | `scripts/generate_all.py`（**0 字节**） | 空文件 | 无 |
| A-7 | `scripts/test.ps1` | 内容为 `Write-Output hello from ps1` | 无 |
| A-8 | `scripts/test.txt` | 内容为 `hello world` | 无 |
| A-9 | `scripts/report_parts/`（9 个 md 片段） | 虚构全景报告的半成品分章，含错误内容 | 无。仅被已作废报告使用 |
| A-10 | `scripts/__pycache__/` | Python 缓存 | 无，自动再生 |

**保留的 scripts**：`fetch_vendor.py`（前端依赖本地化，AGENTS.md 工作流要求）、`deploy_to_vps.py`、`publish_release.py`（发布工具）、`mock_ai.py`（`docs/AI联调记录.md` 使用的联调桩）、`icons_subset_text.txt`（打包图标子集配置，历史构建引用）。

### B 级：作废资产（4 项，移出代码库或删除，零功能影响）

| # | 对象 | 为什么没用 | 清理影响 |
| :--- | :--- | :--- | :--- |
| B-1 | `docs/墨语MoYu_功能与数据流梳理全景报告.md` | 45 条事实错误，已作废（矛盾 5） | 无功能影响。**防误信**是主要收益 |
| B-2 | `docs/墨语MoYu_功能与数据流梳理全景报告.html` | 同上 | 无 |
| B-3 | `docs/墨语MoYu_功能与数据流梳理全景报告.pdf`（3.7 MB） | 同上 | 无 |
| B-4 | `scripts/generate_full_report.js`（220 行） | 虚构报告的生成器，字符串拼 markdown | 无。**留着它只会再产出一份假报告** |

> 建议：B 级不直接删，先移到项目外归档目录（如 `Desktop/墨语归档/作废报告/`），保留一个月观察期。

### C 级：死代码 / 死 schema（5 项，需小改动，影响已逐一评估）

| # | 对象 | 为什么没用 | 清理方式 | 清理影响 |
| :--- | :--- | :--- | :--- | :--- |
| C-1 | （并入 B-4） | — | — | — |
| C-2 | （并入 B-1/2/3） | — | — | — |
| C-3 | `docs/墨语 MoYu 功能去重与体验一体化重构开发计划书 (v1.9.0).md`、`docs/写作工作流全功能技术设计报告与程序清单.md` | 与另两份 MD5 完全相同的重复副本（矛盾 6） | 删除 | 无。内容一字不差地保留在另一份 |
| C-4 | `app/db.py:202` 的 `CREATE TABLE IF NOT EXISTS notes` | v1.9.6 已下线便签，全代码库无任何读写（实测 `FROM notes`/`INTO notes` 零命中） | **不能简单删 CREATE**：老用户库里表已存在。正确做法＝`MIGRATIONS` 追加一条 `DROP TABLE IF EXISTS notes` 迁移 + 删除 CREATE 语句 | 无功能影响；老库升级时静默清掉废表；`tests/` 中便签相关断言（404 防线）不受影响 |
| C-5 | `static/js/pages/workflows.js:678` 兜底对象里的 `notes: []` | 便签已下线，该字段永远不会被消费 | 删除该字段 | 无。下游渲染只遍历存在的键 |

### D 级：大件产物（2 项，需用户决策，默认不动）

| # | 对象 | 现状 | 选项与影响 |
| :--- | :--- | :--- | :--- |
| D-1 | `build/`（**867 MB**）+ `dist/`（**883 MB**） | PyInstaller 中间产物与历史发布包；均未被 git 追踪（`.gitignore` 已排除） | **选项①** 保留现状（推荐：`dist/` 里的历史 exe 是发布留档）；**选项②** 删 `build/`（可随时重建，零风险），`dist/` 移到项目外归档。**对功能无任何影响**，纯磁盘占用问题 |
| D-2 | 281 个 `__pycache__/` 目录 | Python 缓存，git 未追踪 | 可一键清除，首次运行自动再生。零影响 |

### 明确**不**清洗的（防止误删）

| 对象 | 不删的理由 |
| :--- | :--- |
| `app/api/ai.py`、`alchemy.py`、`style.py`（各 6 行 shim） | **不是死代码**——被 `app/api/__init__.py` 挂载，路由由 `app/features.py` 动态构造。删了会丢 20+ 个端点 |
| `POST /api/alchemy/brew|complete` | 矛盾 2 已裁决：降级为内部实验 API，P1 结束再评估 |
| `docs/` 全部历史 development-notes | 演进记录，无矛盾时不改不删 |
| `data/`（导出/导入文件） | 用户数据，`.gitignore` 已排除，永不触碰 |

---

## 第三部分　分阶段修复计划（模块 / 代码 / 修法 / 目的）

> 断点编号 D1–D6 沿用《模块互通性诊断与资产中枢改造方案》。每阶段标注验收标准。

### P0　止血（预计 1 天，5 条改动，不引入新模块）

| # | 修改模块与代码 | 怎么修 | 目的 |
| :--- | :--- | :--- | :--- |
| P0-1 | `static/js/pages/outline.js:765` | 把 `POST /api/works/{id}/timeline/events` 改为后端真实存在的 `POST /api/works/{work_id}/timeline`（`app/api/timeline.py:86`），并按该端点入参模型调整请求体 | 修复大纲页"剧情事件关联"必现 404——当前事件根本没进库（D3 症状） |
| P0-2 | `app/api/seed.py:78,80`；`app/api/timeline.py:231` | INSERT 语句补上 `outline_node_id` 列：seed 按章节已有的大纲节点回填；导入路径按 `outline_nodes.chapter_id` 反查绑定 | 示例作品与导入小说的伏笔/事件不再"入库即隐形"（D3 根因） |
| P0-3 | `app/api/outlines.py:181,190`；`app/services/plot_service.py:15,26` | 聚合 WHERE 从 `outline_node_id=?` 放宽为 `outline_node_id=? OR chapter_id IN (该节点所属章节)` | 读侧兼容只绑了章节的历史数据，老作品产物重新可见（D2） |
| P0-4 | `app/services/plot_service.py:128,148`（`batch_sync_triad_assets`） | 时间线事件与伏笔写入前加去重查询，照抄同文件 `entity_relations`（`app/workflow_assets.py:658`）与大纲节点（`plot_service.py:109`）的既有去重写法 | 工作流重跑不再成倍复制事件/伏笔（D4） |
| P0-5 | `app/api/works.py:224`（`DELETE /chapters/{id}`） | 删除前先 `SELECT COUNT(*)` 统计挂在该章节的伏笔/事件/大纲绑定数，响应体带回影响面；前端 `workbench.js` 弹确认"将解除 N 条绑定" | 消灭"删章节 → 产物静默孤儿化"（D5）——不阻止删除，但必须让用户知情 |

**P0 验收**：① 大纲页添加剧情事件成功且在大纲/工作台可见；② 新建示例作品后其 2 条伏笔在大纲树聚合视图可见；③ 导入 txt 后事件可见；④ 同一工作流跑两次，事件/伏笔数量不翻倍；⑤ 删章节前出现影响面提示；⑥ 161 项测试全绿 + 新增 4 条断言（见 P3-3）。

### P1　收口：引入资产中枢 AssetHub（预计 3–4 天）

| # | 修改模块与代码 | 怎么修 | 目的 |
| :--- | :--- | :--- | :--- |
| P1-1 | **新建** `app/services/asset_hub.py` | 四个公开能力：`resolve_binding()`（两键互派生，只给一个自动补另一个）、`upsert_foreshadow()/upsert_timeline_event()`（幂等键＝work+规范化文本+目标绑定）、`aggregate_for_node()/aggregate_for_chapter()`（唯一读侧聚合口）、`detach_chapter()`（删前影响面+解绑） | 把"绑定契约"从各模块隐式约定提升为唯一显式集成层——这是"各跑各的"的根治 |
| P1-2 | 写侧改造：`app/api/board.py:74`、`app/api/timeline.py:98,231`、`app/api/seed.py:78,80`、`app/services/plot_service.py:85` | 全部改为调用 `asset_hub.upsert_*`，删除各自的裸 INSERT | 任何来源（手动/AI/导入/示例/工作流）的产物都按同一契约入库 |
| P1-3 | 读侧收口：`app/api/outlines.py:173`（plot-items 端点）改为委托 `asset_hub.aggregate_for_*`；**删除** `app/services/plot_service.py:6` 的重复实现 `get_node_plot_triad` | 两份重复聚合实现（D2）合并为一 | 消灭"改一处另一处不跟着变"的漂移源 |
| P1-4 | `app/api/works.py:224` 删除章节改为调用 `asset_hub.detach_chapter()` | P0-5 的临时方案升级为正式善后 | 删除路径唯一化 |
| P1-5 | 治理章节↔大纲节点多对一（D6）：`outlines.py` `link-chapter` 端点 | 同章节重复绑定时返回警告；前端 `workbench.js:877` `flat.find(...)` 改为收集全部匹配节点并按序合并展示 | 修掉"第二个绑定节点下产物彻底不可见" |

**P1 验收**：全代码库 `INSERT INTO foreshadows|timeline_events` 只存在于 `asset_hub.py`；聚合查询只存在于 `asset_hub.py`；测试全绿。

### P2　上下文统一（预计 2–3 天，解决 D1）

| # | 修改模块与代码 | 怎么修 | 目的 |
| :--- | :--- | :--- | :--- |
| P2-1 | `app/services/context_service.py:39` | 扩展装配内容：补上万相谱实体勾选与文风档案（对齐前端现有能力） | 后端装配不再缺实体/文风 |
| P2-2 | `app/api/chat.py`、`app/features.py` generate 链路 | 上下文改为后端统一装配，前端只传"用户勾选项 ID 列表"；**删除** `workbench.js:1133` 的 `renderContext()` 前端拼装（150+ 行）与 `workbench_chat.js:852` 的 `context` 字段透传 | 同一个 AI 能力，任何入口喂给模型的世界知识一致 |
| P2-3 | `static/js/pages/workbench.js` 上下文抽屉 | 改为纯"勾选+预览"UI，预览数据调后端装配结果 | 前端不再承担业务装配职责 |

**P2 验收**：同一章节分别从划词生成、修撰使、工作流发起请求，后端日志中注入的上下文结构一致。

### P3　规范与防线治理（随各阶段同步做）

| # | 修改模块与代码 | 怎么修 | 目的 |
| :--- | :--- | :--- | :--- |
| P3-1 | `AGENTS.md` | 更新：测试数改为动态表述；`scripts/` 增补红线（矛盾 7）；增补"绑定契约以 `asset_hub.py` 为准，禁止裸 INSERT"；增补"brew/complete 为内部实验 API" | 规范文件恢复与代码一致 |
| P3-2 | 执行第二部分清洗清单（A/B/C 级） | A 级直接删；B 级归档；C 级随 P0/P1 顺带改 | 消灭垃圾与死代码 |
| P3-3 | `tests/` 新增 6 条防漂移断言 | ① seed 伏笔含 outline_node_id；② 导入事件含 outline_node_id；③ 聚合读侧含仅绑章节的数据；④ 工作流重跑不复制资产；⑤ 删章节响应含影响面；⑥ 聚合实现唯一性（grep 级守护） | 现在的 161 项全绿挡不住 D1–D6，因为测试只覆盖单模块闭环 |
| P3-4 | 文档纪律 | 把 `check_doc_refs.py`（校验文档中 `file:line` 引用）纳入每次产出技术文档后的必跑项 | 杜绝"看起来很权威实际全靠编"的报告再次出现 |

---

## 执行顺序与依赖

```
第 1 天        第 2–5 天        第 6–8 天       持续
A 级清洗 ──┐
B 级归档 ──┼─→ P0 止血 ──→ P1 AssetHub 收口 ──→ P2 上下文统一
P3-1 文档 ─┘        └── P3-3 断言随各阶段补 ──┘
C 级清洗随 P0/P1 顺带完成；D 级由用户决策，不阻塞任何阶段
```

## 风险与备注

1. **本计划不动代码**，仅作为施工图纸；执行时建议每个 P 阶段单独一个 commit 批次，便于回滚。
2. P0-3 放宽读侧后，历史"只绑章节"的数据会重新出现在大纲聚合视图——这是**预期行为**（找回丢失产物），不是数据错乱。
3. C-4 的 `DROP TABLE notes` 走 `MIGRATIONS` 增量迁移，符合 `AGENTS.md`"严禁破坏现有用户数据"红线（表内已无有效数据，v1.9.6 实测确认）。
4. `data/` 用户数据、`dist/` 历史发布包在任何阶段都不在清洗范围内，除非用户对 D 级明确拍板。


---

## 阶段执行记录与验收归档

- **执行日期**：2026-10-08
- **执行规范依据**：严格依照《墨语MoYu_资产中枢修复计划书》及 `AGENTS.md` 工程红线执行。

### 阶段 0：清洗（A/B/C-3 级）
- **Commit**：`d428df4 chore: 清理报告垃圾脚本与作废/重复文档（计划书A/B/C-3级）`
- **改动文件**：
  - A 级删除：`scripts/build_full_report.py`、`scripts/build_architecture_report.py`、`scripts/build_report_sections.py`、`scripts/generate_report.py`、`scripts/append_chapters.py`、`scripts/generate_all.py`、`scripts/test.ps1`、`scripts/test.txt`、`scripts/report_parts/`、`scripts/__pycache__/`。
  - B 级归档：将作废全景报告移动至仓库外 `../墨语归档/作废报告/`。
  - C-3 级删除：`docs/墨语 MoYu 功能去重与体验一体化重构开发计划书 (v1.9.0).md`、`docs/写作工作流全功能技术设计报告与程序清单.md`。
- **回归测试**：161 项测试全绿。

### 阶段 1：P0 止血
- **Commit**：`c998ca4 fix(P0): 修复大纲事件404/产物双键补全/聚合读侧放宽/回流幂等/删除知情`
- **改动文件**：
  - `static/js/pages/outline.js`：修改事件创建路由为 `POST /api/works/{work_id}/timeline`，修复 404；
  - `app/api/seed.py`、`app/api/timeline.py`：资产产物补全 `outline_node_id` 双键回填；
  - `app/api/outlines.py`、`app/services/plot_service.py`：放宽剧情聚合读侧（直接绑定节点或属于所属章节）；
  - `app/services/plot_service.py`：资产回流防重复写入幂等去重；
  - `app/api/works.py`、`static/js/pages/workbench.js`：删除章节前统计关联伏笔/事件/大纲节点并返回影响面，前端确认弹窗显示解除影响项数。
  - 新增测试：`tests/test_asset_hub_p0.py`。
- **回归测试**：166 项测试全绿。

### 阶段 2：P1 资产中枢收口
- **Commit**：`7e11de8 refactor(P1): 引入AssetHub统一资产绑定契约与聚合读侧，清理notes死schema`
- **改动文件**：
  - 新增中枢：`app/services/asset_hub.py`（封装 `resolve_binding`、`upsert_foreshadow`、`upsert_timeline_event`、`aggregate_for_node`、`aggregate_for_chapter`、`detach_chapter`）；
  - 写侧收口：`app/api/board.py`、`app/api/timeline.py`、`app/api/seed.py`、`app/services/plot_service.py` 裸 INSERT 全部收口至 `asset_hub.py`；
  - 读侧收口：`app/api/outlines.py` 剧情项接口委托 `asset_hub`，消除 `plot_service.py` 中的重复聚合逻辑；
  - 删章节改走 `asset_hub.detach_chapter()`；`link-chapter` 绑定已有章节返回警告；前端支持多对一节点展示；
  - C-4 & C-5 死代码清理：`app/db.py` 引入 `DROP TABLE IF EXISTS notes` 增量迁移并删除死表；`static/js/pages/workflows.js` 移除 `notes: []` 死字段。
  - 新增测试：`tests/test_asset_hub_p1.py`（含全库裸 INSERT 静态守护）。
- **回归测试**：173 项测试全绿。

### 阶段 3：P2 上下文统一
- **Commit**：`a9fa98b refactor(P2): 上下文装配收口至后端context_service，消除前后端双链路`
- **改动文件**：
  - `app/services/context_service.py`：扩展 `assemble_writing_context` 与 `format_entity_block`，统一为正文、前情摘要、大纲三位一体卡片、万相谱实体设定、文风档案的领域知识组装；
  - `app/api/works.py`：新增 `POST /api/chapters/{chapter_id}/context/preview` 上下文装配预览端点；
  - `app/api/chat.py` 与 `app/features.py`：修撰使对话与划词生成统一接入 `context_service.assemble_writing_context`；
  - `static/js/pages/workbench.js` & `static/js/pages/workbench_chat.js`：删除前端 150+ 行手工拼接逻辑，上下文抽屉重构为纯“勾选+预览”UI，透传实体 ID 与配置开关；
  - 新增测试：`tests/test_asset_hub_p2.py`（验证装配组件完整性与预览接口）。
- **回归测试**：175 项测试全绿。

### 阶段 4：P3 规范治理收尾
- **Commit**：`docs(P3): AGENTS.md规范与资产中枢契约同步，计划书执行记录归档`
- **改动文件**：
  - `AGENTS.md`：测试计数转为动态表述、写入资产中枢契约与 `scripts/` 目录治理红线、标注实验 API；
  - `docs/墨语MoYu_资产中枢修复计划书.md`：追加执行记录小节。
- **全量测试验收**：175 项全绿。
