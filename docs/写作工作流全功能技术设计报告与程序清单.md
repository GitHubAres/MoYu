# 墨语 MoYu ·「写作工作流」全功能技术设计报告与程序清单

**版本编号**：v1.8.4  
**归档日期**：2026-10-06  
**系统环境**：FastAPI + SQLite (WAL) + 原生 JavaScript SPA  
**部署节点**：实机 VPS (107.150.5.175) / 本地桌面端 (WebView2)  

---

## 一、 功能背景与架构愿景

### 1.1 业务背景
在早期的分轮 AI 创作对话中，创作者常面临三大痛点：
1. **孤岛效应与重复搬运**：AI 生成的世界观设定、人物矩阵、分卷大纲、伏笔规划停留在聊天窗口内，作者必须反复复制粘贴到对应的设定库与大纲页中。
2. **多方案决策断层**：长篇创作在立项阶段，AI 常一次性给出 2~4 套备选方案（如方案一【古典仙侠】、方案二【悬疑诡道】）。缺乏便捷选项让作者一键采纳特定方案并以此为基准继续推进。
3. **安全红线冲突**：AI 不得在未获授权下静默覆写正文或污染已有数据库。必须遵循**“生成 → 识别解析 → 前置弹窗确认/微调 → 规范落库 → 版本沉淀”**的闭环。

### 1.2 核心目标
建立一个“工作流驱动、多方案可挑、前置可配、资产自动沉淀”的全功能连通体系：
- **步骤前置配置窗口**：从 AI 产出的非结构化文本中精准抽取《故事立项》（作品名/题材/看点）、《万相谱》（角色/势力/地点/道具/法则）、《万相图谱》（关系网）、《故事大纲》（卷/章）、《伏笔计划表》与《世界观设定》，在作者确认采纳前弹出前置窗口供勾选与微调。
- **全流程一键汇总同步**：整套工作流完结后，支持一键将全流程沉淀的所有资产打包入库。
- **系统物理隔离**：工作流中间产生的世界观资料不侵占书架用户的“灵感便签”。
- **强鲁棒性**：外键级联删除、SQLite WAL 模式并发防护，杜绝死锁与删除残留。

---

## 二、 核心架构与交互时序设计

### 2.1 业务交互时序图

```
创作者(前端)                      FastAPI 后端                    SQLite 业务库
     |                                 |                               |
     | 1. 运行工作流 (启动第 N 步)       |                               |
     |-------------------------------->| 异步驱动 AI 并流式写入        |
     |                                 |---> 等待确认闸 (awaiting_review)
     | 2. 轮询/检测到多方案卡片        |                               |
     |    (方案1 / 方案2 / 方案3)      |                               |
     |                                 |                               |
     | 3. 点击【选用并配置导入】       |                               |
     |-------------------------------->| POST .../extracted-assets    |
     |                                 | (精准解析所选方案文本)        |
     |                                 |<------------------------------|
     | 4. 弹出【前置配置确认窗口】     |                               |
     |    - 编辑作品名/题材/看点       |                               |
     |    - 勾选万相谱人物/道具/势力   |                               |
     |    - 勾选分卷大纲/伏笔/设定     |                               |
     |                                 |                               |
     | 5. 点击【确认规范同步到作品库】 |                               |
     |-------------------------------->| POST .../sync-assets          |
     |                                 |---> 更新 works 表 (立项)      |
     |                                 |---> 写入 entities 表 (万相谱) |
     |                                 |---> 写入 entity_relations 表  |
     |                                 |---> 写入 outline_nodes 表     |
     |                                 |---> 写入 foreshadows 表 (伏笔)|
     |                                 |---> 写入 notes 表 (排除便签)  |
     |                                 |---> 更新 review approve       |
     |<--------------------------------| 返回同步摘要 summary          |
     | 6. Toast 提示并自动推进下一步   |                               |
```

---

## 三、 设计的程序清单（文件结构与改动总览）

