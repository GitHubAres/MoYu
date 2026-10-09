# 墨语 MoYu — AI 产出输入输出契约落地・执行任务书

> 本文件是 Codex 的执行依据。Codex 无需在对话中接收长指令，只需被指向本文件并按阶段执行。
> 设计依据：`docs/墨语MoYu_AI产出输入输出契约规范.md`（第 3、4、5 部分）。
> 工程红线：以 `AGENTS.md` 为准，本任务书未提及之处一律遵守 AGENTS.md。

---

## 零、开工前必读（三个文件，读完再动手）

| 文件 | 作用 |
|:---|:---|
| `AGENTS.md` | 项目主规范与工程红线，全文遵守 |
| `docs/墨语MoYu_AI产出输入输出契约规范.md` | 本次改造的设计依据（第 3、4、5 部分） |
| `docs/v2.0.0-development-notes.md` | 当前版本进度基准 |

### 四个必须读懂的现状事实（已实测核对，实现须基于此）

1. `app/workflow_assets.py:75` `extract_structured_assets_from_text()` 是唯一的资产抽取入口，
   被 `app/api/workflows.py:336/337/351` 和 `app/api/entities.py:353,358` 调用。
2. `app/workflow_assets.py:287` 的 `card_pattern` 无条件把「### 任意词」当档案卡吸收，
   导致 AI 输出里的章节标题（如「### 伏笔暗线」）被当成实体入库。
3. `app/workflow_assets.py:71` `clean_str()` 只做了 `re.sub(r'[*#_`]', '', s).strip()`，
   不识别套话行、不识别纯标题行。
4. `app/workflow_engine.py:29` `_truncate_prev()` 对超过 4100 字的前序输出只留头尾各 2000 字，
   中段插「……[中段内容已截断]……」，这是「上一步结果喂给下一步理解不到位」的直接原因。

---

## 一、红线（违反即失败）

| 编号 | 红线 |
|:---|:---|
| R1 | 原生 JS、无构建步骤；不引入任何新的第三方依赖（只用标准库 `re`/`json` 等） |
| R2 | **不新增/修改任何数据库 DDL 与 MIGRATIONS**（本次不需要动表结构；步骤间结构化资产在渲染时实时解析，不落新列） |
| R3 | 不碰 `data/` 目录（用户数据） |
| R4 | **保持向后兼容**：旧的 `{{steps.N.output}}` 引用行为不得改变（仍按原规则截断） |
| R5 | 不动 `app/api/ai.py`、`alchemy.py`、`style.py` 三个 shim；不动 `build/` 与 `dist/` |
| R6 | **本次不处理 notes 资产被静默丢弃的问题**（遗留项 R-1，另行处理）。涉及 notes 的代码路径保持现状，只做净化与校验，不改变其是否入库 |
| R7 | 测试隔离库、`pytest` 全绿才能进下一阶段；不改 `conftest.py` 的隔离策略 |
| R8 | 每阶段一个 commit，message 固定格式见各阶段末尾 |

---

## 二、要解决的问题（判断实现是否到位的背景）

用户实际遇到的现象：写作工作流跑完后，结果里混着「以下是修改后的内容」「希望以上对你有帮助」
这类套话和大量 markdown 标题，这些内容被资产中枢原样吸收并分发给万相谱/大纲/时间线/伏笔看板，
导致消费方出现「伏笔暗线」被当成实体、「世界观 · 设定」被当成设定条目、真正的时间线事件反而漏抽。

四层缺口，本次全部补齐：

| 层 | 缺口 |
|:---|:---|
| A | 没有净化层，脏文本直达抽取器；抽取器靠正则猜格式，没有机器可读契约 |
| B | 步骤间传的是被腰斩的自由文本，下一步只能靠猜 |
| C | 资产中枢照单全收，不拒绝脏数据，也不告诉用户过滤了多少 |
| D | 14 份内置技能手册里有 6 份完全没写交付格式，AI 侧无从遵守 |

---

## 阶段 A：新增净化层 + 抽取器接契约（核心，改动集中）

