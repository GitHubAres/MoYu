# 墨语MoYu 技能路由补齐与润色技能升级任务书（T 组）

> 版本：v1.0（2026-10-10）
> 前置：sepia 移植（S 组）已完成并发布 v2.1.1，测试基线 **204 全绿**
> 执行方式：断言先行、先红后绿；每完成一个实现阶段跑 `.venv/Scripts/python.exe -m pytest -q`，基线只增不减
> 提交前缀：`test(route-T1a)` / `fix(skill-T1)` / `fix(route-T2)`

---

## 1. 背景与诊断结论（已代码级核实）

S 组把 sepia v2 方法论移植进了 `de-ai-tone` 技能，但**修撰使「润色」按钮消费的从来不是它**。全按钮路由核查结果：

| 修撰使按钮 | task | 路由命中技能 | 绑定手册 | 最新内容是否接入 |
|---|---|---|---|---|
| 续写 | continue | `default-continue`（`app/db.py:661`） | STYLE_FINGERPRINT + PROSE_CRAFT（S3 已升级）+ GENRE_PLAYBOOK | ✅ |
| 扩写 | expand | `default-expand`（`app/db.py:697`） | EXPANSION_CRAFT | ✅ |
| 缩写 | condense | `default-shorten`（`app/db.py:731`） | COMPRESSION_FORMATS | ✅ |
| **润色** | polish | `default-rewrite`（`app/db.py:765`） | REWRITE_DIMENSIONS | ❌ **sepia v2 未接入** |
| 推演 | analyze | `default-analysis` | ANALYSIS_RUBRIC | ✅ |

路由机制（`app/features.py:103-125`）：`resolve_skill` 在无 `skill_id` 时按 `TASK_SKILL_MAP`（`app/features.py:117`）映射后找 `default-{task}` 技能；`polish` 映射为 `rewrite`，命中 `default-rewrite`——S 组未触碰该技能（提交 `01b99ab` 中 `default-rewrite` 区域出现 0 次）。

**另外发现一个路由 BUG**：`chat.py:141` 与 `features.py:234` 支持 `check`（一致性检查）任务，但 `TASK_SKILL_MAP` 没有 `check` 映射 → `resolve_skill` 去找不存在的 `default-check` → **回退命中 `default-continue`（用续写技能做设定检查）**。正确目标是已存在的 `default-audit`（`app/db.py:993`「设定检查·脉络稽核」，绑定 CONSISTENCY_TAXONOMY 手册）。

**无需处理的部分**（已核实正常）：内置工作流按技能 name 绑定（`app/db.py:2584-2589` 润色定稿步骤用 `default-rewrite`），T-1 升级后自动受益；14 份手册全部有技能绑定，无孤儿；`de-ai-tone` 保持为手动选用的专项技能（设计如此，不改）。

## 2. 红线

1. `app/db.py` 的 BUILTIN_SKILLS 只改 `default-rewrite` 一个字典项；其余技能（含 `de-ai-tone`）一字不动。
2. `default-rewrite` 的 body_md 必须**保留** `{{context}}`、`{{selection}}`、`{{instruction}}` 三个占位符与原有 5 条改写准则原文；只做增补，增量 ≤ 2000 字符（该技能正文全文注入 prompt，体积即成本）。
3. `TASK_SKILL_MAP` 只追加键，不改动现有三个映射。
4. 不新增 MIGRATIONS、不动 `data/`——seed 为 `ON CONFLICT(name) DO UPDATE`（`app/db.py:2507`），启动自动覆盖老库。
5. 不动任何前端文件、不动 `app/builtin_skill_data.py`（AI_TONE_CATALOG 手册本体已是 S2 最新版，直接复用引用）。

## 3. 环境

- 仓库：`D:\KimiCode工作区`；测试：`.venv/Scripts/python.exe -m pytest -q`（基线 **204**）
- 版本：v2.1.1（`8c78b72`）

## 4. 执行阶段

### T-1a 断言先行（先红）

在 `tests/test_skills.py` 末尾追加（风格与文件内现有用例一致，可直接 `from app.features import resolve_skill`，其内部自行 `get_db()`，无需 client fixture）：