| 序号 | 文件路径 | 模块职责 | 关键实现与改动 |
|---|---|---|---|
| 1 | `app/workflow_assets.py` | 资产提取与数据规范落库核心引擎 | 定义 `AssetWorkInfoIn`、`AssetForeshadowIn`、`AssetEntityIn` 等 Pydantic 数据契约；实现非结构化 Markdown/表格/档案卡解析器 `extract_structured_assets_from_text`；实现原子化多表同步事务 `sync_assets_to_database`。 |
| 2 | `app/api/workflows.py` | 写作工作流 REST API 控制器 | 新增 `POST /runs/{run_id}/steps/{seq}/extracted-assets`（定向方案提取）；新增 `GET /runs/{run_id}/summary-assets`（全流程汇总提取）；更新 `/sync-assets` 路由。 |
| 3 | `app/db.py` | 数据库 Schema 与连接池管理 | 给 `workflow_runs` 外键增加 `ON DELETE CASCADE`；连接池开启 `PRAGMA journal_mode = WAL` 与 `busy_timeout = 15000`，支持高并发无锁执行。 |
| 4 | `app/api/works.py` | 作品管理业务路由 | 在 `delete_work` 中增加显式级联清理：先删除关联的 `workflow_run_steps` 与 `workflow_runs`，解决作品无法删除的外键异常。 |
| 5 | `app/api/notes.py` | 灵感便签业务路由 | 增加 `exclude_tag` 过滤参数支持，允许调用方排除特定标签（如排除“世界观”设定）。 |
| 6 | `static/js/pages/workflows.js` | 工作流 SPA 交互与可视化界面 | 封装 `showAssetSyncModal` 前置弹窗（支持作品立项、万相谱、图谱、大纲、伏笔、设定 6 大配置区）；多方案卡片绑定独立采纳与配置导入；增加工作流完成（`done`）态下的【🎉 全功能一键同步至作品库】大卡片与直达跳转。 |
| 7 | `static/js/pages/bookshelf.js` | 书架与便签前端视图 | 加载便签时追加 `exclude_tag=世界观`，将工作流中间设定与书架便签物理隔离；强化作品删除错误提示。 |
| 8 | `static/index.html` | 静态入口与缓存控制 | 升级静态资源脚本缓存戳版本号 `v=1.8.4`，确保移动端与桌面端实时更新。 |
| 9 | `tests/test_workflows.py` | 自动化回归测试用例 | 覆盖立项信息更新、万相谱多分类落库、关系对映射、分卷大纲层级关联、伏笔计划表插入全量断言（151 项全通）。 |

---

## 四、 核心代码设计与技术细节

### 4.1 数据契约设计 (`app/workflow_assets.py`)
```python
class AssetWorkInfoIn(BaseModel):
    title: Optional[str] = None       # 作品名（如《逆命天尊》）
    genre: Optional[str] = None       # 题材定位（如 古典仙侠）
    intro: Optional[str] = None       # 核心看点 / 故事简介

class AssetForeshadowIn(BaseModel):
    title: str                        # 伏笔标题 / 暗线钩子
    content: str = ""                 # 伏笔线索与回收说明
    status: str = "planted"           # 状态：planted (已埋设)

class AssetEntityIn(BaseModel):
    category: str = "character"       # character | faction | location | item | lore
    name: str                         # 实体名称
    content: str = ""                 # 档案属性 / 描写
    tags: str = ""                    # 标签
    fields_json: Optional[str] = "{}" # 扩展字段 JSON

class SyncAssetsIn(BaseModel):
    work_info: Optional[AssetWorkInfoIn] = None
    entities: list[AssetEntityIn] = []
    relations: list[AssetRelationIn] = []
    outline_nodes: list[AssetOutlineIn] = []
    foreshadows: list[AssetForeshadowIn] = []
    notes: list[AssetNoteIn] = []
    apply_to_chapter: bool = False
    chapter_content: Optional[str] = None
```

### 4.2 智能资产抽取引擎 (`extract_structured_assets_from_text`)
支持从多达 6 种不同的文本结构中自动提取资产：
1. **故事立项识别**：
   - 书名：支持 `《...》`、`书名: ...`、`作品名: ...` 正则提取；
   - 题材：识别 `【古典仙侠】`、`题材: ...` 等标签，并自动过滤 `方案`、`方向` 噪点；
   - 简介：识别 `核心看点:`、`一句话简介:`、`故事梗概:` 等文本。
2. **Markdown 表格提取**：
   - 角色欲望矩阵表（自动提取角色名、定位与各列描述）；
   - 关系网拓扑表（提取双方主体与关系动词，如 `A ↔ B : 争夺宝物`）；
   - 伏笔暗线表（提取伏笔标题与回收条件）；
   - 多品类分类表（势力/地点/道具/法则）。
