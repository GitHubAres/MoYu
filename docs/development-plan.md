# 墨语 MoYu 多端响应式与 VPS 生产部署 · 开发计划书 (v1.2.3)

> **制定日期**：2026-09-30  
> **版本**：v1.2.3  
> **依据**：`docs/audit-report.md`、`docs/spec-changes.md` 与用户目标  

---

## 1. 里程碑拆分与依赖关系

本次开发严格遵循“规范修订 → 部署基础设施就绪 → 响应式精细优化 → 自动化验证”顺序，双线并行推进：

```
[阶段一: 现状审计 (已就绪)] 
       ↓
[阶段二: 规范修订清单 (已就绪)]
       ↓
[阶段三: 开发实施]
  ├── 里程碑 1 (B线): VPS 部署与环境解耦基础设施 (Dockerfile, compose, nginx, systemd, docs/deployment.md)
  ├── 里程碑 2 (A线): 多端响应式进阶改造 (CSS clamp/touch-target, 工作台及业务页窄屏精细化)
  └── 里程碑 3: 自动化测试补齐与交付验收 (回归测试 100% 绿灯, docs/v1.2.3-development-notes.md 归档)
```

---

## 2. 详细工作分解

### 2.1 工作线 B：VPS 部署与环境解耦 (优先落地，解除容器环境阻碍)
- **任务 B.1**：`run.py` 改造，支持 `HOST`、`PORT` 环境变量；`app/paths.py` 支持 `MOYU_DATA_DIR`。
- **任务 B.2**：`app/main.py` 增加 `/api/health` 健康检查端点。
- **任务 B.3**：编写轻量多阶段 `Dockerfile`（基于 `python:3.11-slim`，非 root 用户 `moyu` 运行，工作区 `/app`，对外暴露 `8321`）。
- **任务 B.4**：编写 `.dockerignore`，排除无关环境、测试文件及敏感数据。
- **任务 B.5**：编写 `docker-compose.yml`（持久化卷 `./data:/app/data`，健康探测，重启策略）。
- **任务 B.6**：编写 `deploy/nginx/moyu.conf` 反代模版与 `deploy/systemd/moyu.service` 守护单元。
- **任务 B.7**：编写 `docs/deployment.md` 生产部署指南。

### 2.2 工作线 A：多端响应式精细化适配
- **任务 A.1**：`static/css/app.css` 扩充 `.touch-target`（≥44×44px）、流式字号 clamp 规则与小屏折行保底。
- **任务 A.2**：`static/js/ui.js` 统一触控热区封装与弹窗小屏宽度保护。
- **任务 A.3**：`static/js/pages/workbench.js` 对齐 375px/393px/768px 响应式，优化字数统计与操作控制条在窄屏下的自然流动。
- **任务 A.4**：检查 `static/js/pages/` 下全部子页面（`board.js`, `outline.js`, `entities.js`, `prompts.js`, `settings.js`），消除窄屏横向撑裂隐患，确保触控元素满足无障碍标准。

### 2.3 验证与测试
- **任务 C.1**：编写 `tests/test_deploy_and_env.py`，验证环境变量覆盖与 `/api/health` 正常返回。
- **任务 C.2**：编写/扩充 `tests/test_responsive.py`，验证 44px 触控类、clamp 流式样式与关键视口规则。
- **任务 C.3**：运行全量回归测试，保证 100% 绿灯。
- **任务 C.4**：归档 `docs/v1.2.3-development-notes.md`。

---

## 3. 验收标准

1. **功能与业务零改动**：小说编写、AI 润色修撰、大纲与设定等核心功能无任何破坏。
2. **桌面端表现零回归**：在 ≥1024px, 1366px, 1920px 桌面视口下，完全保持原书斋三栏体验。
3. **移动端完全可用**：在 375px, 393px, 768px 下无全屏横向滚动条、无文字溢出，关键操作按钮触控热区 ≥44×44px。
4. **一键部署就绪**：`docker-compose up -d` 即可拉起完整服务并安全持久化数据。