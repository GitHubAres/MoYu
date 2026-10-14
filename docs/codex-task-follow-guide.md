# 墨语 MoYu · Codex 统摄指令（自调取开发指引并按指引执行）

> 用法：把本文件全文（或下方「指令正文」）直接投喂给 Codex 即可。指令自包含，无需补充对话上下文。

---

## 指令正文

你是「墨语 MoYu」本地小说写作工作台（FastAPI + SQLite + 原生 JS SPA，仓库根目录为当前工作目录）的开发协作者。请严格按以下顺序工作：

### 第一步：自调取开发指引，建立工程上下文（必须先做，禁止跳过）
1. 读取仓库根目录的 **`AGENTS.md`**（协作者导读 / 开发指引），完整遵循其中：
   - 第 9 节「接手任务与 AI 读档顺序」：按 AGENTS.md → 当前版本开发说明（`docs/vX.Y.Z-development-notes.md`，若该文件暂缺则跳过此条，不要因此中断）→ README.md → `docs/PRD-本地版.md` 的顺序读档；
   - 第 4 节架构约定（资产中枢契约以 `app/services/asset_hub.py` 为准、MIGRATIONS 增量迁移、AI 工作流「生成→预览→采纳→写版本→可撤销」）；
   - 第 5 节设计规范（前端禁止构建链路、DOM 一律 `ui.el()/ui.icon()`、三主题、状态不得只靠颜色表达）；
   - 第 8 节操作边界（不碰 `data/`、不回显 API Key、不引 ORM/构建步骤、scripts 红线）；
   - 第 10 节版本迭代规约。
2. 读档完成后，对照任务查验对应 API 与页面模块，再动手。

### 第二步：执行任务（用户原始需求）
用户需求原文：
> 「每写完一篇，新增的人物、地点、关系、道具应自动识别并收录到万象谱等现有模块；能自动识别是否有悖论的故事内容；编辑器功能太少，需要前后对比、AI 识别到问题处自动标注填充颜色等功能。」

该需求的 Phase 1+2 代码已实现且静态回归全绿，但**从未运行时验证**。本次执行 P0：

1. 先读 `docs/codex-handoff-smart-intake-audit.md`（接管计划书，含已完成清单与 P0-P2 路线图）与 `docs/codex-task-runtime-verify.md`（P0 详细测试清单）。
2. 按 `docs/codex-task-runtime-verify.md` 执行：新增 `tests/test_smart_intake.py`（复用 `tests/conftest.py` 的 `client` 夹具与 `make_wvc`），覆盖 smart-intake 候选预览/真实落库/is_new 判定/location→place 归一回归/audit 字段契约（mock httpx LLM），跑通后修复发现的全部后端 bug。
3. 回归命令与完成标准以 `docs/codex-task-runtime-verify.md` 为准（pytest 全绿 + 写 `docs/codex-report-runtime-verify.md` + stdout 输出 `TASK_DONE`）。

### 红线（与 AGENTS.md 叠加，冲突时从严）
- 不 `git commit` / `push`，改动留在工作区由用户验收。
- 不动 `static/js/` 前端、不改 8 产物键 schema、不引入新依赖、不重写已有能力（detect-unregistered / batch-intake / versions diff / audit 复用）。
- AI 生成内容必须先预览经用户确认，任何路径不得静默改写正文。
- 测试只增不减；测试库重定向临时目录，禁止触碰真实 `data/`。

### 执行方式
直接开始执行，禁止长时间分析；每完成一步就落实（改码 + 跑测试），不要攒到最后。
