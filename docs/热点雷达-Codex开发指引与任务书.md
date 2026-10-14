# 热点雷达 · Codex 开发指引与任务书

> 版本：v1.0　日期：2026-10-12　目标版本：v2.2.0（候选）
> 适用对象：Codex / AI 协作者 / 人工开发者
> 前置文档：`AGENTS.md`（全局规范，必须首先读）、`docs/开发计划-热点雷达.md`（实施方案）
> 本文档用途：Part A 是**开发约束指引**（Codex 执行前必读）；Part B 是**可直接粘贴的任务指令**（自包含，不依赖对话上下文）。

---

# Part A · 开发计划指引（Codex 必读约束）

## A1 读档顺序（强制，不得跳过）

严格按 `AGENTS.md` §9 + §10「读档第一法则」执行，并在本任务下追加两项：

1. `AGENTS.md` —— 全局约定、设计语言、版本迭代规约
2. **最新版本开发说明** —— 当前为 `docs/v2.1.2-development-notes.md`（随版本滚动，以 `docs/vX.Y.Z-development-notes.md` 为准）
3. `README.md`
4. `docs/PRD-本地版.md`
5. 本任务书 + `docs/开发计划-热点雷达.md`
6. 按需查阅：`app/db.py`（表与迁移）、`app/api/__init__.py`（路由注册）、`app/features.py`（提示词装配）

> ⚠️ **严禁引用 `docs/development-plan.md`**。该文件为 v1.2.3 时代历史计划，已标注「已停维护·归档」，读取它会引入过期上下文。

## A2 全局红线清单（违反即驳回）

| # | 红线 | 来源 | 检查点 |
|---|---|---|---|
| R1 | 新增表/字段必须通过 `app/db.py` 的 **MIGRATIONS 增量迁移**，裸 `sqlite3` | §4 | 不得引入 ORM（§8 明令禁止） |
| R2 | AI 客户端 httpx 异步，**绝不传 `temperature`** | §4 | 部分模型只接受固定值 |
| R3 | AI 生成内容**必须先预览、经用户确认后**才写入，禁止静默改写/覆盖正文 | §1/§5 | 交互红线 |
| R4 | `foreshadows` 与 `timeline_events` 写入**必须走 `app/services/asset_hub.py`**，禁止裸 INSERT | §4 | 资产中枢唯一写口 |
| R5 | 测试数据库/文件目录**重定向到临时位置**，绝不触碰真实 `data/` | §3/§6 | 自动化测试用临时隔离库 |
| R6 | 不提交/回显 `data/` 作品、数据库、API Key | §8 | 输出安全 |
| R7 | 不引入前端构建步骤（无 Webpack/Vite/NPM），DOM 用 `ui.el()` / `ui.icon()` | §5/§8 | Tailwind 浏览器端运行时编译 |
| R8 | `scripts/` 只放构建/部署/依赖本地化/核心 AI 联调工具；一次性脚本**用完即删** | §8 | 严禁堆积垃圾脚本 |
| R9 | 响应式：`<1024px` 抽屉导航、禁止横向滚动条、触控热区 **≥44×44px** | §4 | 不得破坏桌面端 WebView2 离线能力 |
| R10 | 测试**只增不减**；全量 `pytest` 必须保持 **207 passed 零回退** | §3 | 当前基线 207 |

## A3 热点雷达专项约束

- **只采公开热榜元数据**（书名 / 排名 / 题材标签 / 热度）。绝不下载或存储平台正文章节、简介全文。
- **限速 + 随机 UA + 遵守目标站 ToS/robots**；榜单数据保留 7 天后自动清理（`fetched_at` 判定）。
- 存储**两者结合**：榜单索引落 `hot_topics` 表；只有作者主动「收藏/立项」的热点才转 `MOYU:ASSETS` 资产（经 `asset_hub`，未涉及键留空数组 `[]`）。
- 契约权威以 `docs/墨语产物交付规范.md` 为**唯一现行版本**（v1.0），不得依据已归档的《AI产出输入输出契约规范（提案）》新建接口或判定功能缺失。
- 对外接口须复用现有 `auth` 鉴权，防止未授权触发爬虫。
- 路由挂载于 `/api/hotradar`，经 `app/api/__init__.py` 注册。

## A4 交付与验收标准

1. 全量回归 `.venv/Scripts/python.exe -m pytest -q` 须 **207 passed 零回退**（Windows 环境用 `.venv/Scripts/`，非 `bin/`）。
2. 新增测试单独成文件（如 `tests/test_hotradar.py`），fetcher 须 mock，**禁止测试环境真实外发请求**。
3. 落 v2.2.0 时按 §10 规范打包：同步 `AGENTS.md`、`README.md`、`docs/PRD-本地版.md`，并新建 `docs/v2.2.0-development-notes.md`（记载版本号/日期/新增模块与路由/回归覆盖/已知问题/下一阶段待办）。
4. 版本号落点**先用 grep 定位 `2.1.2` 的所有出现处**再逐一同步，**不得臆造落点**（历史教训：曾出现文档写 `/api/ai/brew/complete` 而代码实为 `/api/alchemy/*` 的臆造路径问题）。

