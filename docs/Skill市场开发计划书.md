# 墨语MoYu · Skill 市场开发计划书（提示词中心 → Agent Skill 升级）

- **版本**：V1.0（草案）
- **日期**：2026-10-02
- **目标版本**：墨语 V1.6.0
- **依据规范**：Agent Skills 规范（SKILL.md frontmatter + 渐进式披露 + scripts/references/assets 三类资源）
- **约束**：本计划书只做设计，不改代码

---

## 1. 背景与目标

### 1.1 背景
墨语当前"提示词中心"是最简单的"一段文字模板"模式：用户建模板 → 模板整体顶替 system prompt。Agent Skill 规范代表了更先进的模式——技能 = **元数据（name/description）+ 核心指令（SKILL.md 正文）+ 按需挂载的资源（scripts/references/assets）**，配合渐进式披露控制上下文成本。目标是把提示词中心升级为 **Skill 市场**：以 Agent Skill 为功能核心，淘汰纯文字模板模式。

### 1.2 Agent Skill 规范要点（本计划的实现基准）
1. `SKILL.md` 必须：YAML frontmatter 仅含 `name`（小写字母/数字/连字符，≤64）与 `description`（触发依据，写清"是什么+何时用"）；正文为 Markdown 指令
2. 三类资源：`scripts/`（可执行代码）、`references/`（供读取的文档）、`assets/`（产出用素材）
3. 渐进式披露：元数据常驻 → 正文触发时加载 → 资源按需加载
4. SKILL.md 正文 <500 行，禁止 README 等多余文档文件
5. 技能可打包为 `.skill` 文件（zip 格式）分发与导入

### 1.3 目标
- 「提示词中心」更名并升级为「Skill 市场」，旧模板全面迁移为 Skill
- Skill 支持：元数据 + SKILL.md 正文 + references/scripts/assets 资源挂载 + .skill 导入导出
- AI 写作链路（工作台侧栏生成、多轮聊天）全部改走 Skill 注入
- 旧 prompts 接口与页面在本版退役（非双轨维护）

---

## 2. 现状分析（原功能运作模式）

### 2.1 数据与接口
- 表 `prompts`：`id / name / task_type / template / builtin`
- 任务类型 6 种：continue 续写、expand 扩写、shorten 缩写、rewrite 改写润色、outline 大纲生成、audit 设定检查
- 接口：`GET/POST /api/prompts`、`PATCH/DELETE /api/prompts/{id}`、`POST /api/prompts/{id}/duplicate`，实现在 `app/features.py` 的 `PromptLibrary` 类
- 内置种子：`BUILTIN_PROMPTS` 6 条精写模板（首启种子入库，builtin=1 不可删可副本）

### 2.2 消费链路（两处）
1. **工作台侧栏生成**：`workbench.js` 下拉选模板 → `prompt_id` → `AIOrchestrator.generate()`（features.py ~124 行）：`sys_prompt = template`，后接 LENGTH_HINTS 与【上下文】【选区】【要求】拼装
2. **多轮聊天**：`app/api/chat.py` ~172 行：同样 `sys_prompt = template` + 历史消息 + 结构化上下文

### 2.3 前端
- `pages/prompts.js`（236 行）：卡片网格、任务类型 Tab、统计（全部/内置/自定义）、新建/编辑弹窗、复制副本、删除、`{{占位符}}` 高亮预览
- 入口：侧边栏 `#/prompts`；`workbench.js` 第 72 行拉取 `/prompts` 填充下拉

### 2.4 ⚠️ 现状隐藏问题（升级时必须一并解决）
1. **占位符是死代码**：模板里写的 `{{context}}/{{selection}}/{{instruction}}` 在前后端均无任何替换逻辑（已核实 features.py / chat.py 无 replace）。模型实际靠 user 消息里重复拼装的【上下文】等工作，system prompt 里的 `{{}}` 原样残留——属于半成品状态
2. **无资源概念**：模板只能是纯文本，无法挂载参考文档（如"本书设定集""文风样例"），能力天花板低
3. **无分发形态**：技能无法导出分享/导入第三方

---

## 3. 总体设计

### 3.1 核心映射：渐进式披露 → 无 Tool 的 LLM API
墨语 AI 客户端（`app/ai_client.py`）是标准 OpenAI 兼容 chat/completions，**不支持 tool/function calling**。因此 Skill 的三级披露按以下方式落地：

