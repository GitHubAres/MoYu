# 墨语MoYu 契约链路复审修复任务书（H 组）

> 适用版本：v2.0.0
> 测试基线：181 passed（命令 `.venv/Scripts/python.exe -m pytest -q`），修改后不得下降
> 本组定位：**缺陷修复**，不新增业务功能
> 提交前缀：`fix(contract-Hn): ...`
> 执行原则：**断言先行** —— 每个修复阶段先写/补断言，再改实现

---

## 0. 红线（不得违反）

1. 无打包步骤，不执行 `build_exe.py`、不生成 spec 产物。
2. 数据库结构变更必须走 `app/db.py` 的 `MIGRATIONS` 增量迁移；本组**不需要**表结构变更。
3. 不碰 `data/` 目录下任何文件。
4. AI 内容一律"先预览后写入"，不得跳过预览直接落库。
5. 不新增第三方依赖。
6. 只改动本任务书列出的文件；未列出的文件不得顺手改。

---

## 1. 缺陷清单（本次复审实测得出）

### H-1【P0】多契约块只解析第一个 → 全流程汇总资产静默丢失

- **现象（实测）**：构造 2 个步骤输出、各含 1 个合法 `MOYU:ASSETS` 契约块（第 1 块含实体「宁恪」+伏笔「铜钥匙」，第 2 块含实体「苏昀」+时间线「灵脉抽签」+伏笔「断剑」+大纲「第二章·旧宅」），调用 `extract_structured_assets_from_text(step1 + "\n" + step2)` 返回：`source="contract"`，仅得到「宁恪」「铜钥匙」，第 2 块 4 条**全部丢失**，且 `_rejected` 为空数组 —— 无任何提示。
- **根因链**：
  1. `app/api/workflows.py:364-366`：`get_summary_assets` 把所有步骤 output 用换行拼成一篇 `full_text`，只做**一次**抽取；
  2. `app/services/output_normalizer.py:138`：`extract_assets_block` 用 `re.search`，只命中**第一个**块；
  3. `app/workflow_assets.py:652`：`re.sub` 把**所有**契约块从 `text_remain` 中删除 → 第 2 块及之后的资产连启发式兜底都捞不回来。
- **影响面**：工作流主入口「全功能一键同步至作品库」与完成后自动弹出的资产弹窗（`static/js/pages/workflows.js:627`、`:649`）都走 `/workflows/runs/{run_id}/summary-assets`。多步骤工作流（默认 3 步以上）必然踩中。
- **附带误导**：此时 `source` 仍返回 `"contract"`，前端不会显示"请人工核对"提示条，用户以为同步完整。

### H-2【P1】单标记收尾的契约块解析失败并静默降级

- **现象（实测）**：AI 输出 `<!-- MOYU:ASSETS\n{...}\n-->`（只用 `-->` 收尾，不重复 `MOYU:ASSETS`）时，`extract_assets_block` 返回 `None`，`source` 降为 `"heuristic"`，实体「宁恪」**未被抽取到**（块内 JSON 文本污染启发式）。
- **根因**：`app/services/output_normalizer.py:138` 的正则强制要求结束标记处再出现一次 `MOYU:ASSETS`。该写法是模型的高频输出变体。
- **附带误导**：前端 `static/js/pages/workflows.js:714` 提示"未检测到标准资产契约块"，而实际上模型是写了契约块的 —— 文案与事实不符。

### H-3【P1】实体 category 无枚举兜底 → 万相谱分类视图中隐身

- **现象**：`app/workflow_assets.py:813` 插入实体时使用 `ent.category or "character"`，**不做** `CATEGORIES` 校验。契约块由模型自由输出，`category` 极可能写成 `"人物"`/`"主角"`/`"设定"` 等非法值。
- **影响面**：`static/js/pages/entities.js:77` 用 `items.filter((e) => e.category === activeCat)` **精确匹配**分类。非法分类值不属于 `CATEGORIES = ("character", "place", "faction", "item", "term", "custom")`（`app/api/entities.py:13`）中任何一个 → 该实体在万相谱所有分类页签下都筛不到，只在"全部"里可见，等同半隐身。
- **对照**：`app/api/entities.py:492` 的批量导入接口已有兜底 `cat = item.category if item.category in CATEGORIES else 'term'`，同步接口缺失该兜底。

