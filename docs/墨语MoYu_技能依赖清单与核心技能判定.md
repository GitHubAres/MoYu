# 墨语MoYu 功能-技能依赖清单与核心技能判定

> 版本：v1.0（2026-10-10）｜代码基线：v2.1.1 + T 组（`9235a69`），pytest 207 全绿
> 结论先行：**13 个内置技能中，11 个有功能硬依赖（7 个 P0 核心 + 4 个 P1 工作流依赖），2 个无硬依赖。所有内置技能 API 层已禁止删除，真正的风险操作是「改名」与「禁用」。**

---

## 1. 技能被功能消费的三种机制

| 机制 | 代码位置 | 匹配方式 | 受影响功能 |
|---|---|---|---|
| ① 预设按钮兜底路由 | `app/features.py:103-125` `resolve_skill` + `:117` TASK_SKILL_MAP | 按 **name** 匹配 `default-{task}`，兜底 `default-continue` | 修撰使 5 按钮、写作台划词生成、`/generate` API |
| ② 内置工作流绑定 | `app/db.py:2568-2645` seed 时按 **name** 解析为 `workflow_steps.skill_id` | name→id（seed 时一次性固化） | 章节标准生产流、新书开坑五连流 |
| ③ 手动选用 | 修撰使/写作台技能选择器 `window.aiActiveSkillId` | 按 id | 所有 AI 入口 |

前端 `static/js/` 无任何硬编码技能名（已全量检索确认），依赖全部集中在后端这三层。

## 2. 全量依赖矩阵（13 个内置技能）

| 技能 name | 标题 | 消费它的功能 | 依赖机制 |
|---|---|---|---|
| `default-continue` | 续写 | 续写按钮；**全部任务的最终兜底**（`features.py:119` cand_names 第二顺位）；章节标准生产流·第1步 | ①② |
| `default-expand` | 扩写 | 扩写按钮 | ① |
| `default-shorten` | 缩写 | 缩写按钮（condense→shorten 映射） | ① |
| `default-rewrite` | 改写润色 | 润色按钮（polish→rewrite 映射）；章节标准生产流·第3步「润色定稿」 | ①② |
| `default-outline` | 大纲生成 | outline 任务（chat.py 支持）；新书开坑五连流·第4步「故事大纲」 | ①② |
| `default-analysis` | 分析评价 | 推演按钮（analyze→analysis 映射） | ① |
| `default-audit` | 设定检查 | check 任务（T-2 已修路由）；章节标准生产流·第2步「一致性检查」 | ①② |
| `novel-premise` | 故事立项 | 新书开坑五连流·第1步 | ② |
| `novel-world` | 世界观设定 | 新书开坑五连流·第2步 | ② |
| `novel-cast` | 人物与关系 | 新书开坑五连流·第3步 | ② |
| `novel-scene` | 分场细纲 | 新书开坑五连流·第5步 | ② |
| `de-ai-tone` | 去 AI 味 | **无自动入口**，仅手动选用；被其他技能正文交叉引用（`db.py:1191`、`:1349`） | ③ |
| `novel-forge` | 端到端写书总控 | **无任何功能引用**，仅手动选用 | ③ |

## 3. 核心技能判定（不能删除/不能改名/慎禁用）

### P0 核心层（7 个 default-*）——删掉或改名即功能降级

| 技能 | 失去它的后果 |
|---|---|
| `default-continue` | **双重致命**：续写按钮失去技能注入；且它是所有任务的最终兜底——它不在，`resolve_skill` 全部回落到 `BASIC_PROMPTS` 一句话硬编码 prompt（`features.py:147-150`），全部 AI 功能质量退回裸模型 |
| `default-rewrite` | 润色按钮 + 生产流润色步骤双双失效 |
| `default-audit` | check 任务 + 生产流检查步骤失效 |
| `default-expand` / `default-shorten` / `default-analysis` / `default-outline` | 对应按钮回落到一句话硬编码 prompt |

### P1 工作流依赖层（4 个 novel-*）——禁用即工作流报错

`novel-premise` / `novel-world` / `novel-cast` / `novel-scene`：五连流步骤按 id 调用，引擎走显式 `skill_id` 路径（`workflow_engine.py:271-272`），**被禁用时直接抛 400「已被禁用」**，对应步骤失败。

### P2 无硬依赖层（2 个）——理论上可移除，仅失去手动选项

- `de-ai-tone`：删除不破坏任何按钮/工作流；但其他技能正文里的交叉引用会变成死指引（文案层面）。
- `novel-forge`：全库零引用，纯手动技能。

## 4. 现有保护机制与真实风险

**已有的硬保护**：`DELETE /api/skills/{id}` 对 `source='builtin'` 直接 403（`app/api/skills.py:239-240`）——**13 个内置技能在产品内本来就删不掉**。且 seed 为 `ON CONFLICT(name) DO UPDATE`（`db.py:2507`），每次启动把内置技能正文/手册重置为代码版本——改动不持久，设计意图是「可复制副本后修改」。

**真实风险操作**（当前无防护）：

| 操作 | 入口 | 后果 | 风险等级 |
|---|---|---|---|
| **改名** | `PATCH /{id}`（`skills.py:185-228`，**无内置保护**） | 机制①按 name 匹配立即失效（如 `default-rewrite` 改名→润色按钮落到 `default-continue`）；重启后 seed 按原名**新插一行**，库里出现重复技能，工作流仍绑旧 id | ⚠️ 高 |
| **禁用** | `PATCH /{id}` enabled=0 | 机制②（工作流显式 skill_id）直接 400 报错；机制①（按钮兜底）**不检查 enabled**，禁用后照常用——两条路径行为不一致 | ⚠️ 中 |
| **改正文** | `PATCH /{id}` body_md | 当下生效，但**重启即被 seed 覆盖还原**，用户易误以为修改生效 | 低（可逆） |

## 5. 建议（观察项，本次不动代码）

1. `update_skill` 对 `source='builtin'` 禁止修改 `name` 字段（一行守卫），消除最高风险操作；
2. `resolve_skill` 兜底候选查询补 `AND enabled=1`，让两条路径行为一致；
3. 前端技能列表对 P0 技能（7 个 default-*）的「禁用」开关加确认提示（说明会影响哪些按钮/工作流）。

以上三条如需落地，按老规矩出任务书 + Codex 指令。