| 层级 | 规范含义 | 墨语实现 |
|---|---|---|
| L1 元数据 | name+description 常驻 | 用户显式选中 Skill 时不必常驻；多 Skill 场景（后续）再注入"可用技能清单"。本期：description 参与校验与卡片展示 |
| L2 正文 | SKILL.md body 触发时加载 | **服务端渲染为 system prompt 主体**（替代旧 template 角色） |
| L3 资源 | scripts/references/assets 按需 | references：小文件（≤1500 token/个，总量 ≤3000）**自动内联**进 system prompt，超出截断并标注；scripts/assets：**仅列清单**（路径+说明），不内联——因为模型无法执行脚本，本版明确此定位 |

**本版 Skill 定位**：面向写作场景的"结构化技能包 = 指令正文 + 参考资源内联 + 资源清单"。不承诺通用 Agent 的脚本执行能力（待 AI 客户端支持 tool 后再升级，接口预留）。

### 3.2 system prompt 组装结构（新）
```
【技能】<title>（<name>@<version>）
<body_md，占位符已替换>
【参考资源】（如有内联 references，逐份带路径标题）
【附带资源清单】（如有 scripts/assets，仅列路径，一句话说明）
```
随后沿用现有 LENGTH_HINTS 与上下文拼装；**body 中出现过的占位符由服务端统一替换，替换后即不再重复 append 对应上下文块**（修复 2.4-1 的死占位符问题）。

---

## 4. 详细设计

### 4.1 数据模型（db.py 新增）
```sql
CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,          -- 规范名：^[a-z0-9][a-z0-9-]{0,63}$
    title       TEXT NOT NULL,                 -- 展示名
    description TEXT NOT NULL DEFAULT '',      -- 触发依据（L1）
    body_md     TEXT NOT NULL DEFAULT '',      -- SKILL.md 正文（L2）
    version     TEXT NOT NULL DEFAULT '1.0.0',
    enabled     INTEGER NOT NULL DEFAULT 1,
    applies_to  TEXT NOT NULL DEFAULT '',      -- 兼容旧任务类型：continue,expand,... 空=通用
    source      TEXT NOT NULL DEFAULT 'custom',-- builtin|custom|migrated|imported
    icon        TEXT NOT NULL DEFAULT 'auto_awesome',
    created_at  TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS skill_files (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    path       TEXT NOT NULL,                  -- 白名单：scripts/ references/ assets/ 前缀
    content    TEXT NOT NULL,
    size       INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    UNIQUE(skill_id, path)
);
```

### 4.2 迁移（首启自动执行）
- `prompts` 全量 → `skills`：`title=name`、`body_md=template`、`applies_to=task_type`、`source='migrated'`、`name='migrated-'||id`（若与规范名冲突则追加 `-2`）
- `BASIC_PROMPTS` 六件套 + `BUILTIN_PROMPTS` 全部转为 `source='builtin'` 的 Skill（name 用 `default-continue` 等规范名）
- `AIOrchestrator.BASIC_PROMPTS` 保留为"未选 Skill 时的兜底默认 Skill"，行为不变
- 迁移记录写入 `app_settings.skill_migration_done=1`，幂等不重复

### 4.3 后端 API（新增 app/api/skills.py，风格对齐现有 router）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/skills` | 列表（支持 `applies_to`、`enabled`、`source` 过滤），含 files 数量摘要 |
| POST | `/api/skills` | 新建（服务端强制校验 name 规范、description 非空） |
| GET | `/api/skills/{id}` | 详情（含全部 files） |
| PATCH | `/api/skills/{id}` | 改元数据/正文/启停 |
| DELETE | `/api/skills/{id}` | 删除（builtin 禁止，可复制副本） |
| POST | `/api/skills/{id}/duplicate` | 复制副本 |
| PUT/DELETE | `/api/skills/{id}/files/{path}` | 资源文件写/删（路径白名单校验） |
| POST | `/api/skills/import` | 上传 .skill（zip）导入，见 4.5 |
| GET | `/api/skills/{id}/export` | 导出 .skill 下载 |
| POST | `/api/skills/{id}/validate` | 规范校验，返回结构化问题清单 |
| — | ~~`/api/prompts`~~ | **本版移除**（前端两处调用同步改造） |

### 4.4 AI 集成（features.py + chat.py）
- 新增公共 helper `build_skill_system_prompt(skill_id, *, context, selection, instruction, length)`：
  1. 查 Skill（不存在/未启用 → 400）；2. body_md 占位符统一替换；3. references 内联（token 预算+截断标注）；4. scripts/assets 列清单；5. 拼接 LENGTH_HINTS