### H-4【P2】步骤输出展示层残留契约块 JSON

- **现象**：`static/js/pages/workflows.js:1074`（人工确认闸的 textarea）与 `:1093` 直接展示 `s.output` 原文，`<!-- MOYU:ASSETS {...} -->` 整段出现在用户可编辑区域。
- **要求**：展示时剥离契约块，但**保存/采纳仍用原始 `s.output`**（契约块必须保留在存储值里，否则 H-1 修复后仍拿不到数据）。

---

## 2. 执行顺序（严格按序，断言先行）

```
H-1A（断言）→ H-1（实现）→ H-2A（断言）→ H-2（实现）→ H-3A（断言）→ H-3（实现）→ H-4（前端）→ H-5（全量回归）
```

每完成一个实现阶段，立刻运行 `.venv/Scripts/python.exe -m pytest -q`，确认 181 基线不下降再进入下一阶段。

---

## 3. H-1A：先补失败断言（预期红）

文件：`tests/` 下新增或追加（建议 `tests/test_workflow_contract.py`，若已存在同名文件则追加）。

必须包含以下断言（跑出来应为**红**）：

1. **多块汇总断言**
   - 造 3 个步骤输出，每步各含 1 个合法契约块，块内资产互不重复（实体 2 个 + 关系 1 条 + 时间线 1 条 + 伏笔 2 条 + 大纲 1 个，分散在 3 步）。
   - 调用 `app.api.workflows.get_summary_assets` 的等价链路：直接调用 `merge_assets([extract_structured_assets_from_text(s) for s in steps])`（函数此时尚不存在，允许先 import 失败作为红灯），断言：
     - 返回 `entities` 含全部 2 个实体名；
     - `timeline_events` / `foreshadows` / `outline_nodes` 均含第 2、3 步的条目；
     - 三个步骤全为契约块时 `source == "contract"`。
2. **去重断言**：两个步骤输出同名实体「宁恪」，合并后 `entities` 中「宁恪」只出现 1 次。
3. **mixed 断言**：步骤 1 有契约块、步骤 2 无契约块（纯文本），合并后 `source == "mixed"`，且步骤 2 的启发式资产仍在结果中。
4. **rejected 合并断言**：步骤 1 拒绝 1 条、步骤 2 拒绝 1 条，合并后 `_rejected` 长度为 2，且无 (kind,title,reason) 完全重复的条目。

---

## 4. H-1：多契约块汇总修复

### 4.1 新增合并工具函数

文件：`app/workflow_assets.py`
位置：在 `def extract_structured_assets_from_text`（`app/workflow_assets.py:600`）**之前**新增。

```python
_CONTRACT_TITLE_KEYS = [
    ("entities", "name"),
    ("relations", "label"),
    ("outline_nodes", "title"),
    ("foreshadows", "title"),
    ("timeline_events", "event"),
    ("notes", "title"),
]


def merge_assets(assets_list: list[dict]) -> dict:
    """合并多次抽取结果：按「种类 + 标题」去重（先出现者优先），合并 _rejected 与 source。"""
    merged = {
        "work_info": {"title": "", "genre": "", "intro": ""},
        "entities": [],
        "relations": [],
        "outline_nodes": [],
        "foreshadows": [],
        "timeline_events": [],
        "notes": [],
        "_rejected": [],
        "source": "contract",
    }
    sources = []
    for a in assets_list or []:
        if not isinstance(a, dict):
            continue
        sources.append(a.get("source") or "heuristic")
        # work_info：先非空者胜
        for k in ("title", "genre", "intro"):
            if not merged["work_info"][k]:
                merged["work_info"][k] = ((a.get("work_info") or {}).get(k) or "")
        # 资产：按 种类+标题 去重
        for field, tkey in _CONTRACT_TITLE_KEYS:
            seen = {str(i.get(tkey, "")).strip() for i in merged[field]}
            for item in a.get(field) or []:
                if not isinstance(item, dict):
                    continue
                tv = str(item.get(tkey, "")).strip()
                if tv and tv in seen:
                    continue
                if tv:
                    seen.add(tv)
                merged[field].append(item)
        # rejected：按 (kind, title, reason) 去重
        seen_r = {(r.get("kind"), r.get("title"), r.get("reason")) for r in merged["_rejected"]}
        for r in a.get("_rejected") or []:
            if not isinstance(r, dict):
                continue
            key = (r.get("kind"), r.get("title"), r.get("reason"))
            if key in seen_r:
                continue
            seen_r.add(key)
            merged["_rejected"].append(r)
    if not sources:
        merged["source"] = "heuristic"
    elif all(s == "contract" for s in sources):
        merged["source"] = "contract"
    elif all(s == "heuristic" for s in sources):
        merged["source"] = "heuristic"
    else:
        merged["source"] = "mixed"
    return merged
```

