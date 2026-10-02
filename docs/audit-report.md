# 墨语 MoYu 多端响应式与 VPS 生产部署 · 现状审计报告

> **报告版本**：v1.0.0  
> **审计日期**：2026-09-30  
> **状态**：阶段一完成（待用户审核确认，未改动任何代码）

---

## 1. 项目技术栈与系统架构澄清

在深入扫描前，首先界定「墨语 MoYu」当前的真实架构，澄清任务假设与实际代码形态的本质差异：

| 维度 | 实际实现形态 | 架构特征与约束 |
| :--- | :--- | :--- |
| **后端形态** | Python 3.10+ / FastAPI + Uvicorn | 异步轻量单体全栈服务，统一提供 RESTful API 及前端静态文件挂载。 |
| **数据持久层** | 裸 SQLite3（`data/moyu.db`） | 嵌入式单文件数据库，无外置数据库依赖；支持增量 SQL 迁移（`MIGRATIONS`）。 |
| **前端架构** | 原生 Vanilla JavaScript (ES6+) | **无 Node.js、无 package.json、无 npm/vite/webpack 构建流水线**。 |
| **样式与依赖** | Tailwind CSS (CDN/运行时编译) + Vendor 脚本 | 依赖通过 `scripts/fetch_vendor.py` 离线化至 `static/vendor/`。 |
| **客户端形态** | 双模运行（Windows 原生 pywebview + 浏览器模式） | 桌面版通过 PyInstaller 构建单文件 exe，内嵌 WebView2 内核。 |

> **核心结论**：本项目为标准的 **Python FastAPI 单体全栈应用**，所有前端产物直接由后端托管在 `/static` 路由下。因此，任务中关于 `package.json`、Node 构建流水线、微服务拆分等假设施加于前端是**不适用**的，部署与构建重点应在 **Python 容器化、环境变量解耦、数据目录持久化及 Nginx+systemd 生产化配置**。

---

## 2. 逐项审查：与目标的矛盾点及缺失项

### 2.1 依赖描述与构建配置 (`package.json`, `requirements.txt`)
- **文件路径**：`package.json`（缺失）、`requirements.txt`
- **现有内容**：
  - 根目录下不存在 `package.json`（原生 JS 前端，不需要 node 依赖）。
  - `requirements.txt` 声明了：`fastapi`, `uvicorn[standard]`, `httpx`, `python-docx`, `python-multipart`, `pywebview`, `pytest`。
- **与目标的矛盾点 / 缺失项**：
  - `requirements.txt` 包含了桌面 GUI 依赖 `pywebview`。在 VPS 纯无头 Linux 环境或 Docker 容器内构建时，`pywebview` 安装可能引入不必要的系统图形依赖或构建噪音（虽可通过 wheel 安装，但在纯服务端非必要）。
- **修改建议**：
  - 保持 `requirements.txt` 作为默认依赖，或区分基础服务端依赖，在 Dockerfile 中通过 `--no-cache-dir` 安装。无需添加虚构的 `package.json`。

### 2.2 启动入口与网络监听配置 (`run.py`, `app/paths.py`, `app/main.py`)
- **文件路径**：`run.py`, `app/paths.py`
- **现有内容**：
  - `run.py`: `uvicorn.run(create_app(), host="127.0.0.1", port=8321, log_level="info")`。
  - `app/paths.py`: 
    ```python
    if getattr(sys, "frozen", False):
        RESOURCE_DIR = Path(sys._MEIPASS)
        EXE_DIR = Path(sys.executable).resolve().parent
    else:
        RESOURCE_DIR = Path(__file__).resolve().parent.parent
        EXE_DIR = RESOURCE_DIR
    STATIC_DIR = RESOURCE_DIR / "static"
    DATA_DIR = EXE_DIR / "data"
    ```