- `_GenIn.prompt_id` → `skill_id`（字段更名，旧字段本版直接移除不留兼容）；chat.py 同样改造
- 兜底：无 skill_id 时走 `default-continue` 内置 Skill（即现 BASIC_PROMPTS["continue"] 的 Skill 化）

### 4.5 导入 / 导出 / 校验
- **导入 .skill**：解压 → 根目录唯一 `SKILL.md` → 解析 frontmatter（name/description 必填）→ 资源文件按白名单落库（拒绝 `..`、绝对路径、可执行位诉求；单文件 ≤200KB、总 ≤1MB）→ name 冲突自动改名 `<name>-imported`
- **导出**：由字段重建 frontmatter + 挂载文件打 zip，扩展名 `.skill`
- **校验规则**：name 正则、description 非空且 ≥20 字（警告级）、body <500 行、资源路径白名单、无 README 等多余文件（警告级）、frontmatter 仅 name/description 两字段

### 4.6 前端（pages/skills.js 全新页面，替换 prompts.js）
- **路由/入口**：`#/skills`，侧边栏「Skill 市场」（图标 `auto_awesome`）；旧 `#/prompts` 自动重定向
- **卡片**：图标、title、name@version、description 摘要、applies_to 标签、来源徽标（内置/迁移/导入/自定义）、启停开关
- **编辑**：双栏——左元数据表单（name/title/description/applies_to/version/enabled）+ 右 SKILL.md 编辑器（沿用占位符高亮，新增 frontmatter 模板插入按钮）
- **资源管理器**：文件列表（路径/大小/更新 time）、新建/编辑/删除；scripts/assets 内容只读预览，references 可编辑
- **工具条**：校验（红绿清单）、导入 .skill、导出 .skill、复制副本、删除
- **workbench.js 改造**：模板下拉 → Skill 下拉（`api.get("/skills?enabled=1")`，显示 title+applies_to 分组），提交参数 `skill_id`

---

## 5. 里程碑与任务拆解

| 阶段 | 任务 | 产出 | 预估 |
|---|---|---|---|
| M1 数据层 | skills/skill_files 表 + 迁移脚本 + 内置 Skill 种子 | 库就绪 | 0.5 天 |
| M2 后端 API | skills.py 全套 CRUD + files + import/export/validate | 接口可用 | 1 天 |
| M3 AI 集成 | build_skill_system_prompt + generate/chat 改造 + workbench.js 参数切换 | 链路通 | 0.5 天 |
| M4 前端页面 | skills.js 全页面 + 导航/路由/重定向 + 资源管理器 + 导入导出 UI | 页面可用 | 1 天 |
| M5 测试验收 | pytest ≥10 条新用例（迁移幂等、CRUD、白名单拦截、导入校验、导出往返、prompt 组装、占位符替换、兜底、builtin 删除保护、禁用 400）+ 打包走查 | 可发布 | 0.5 天 |

合计约 **3.5 天**。

---

## 6. 验收标准
1. 老用户升级首启：`prompts` 数据全部以 Skill 形态出现在 Skill 市场（来源标记"迁移"），AI 生成结果与旧版无感差异
2. 内置 6 任务 Skill 不可删除、可复制副本
3. 一个带 references 的 Skill 在生成时：正文替换占位符、references 内联、scripts 只列清单
4. 导出→清空→导入往返后内容一致；非法 .skill（缺 frontmatter/路径穿越/超大）被拦截并给出中文提示
5. `#/prompts` 旧链接重定向到 `#/skills`；`/api/prompts` 返回 404
6. `pytest -q` 全绿（含新增），`build_exe.py` 打包实测通过

---

## 7. 风险与对策
| 风险 | 对策 |
|---|---|
| AI 无 tool 能力，scripts 成摆设 | 本版明确定位"清单可见不可执行"；接口与数据模型已为未来 tool 化预留 |
| references 内联撑爆上下文 | 单文件/总量 token 预算 + 截断标注；校验时提示过大文件 |
| 迁移后行为差异引发用户感知 | 兜底 default Skill 与旧 BASIC_PROMPTS 完全同文；验收第 1 条做无感回归 |
| 第三方 .skill 恶意路径 | 导入白名单 + 尺寸上限 + 不解压执行任何文件 |

---
*本计划书由 Kimi（OpenClaw 主会话）依据 Agent Skills 规范与墨语 V1.4.0 现状编写，供 Codex 开发参考。冲突时以 §1.3 目标为准。*