## A5 已知陷阱（真实踩坑记录，务必规避）

1. **接口路径臆造**：炼丹炉真实路径是 `/api/alchemy/brew` 与 `/api/alchemy/complete`，**不存在 `/api/ai/brew/complete`**。任何接口引用前先 grep 代码确认。
2. **误删被测试引用的文件**：`scripts/icons_subset_text.txt` 曾被当成「一次性残留」删除，实为 `tests/test_font_icons.py` 的字体连字校验夹具，直接导致回归失败。**删除 scripts/ 下任何文件前，必须全局 grep 确认无测试/代码引用。**
3. **过期文档误导**：`docs/development-plan.md` 已归档停维护；《AI产出输入输出契约规范》为提案且已归档。二者均不得作为现行依据。
4. **测试配置争用**：测试进程与联调脚本会争用 `app_settings` 的 AI 配置，自动化测试必须用临时隔离库。
5. **契约键不得省略**：MOYU:ASSETS 未涉及的键必须留空数组 `[]`，不可省略键。

---

# Part B · 任务指令（可直接粘贴给 Codex）

> 使用说明：以下指令**自包含**，可直接复制粘贴。执行前按 A1 完成读档。
> 工作目录：`D:\KimiCode工作区`　环境：Windows，Python 用 `.venv/Scripts/python.exe`

---

## 指令 1 · M0：第三方热榜 API 可行性调研（前置，不写业务代码）

```
【任务】调研起点、番茄、晋江三平台小说热榜是否有可用的第三方聚合 API，输出结论供后续接入决策。本阶段不写业务代码。

【前置读档】
按 A1 顺序读取 AGENTS.md、docs/v2.1.2-development-notes.md、README.md、docs/PRD-本地版.md、docs/热点雷达-Codex开发指引与任务书.md、docs/开发计划-热点雷达.md。

【执行要点】
1. 联网检索是否有提供中文网文平台热榜/排行榜的第三方聚合 API（优先免费或低成本；记录限流、鉴权、字段结构、是否含题材标签与热度值）。
2. 逐个评估：能否覆盖「起点 / 番茄 / 晋江」三平台热榜的书名、排名、题材标签、热度。
3. 若存在可用 API：给出接入方式（端点、参数、返回样例、限频），并说明是否需 API Key。
4. 若不存在或不可用：明确结论「回退自写爬虫」，并给出三平台公开热榜页的抓取可行性评估（是否需登录、是否反爬、DOM 结构是否稳定）。

【交付】
将结论写入 docs/开发计划-热点雷达.md 的「九、风险与回退」「M0」章节，或新建 docs/热点雷达-API调研结论.md。结论必须包含：选定方案（第三方API / 自写爬虫）、理由、接入或抓取要点。

【验收】
- 结论明确可执行，不含模糊表述。
- 未新增任何业务代码文件；未修改 app/ 与 static/。
- 未触碰 data/；未回显任何 API Key。
```

---

## 指令 2 · M1–M4：热点雷达底座（数据 / 采集 / 调度 / 服务 / 前端）

```
【任务】按 docs/开发计划-热点雷达.md 实施 M1–M4，打通「采集 → 存储 → 服务 → 前端」主链路。目标版本 v2.2.0（候选）。

【前置读档】按 A1 顺序读档，并阅读 docs/热点雷达-API调研结论.md（若已产出）确认数据源方案。

【执行要点】
M1 数据层：
- 在 app/db.py 通过 MIGRATIONS 增量迁移新增 hot_topics 表：id, platform, title, rank, genre_tags(JSON), heat, collected(bool), fetched_at(datetime)。
- 裸 sqlite3，禁止 ORM。

M1 采集层：
- 新建 app/services/hotradar_fetcher.py：优先调第三方聚合 API；不可用则回退自写轻量爬虫（仅抓公开热榜页元数据）。
- 统一输出结构 List[{platform, title, rank, genre_tags, heat}]，写入 hot_topics。
- 限速 + 随机 UA + 遵守 ToS/robots；失败降级不抛崩溃。

M2 调度层：
- 独立 scheduler（apscheduler 或等价后台机制），按 cron 定时调用 fetcher 刷新缓存。
- 定时清理 fetched_at 超过 7 天的过期榜单。
- 与现有 tasks 系统解耦。

M3 服务层：
- 新建 app/api/hotradar.py，挂载 /api/hotradar，在 app/api/__init__.py 注册。
- 接口：GET /api/hotradar/list?platform=&genre=&limit=；POST /api/hotradar/refresh（手动/调度触发）；POST /api/hotradar/to-outline；POST /api/hotradar/collect。
- 复用现有 auth 鉴权。

M4 前端：
- 新建 static/js/pages/hotradar.js，index.html 注册路由与入口。
- 页面：热榜列表、平台/题材筛选、热点详情、一键立项、收藏、立即刷新。
- 遵循 §5 设计语言（黛青 #1B2A38 / 朱砂 #D9483B；标题 Noto Serif，正文无衬线；三主题）；原生 JS + ui.el()/ui.icon()，无构建步骤；<1024px 抽屉导航、热区≥44×44px、禁横向滚动条。

【红线】
- 只存公开榜单元数据，绝不下载/存储正文章节。
- 绝不传 temperature。
- 不得修改既有模块行为导致回归退化。

【验收】
- .venv/Scripts/python.exe -m pytest -q 结果 207 passed 零回退。
- 启动 python run.py 后热点雷达页面可访问，榜单可展示（无真实数据时允许空态/占位）。
- 未触碰 data/。
```