### A-1 新建 `app/services/output_normalizer.py`

实现且仅实现下列四个函数（不要塞别的东西）：

**① `strip_ai_chatter(text: str) -> str`** — 删除 AI 套话行。判定规则（大小写不敏感，去空白后匹配）：

- 整行命中**前缀词表**即删除该行：
  「好的」「好的，」「以下是」「以下为」「如上所述」「综上所述」「这是为您」「这是给你」
  「希望以上」「希望这」「希望能」「如需」「如果需要」「如有需要」「请注意」「注意：」
  「供你参考」「供您参考」「祝你」「祝创作」「感谢」「期待」「如果有任何」
- 整行命中**包含词**即删除该行：
  「修改后的内容」「修改后的正文」「修改后的版本」「改写后的内容」「优化后的内容」
  「完整内容如下」「内容如下：」「这是我的创作」「希望对你有帮助」
  「如有任何问题」「请随时告诉我」「随时告诉我」
- 删除纯分隔线行（整行只由 `---` `===` `***` `___` 组成）
- **只删「整行命中」的行，绝不做全文子串替换**，保留正文中的正常句子
- 返回删除后文本，保留原有换行结构

**② `strip_heading_only_lines(text: str) -> str`** — 删除「纯标题行」：
整行匹配 `^\s{0,3}#{1,6}\s*.+$`，且去掉 `#` 与空白后长度 ≤ 20 且不含冒号「：」「:」，
视为纯标题行并删除。若标题行后面紧跟着非空内容行，仍删除标题行本身（内容保留）。