> 注意：`"mixed"` 是本任务书**指定的字面量**，不得改用 `partial` / `hybrid` 等其它拼写。

### 4.2 改造汇总接口

文件：`app/api/workflows.py`
位置：`get_summary_assets`（`app/api/workflows.py:352`）内，替换 `app/api/workflows.py:364-366`。

原代码：
```python
    combined_texts = [r["output"] for r in steps if r["output"]]
    full_text = chr(10).join(combined_texts)
    raw_assets = extract_structured_assets_from_text(full_text)
```

改为：
```python
    per_step_assets = [
        extract_structured_assets_from_text(r["output"])
        for r in steps if r["output"] and r["output"].strip()
    ]
    raw_assets = merge_assets(per_step_assets) if per_step_assets else extract_structured_assets_from_text("")
```

同文件顶部 import 处补充 `merge_assets`（与 `extract_structured_assets_from_text` 同一条 import 语句，见 `app/api/workflows.py:13`）。

### 4.3 前端提示条适配 mixed

文件：`static/js/pages/workflows.js`
位置：`static/js/pages/workflows.js:714`（当前为 `if (assets.source === "heuristic") {`）。

改为按"非全契约"判定，并区分文案：
- `assets.source === "heuristic"`：沿用现有文案"以下条目由启发式识别得出（未检测到标准资产契约块），请人工核对后再同步。"
- `assets.source === "mixed"`：文案改为"部分步骤未输出标准资产契约块，已合并启发式结果，请人工核对后再同步。"
- 实现建议：把条件改为 `if (assets.source === "heuristic" || assets.source === "mixed") {`，文案用三元表达式按 `assets.source` 取值；提示条样式类（现有 `bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300`）保持不变。

### 4.4 验收

- 运行 `.venv/Scripts/python.exe -m pytest -q`，H-1A 的断言由红转绿，总数 ≥ 181。
- 自检：3 步骤各 1 块的场景，`/summary-assets` 返回资产数与 3 块之和一致（去重后）。

---

## 5. H-2A：先补失败断言（预期红）

文件：同 `tests/test_workflow_contract.py`（或既有契约测试文件）追加。

断言：
1. 输入 `<!-- MOYU:ASSETS\n{"entities":[{"name":"宁恪","category":"character","content":"主角"}],...}\n-->`（**单标记收尾**），`extract_assets_block(text) is not None`，且 `entities[0]["name"] == "宁恪"`。
2. 同上文本走 `extract_structured_assets_from_text`，`source == "contract"`。
3. 双标记写法（现有形态）行为不变，`source == "contract"`。
4. 文本中**不含**任何契约块时，`extract_assets_block` 仍返回 `None`（防误伤：单标记正则不得把普通 `-->` 或注释当块吃掉）。

---

## 6. H-2：单标记收尾容错

### 6.1 抽取正则支持两种收尾

文件：`app/services/output_normalizer.py`
位置：`extract_assets_block`（`app/services/output_normalizer.py:134`），替换 `app/services/output_normalizer.py:138` 的 `re.search` 一行。

