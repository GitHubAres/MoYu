# 公告模块开发任务（交给 Codex 执行）

## ⚠️ 执行方式（必须遵守）
- **直接开始写代码，禁止长时间分析**。不要反复"Wait!/Let's check"式推理；文件内容如需确认，最多快速看一眼，然后立刻动手。
- 下面的设计要点已给出全部所需信息，**以此为准实现即可**，不要再全文通读其他文件。
- 每完成一个文件就写盘，不要攒到最后。

## 任务来源
严格按 `docs/公告模块开发计划书.md` 实现公告模块。计划书是权威需求文档，实现细节以它为准；如实现中发现计划与现状代码冲突，以计划书 §2 需求表为准，并在最终汇报中说明冲突点。

## 范围（本次必须完成）
- M1 后端：`app/db.py` 新增 `announcements`、`announcement_acks` 两张表；新增 `app/api/announcement.py`（`GET /api/announcements/latest`、`GET /api/announcements`、`POST /api/announcements/{id}/ack`），挂到 `app/api/__init__.py` 路由；双通道拉取（远程 URL 可配置，默认指向 GitHub Releases 的 announcement.json）→ 本地缓存 → `static/announcements/builtin.json` 兜底；httpx 5s 超时静默降级，风格对齐 `app/api/update.py`。
- M2 前端浮层：新增 `static/js/pages/announcement.js`（浮层组件 + 迷你 Markdown 渲染器，白名单防 XSS + URL 协议白名单）；`static/js/app.js` 在 `router.start()` 前调用 `announcement.checkOnBoot()`，失败绝不阻塞主流程；normal/force 两级交互按 plan §4.4；视觉对齐现有 `ui.js` 弹窗体系（design token，支持深色模式）；z-index z-[95]。
- M3 公告中心：`#/announcements` 路由 + 侧边栏「公告」入口；列表含标题/日期/已读状态，点击展开正文。
- M4 中的代码部分：撰写 `static/announcements/builtin.json`（内容为 V1.5.0 更新说明示例，level=normal）；检查 `moyu_entry.spec` / `build_exe.py` 确认新 json 会被打进包，缺则补上。**本次不实际运行打包、不发版**。

## 新增测试（tests/，pytest 风格对齐现有用例，≥8 条）
拉取成功入库、远程超时降级到缓存、双空走 builtin、ack 幂等、force 逻辑、min_app_version 过滤、XSS 渲染转义、列表排序。

## 红线
- 不改计划书、不动公告模块以外的代码、不 git commit/push（代码留在工作区由用户验收）。
- 不新增 npm/pip 依赖（vendor 不引入 marked.js）。
- 全部接口失败路径静默降级，前端任何异常不得阻塞 router 启动。

## 完成标准
`pytest -q` 全绿（含新增用例）。最终汇报：改动文件清单、测试结果、遗留风险。汇报写在 `docs/codex-report-announcement.md`，并在 stdout 里输出 "TASK_DONE" 标记。
