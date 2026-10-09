# 墨语 MoYu 公告模块（Announcement）开发与交付汇报

> **日期**：2026-10-02  
> **任务来源**：`docs/公告模块开发计划书.md` 与 `docs/codex-task-announcement.md`  
> **状态**：全部里程碑（M1、M2、M3、M4 及单测套件）已按规范完成，全量测试 100% 绿灯通过。

---

## 一、改动文件清单

| 文件路径 | 模块 / 归属 | 改动说明 |
|---|---|---|
| `app/db.py` | 数据库持久层 | 登记 `announcements`（公告快照表）与 `announcement_acks`（用户确认表）；在 `DEFAULT_SETTINGS` 注册 `announcement_url` |
| `app/api/announcement.py` | 后端服务 API (M1) | 实现 `GET /api/announcements/latest`、`GET /api/announcements`、`POST /api/announcements/{id}/ack`；三级降级策略（远程源 5s 超时 → 本地缓存快照 → 内置 JSON 兜底）；支持版本比对与时间窗口过滤 |
| `app/api/__init__.py` | 路由总线 (M1) | 挂载 `announcement.router` 至全局 `/api` 路由 |
| `static/js/pages/announcement.js` | 前端组件与页面 (M2/M3) | 启动公告浮层（z-[95]，normal 与 force 两级交互策略）；200 行内迷你安全 Markdown 渲染器（白名单标签 + 仅允许 `https:` 协议链接防 XSS）；实现 `#/announcements` 公告中心页面 |
| `static/js/app.js` | 前端启动总线 (M2) | 在 `router.start()` 前调用 `announcement.checkOnBoot()`，严格保证异常时静默降级、绝不阻塞主流程 |
| `static/index.html` | 页面框架与入口 (M3) | 侧边栏导航增加「公告中心」入口；页面底部引入 `announcement.js` 脚本 |
| `static/announcements/builtin.json` | 内置兜底数据 (M4) | 随版本发布的离线内置公告兜底文件（V1.5.0 更新说明，level=normal） |
| `tests/test_announcement.py` | 测试套件 | 9 项自动化单元测试，覆盖远程拉取入库、超时降级、内置兜底、ack 幂等、force 逻辑、min_app_version 过滤、XSS 转义、列表倒序排序、生效时间窗口判定 |

---

## 二、测试结果

- **测试命令**：`.venv\Scripts\python.exe -m pytest -q`
- **执行结果**：**86 passed, 1 warning (6.92s)**（通过率 **100%**）
- **用例构成**：
  - **既有用例**：77 条已有回归用例（覆盖 API、AI 聊天、工作台、画廊、部署环境、响应式、更新模块等）全绿通过，无任何功能回退；
  - **新增用例**（`tests/test_announcement.py`，共 9 条全部通过）：
    1. `test_fetch_remote_and_save_to_db`：远程拉取成功并正确落库持久化；
    2. `test_remote_timeout_falls_back_to_cache`：远程连接超时 5s 时静默降级至本地缓存快照；
    3. `test_empty_remote_and_empty_cache_falls_back_to_builtin`：双空状态下无缝兜底读取 `builtin.json`；
    4. `test_ack_idempotency_and_types`：ack 记录更新的幂等性与非法类型拦截；
    5. `test_force_level_logic`：force 级重要公告字段及确认状态返回；
    6. `test_min_app_version_filtering`：客户端版本低于 min_app_version 时自动过滤远端公告；
    7. `test_announcement_list_sorting_and_acked_flags`：公告中心列表按拉取时间倒序排列及已读/未读状态回显；
    8. `test_xss_protection_and_markdown_rules`：Node 运行隔离验证迷你渲染器对 `<script>`、`onerror`、`javascript:`、`http:` 的彻底剥除与 HTML 转义；
    9. `test_time_window_filtering`：starts_at 与 ends_at 生效时间窗口精确判定。

---

## 三、遗留风险与评估

1. **远程源连通性与高并发**：
   - *风险*：国内部分网络环境下访问 GitHub Releases 托管的 `announcement.json` 可能偶发超时。
   - *对策*：后端设置了 5 秒短超时 + 静默降级本地缓存与内置 JSON，不会产生任何错误弹窗；同时支持复用设置页已有的 `update_mirror` GitHub 镜像加速代理。
2. **XSS 安全防线**：
   - *风险*：远程公告若被第三方恶意篡改，可能注入脚本。
   - *对策*：渲染器遵循纯白名单转义，链接严格校验 `^https:\/\/` 正则，任何 `javascript:` 或非安全协议直接剥除或降级为纯文本，无 DOM 注入风险。
3. **打包包含检查**：
   - *核验*：已查验 `build_exe.py`，其通过 `shutil.copytree(BASE / "static", ...)` 自动将 `static/` 整体打包进可执行文件，`static/announcements/builtin.json` 确认会被完整纳入打包资源。