改为两步匹配：
```python
    patterns = [
        r'<!--\s*MOYU:ASSETS\s*([\s\S]*?)\s*MOYU:ASSETS\s*-->',   # 双标记
        r'<!--\s*MOYU:ASSETS\s*([\s\S]*?)\s*-->',                  # 单标记收尾
    ]
    raw_json = None
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            raw_json = match.group(1).strip()
            break
    if raw_json is None:
        return None
```
后续剥离代码围栏、中文引号、尾逗号的逻辑保持不变（原 144-149 行）。

### 6.2 抽取块删除逻辑统一复用

文件：`app/services/output_normalizer.py` 新增：
```python
def strip_assets_blocks(text: str) -> str:
    """删除文本中全部 MOYU:ASSETS 契约块（兼容双标记与单标记收尾）。"""
    if not text:
        return ""
    text = re.sub(r'<!--\s*MOYU:ASSETS[\s\S]*?MOYU:ASSETS\s*-->', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<!--\s*MOYU:ASSETS[\s\S]*?-->', '', text, flags=re.IGNORECASE)
    return text
```

文件：`app/workflow_assets.py`
位置：`app/workflow_assets.py:652`，把
```python
        text_remain = re.sub(r'<!--\s*MOYU:ASSETS[\s\S]*?MOYU:ASSETS\s*-->', '', text, flags=re.IGNORECASE)
```
改为
```python
        text_remain = strip_assets_blocks(text)
```
并在文件顶部 import 处补充 `strip_assets_blocks`。

### 6.3 验收

- `.venv/Scripts/python.exe -m pytest -q` 全绿，H-2A 断言转绿。
- 手工确认：双标记块仍走 `contract`，`source` 字面量不变。

---

## 7. H-3A：先补失败断言（预期红）

文件：同测试文件追加。

断言：
1. 契约块实体 `{"name":"宁恪","category":"人物","content":"主角"}` 走 `sync_assets_to_database` 后，库内 `entities.category == "character"`。
2. `category="主角"` → `"character"`；`category="地点"` → `"place"`；`category="门派"` → `"faction"`；`category="神兵"` → `"item"`；`category="世界观"` → `"term"`；`category="乱写的分类"` → `"term"`；`category` 缺省 → `"character"`（沿用现有默认）。
3. 合法值 `"character"` 原样保留，不被映射改写。

---

## 8. H-3：实体分类枚举兜底

文件：`app/workflow_assets.py`

### 8.1 新增映射函数
位置：`def sync_assets_to_database`（`app/workflow_assets.py:711`）之前新增：
```python
CATEGORY_ALIASES = {
    "人物": "character", "角色": "character", "主角": "character", "配角": "character",
    "人物角色": "character", "主要角色": "character",
    "地点": "place", "场景": "place", "地理": "place", "位置": "place",
    "势力": "faction", "组织": "faction", "门派": "faction", "阵营": "faction",
    "道具": "item", "物品": "item", "神兵": "item", "兵器": "item", "物件": "item",
    "术语": "term", "设定": "term", "概念": "term", "世界观": "term", "规则": "term",
}
VALID_CATEGORIES = ("character", "place", "faction", "item", "term", "custom")


def normalize_category(cat: str | None) -> str:
    """把模型自由输出的分类值归一到 CATEGORIES 枚举；无法识别时回落 'term'。"""
    if not cat:
        return "character"
    c = str(cat).strip()
    if not c:
        return "character"
    if c in VALID_CATEGORIES:
        return c
    if c in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[c]
    return "term"
```
> 说明：与 `app/api/entities.py:492` 的兜底口径保持一致（无法识别 → `term`）；缺省值沿用同步接口现有默认 `character`。

### 8.2 接入同步逻辑
位置：`app/workflow_assets.py:813`，把
```python
                (work_id, ent.category or "character", name, ent.content, fields_str, ent.tags),
```
改为
```python
                (work_id, normalize_category(ent.category), name, ent.content, fields_str, ent.tags),
```

### 8.3 已存在实体的分支
`app/workflow_assets.py` 中 `name in name_to_id` 的 UPDATE 分支（约 795-810 行）**不修改** `category`，保持现状（避免覆盖人工调整过的分类）。