- **与目标的矛盾点 / 缺失项**：
  - **严重阻塞 Docker/VPS 访问**：`run.py` 硬编码了 `host="127.0.0.1"`，在 Docker 容器内会导致外界请求无法穿透容器端口映射；
  - **端口不可配**：硬编码 `port=8321`，不支持通过环境变量动态切换；
  - **数据目录缺乏环境变量覆盖**：`app/paths.py` 的 `DATA_DIR` 固定为当前工作目录下的 `data/`。虽然 `app/db.py` 允许 `MOYU_DB` 覆盖数据库文件，但导出的文档、备份、日志等缺少统一的 `MOYU_DATA_DIR` 环境变量控制。
- **修改建议**：
  - 修改 `run.py`，支持从环境变量读取：`HOST = os.getenv("HOST", "127.0.0.1")`，`PORT = int(os.getenv("PORT", "8321"))`；容器启动命令传参 `--host 0.0.0.0 --port 8321`；
  - 在 `app/paths.py` 中引入 `MOYU_DATA_DIR` 环境变量支持，默认回退到原有本地 `data/` 逻辑，确保桌面单文件与容器化兼顾。

### 2.3 资源引用与绝对路径检查
- **文件路径**：`static/index.html`, `static/js/api.js`, `static/js/pages/*.js`
- **现有内容**：
  - `static/index.html` 引用静态资源使用绝对路径（如 `/static/css/app.css`）；
  - `api.js` 请求 API 使用 `fetch("/api" + url)`。
- **与目标的矛盾点 / 缺失项**：
  - 无硬编码 `localhost` 或 `127.0.0.1`，整体使用相对根路径 `/api` 和 `/static`。
  - 在标准 Nginx 反代（代理到 `127.0.0.1:8321` 根路径）时运行完全正常；但若部署在二级子路径（如 `example.com/moyu/`），根路径引用可能会失效。
- **修改建议**：
  - 针对根路径反代标准架构，当前设计无需侵入；在生产部署 Nginx 模版中明确提供根反代范例，并增加安全代理头（`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`）。

### 2.4 容器化与部署编排文件缺失
- **文件路径**：`Dockerfile`, `.dockerignore`, `docker-compose.yml`, `nginx/moyu.conf`, `systemd/moyu.service`
- **现有内容**：全量缺失。
- **与目标的矛盾点 / 缺失项**：
  - 缺乏轻量容器构建机制；
  - 缺乏容器卷 `data/` 的持久化挂载声明；
  - 缺乏容器健康检查配置（Healthcheck）；
  - 缺乏非 root 安全运行配置；
  - 缺乏生产环境反向代理与进程保活脚本。
- **修改建议**：
  - 补充 `Dockerfile`（基于 `python:3.11-slim`，非 root 用户 `moyu` 运行，剥离无关测试与编译缓存）；
  - 补充 `.dockerignore`（忽略 `tests/`, `.venv/`, `dist/`, `build/`, `*.spec`, `.git`, `data/`）；
  - 补充 `docker-compose.yml`（单服务 + 卷挂载 `./data:/app/data` + 8321端口映射 + healthcheck）；
  - 补充生产级 `Nginx` 配置模版与 `systemd` 单元服务文件。

### 2.5 多端响应式现状与目标规范差异
- **文件路径**：`static/index.html`, `static/css/app.css`, `static/js/ui.js`, `static/js/pages/`
- **现有内容**：
  - `v1.2.2` 已引入移动端视口声明、侧边栏抽屉折叠（`< 1024px`）、顶栏汉堡按钮、工作台三栏在手机端收拢为全宽编辑 + 快捷浮动呼出按钮；
  - 全局弹窗支持 `max-w-[calc(100vw-2rem)]` 防撑裂。