**③ `extract_assets_block(text: str) -> dict | None`** — 解析资产契约块。
块格式严格为：以 `<!-- MOYU:ASSETS` 开头，以 `MOYU:ASSETS -->` 结尾，中间是 JSON 对象。
解析成功返回该 dict（键限定 `entities` / `relations` / `timeline_events` / `foreshadows` / `outline_nodes`，
缺失的键补空 list）；失败或块不存在返回 `None`。
JSON 解析必须容错：允许块内出现中文引号、尾随逗号、``` 围栏，先剥离围栏与注释符再 `json.loads`。

**④ `sanitize_asset_item(item: dict, kind: str) -> tuple[bool, str]`** — 单条资产校验，
返回 `(是否通过, 不通过原因)`，原因要能直接展示给用户：

- 取标题字段：`foreshadow`→`title`，`timeline_event`→`event`，`entity`→`name`，
  `outline_node`→`title`，`relation`→`label`，缺省取空串
- 标题 strip 后为空 → 不通过「标题为空」
- 标题长度 > 30 字 → 不通过「标题过长」
- 标题命中 ① 的套话词表 → 不通过「疑似 AI 套话」
- 标题或内容含 `[中段内容已截断]` 或 `……[` 或 `]……` → 不通过「含截断标记」
- 标题 strip 后全是标点符号或纯符号（不含汉字/字母/数字）→ 不通过「无有效内容」
- 全部通过 → `(True, "")`

### A-2 改造 `app/workflow_assets.py:75` `extract_structured_assets_from_text()`

在函数最开头按此顺序执行，再进入原有逻辑：

- **step1** `text = strip_ai_chatter(text)`
- **step2** `block = extract_assets_block(text)`
  - 若 `block` 不为 None：逐条用 `sanitize_asset_item` 过滤，通过的条目直接进入返回结果，
    被拒条目累计到 `result["_rejected"]`；正文部分（去掉契约块后的文本）仍走原有启发式抽取兜底补充，
    补充时同样逐条执行 `sanitize_asset_item`；
    **同一条资产不得重复进入结果**（按「种类 + 标题」去重，契约块优先，启发式补充时跳过已存在的标题）；
    返回结果增加 `result["source"] = "contract"`
  - 若 `block` 为 None：`text = strip_heading_only_lines(text)`，走原有启发式抽取，
    但对每条结果执行 `sanitize_asset_item`，被拒条目计入 `result["_rejected"]`；
    返回结果增加 `result["source"] = "heuristic"`

返回结果固定包含 `_rejected`（list，元素形如 `{"kind": "...", "title": "...", "reason": "..."}`）
与 `source`（`"contract"` 或 `"heuristic"`）两个字段。**其余字段保持与现状完全一致**，
不得改变现有返回结构（`work_info` / `entities` / `relations` / `outline_nodes` /
`foreshadows` / `timeline_events` / `notes` 都保留），否则会打断
`app/api/workflows.py` 与 `app/api/entities.py` 的调用方。

**目的**：AI 套话与纯标题行在进入抽取前就被清掉；有契约块时按契约读，不再靠正则猜。

### A-3 改造 `app/workflow_assets.py:287` 附近的 `card_pattern` 使用处

匹配到标题后，先用 `sanitize_asset_item({"name": 匹配到的标题}, "entity")` 校验，
不通过则跳过该候选（不要入库）。**不要改动正则本身**，避免影响其他既有匹配。

### A-4 门禁（必须通过才能进阶段 B）

用下列样例实测（可临时写脚本跑，跑完删掉脚本，不要留在仓库里）：

输入文本：

```
好的，我已经根据你的要求完成创作。以下是修改后的内容：
### 世界观设定
- 灵根：天地灵气的载体
### 伏笔暗线
| 伏笔标题 | 回收条件 |
| --- | --- |
| 青玉佩的来历 | 第三卷揭示身世 |
### 时间线
- 开元三年 · 顾风下山，途经剑阁
希望以上内容对你有帮助，如需调整请告诉我。
```

必须满足：

- `entities` 中不含「伏笔暗线」
- `notes` 中不含「世界观 · 设定」
- `timeline_events` 能抽出「开元三年 · 顾风下山，途经剑阁」这条事件
- `_rejected` 至少记录了被拒绝的标题类条目

任一条不满足则继续修，不要提交。

**commit**：`fix(contract-A): 新增输出净化层并让抽取器优先解析资产契约块`

---

## 阶段 B：步骤间引用改造（解决「上一步喂给下一步理解不到位」）

### B-1 扩展引用标记

`app/workflow_engine.py:26` 的 `_STEP_REF_RE` 由

```python
r"\{\{steps\.(\d+)\.output\}\}"
```

扩展为

```python
r"\{\{steps\.(\d+)\.(output|assets|summary)\}\}"
```

并修改 `:51` `_render_instruction`：

- 捕获组 2 为 `output` → 行为完全不变（仍走 `_truncate_prev` 截断）
- 捕获组 2 为 `assets` → 从该步骤输出中实时解析结构化资产并渲染为紧凑清单，
  **全量不截断**（关键：正文可以截断，结构化资产不能截断）
- 捕获组 2 为 `summary` → 渲染该步骤输出的结论摘要（取去套话后的前 300 字）

解析资产时复用 `output_normalizer.extract_assets_block`，失败则回退
`workflow_assets.extract_structured_assets_from_text`（同样只取通过校验的条目）。

### B-2 前序上下文分块标注

`app/workflow_engine.py:70` `_build_step_context`：在 `:104` 组装「【前序参考：步骤 N】」
文本块之后，为每个被引用的前序步骤追加一个「【前序结构化资产（可信，全量）】」文本块，
内容为该步骤的结构化资产紧凑清单（每行一条：种类 + 标题 + 关键字段），并明确标注：

> 以下是结构化产出（可信，可直接引用）；原始正文片段可能包含套话与标题，仅供文风参考。

正文块保持现有截断行为不变（R4）。

### B-3 提示词注入输出契约

在步骤提示词组装处（`app/workflow_engine.py:172-195`，`parts` 拼装处）追加一段输出契约要求，
**仅当该步骤 instruction 或技能手册涉及产出资产时追加**（不要给纯改写类步骤乱加）：

> 若本步骤产出可入库资产（实体/关系/时间线事件/伏笔/大纲节点），
> 必须在回答末尾追加如下契约块，正文里写什么都可以，但契约块必须存在且为合法 JSON：
> `<!-- MOYU:ASSETS` …（entities / relations / timeline_events / foreshadows / outline_nodes 五个键）… `MOYU:ASSETS -->`
> 没有对应资产的种类填空数组，不要省略键。

### B-4 门禁

`pytest` 全绿；并人工确认旧模板 `{{steps.1.output}}` 渲染结果与改造前一致（截断行为未变）。

**commit**：`fix(contract-B): 步骤间引用支持结构化资产字段，避免前序输出腰斩`

---

## 阶段 C：资产中枢加固 + 前端可见

### C-1 中枢入口校验

`app/services/asset_hub.py:60` `upsert_foreshadow` 与 `:125` `upsert_timeline_event`：
在函数入口（解析入参之后、任何 SQL 之前）调用 `sanitize_asset_item` 校验。
不通过时：不写库，返回结构中原样保留现有字段，并附带
`"_rejected": true, "_reason": "<sanitize 返回的原因>"`。
调用方（`app/workflow_assets.py:526` `sync_assets_to_database`）需识别 `_rejected`
并累加到返回值，不要把它当成成功写入计数。

### C-2 同步返回过滤计数

`app/workflow_assets.py:526` `sync_assets_to_database`：返回值在现有
`entities_added` / `relations_added` / `outlines_added` / `foreshadows_added` /
`timeline_events_added` / `notes_added` 之外，增加：

- `"rejected_count"`：被拒绝条目总数
- `"rejected_items"`：最多 20 条，元素 `{"kind":"","title":"","reason":""}`

**目的**：前端能明确告诉用户「已过滤 N 条无效条目」，不再静默。

### C-3 前端同步提示

`static/js/pages/workflows.js:973-988` 同步成功提示处：在 `tips` 数组里，
当 `sm.rejected_count > 0` 时追加一条 `已过滤 ${sm.rejected_count} 条无效条目`，
并用 `ui.toast` 的警告样式（不是 ok）提示，保证用户可见。

### C-4 前端预览提示

`static/js/pages/workflows.js:674-691` 资产预览弹窗：

- `assets.source === "heuristic"` 时，在弹窗顶部显示提示条：
  「以下条目由启发式识别得出（未检测到标准资产契约块），请人工核对后再同步。」
- `assets._rejected` 非空时，显示「已自动过滤 N 条疑似无效条目」。
- 原生 JS 实现，不引入任何框架。

**commit**：`fix(contract-C): 资产中枢入口校验脏数据并向前端回传过滤计数`

---

## 阶段 D：技能手册补统一交付段

`app/builtin_skill_data.py` 中有 6 份技能手册**完全没有交付格式约定**，需各自追加统一交付段：

- `STYLE_FINGERPRINT`
- `GENRE_PLAYBOOK`
- `STRUCTURE_MODELS`
- `CONSISTENCY_TAXONOMY`
- `CHARACTER_ARC_MODELS`
- `WORLDBUILDING_CHECKLIST`

追加内容（写在手册末尾，措辞可与该手册风格一致，但必须包含下列要点）：

> 【交付格式】本技能若产出可入库资产（实体/关系/时间线事件/伏笔/大纲节点），
> 必须在回答末尾追加 MOYU:ASSETS 契约块（格式见 `docs/墨语MoYu_AI产出输入输出契约规范.md` 3.1），
> 正文可自由书写，但契约块必须是合法 JSON；无对应资产的种类填空数组。

其余 8 份已有格式约定的手册（`PROSE_CRAFT`、`EXPANSION_CRAFT`、`REWRITE_DIMENSIONS`、
`COMPRESSION_FORMATS`、`AI_TONE_CATALOG`、`ANALYSIS_RUBRIC`、`CREATION_PIPELINE`、`SCENE_BEATS`）
**只做一件事**：在其现有交付约定末尾补一句「若产出可入库资产，另按 MOYU:ASSETS 契约块提交」，
不要推翻它们原有的格式约定。

**commit**：`fix(contract-D): 技能手册补统一交付段并在提示词注入输出契约`

---

## 阶段 E：回归断言与文档同步

### E-1 新建 `tests/test_output_contract.py`

至少 6 条断言（每条都要真断言，不许空跑）：

1. 阶段 A-4 的样例：`entities` 不含「伏笔暗线」、`notes` 不含「世界观 · 设定」、
   `timeline_events` 非空、`_rejected` 非空
2. 契约块存在时，`source == "contract"`，且块内资产 100% 被抽出
3. 契约块缺失时，`source == "heuristic"`，套话行不产生任何资产
4. `sanitize_asset_item` 对「含截断标记」「超长标题」「空标题」「纯标点」四类输入全部返回 False
5. 同一条事件用四种写法（契约块 / 列表+中文冒号 / 无标题纯文本 / 套话开头）输入，
   断言：契约块写法必被抽出，其余写法不产生错误资产（不产生以套话为标题的条目）
6. `upsert_foreshadow` 传入套话标题时被拒绝且返回 `_rejected == true`（不写库）

### E-2 同步开发说明

`docs/v2.0.0-development-notes.md` 追加一段「v2.0.0 AI 产出输入输出契约」，
说明新增了 `output_normalizer` 与 `MOYU:ASSETS` 契约，以及它对工作流资产分发的影响。

### E-3 门禁

`.venv/Scripts/python.exe -m pytest -q` 全绿，测试总数 ≥ 181（现有 175 + 新增 ≥6）。
**若现有测试因本次改动失败，说明改变了既有返回结构——回退到兼容实现，不要改旧测试来适配。**

**commit**：`test(contract-E): 补齐输入输出契约回归断言`

---

## 三、最终输出（执行完必须给出）

1. 逐阶段的 commit hash 与改动文件清单（文件路径 + 增删行数）
2. 阶段 A-4 门禁的实测输出（四个断言的实际结果，贴原文）
3. `pytest` 最终统计（passed 数与耗时）
4. 「遗留问题」清单：执行中发现但本任务书未覆盖的问题，写明文件与行号
5. 明确回答：`MOYU:ASSETS` 契约块在下列四个调用点是否都生效
   （`app/api/workflows.py:336` / `:337` / `:351`，`app/api/entities.py:358`）

---

## 附：阶段分批建议

| 批次 | 阶段 | 说明 |
|:---|:---|:---|
| 批次一 | A + B | 新增净化层 + 抽取器接契约 + 步骤间结构化引用，风险低、效果直观 ✅ 已完成并通过审核 |
| 批次二 | M-1 → M-4 → M-2/M-3 → C → D → E | 审核待修正项 + 中枢加固 + 前端可见 + 手册补交付段 + 回归断言 |

---

# 阶段 M：批次一审核待修正项（来源：阶段一审核报告）

审核结论：阶段 A/B 已通过（175 passed，A-4 门禁四条全过，8 类差分样例与改造前完全一致）。
以下 4 项为审核发现的待修正项，按 M-1 → M-4 → M-2/M-3 顺序执行，再进入 C/D/E。

---

## M-1 换行符规范化（单独一次提交，不与逻辑改动混在一起）

**问题**：`app/workflow_assets.py` 与 `app/workflow_engine.py` 在阶段 A/B 中被从 CRLF 整体改写为 LF，
git 显示为 1595 / 636 行变更，而忽略换行差异后真实改动仅 +187/-4 与 +114/-4。
仓库无 `.gitattributes`，`core.autocrlf=false`，40 个 `app/**/*.py` 中 17 CRLF / 13 LF / 10 混合。

**做法**：

1. 新建 `.gitattributes`，内容固定为：

```
* text=auto
*.py text eol=lf
*.js text eol=lf
*.html text eol=lf
*.css text eol=lf
*.md text eol=lf
```

2. 对 `app/**/*.py`、`tests/**/*.py` 及根目录 `*.py` 做一次换行统一为 LF 的规范化提交。
3. 该提交**不得包含任何逻辑改动**，只允许换行变化。

**门禁**：`pytest` 全绿；用 `git diff --stat --ignore-cr-at-eol <base> HEAD -- app/` 复核，
确认这一步之外不再有换行造成的虚高差异。

**commit**：`chore(contract-M1): 统一换行符为LF并新增.gitattributes`

> 保守替代（若担心影响面过大）：仅在 `.gitattributes` 中写 `* -text` 冻结现状、不做全库规范化，
> 并在总结里说明采用替代方案。默认按上面的完整方案执行。

---

## M-4 补断言锁死阶段 A/B 行为（必须在改净化层之前做）

**问题**：阶段 A/B 未留任何回归断言，后续 C/D/E 继续改 `workflow_assets.py` 可能把已修好的行为改回去，
而现有 175 项测试一条都挡不住。

**做法**：新建 `tests/test_output_contract.py`，先写入这 4 条（后续阶段 E-1 在此基础上补足其余条目，不要重复）：

1. **A-4 门禁样例**：`entities` 不含「伏笔暗线」、`notes` 不含「世界观 · 设定」、
   `timeline_events` 抽出「开元三年 / 顾风下山，途经剑阁」、`_rejected` 非空
2. **契约块优先**：有契约块时 `source == "contract"`，块内资产 100% 被抽出，
   且正文中的套话行与 `###` 标题不进入结果
