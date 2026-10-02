# 墨语 MoYu 规范与配置修订方案 (spec-changes.md)

> **制定日期**：2026-09-30  
> **依据**：`docs/audit-report.md` 阶段一审计结果与用户确认的目标  

---

## 1. 规范修订总览

针对「墨语」单体架构（FastAPI + 原生 JS + SQLite），为达成“多端响应式（移动端无横向溢出、44px触控、流式自适应）”与“VPS 生产部署能力（Docker、compose、Nginx反代、systemd）”，拟修订与新增以下规范及配置文件。

---

## 2. 逐项修订清单

### 2.1 后端服务与环境适配规范
1. **文件**：`run.py`
   - **修改项**：服务监听地址与端口配置
   - **改成什么**：从环境变量读取 `HOST`（默认 `127.0.0.1`，容器/VPS传入 `0.0.0.0`）与 `PORT`（默认 `8321`）。
   - **原因**：支持容器外界访问与自定义端口，解除本地硬编码绑定。
2. **文件**：`app/paths.py`
   - **修改项**：`DATA_DIR` 解析逻辑
   - **改成什么**：支持 `MOYU_DATA_DIR` 环境变量覆盖。若未设置，则保持原 PyInstaller 冻结/开发模式解析规则。
   - **原因**：允许 Docker 卷挂载（如挂载宿主机 `/var/lib/moyu/data`）或自定义生产环境存储路径。
3. **文件**：`app/main.py`
   - **修改项**：健康检查端点
   - **改成什么**：添加 `@app.get("/api/health")` 显式路由，返回 `{"status": "ok", "version": "1.2.3"}`。
   - **原因**：提供标准 Docker 与 Nginx 反代健康探测端点。

### 2.2 生产容器化规范文件新增
1. **文件**：`Dockerfile`
   - **内容**：多阶段轻量构建，基于 `python:3.11-slim`，安装生产依赖，创建并切换至非 root 用户 `moyu`，暴露 8321 端口，声明卷 `/app/data`，健康检查探测 `/api/health`。
   - **原因**：满足轻量、安全、单容器部署标准。
2. **文件**：`.dockerignore`
   - **内容**：忽略 `.venv/`, `tests/`, `dist/`, `build/`, `*.spec`, `.git`, `data/`, `__pycache__` 等开发测试与本地数据资产。
   - **原因**：缩减构建上下文大小，杜绝将本机敏感密钥和作品数据打包进镜像。
3. **文件**：`docker-compose.yml`
   - **内容**：标准单服务编排，映射 `8321:8321`，持久化卷 `./data:/app/data`，`restart: unless-stopped`，集成 healthcheck 与环境变量声明。
   - **原因**：实现一键部署与数据持久化。

### 2.3 裸机部署与生产反代规范文件新增
1. **文件**：`deploy/nginx/moyu.conf`
   - **内容**：Nginx 80/443 反代至 `127.0.0.1:8321`；配置静态文件缓存、`client_max_body_size 50M`；关闭 `proxy_buffering`（保障 AI 流式输出响应实时性）；传递标准 Host、X-Real-IP 等代理头。
   - **原因**：保障 VPS 裸机高并发、反代与长链接流式稳定性。
2. **文件**：`deploy/systemd/moyu.service`
   - **内容**：Linux 标准 systemd 服务单元配置，非 root 运行，`Restart=always`，指定虚拟环境 Python 启动。
   - **原因**：等效替代 PM2，实现 Linux 原生进程常驻守护与开机自启。
3. **文件**：`docs/deployment.md`
   - **内容**：全套从零到生产上线的部署指南（Docker、compose、Nginx+systemd 双路径完整操作手册）。

### 2.4 多端与移动端响应式样式规范
1. **文件**：`static/css/app.css`
   - **修改项**：流式字号与移动触控基线
   - **改成什么**：
     - 增加 `.touch-target` 触控辅助样式类：`min-width: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center;`；
     - 增加 `clamp()` 流式正文字号与标题层级规范，保障 375px/393px/768px 下排版自适应无横向溢出；
     - 增强 `@media (max-width: 640px)` 与 `@media (max-width: 1023px)` 下的表格、弹性盒子自然折行规则。
2. **文件**：`static/js/ui.js`
   - **修改项**：通用组件触控热区与弹窗移动自适应
   - **改成什么**：确保所有 `ui.btn`、`ui.icon` 点击包装器在移动端自动具备 `min-h-[44px]` 或合适的触控外边距，所有弹窗与抽屉在 375px~768px 下内边距与最大宽度紧凑自适应。
3. **文件**：`static/js/pages/workbench.js` 等业务页面
   - **修改项**：窄屏状态栏与操作栏布局优化
   - **改成什么**：工作台顶部状态栏与统计项在 `< 640px` 时采用网格两两自适应排布，防止挤压断行；大纲、看板、实体等移动端抽屉与浮动按钮热区核验。

---

## 3. 验收标准与验证方案

1. **测试用例 100% 绿灯**：新增环境变量覆盖测试与健康检查端点测试，原有 55 项测试全部通过。
2. **移动端视觉验证**：在 375px (iPhone SE)、393px (iPhone 15)、768px (iPad) 视口下，无横向滚动条、无元素溢出、触控区 ≥44px。
3. **桌面端视觉零回归**：在 1024px、1366px、1920px 桌面视口下，完全保持原有三栏/双栏沉浸体验。