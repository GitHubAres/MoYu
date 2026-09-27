# AGENTS.md — 墨语MoYu AI 协作者导读

> 本文件面向 AI 开发协作者（如 KimiClaw「墨语MoYu助手」）。读完本文件 + 根目录 README.md + docs/PRD-本地版.md，即可开始协同开发。

## 1. 项目一句话

本地优先的 AI 长篇小说写作工作台：Python FastAPI + SQLite + 原生 JS 单页应用，PyInstaller 打包为 Windows 单 exe，数据 100% 本地（`data/moyu.db`），AI 走用户自配的 OpenAI 兼容接口。

**铁律：AI 是助手不是写手。一切 AI 生成内容必须先预览、经用户确认后才入库，任何路径都不得静默写入正文。**

## 2. 目录地图

```
moyu/
├── app/                  # 后端
│   ├── main.py           # FastAPI 入口：create_app()，挂载 API 路由 + 静态文件
│   ├── db.py             # SQLite 层：连接管理、建表 SCHEMA、增量迁移 MIGRATIONS
│   ├── ai_client.py      # OpenAI 兼容客户端：chat() 非流式 / chat_stream() SSE
│   ├── exporter.py       # TXT/DOCX 导出
│   ├── paths.py          # 路径常量
│   └── api/              # 18 个功能路由模块，每个一块业务域（见 README 功能表）
├── static/               # 前端（原生 JS SPA + Tailwind 运行时，无构建步骤）
│   ├── index.html
│   ├── js/               # app.js / router.js / ui.js / api.js + pages/*.js（每页一个模块）
│   └── vendor/           # 本地化资源（tailwind.js、字体），由 scripts/fetch_vendor.py 生成
├── tests/                # pytest，27 项 API 回归测试
├── scripts/              # fetch_vendor.py（本地化前端依赖）/ mock_ai.py（联调用）
├── docs/                 # PRD-本地版.md、墨语MoYu产品介绍.md、AI联调记录.md、界面截图
├── data/                 # 运行数据（moyu.db、imports/、exports/）——gitignore，绝不入库
├── build_exe.py          # PyInstaller 打包（默认 onefile，--onedir 启动更快）
├── moyu_entry.py         # exe 入口：单实例守卫（重复双击只唤起页面）
└── run.py                # 开发入口：python run.py → http://127.0.0.1:8321
```

另：上级目录的 `moyu-cloud/` 是云端部署变体（代码同构 + MOYU_TOKEN 令牌门 + deploy/ 脚本），改动后需手动同步两边，见第 7 节。

## 3. 开发工作流

```bash
pip install -r requirements.txt   # 依赖：fastapi/uvicorn/httpx/python-docx/python-multipart/pytest
python scripts/fetch_vendor.py    # 首次或更新前端依赖时（需联网）
python run.py                     # 开发服务
pytest -q                         # 回归测试（27 项）
python build_exe.py               # 打包 dist/墨语MoYu.exe
python build_exe.py --onedir      # 文件夹形态
```

运行配置（Base URL / API Key / 模型名）存在数据库 `app_settings` 表，开发机可在设置页或 mock_ai.py 联调。

## 4. 架构要点

- **数据层**（`app/db.py`）：零 ORM，裸 sqlite3 + 线程局部连接（`threading.local`）。新增字段走 `MIGRATIONS` 增量字典（旧库自动 ALTER TABLE），不要改 SCHEMA 里的旧表定义去冒充迁移。
- **字数口径**：`word_count()` = 去空白后的字符数（含标点、中英文）。
- **AI 安全模型**（贯穿所有 AI 功能）：生成 → 预览/差异对比 → 用户采纳 → 写入并自动进 `chapter_versions` → 可撤销。新增 AI 功能必须沿用此链路。
- **AI 客户端**（`app/ai_client.py`）：httpx 异步，SSE 流式解析 + 非 SSE 回退；错误已友好化（`AIError` 可直接展示）。**不要传 temperature 参数**——部分模型（如 kimi-k2.6）只允许 temperature=1，传了会 400。
- **配置**：`app_settings` 表 key-value，默认值在 `db.DEFAULT_SETTINGS`；新增设置项要在这里注册。
- **测试**（`tests/conftest.py`）：顶层先设 `MOYU_DB` 环境变量再 import app（模块导入期一次性求值路径）；导出/导入目录重定向到临时目录。测试不触碰真实 data/。

## 5. 代码风格（沿用现状）

- Python：中文注释与 docstring；路由函数薄、业务逻辑直白；状态用字符串枚举（如 chapters.status: draft/…）。
- 前端：无框架无构建，原生 ES 模块式 page 文件；Tailwind 运行时编译（浏览器端）；设计语言黛青 `#1B2A38` / 朱砂 `#D9483B` / Noto Serif 标题。
- UI 文案：中文、克制、有文气；错误提示要给人能看懂的原因和下一步。

## 6. 已知坑（联调实测，docs/AI联调记录.md）

1. 预设模型名可能在用户账号下不可用 → 404。设置页"测试连接"通过 ≠ 模型可用。
2. 模型"无问题时"可能返回空壳对象而非空数组 → 解析层过滤空条目。
3. 并行测试流会改 app_settings 的 ai_* 配置 → 联调前确认设置页仍为真实 Key。

## 7. 双版本同步约定

`moyu/`（本地版，主）与 `moyu-cloud/`（云端版）当前代码同构。改公共逻辑时两边一起改；云端版特有的只有：

- `app/main.py` 增加 MOYU_TOKEN 令牌门中间件（Cookie 通行，`?token=` 首次访问种 Cookie）
- `deploy/` 部署脚本与 `moyu.service`

若两边差异继续扩大，优先方案是抽公共包，而不是保持两份拷贝漂移。

## 8. 边界（不要做的事）

- 不要提交/上传 `data/`（含用户作品与 API Key）到任何远端。
- 不要在输出中回显用户的 API Key。
- 不要引入需要构建步骤的前端框架或 ORM——本地化、零构建是本项目的取舍。
- 不要静默改动 `dist/`、`release/` 里的产物；打包产物由 `build_exe.py` 重新生成。
- 破坏性操作（删数据、删表、重置数据库）前先问用户。

## 9. 接到任务时的建议路径

1. 读本文件 + README.md + docs/PRD-本地版.md
2. 按任务涉及模块读 `app/api/<模块>.py` 与对应 `static/js/pages/<页面>.js`
3. 改动后 `pytest -q` 全绿再交付；涉及打包时跑 `python build_exe.py` 验证