---

## 指令 3 · M5–M8：双向互通（立项 / AI提示词 / 工作流 / 资产中枢 + 回灌）

```
【任务】按 docs/开发计划-热点雷达.md 实施 M5–M8，完成热点雷达与现有模块的双向互通。

【前置读档】按 A1 顺序读档，重点精读 app/features.py（build_skill_system_prompt）、app/services/asset_hub.py、app/workflow_engine.py、docs/墨语产物交付规范.md。

【执行要点】
M5 立项灵感：
- /api/hotradar/to-outline：热点 → 生成 P0 立项草稿（work_info：方向/一句话故事/目标读者）。
- 必须「先预览 + 用户二次确认」后才写入（红线 R3），禁止静默入库。

M6 AI 提示词注入：
- 在 app/features.py 的 build_skill_system_prompt 中条件式追加一句「当前热门题材 TOP10：…」。
- 条件式触发，对纯续写/扩写等正文任务无副作用。

M7 工作流「灵感采集」节点：
- workflows 新增节点类型「灵感采集」，运行时拉取当前热点摘要供后续节点消费。
- 节点定义须兼容 app/workflow_engine.py 现有节点契约。

M8 资产中枢与回灌：
- 作者主动「收藏」时，经 asset_hub 写入 MOYU:ASSETS 契约块（建议映射 notes 或 work_info；未涉及键留空数组 []）。
- 作品 works.genre 回灌热点雷达，前端提供「我的题材 vs 全网热点」对比视图。

【红线】
- foreshadows/timeline_events 写入必须走 asset_hub，禁止裸 INSERT（R4）。
- 契约权威以 docs/墨语产物交付规范.md 为准，不得依据已归档提案文档。
- AI 内容先预览后写入。

【验收】
- 全量 pytest 207 passed 零回退。
- 一键立项可生成草稿且需用户确认；收藏可沉淀资产；工作流节点可运行；提示词注入对正文任务无副作用。
- 未静默改写任何用户正文/资产。
```

---

## 指令 4 · M9：测试接入、版本归档与规范同步

```
【任务】完成 M9：新增测试、全量回归验证，并按 AGENTS.md §10 完成 v2.2.0 规范打包与开发说明归档。

【前置读档】按 A1 顺序读档，并复查已完成的前序改动。

【执行要点】
1. 新增 tests/test_hotradar.py：覆盖表迁移、fetcher（必须 mock，禁止真实外发请求）、API 端点、收藏与立项链路。
2. 跑全量回归：.venv/Scripts/python.exe -m pytest -q，必须 207 passed 零回退（测试只增不减）。
3. 版本号同步：先用 grep 定位当前版本号 2.1.2 的所有出现处，逐一同步为 2.2.0，不得臆造落点、不得遗漏。
4. 新建 docs/v2.2.0-development-notes.md，记载：版本号与日期、新增/修复模块与路由、自动化测试回归覆盖（用例数与通过率）、改动边界与已知问题、下一阶段待办。
5. 按 §10 同步更新 AGENTS.md、README.md、docs/PRD-本地版.md，确保表述与代码 100% 同步。

【红线】
- 测试不得触碰真实 data/，须用临时隔离库（R5）。
- 不得删除用户数据或重置数据库（§8）。
- 不得提交或回显 API Key。

【交付】
输出一份改动清单（新增/修改文件、测试数量变化、版本号同步落点列表），并说明已知问题与后续待办。

【验收】
- pytest 全量通过且用例数只增不减。
- 文档与代码无冲突（无臆造路径、无过期引用）。
- git status 中无 data/ 相关文件、无一次性垃圾脚本残留。
```

---

## 附：快速核验命令（Windows / Git Bash）

```bash
cd "D:/KimiCode工作区"
.venv/Scripts/python.exe -m pytest -q                 # 全量回归，基线 207 passed
.venv/Scripts/python.exe -m pytest --collect-only -q   # 用例计数
grep -rn "2\.1\.2" --include="*.py" --include="*.md" --include="*.html" . | grep -v ".venv" | grep -v "__pycache__"   # 版本号落点
grep -rn "hotradar" app/ static/                       # 新模块挂载核验
```