### 8.4 验收

- `.venv/Scripts/python.exe -m pytest -q` 全绿，H-3A 断言转绿。
- 抽查：万相谱分类页签能筛到由契约块同步进来的实体。

---

## 9. H-4：展示层剥离契约块

文件：`static/js/pages/workflows.js`

1. 在文件顶部工具函数区新增（函数名与行为固定）：
```js
function stripMoyuAssetsBlock(t) {
  if (!t) return "";
  return String(t)
    .replace(/<!--\s*MOYU:ASSETS[\s\S]*?MOYU:ASSETS\s*-->/gi, "")
    .replace(/<!--\s*MOYU:ASSETS[\s\S]*?-->/gi, "");
}
```
2. `static/js/pages/workflows.js:1074`：textarea 展示值由 `s.output` 改为 `stripMoyuAssetsBlock(s.output)`。
3. `static/js/pages/workflows.js:1093`：预览/展示处同理改为 `stripMoyuAssetsBlock(s.output)`。
4. **硬约束**：`static/js/pages/workflows.js:1098` 的 `parseWorkflowOptions(s.output)` 与任何保存/采纳链路**必须继续用原始 `s.output`**，不得改用剥离后的值 —— 契约块必须留在存储值里。

---

## 10. H-5：全量回归与提交

1. 运行 `.venv/Scripts/python.exe -m pytest -q`，要求 **全部通过且总数 ≥ 181**。
2. 检查 `git status`，确认只出现本任务书列出的文件：
   - `app/workflow_assets.py`
   - `app/api/workflows.py`
   - `app/services/output_normalizer.py`
   - `static/js/pages/workflows.js`
   - `tests/` 下测试文件
3. 逐阶段提交，提交信息前缀 `fix(contract-H1)` … `fix(contract-H5)`。
4. 不得改动 `docs/` 下任何文档，不得修改本任务书。

---

## 11. 未纳入本组的已知遗留（下一轮处理，本次不要碰）

- **R-1**：工作流抽取的「世界观设定 / notes」资产在 `sync_assets_to_database` 中完全未被处理（`SyncAssetsIn.notes` 存在但无消费端，`notes` 表已随 `app/db.py` 迁移被 DROP），前端 `sm.notes_added` 恒为 0。方案：同步为 `entities` 且 `category="term"`。
- **R-3**：仅绑定章节的资产在删章后失去归属。方案：新增 `unbound-assets` 查询 + 批量重绑 + 时间线/看板"仅看未归属"筛选。

本组完成后，这两项仍然挂着，需要单独下发指令。

---

## 12. 引用索引（file:line）

| 引用 | 说明 |
|---|---|
| `app/api/workflows.py:13` | 资产抽取函数 import |
| `app/api/workflows.py:352` | `get_summary_assets` 定义 |
| `app/api/workflows.py:364-366` | 拼接全文后单次抽取（H-1 根因） |
| `app/api/entities.py:13` | `CATEGORIES` 枚举定义 |
| `app/api/entities.py:492` | 批量导入接口的分类兜底口径 |
| `app/workflow_assets.py:600` | `extract_structured_assets_from_text` |
| `app/workflow_assets.py:652` | 契约块删除 re.sub（H-1 根因之一） |
| `app/workflow_assets.py:711` | `sync_assets_to_database` |
| `app/workflow_assets.py:813` | 实体插入时未校验 category（H-3） |
| `app/services/output_normalizer.py:134` | `extract_assets_block` |
| `app/services/output_normalizer.py:138` | 双标记正则（H-2 根因） |
| `static/js/pages/workflows.js:649` | 全流程汇总同步入口 |
| `static/js/pages/workflows.js:714` | heuristic 提示条（H-1 前端适配点） |
| `static/js/pages/workflows.js:1074` | 步骤输出 textarea（H-4） |
| `static/js/pages/workflows.js:1093` | 步骤输出展示（H-4） |
| `static/js/pages/entities.js:77` | 分类精确匹配筛选（H-3 影响面） |
