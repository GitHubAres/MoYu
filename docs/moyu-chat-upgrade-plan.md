# 墨语 MoYu「AI 修撰使」多轮对话聊天升级方案 (v1.3.0)

> **计划编号**：moyu-chat-upgrade-plan.md  
> **版本目标**：v1.3.0  
> **核心目标**：将写作工作台的「AI 修撰使」右侧面板从单轮任务模式升级为多轮对话式聊天窗口。

---

## 1. 核心原则与红线

1. **内容安全红线**：AI 生成的任何内容必须先预览、经用户点击「采纳」后才写入正文；任何路径不得静默改写正文。采纳前必须自动留存版本快照，采纳后必须可撤销。
2. **前端架构约束**：原生 JavaScript，禁止引入任何构建工具/前端框架/npm 依赖；DOM 构建必须使用 `ui.el()`、`ui.icon()`；禁止在页面布局前访问后声明的 const/let 变量（TDZ）；气泡内容按纯文本渲染，不引入 Markdown 解析库。
3. **数据库约束**：新增表必须通过 `app/db.py` 的 SCHEMA + MIGRATIONS 机制登记，使用裸 sqlite3。
4. **AI 客户端约束**：复用 `app/ai_client.py` 的 `chat_stream()`（已兼容多轮 messages 数组），不传 temperature。
5. **响应式约束**：桌面 ≥1024px 保持右栏三栏布局；移动端 <1024px 聊天窗口为全屏抽屉，输入区触控热区 ≥44×44px，禁止横向滚动条。
6. **设计规范**：遵循 Literary Minimalist Ink 设计系统（黛青 #1B2A38、朱砂 #D9483B、Noto Serif 标题 + 无衬线正文）；关键状态不能只靠颜色表达，需辅助图标或文案。
7. **操作边界**：不提交 data/、不回显 API Key、不静默修改 dist/release 产物、不删除用户数据。

---

## 2. 数据层设计（app/db.py）

- `chat_sessions` 表：
  - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `work_id`: INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE
  - `chapter_id`: INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE
  - `created_at`: TEXT
  - `updated_at`: TEXT
- `chat_messages` 表：
  - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `session_id`: INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE
  - `role`: TEXT ('user' / 'ai')
  - `content`: TEXT
  - `task_type`: TEXT
  - `meta_json`: TEXT
  - `adopted`: INTEGER DEFAULT 0
  - `created_at`: TEXT

---

## 3. API 层设计（app/api/chat.py）

- `GET /api/chat?chapter_id={id}`：返回当前章节关联的最新 session 及按时间正序的消息列表。
- `POST /api/chat`：
  - 入参：`{chapter_id, message, task, selection, prompt_id, context, length, stream}`。
  - 自动 get_or_create session。
  - 用户消息入库 `chat_messages`。
  - 读取当前 session 全部历史，映射为 user/assistant 数组，组装本轮结构化上下文消息。
  - 调用 `chat_stream` 实时流式输出（SSE）。
  - 流式结束后将 AI 回复写入 `chat_messages`，登记异步任务审计。
- `PATCH /api/chat/messages/{id}`：更新消息采纳状态（`adopted=1` 或 `0` 撤销）。
- `POST /api/chat/session/new`：创建新对话，清空当前激活轮次重新计数。

---

## 4. 前端交互设计（static/js/pages/workbench_chat.js）

- 导出 `WorkbenchChat.init`，挂载至工作台右侧。
- 顶部条：修撰使头像 + 名称 + ⚙设置抽屉展开按钮 + 「新对话」按钮。
- 设置抽屉：精调任务/长度/候选/提示词模板，以及「经典候选模式」开关。
- 上下文折叠栏：显示“已挂载 N 项上下文”，支持展开折叠与细项勾选。
- 消息流列表：
  - 用户气泡（右对齐，朱砂色系）。
  - AI 气泡（左对齐，带 AI 标识与任务标签，流式打字机效果）。
  - 底部操作条：`[采纳(主按钮)]`、`[复制]`、`[重试]`、`[放弃]`。
  - 已采纳状态下主按钮切换为 `[已采纳 / 撤销采纳]`。
- 底部输入区：多行自适应文本框，Enter 发送 / Shift+Enter 换行；上方一排快捷标签 `[续写|扩写|缩写|改写]`；选区引用状态条。
- 移动端适配：`<1024px` 全屏抽屉遮罩，热区 `≥44×44px`。

---

## 5. 工作台集成（static/js/pages/workbench.js）

- `buildAiPanel()` 接入 `WorkbenchChat`。
- 保留 `adopt()`、`lineDiff()`、`candidatesBox` 等底层基础设施；当开启“经典候选模式”时可切换回原多候选卡片视图。
- 选区浮动工具栏（Floating Toolbar）无缝将选区注入聊天发送流。

---

## 6. 完成定义（DoD）与测试执行指令

1. 聊天窗口支持 ≥3 轮上下文连贯对话（AI 能引用前文内容）。
2. 切换章节后各自恢复独立对话历史。
3. AI 气泡内容未点「采纳」绝不写入正文。
4. 采纳后气泡显示"已采纳"，点击可撤销（正文恢复）。
5. 桌面 1366px 三栏布局无回归，移动端 393px 无横向滚动。
6. pytest 全量绿灯（含新增 chat 用例 `tests/test_chat.py`）。
7. PRD/README/development-notes 同步归档（`docs/v1.3.0-development-notes.md`）。