3. **套话不产生资产**：无契约块且仅有套话的输入，所有资产列表为空
4. **upsert 拒绝脏数据**：`asset_hub.upsert_foreshadow` 传入套话标题时被拒绝，返回 `_rejected == true` 且不写库
   （此条依赖阶段 C-1，若先做 M-4 则改为断言 `sanitize_asset_item` 返回 False，等 C-1 完成后再补 upsert 版本）

**门禁**：`pytest` 全绿。

**commit**：`test(contract-M4): 补齐阶段AB行为回归断言`

---

## M-2 套话清理误伤合法正文（修正 `strip_ai_chatter`）

**问题（实测）**：`CHATTER_PREFIXES`（`app/services/output_normalizer.py:6`）中的歧义词整行前缀匹配，
会删掉合法的小说正文。实测以下 4 行有 4 行被删：

```
期待已久的雪终于落下，他回头看了一眼山门。   ← 前缀「期待」
感谢前辈出手相救，宁恪抱拳。                  ← 前缀「感谢」
祝你此去一路顺风。                            ← 前缀「祝你」
以下是他要带走的清单：一柄旧剑、半块青玉佩。  ← 前缀「以下是」
```

危害边界已核实：净化只作用于抽取输入、不写回正文，后果是「漏抽 / 漏检」而非「丢数据」。
但 `app/api/entities.py:358` 用同一抽取器扫描**用户撰写的章节正文**做未入库实体探测，此处不应按 AI 套话标准清理。