- **与新目标（移动端优先、375/393/768px、rem/clamp、≥44px触控）的差距点**：
  1. **断点策略**：当前响应式主要依赖 `lg:` (1024px) 一刀切切换，缺乏对 `md:` (768px 平板竖屏) 与 `sm:` (640px) 的精细化阶梯适配；
  2. **字号策略**：大部分文本采用 Tailwind 固化工具类（如 `text-xs`, `text-sm`, `text-base`），未全局接入 `clamp()` 响应式流式字号，移动端部分标题偏大或正文间距需优化；
  3. **触控热区全量覆盖**：虽然核心弹窗按钮满足 `min-h-[44px]`，但在部分复杂子页面（如 `prompts.js` 提示词标签、`board.js` 泳道细碎按钮、`timeline.js` 节点时间线操作项）中，仍存在局部小图标按钮（如 `h-7 w-7` 约 28px）未达到 44×44px 触控无障碍标准；
  4. **局部溢出隐患**：`workbench.js` 中的部分水平行（如字数统计状态条、底部状态指示符）在 375px 超窄屏下可能存在被挤压换行导致的视觉凌乱。
- **修改建议**：
  - 完善 CSS 触控热区辅助类（`touch-target` / `min-w-[44px] min-h-[44px]`）；
  - 针对 375px (iPhone SE)、393px (iPhone 15) 与 768px (iPad) 进行逐页面视口查缺补漏；
  - 保持桌面端（≥1024px）原有视觉 100% 绝对一致，杜绝任何桌面回归。

---

## 3. 假设校验（与开发指令第一节对照）

| 序号 | 初始指令假设 | 项目实际相符情况 | 差异说明与等效替代方案 |
| :---: | :--- | :---: | :--- |
| **1** | **多端范围**：桌面端浏览器 + 移动端浏览器，不含小程序和原生 App。 | **完全相符** | 目标一致。改造重心为 Web 视口响应式适配，保持既有 Windows 桌面版能力。 |
| **2** | **前端框架与构建工具**：假设存在前端构建流水线、package.json、打包输出目录。 | **不相符** | **实际为裸 Vanilla JS + 后端静态直接托管**。无前端打包环节，无需维护 package.json 或构建中间件。 |
| **3** | **部署方式 a**：Dockerfile 单容器构建（多阶段构建，镜像尽可能小）。 | **完全相符** | 可行。采用 `python:3.11-slim`，单容器内同时运行 FastAPI 并挂载静态资源，构建精炼镜像（预计 < 180MB）。 |
| **4** | **部署方式 b**：docker-compose 编排（针对多服务架构）。 | **部分相符** | 本项目为轻量单体架构（含内嵌 SQLite），非微服务体系。compose 将作为**单容器标准编排工具**，负责端口映射、重启策略与 `./data` 卷持久化，可选附带轻量 Nginx 容器反代。 |
| **5** | **部署方式 c**：传统裸机部署（Nginx 反代 + 进程守护 systemd 或 PM2）。 | **完全相符** | 可行。Python Web 应用标准生产守护方式为 **systemd**，等效替代 PM2，配合 Nginx 反代提供稳定服务。 |
| **6** | **代码规范工具**：ESLint / Prettier / EditorConfig。 | **缺失** | 原生静态项目目前无此类工具链。保持纯净度，避免引入 node 工具链，代码风格遵循已有原生规范。 |
| **7** | **持久化与数据安全**：SQLite 数据库与用户文件存储。 | **完全相符** | 所有用户数据严格集中于 `data/`。只需确保该目录在 Docker 与 VPS 上具有挂载点与权限保障，即可保障数据永不丢失。 |

---

## 4. 阶段一结论与下一步动作

1. 本阶段已彻底查清项目技术栈形态、部署关键阻塞点（`run.py` 127.0.0.1 绑定与端口硬编码）及移动端响应式待优化点；
2. **全程未修改任何代码与业务逻辑**，所有已有 55 项自动化测试保持绿灯；
3. 本报告保存于 `docs/audit-report.md`，请审核确认。获得确认后即可进入【阶段二：规范修订方案】。