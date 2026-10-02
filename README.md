# 墨语MoYu · 本地与云端 AI 小说写作工作台

> 一支笔、一炉丹、一盏灯——部署在本地或私有 VPS、数据不出机的一站式 AI 长篇创作工作台。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Docker-lightgrey)
![Data](https://img.shields.io/badge/data-100%25%20本地私有-orange)

「墨语MoYu」面向网文作者与长篇创作者：涵盖灵感孵化、大纲规划、正文写作、设定管理到作品导出的完整闭环。**全部数据存储在私有 SQLite**，AI 是严谨可控的创作助手——所有 AI 内容先预览、由你确认后才入库，绝不静默写入正文。

## ✨ 功能一览

| 模块 | 能力与特性 |
|---|---|
| 🖥️ 原生桌面与全端响应式 | 基于 Windows WebView2 原生窗口（1366x820），支持 --browser 外部浏览器与手机/平板自适应，全端无横向滚动条，移动端抽屉导航与大触控区适配（≥44×44px，clamp流式字号） |
| 🚢 生产级 VPS 与容器部署 | 官方提供轻量 Dockerfile（基于 python:3.11-slim，非 root 运行）、docker-compose 卷持久化、Nginx 反代（支持 AI 流式输出不卡顿）及 systemd 常驻守护支持 |
| 📚 书架仪表盘 | 作品管理、字数/今日目标统计卡片、搜索过滤、最近写作直达、灵感便签侧栏 |
| ✍️ 写作工作台 | 卷章拓扑树、沉浸大字号纯文本编辑器、自动保存、专注模式、查找替换、选区悬浮工具栏、章节拖拽排序 |
| 🤖 AI 修撰使 | 多轮对话式伴写窗口，支持按章节独立维护会话与重置，SSE 流式打字机生成，选区与设定库深度感知，采纳前自动快照留存且可一键撤销，内置经典多候选对比模式开关 |
| 📑 故事大纲 | 树形卷章大纲、节点详情摘要、卷章自动关联、AI 剧构推演与草稿生成 |
| 🗃️ 设定人物库 | 角色/地点/势力/物品等类型设定卡片 CRUD，正文智能识别关联，可一键挂载到 AI 上下文 |
| 🕸️ 关系图谱 | 人物与实体关系网络力导向图可视化，缩放/平移/拖拽，直观编辑势力关系连线 |
| ⏳ 剧情时间线 | 纵向大事记时间轴编排，事件概要、涉及章节与登场人物关联 |
| 🏛️ 伏笔看板 | 未解/推进中/已收线三泳道流转，埋笔描述、回收设想与章节定位 |
| ⚗️ 炼丹炉 | 故事骨架与立意推演 → 世界观法则生成 → 核心角色塑造 → 一键开炉建书生成长纲与设定集 |
| 🎨 丹青阁 | AI 生成作品封面与角色立绘，本地画廊管理，一键设为作品封面 |
| 🕰️ 版本快照 | 定时与 AI 采纳自动快照、手动快照、行级差异对比、一键无损回滚（恢复前自动留底） |
| 🛡️ 一致性检查 | AI 审计章节正文与设定集实体的冲突与前后矛盾，附原文引用定位与修改指引 |
| 💬 提示词中心 | 系统预置精调模板（续写/扩写/缩写/润色）+ 自定义提示词模板增删改查 |
| 📋 任务中心 | 异步后台 AI 任务列表、进度追踪、错误日志回溯与重试 |
| 🔄 软件自动更新 | 设置页内置版本检查与发布日志展示，支持稳定/尝鲜通道与国内镜像加速；桌面端引导下载与版本跳过；Linux/VPS 一键自动备份与代码平滑升级，Docker 支持 Watchtower 自动更新 |
| 📦 导入导出 | TXT/DOCX 智能正则拆章导入，全书/按卷多格式导出排版文稿，整库结构化备份 |
| 🔍 全局搜索 | Ctrl+K 极速唤起，跨作品/章节/设定/大纲全库秒级检索定位 |

## 🚀 安装与运行

### 方式 A：Windows 原生单文件桌面端（无需环境）
1. 从 [Releases](../../releases) 下载 `墨语MoYu-v1.4.0-win64.exe`
2. **双击运行**：直接打开沉浸式轻量原生窗口（依托系统内置 WebView2 运行，无黑框命令行，双击秒开）。
3. **关闭退出**：点击窗口右上角“关闭”按钮（×），程序自动优雅停止后台服务并退出，绝不留存后台僵尸进程。
4. **单实例保护**：重复双击 exe 不会发生端口争用冲突，会自动唤起激活已有运行中的墨语。
5. **浏览器回退模式**：命令行运行 `墨语MoYu-v1.4.0-win64.exe --browser` 或设置环境变量 `MOYU_WEBVIEW=0`，即可自动回退至外部浏览器访问模式。

### 方式 B：Linux VPS / 私有服务器 Docker 部署（一键上线）
```bash
# 1. 克隆代码
git clone https://github.com/GitHubAres/MoYu-V1.0.0.git /opt/moyu
cd /opt/moyu

# 2. 一键启动并自动持久化数据卷
docker compose up -d --build
```
> 详细 VPS 裸机（Nginx + systemd）与 Docker 部署指南详见 [docs/deployment.md](docs/deployment.md)。

---

## 🛠️ 从源码运行与本地开发

```bash
# 需要 Python 3.10+
pip install -r requirements.txt
python scripts/fetch_vendor.py   # 首次运行：本地化前端静态依赖
python run.py                    # 启动本地开发服务：http://127.0.0.1:8321
```

测试与打包构建：
```bash
python -m pytest -q          # 58 项 API、响应式与部署健康检查回归测试全绿
python build_exe.py          # 构建单文件 exe：dist/墨语MoYu-v1.4.0-win64.exe
python build_exe.py --onedir # 文件夹形态（便于调试与启动优化）
```

## 🧱 技术栈

- **后端**：Python 3.10+ · FastAPI · SQLite（标准库驱动，零 ORM，无外部数据库守护进程）
- **桌面视窗**：pywebview 5.x/6.x + Windows WebView2（Chromium 内核，极速轻量，无控制台黑框）
- **容器与部署**：Docker（多阶段构建，非 root 运行）、docker-compose、Nginx 反代模版、systemd 服务单元
- **前端**：原生 JavaScript 单页应用（SPA）+ Tailwind CSS（纯本地化，全端响应式自适应）
- **AI**：标准 OpenAI 兼容协议客户端（httpx 异步流式处理，固定超参规避模型限制）
- **数据存储**：SQLite 单文件数据库，支持通过 `MOYU_DATA_DIR` 环境变量指定持久化路径

## 🔒 隐私与数据安全

- 数据 100% 存在用户指定的数据目录（默认 `data/moyu.db`），无遥测、无后台日志上传
- 用户的 API Key 仅保存在 SQLite 数据库，不在前端日志或打包文件中回显
- 数据备份极简：直接拷贝 `data/` 目录即可无损迁移

## 📄 许可证

墨语 MoYu 遵循 MIT License 发布，许可证全文见根目录 LICENSE。
界面视觉语言基于 Literary Minimalist Ink（黛青 #1B2A38 + 朱砂 #D9483B）。