**做法**：

1. 在 `app/services/output_normalizer.py` 中把前缀词表拆成两组：

   - `CHATTER_PREFIXES_STRONG`（无条件整行删除）：
     「好的」「好的，」「如上所述」「综上所述」「这是为您」「这是给你」
     「供你参考」「供您参考」「如果有任何」「祝创作顺利」
   - `CHATTER_PREFIXES_AMBIGUOUS`（条件命中才删）：
     「感谢」「期待」「祝你」「祝你创作」「希望以上」「希望这」「希望能」
     「如需」「如果需要」「如有需要」「请注意」「注意：」「以下是」「以下为」

2. `strip_ai_chatter(text: str, strict: bool = True)`：
   - `strict=True`（默认，用于 AI 产出）：强词表无条件删 + 弱词表在满足条件时删
   - `strict=False`（用于用户正文）：**只用强词表**，弱词表完全不启用
   - 弱词表命中条件（全部满足才删）：
     该行去空白后长度 ≤ 25 **且** 位于全文首尾各 3 个非空行之内 **且** 不含「：」「:」「，」「,」

3. `extract_structured_assets_from_text(text: str, source_kind: str = "ai") -> dict`：
   - `source_kind="ai"`（默认）→ `strip_ai_chatter(text, strict=True)`
   - `source_kind="chapter"` → `strip_ai_chatter(text, strict=False)`
   - 默认行为不得改变，现有四个调用点不传参时行为与现在一致