1. `resolve_skill(None, "polish")` 命中的技能 `name == "default-rewrite"`，且其 `body_md` 含「校准三原则」字样（当前不含 → 红）。
2. `resolve_skill(None, "check")` 命中的技能 `name == "default-audit"`（当前命中 `default-continue` → 红）。
3. `default-rewrite` 在 skills 表中的 `files`（查 `skill_files` 表该技能 path 列表）包含 `references/ai-tone-catalog.md`（当前只有 `references/rewrite-dimensions.md` → 红）。注意：断言前先确保库已 seed（测试库由 conftest 初始化即含内置技能）。

运行确认 3 条全红后提交：`test(route-T1a): 润色/检查技能路由与手册绑定断言`。

### T-1 升级 default-rewrite（转绿断言 1、3）

修改 `app/db.py:765-797` 的 `default-rewrite` 字典项，两处：

**(a) body_md 增补**（在「控 AI 腔」准则之后、「请直接输出改写后的正文」之前插入），内容要点（中文，压缩自 sepia v2，总量 ≤2000 字符）：

- **校准三原则**：瞄准区间不反极（回归正常人类表达区间，不矫枉过正走到另一极端）；选择不堆砌（每处只选最有效的一处修改，不把技巧叠满）；留白（允许句子短、允许不完整，不要把所有松散处都拧紧）。
- **编辑比例约束**：74% 替换 / 18% 删除 / 8% 新增；新增仅限必要的事实具象化；润色后篇幅明显变长即为改错。
- **三关自检指针**：改完按三关过一遍——叙事架构（这场戏有没有非如此不可的理由）、语篇流（每段是否回答读者当下疑问、有无中段塌陷）、表层风格（黑名单词、排比、总结式升华）；详细对照见 `references/ai-tone-catalog.md`。
- **自检清单追加**（并入原有「改写准则」之后）：校准三原则复核；黑名单清扫（对照 ai-tone-catalog）。

**(b) files 追加一行**（格式照抄 `app/db.py:1594-1597` de-ai-tone 的绑定）：

```python
        "files": [
            ("references/rewrite-dimensions.md", REWRITE_DIMENSIONS),
            ("references/ai-tone-catalog.md", AI_TONE_CATALOG),
        ],
```

效果：润色/改写调用时，`build_skill_system_prompt` 会把该手册按现有渐进式内联机制注入（`app/features.py:185-216` 的 references 内联段），无需改任何注入代码。

运行测试确认断言 1、3 转绿、基线不降，提交：`fix(skill-T1): default-rewrite 接入 sepia v2 校准体系与痕迹词表`。

### T-2 修复 check 路由（转绿断言 2）

`app/features.py:117` 改为：

```python
        TASK_SKILL_MAP = {"condense": "shorten", "polish": "rewrite", "analyze": "analysis", "check": "audit"}
```

运行测试确认断言 2 转绿、全量基线不降，提交：`fix(route-T2): check 任务路由至 default-audit`。

### T-3 全量回归

`.venv/Scripts/python.exe -m pytest -q` 全绿（预期 **207**），工作区无任务书外改动。

## 5. 验收清单

- [ ] `resolve_skill(None, "polish")` → `default-rewrite`，body 含「校准三原则」
- [ ] `resolve_skill(None, "check")` → `default-audit`（不再落到 `default-continue`）
- [ ] `default-rewrite` 的 skill_files 含 `references/ai-tone-catalog.md`
- [ ] `default-rewrite` 的 `{{context}}/{{selection}}/{{instruction}}` 占位符与原 5 条准则原样保留
- [ ] 其余 12 个内置技能定义零改动（可用 `git diff app/db.py` 核对仅 `default-rewrite` 一个区块）
- [ ] pytest 207 全绿

## 6. 手动验收（修复完成后用户侧确认）

1. 重启墨语（本地与 VPS 各一次，让 seed 覆盖生效）；
2. 修撰使选中一段文字 → 点「润色」→ 发送前展开「本次调用」步骤详情，「匹配写作技能」应显示 `default-rewrite`，且产出文风可见校准约束效果（不堆叠技巧、篇幅不明显变长）；
3. 技能列表中 `default-rewrite` 的 references 里应能看到 `ai-tone-catalog.md`。