3. **卡片式与列表式识别**：
   - `### 宁恪（Ning Ke）` 档案卡；
   - `* 【伏笔】青铜残片的真实来历：...`；
   - `第1卷：凡尘逆命` / `第1章：祖祭破庙` 分卷大纲识别；
   - `### 规则一：死生枯荣律` 世界观规则识别。

### 4.3 规范入库与落库事务 (`sync_assets_to_database`)
1. **作品立项 (`works`)**：将抽取的书名、题材、简介自动回写更新至对应作品元数据。
2. **万相谱实体 (`entities`)**：查重机制（按 `work_id + name`），已存在则追加内容，不存在则规范入库并归入对应分类标签（人物/势力/地点/道具/法则）。
3. **万相图谱关系 (`entity_relations`)**：自动关联源节点与目标节点的主键 ID，若关系实体在库中未声明，自动做防御性补全推断创建，防止连线丢失。
4. **故事大纲 (`outline_nodes`)**：自动维护树形拓扑结构，分卷为一级父节点（`parent_id IS NULL`），章节自动挂载于对应卷下方。
5. **伏笔库 (`foreshadows`)**：独立写入作品伏笔计划库，标记为 `planted`。
6. **设定资料便签 (`notes`)**：写入专用标签 `世界观`，供全书资料库索引，书架便签列表自动过滤。

---

## 五、 前端交互设计实现 (`static/js/pages/workflows.js`)

### 5.1 方案卡片与采纳按钮交互
当工作流输出包含方案 1、方案 2、方案 3 等备选方案时：
- 前端通过多方案解析正则自动渲染**方案卡片**；
- 卡片提供**【选用并配置导入】**按钮：
  - 点击后异步调用 `POST /runs/{run_id}/steps/{seq}/extracted-assets`（精准传入当前方案文本进行提取）；
  - 弹出前置配置弹窗；
  - 确认后同步入库，并自动将该方案文本作为正式成果采纳，推进流程。
- 主审核栏提供**【采纳并配置导入 (推荐)】**与**【仅采纳继续】**双模式，满足深度配置与快速推演两种诉求。

### 5.2 前置配置弹窗（`showAssetSyncModal`）
- **顶部**：识别项总数徽标（如 `识别到 11 项`）与关闭按钮；
- **故事立项卡片**：作品书名输入框、题材标签输入框、核心看点多行文本框，默认勾选“同步更新作品信息”；
- **万相谱实体网格**：分类彩色标签展示，条目复选框，支持内容缩略预览；
- **图谱关系网列表**：`宁恪 ➔ 争夺宝物 ➔ 陆玄` 箭头关系可视化；
- **故事大纲树**：卷/章图标分级预览；
- **伏笔计划列表**：暗线标题与回收说明；
- **底部操作**：【全选】、【反选】、【取消】、【确认规范同步到作品库】。

### 5.3 全流程一键汇总同步（`done` 态）
工作流全部步骤完成后，页面顶部浮现专属完成通知大卡片：
- 展示【🎉 全功能一键同步至作品库】按钮，调用 `GET /summary-assets` 获取全套产出并弹出汇总弹窗；
- 附带直达【查看万相谱】、【查看大纲】快捷导航按钮。

---

## 六、 实机生产环境测试与验证记录

在真实 VPS（`107.150.5.175`）环境下，经热重启与实机自动化验证，全部指标达标：

```text
[自动化回归测试]
tests/test_ai_models.py .................................. [ 22%]
tests/test_api_works.py .................................. [ 45%]
tests/test_entities_notes_prompts.py .................... [ 68%]
tests/test_workflows.py ................................. [100%]
======================= 151 passed, 1 warning in 19.68s =======================

[实机端到端全链路验证]
1. 服务连通性测试 (GET /api/stats/dashboard)         -> HTTP 200 OK
2. 书架作品级联删除测试 (DELETE /api/works/{id})     -> HTTP 204 OK (无外键报错)
3. 灵感便签世界观过滤测试 (GET /api/notes?exclude)   -> HTTP 200 OK (0 噪点)
4. 多方案故事立项定向提取 (POST .../extracted-assets) -> HTTP 200 (书名/题材/看点精准抽取)
5. 前置弹窗模拟规范同步 (POST .../sync-assets)        -> HTTP 200 (立项/实体/关系/大纲/伏笔全落库)
6. 全流程汇总接口测试 (GET .../summary-assets)       -> HTTP 200 OK
```

至此，墨语“写作工作流”已完整实现从单一对话输出到全系统规范联通的跨越，兼具前置可视配置的严谨性与一键采纳的流畅性。