4. `app/api/entities.py:358` 改为 `extract_structured_assets_from_text(content, source_kind="chapter")`。
   其余三处（`workflows.py:336` / `:337` / `:351`）保持默认 `"ai"`，不改。

**门禁**：`pytest` 全绿；并用下列样例实测，4 行中至少 3 行被保留：

```
期待已久的雪终于落下，他回头看了一眼山门。
感谢前辈出手相救，宁恪抱拳。
祝你此去一路顺风。
以下是他要带走的清单：一柄旧剑、半块青玉佩。
```

（预期：前两行含「，」保留；第三行无逗号仍会删，属可接受的边界；第四行含「：」保留。
以 `source_kind="chapter"` 调用时四行应全部保留。）

**commit**：`fix(contract-M2): 套话词表分级，避免误删合法正文`

---

## M-3 `_rejected` 在启发式模式下统计不完整

**问题**：`app/workflow_assets.py:684-693` 用一份**硬编码的 5 个标题名**
（伏笔暗线 / 世界观设定 / 时间线 / 分卷大纲 / 角色关系网）来补记被删的标题行。
实测输入 `### 道具神兵` 时标题被正确删除，但 `_rejected` 不记录 → 阶段 C 的「已过滤 N 条」会少报。

**做法**：

1. `app/services/output_normalizer.py:66` 的 `strip_heading_only_lines` 改为返回
   `(清洗后文本, 被删行列表)`；被删行元素形如 `{"title": "<标题文本>", "line_no": <行号>}`。
2. `app/workflow_assets.py:695` 的调用处同步改为接收二元组，
   **删除** `:684-693` 那份硬编码名单，改由返回值汇总进 `_rejected`
   （`reason` 统一为「疑似纯标题」，`kind` 沿用现有的推断逻辑）。
3. 若其他位置也调用了该函数，一并同步（当前仅此一处调用）。

**门禁**：`pytest` 全绿；实测 `### 道具神兵` 进入 `_rejected`。

**commit**：`fix(contract-M3): 启发式分支改用返回值统计被过滤标题`

---

## 执行顺序与注意

```
M-1（换行，独立提交） → M-4（补断言） → M-2（词表分级） → M-3（_rejected 统计） → C → D → E
```

- M-4 必须在 M-2 之前：先把「正确行为」用测试锁死，再改净化层，才能验证改完没改坏。
- M-2 改完后，`tests/test_output_contract.py` 中 M-4 的断言必须仍然全绿；若出现失败，
  说明词表分级破坏了既有能力，需调整条件而非改测试。
- 阶段 E-1 的测试总数要求仍为 **≥181**（现有 175 + 新增 ≥6，M-4 的断言计入其中，不要重复计数）。

---

# 阶段 F：补齐前端可见性（批次二审核发现 C-3 / C-4 未实现）

**问题**：阶段 C 的提交 `7313076` 中，`static/js/pages/workflows.js` 显示 2380 行变更，
但经核验**全部是 CRLF → LF 的换行规范化**（CR 由 1190 → 0，忽略 CR 后 diff 为空）。
也就是说：**C-3 与 C-4 两条前端改动一行都没做**。

后果：后端已经在 `sync_assets_to_database` 里统计了 `rejected_count`，
但前端不读取也不展示 → 用户依然不知道有多少条目被过滤掉了，「不静默」的目标没达成。

## F-1 同步成功提示增加过滤计数

文件：`static/js/pages/workflows.js`，锚点 `:973-988`（`const sm = res.summary || {}` 起，
`tips.push` 序列在 `:976-982`，`ui.toast(...)` 在 `:988`）。

做法：

1. 在 `tips` 序列末尾追加：

```js
if (sm.rejected_count) tips.push(`已过滤 ${sm.rejected_count} 条无效条目`);
```

2. `:988` 的 toast 改为：**当 `sm.rejected_count > 0` 时用警告样式**（`ui.toast` 的第二个参数
   由 `"ok"` 改为警告类型），否则保持 `"ok"`。保证用户看得见。

## F-2 资产预览弹窗增加置信度提示

文件：`static/js/pages/workflows.js`，锚点 `:673 showAssetSyncModal`、`:674 let assets = initialAssets`。

做法：

1. 在弹窗顶部（`:674` 之后、`:685 const workInfo` 之前）插入提示条：
   - 当 `assets.source === "heuristic"` 时显示：
     「以下条目由启发式识别得出（未检测到标准资产契约块），请人工核对后再同步。」
   - 当 `assets._rejected` 非空时显示：「已自动过滤 N 条疑似无效条目」（N 取 `assets._rejected.length`）。
2. 原生 JS 实现，不引入任何框架；样式沿用该文件现有的 `ui.el(...)` / `ui.toast` 写法。

## F-3 门禁

- `pytest` 全绿（应保持 181）。
- 人工确认：`rejected_count > 0` 时同步提示出现「已过滤 N 条无效条目」且为警告样式；
  启发式抽取的预览弹窗顶部出现核对提示条。

**commit**：`fix(contract-F): 前端补齐过滤计数提示与低置信度核对提示`

---

## G-1 `ui.toast` 补充 warn 配色

**背景**：阶段 F-1 在 `static/js/pages/workflows.js:1001` 写了
`const toastStyle = (sm.rejected_count && sm.rejected_count > 0) ? "warn" : "ok";`，
但 `static/js/ui.js:28-32` 的 toast 配色表**只有 `info` / `ok` / `err` 三个键**，没有 `warn`：

```js
const colors = {
  info: "bg-primary-container text-on-primary",
  ok: "bg-secondary-container text-on-secondary-container",
  err: "bg-error text-on-error",
};
```

而 `:34` 的使用处是 `${colors[type] || colors.info}`，所以传入 `"warn"` 会**静默 fallback 成 `info`（主色蓝）**。
结果：同步成功但有内容被过滤时，toast 与普通信息提示视觉无差别，用户极易忽略——
F-1「不再静默」的目标实际只达成一半。

**佐证**：全项目 `ui.toast` 调用共 274 处（`err` 175 / `ok` 89 / `info` 10），
在此之前**没有任何一处用过 `"warn"`**，因此配色表从未补过这个键。

### 做法

文件：`static/js/ui.js`，锚点 `:28 const colors = {`。

在 `:31`（`err` 那一行）之后**新增一行**：

```js
      warn: "bg-tertiary-container text-on-tertiary-container",
```

即完整配色表变为：

```js
const colors = {
  info: "bg-primary-container text-on-primary",
  ok: "bg-secondary-container text-on-secondary-container",
  err: "bg-error text-on-error",
  warn: "bg-tertiary-container text-on-tertiary-container",
};
```

### 约束

1. **只改这一个文件、只加这一行。**
2. **不得改动** `info` / `ok` / `err` 三个键的现有取值（会影响全项目 274 处调用）。
3. **不得改动** `workflows.js`（阶段 F 的代码已经正确，缺的只是配色定义）。
4. 该 token 已在 `static/index.html:44-45` 定义
   （`--color-tertiary-container` / `--color-on-tertiary-container`），可直接引用，无需新增 CSS 变量。
5. 换行符保持 LF（仓库已由 M-1 统一，见 `.gitattributes`）。

### G-2 门禁

- `pytest` 全绿，保持 **181**。
- 自检：确认 `ui.toast("x", "warn")` 渲染出的元素 class 含 `bg-tertiary-container`，
  而非 fallback 的 `bg-primary-container`。
- 确认 `ui.toast("x", "ok")`、`ui.toast("x", "err")`、`ui.toast("x", "info")` 行为与改前完全一致。

**commit**：`fix(contract-G): toast 补充 warn 配色，使过滤提示具备警告语义`
