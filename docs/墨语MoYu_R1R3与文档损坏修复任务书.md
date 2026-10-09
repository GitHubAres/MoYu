# 墨语MoYu R-1/R-3 与文档损坏修复任务书（R+D 组）

> 适用版本：v2.0.1（工作区未提交发版态）
> 测试基线：`.venv/Scripts/python.exe -m pytest -q` → **181 passed**，修改后只增不减
> 本组定位：遗留缺陷修复 + 文档完整性修复，不新增业务功能
> 提交前缀：`fix(docs-Dn)` / `release(v2.0.1)` / `fix(contract-R1n)` / `fix(contract-R3n)`
> 执行原则：**断言先行** —— 先写断言跑出红，再改实现转绿

---

## 0. 红线（不得违反）

1. 无打包步骤，不执行 `build_exe.py`、不生成 spec/exe 产物。
2. 数据库结构变更必须走 `app/db.py` 的 `MIGRATIONS`；本组 **不需要** 任何 DDL（R-1 复用 `entities` 表，R-3 复用既有两键字段）。
3. 不碰 `data/` 目录。
4. AI 内容先预览后写入；本组所有入库路径都经过同步弹窗预览勾选，不得绕过。
5. 只改本任务书列出的文件。
6. **前置条件**：若 `docs/墨语MoYu_契约汇总与分类兜底修复任务书.md`（H 组）尚未执行，先完成 H 组再开始本任务书；若 H 组已完成，本文标注"以函数/变量名定位"的行号可能偏移，一律以名称为准。
7. 工作区当前有**未提交的 v2.0.1 发版改动**（`app/version.py`、`README.md`、`AGENTS.md`、`docs/PRD-本地版.md`、新增 `docs/v2.0.1-development-notes.md`），属于本任务 D 组的处理对象，见 D-5。

---

## 1. 复审结论（2026-10-09 实测）

### R-1 世界观设定资产静默丢弃 —— **确认存在，且比原计划判断更严重**

- `sync_assets_to_database`（`app/workflow_assets.py:711`）内遍历 entities/relations/outline_nodes/foreshadows/timeline_events，**没有 notes 处理循环**；`notes_added` 只在 `app/workflow_assets.py:719` 初始化为 0，全文件无累加。
- `notes` 表已随 v1.9.6 迁移删除（`app/db.py:630` `DROP TABLE IF EXISTS notes`），但抽取侧（`app/workflow_assets.py:544/:565/:577/:677`）仍在产出 notes。
- **新发现（推翻此前"前端正常勾选发送"的判断）**：`static/js/pages/workflows.js:938` 声明 `const noteChecks = []` 后**从未填充**——同步弹窗里根本没有「世界观设定」分组卡片（对照：伏笔组卡片在 `:911-933`）。所以 `:972` 发送的 `notes` 恒为空数组。用户连"看到然后勾选"的机会都没有。
- 修法不变：notes 归入万象谱 `category='term'`（依据：`app/api/entities.py:13` CATEGORIES 含 term；`app/api/entities.py:492` fallback 默认即 `'term'`；`static/js/pages/entities.js:13` 已渲染「术语」页签）。

### R-3 删章后产物失去归属、无法归位 —— **确认存在**

- 全库（`app/`、`static/js/`）检索 `unbound` 零命中：没有任何"未归属资产"的查询/筛选/重绑能力。
- `detach_chapter`（`app/services/asset_hub.py:349`，三个 UPDATE 在 `:356-358`）删章时只置 `chapter_id=NULL`。已绑节点的章节删后 `outline_node_id` 保留（大纲聚合仍可见）；未绑节点的章节删后两键皆空，产物**不会消失**（时间线 `app/api/timeline.py:68-75`、看板 `app/api/board.py:12-18/:51-54` 均按 `work_id` 全量列出）但**永久混入全量列表、无法筛出、无法重绑**。
- 方案维持"可看见 + 可归位"，不做数据恢复。

### D 文档控制字符损坏 —— 根因已定位

- **现象**：`docs/v2.0.1-development-notes.md` 4 处（`:17/:23/:27/:38`）＋ `AGENTS.md` 3 处（`:33/:42/:84`）。
- **损坏特征**：`\x07`（BEL 响铃）出现在 "pp" 前、`\x08`（BS 退格）出现在 "ash" 前——即源文本里的 `\a`、`\b` 被**转义解释**后分别变成了控制字符，反斜杠消失、正字被吞一个：`\app` → BEL+`pp`（应为 `app`）、`\bash` → BS+`ash`（应为 `bash`）、`\app_settings` → BEL+`pp_settings`（应为 `app_settings`）。
- **根因**：这些 markdown 是**经由会解释反斜杠转义的写入通道**生成的（Python 非原始字符串 / `echo -e` / `printf` 一类），作者在文本里写了 Windows 路径式前缀 `\app/...`、`\bash`、`\app_settings`，`\a`/`\b` 被吞成控制字符。**不是一次性笔误**：`AGENTS.md` 的 3 处早在 v1.4.0 发版提交（`4db5a3d`）就已入库，今天 v2.0.1 说明文档又新增 4 处同签名损坏——这是文档生成流程的**系统性风险**，所以修复必须同时加守护断言（D-4）防再犯。
- 伴随问题：`README.md:14` 测试徽章写 "154 项"、`:126` 写 "153 项"，实测 181（`:68/:69` 是历史版本记录，**不改**）。

---

## 2. 执行顺序（严格按序）

```
D-4（守护断言，预期红）→ D-1 → D-2 → D-3（转绿）→ D-5（发版提交）
→ R1-4（断言，预期红）→ R1-1 → R1-2 → R1-3
→ R3-4（断言，预期红）→ R3-1 → R3-2
→ R3-3（可选，单独批次，默认跳过）→ 全量回归
```

每完成一个实现阶段运行 `.venv/Scripts/python.exe -m pytest -q`，基线不降再进下一阶段。

---

## 3. D 组：文档完整性修复

### D-4 守护断言（先写，预期红）

新增 `tests/test_doc_integrity.py`：

1. 遍历仓库根的 `README.md`、`AGENTS.md` 与 `docs/` 下所有 `.md`（排除 `docs/screenshots/` 等非 md 资源目录），逐文件断言内容不含 `\x00-\x08\x0b\x0c\x0e-\x1f` 控制字符；命中时报出文件名+行号+字符码，便于定位。
2. 断言 `README.md` 徽章行与「pytest -q」说明行中的测试数量与 `pytest --collect-only -q` 实际收集数一致（用 `str(数目)` 包含匹配即可，避免正则过脆）。

写完先跑一次：第 1 条应红（现存 7 处损坏），第 2 条应红（154/153 vs 181）。

### D-1 修复 v2.0.1 说明文档（4 处）

文件：`docs/v2.0.1-development-notes.md`
- `:17` BEL+`pp/services/output_normalizer.py` → `app/services/output_normalizer.py`
- `:23` BEL+`pp/workflow_engine.py` → `app/workflow_engine.py`
- `:27` BEL+`pp/services/asset_hub.py` → `app/services/asset_hub.py`
- `:38` BEL+`pp/builtin_skill_data.py` → `app/builtin_skill_data.py`

修完用 `.venv/Scripts/python.exe -c "import re;print(re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',open('docs/v2.0.1-development-notes.md',encoding='utf-8').read()))"` 自检应为 `[]`。

### D-2 修复 AGENTS.md（3 处）

文件：`AGENTS.md`
- `:33` 反引号+BS+`ash` → 代码围栏语言标记 `bash`
- `:42` BEL+`pp_settings` → `app_settings`
- `:84` BEL+`pp_settings` → `app_settings`

### D-3 修复 README.md 计数

文件：`README.md`
- `:14` 徽章 `tests-154%20%E9%A1%B9...` → `tests-181%20%E9%A1%B9...`（URL 编码数字同步改）
- `:126` `153 项 API、响应式...` → `181 项 API、响应式...`
- `:68/:69` 为历史版本记录，**保持原样**。

### D-4 验收

`pytest tests/test_doc_integrity.py -q` 全绿；全量 `pytest -q` ≥ 182（181+1 文件内多条断言按文件计至少 +1）。

### D-5 发版提交

D-1~D-3 完成后，工作区的 v2.0.1 发版改动分两个提交：

1. `fix(docs-D): 修复控制字符损坏与陈旧测试计数并新增文档守护断言` —— `AGENTS.md`、`README.md`、`docs/v2.0.1-development-notes.md`、`tests/test_doc_integrity.py`（AGENTS/README 里的 v2.0.1 版本串顺带入库，可接受）。
2. `release(v2.0.1): 升级版本为 v2.0.1 并发布开发说明` —— `app/version.py`、`docs/PRD-本地版.md`。

若按文件拆分提交确有困难，允许合并为一个 `release(v2.0.1)` 提交，但提交信息须注明包含文档完整性修复。

---

## 4. R-1 组：世界观设定资产入库

### R1-4 断言（先写，预期红）

文件：`tests/test_output_contract.py`（既有契约断言文件，追加）。探针手法：复用 `conftest.py` 的 `make_wvc` + `db_module.get_db()` 直接调 `sync_assets_to_database`；`workflow_runs` 需先插 `workflows` 取 `workflow_id`（NOT NULL）。

1. 传入一条 `notes`（title「灵脉代价」、content「施法消耗记忆」、tags「世界观」）→ 断言 `summary["notes_added"] == 1`，且 `entities` 表能查到 `work_id` 下 `name='灵脉代价'`、`category='term'` 的行。
2. 同一 notes 连续同步两次 → 第二次 `notes_added == 0`，`entities` 中该 name 仅一行（幂等）。
3. 传入脏 note（title「以下是修改后的内容」）→ 断言计入 `summary["rejected_count"]`，不入库。

### R1-1 同步函数新增 notes 分支

文件：`app/workflow_assets.py`
位置：`sync_assets_to_database` 内，`# 5. 文章正文与版本沉淀同步`（`app/workflow_assets.py:889`）之前，新增 `# 4.5 世界观设定同步（归入万象谱术语）` 块：

```python
    for note in body.notes:
        ok_note, r_note = sanitize_asset_item(
            {"name": note.title, "title": note.title, "content": note.content, "tags": note.tags}, "note")
        if not ok_note:
            summary["rejected_count"] += 1
            if len(summary["rejected_items"]) < 20:
                summary["rejected_items"].append({"kind": "note", "title": note.title, "reason": r_note})
            continue
        n_title = (note.title or "").strip()
        if not n_title:
            continue
        exist_note = db.execute(
            "SELECT id, content FROM entities WHERE work_id=? AND name=?", (work_id, n_title)
        ).fetchone()
        if exist_note:
            if note.content:
                db.execute(
                    """UPDATE entities
                       SET content = CASE WHEN content != '' THEN content || '\n' || ? ELSE ? END,
                           updated_at = datetime('now','localtime')
                       WHERE id = ?""",
                    (note.content, note.content, exist_note["id"]),
                )
        else:
            db.execute(
                "INSERT INTO entities (work_id, category, name, content, fields_json, tags) VALUES (?, 'term', ?, ?, '{}', ?)",
                (work_id, n_title, note.content or "", (note.tags or "").strip() or "世界观"),
            )
            summary["notes_added"] += 1
```

要点：`category` 写死字面量 `'term'`（勿用 `custom`）；幂等键 = `work_id + name`；tags 缺省补「世界观」；已存在时只补 content 不新增计数。若 D/R 前序提交使行号偏移，以 `# 5. 文章正文` 注释为锚点。

### R1-2 契约块路径兼容 notes

1. 文件：`app/services/output_normalizer.py`，`extract_assets_block` 的 `valid_keys` 列表（`app/services/output_normalizer.py:155`）追加 `"notes"`（保持列表内既有顺序，加在末尾）。
2. 文件：`app/workflow_assets.py`，契约分支的类型遍历列表（`app/workflow_assets.py:628` 的 `for kind, field in [...]`）追加 `("note", "notes")`。

目的：防御用户自建 Skill 在契约块里写 notes 键。当前 14 份内置手册模板不含 notes，契约路径行为不变。

### R1-3 前端：新增「世界观设定」分组卡片

文件：`static/js/pages/workflows.js`

1. 在伏笔计划表分组（`:911-933` 模板）之后、`const noteChecks = [];`（`:938`）处，照同样卡片结构新增「世界观设定」分组：
   - 条件 `(assets.notes || []).length > 0`；
   - 分组标题：`世界观设定 (N条) · 将归入万象谱「术语」`，图标用 `menu_book`（与 `entities.js:13` 术语页签一致）；
   - 每条渲染 checkbox（默认勾选）+ `title`（主色加粗）+ `content`（灰色两行截断）+ `tags`（若有，小字），push 进 `noteChecks`。
2. `:994` `if (sm.notes_added) tips.push(`设定+${sm.notes_added}`)` 文案改为 `` `术语+${sm.notes_added}` ``。

注意：`:940` 的 `allCheckboxes` 已包含 `noteChecks`，无需改；`:972` 的 payload 已发送 notes，无需改。

### R1 验收

`pytest -q` 全绿且 ≥ 184；手测路径：工作流产出含「世界观设定」→ 弹窗出现该分组 → 勾选同步 → toast「术语+1」→ 万象谱「术语」页签可见该条目且 tags 含「世界观」→ 再次同步无重复。

---

## 5. R-3 组：未归属产物可看见、可归位

### R3-4 断言（先写，预期红）

文件：`tests/test_asset_hub_p2.py` 追加（或新建 `tests/test_unbound_assets.py`）：

1. 章节已绑节点：`resolve_binding` 写入产物（双键齐）→ 删章（`client.delete(f"/api/chapters/{id}")`）→ 断言产物在大纲节点聚合 `GET /api/works/{wid}/outline/nodes/{nid}/plot-items` 中仍可见（锁死既有行为）。
2. 章节未绑节点：删章 → 断言产物在 `GET /api/works/{wid}/timeline` 与 `GET /api/works/{wid}/foreshadows` 仍可见，且 `GET /api/works/{wid}/unbound-assets` 能查到（此接口 R3-1 才实现，先红）。
3. rebind：调 `POST /api/works/{wid}/unbound-assets/rebind` 把产物绑到某节点 → 断言其出现在该节点聚合中，且 `chapter_id/outline_node_id` 双键一致（此接口先红）。

### R3-1 后端：未归属查询 + 批量重绑

1. 文件：`app/services/asset_hub.py` 新增：
   ```python
   def list_unbound_assets(db, work_id: int) -> dict:
       """两键皆空的产物：可看见、可归位。"""
       foreshadows = db.execute(
           "SELECT id, title, content, status, chapter_id, outline_node_id FROM foreshadows "
           "WHERE work_id=? AND chapter_id IS NULL AND outline_node_id IS NULL ORDER BY id DESC",
           (work_id,)).fetchall()
       timeline_events = db.execute(
           "SELECT id, time_label, event, characters, chapter_id, outline_node_id FROM timeline_events "
           "WHERE work_id=? AND chapter_id IS NULL AND outline_node_id IS NULL ORDER BY id DESC",
           (work_id,)).fetchall()
       return {"foreshadows": [dict(r) for r in foreshadows],
               "timeline_events": [dict(r) for r in timeline_events]}
   ```
2. 文件：`app/api/works.py` 新增两个端点（该 router 无前缀，实际路径为 `/api/works/...`）：
   - `GET /works/{work_id}/unbound-assets` → 返回 `list_unbound_assets` 结果；
   - `POST /works/{work_id}/unbound-assets/rebind`，入参 Pydantic 模型：
     ```python
     class RebindIn(BaseModel):
         foreshadow_ids: list[int] = []
         timeline_event_ids: list[int] = []
         chapter_id: int | None = None
         outline_node_id: int | None = None
     ```
     校验（复用既有 `_check_*` 风格）：目标章节/节点必须属于该 work；`chapter_id` 与 `outline_node_id` 至少给一个。逐条 UPDATE 前调用 `resolve_binding(db, chapter_id, outline_node_id)` 取得双键一致值再写入；只更新属于该 `work_id` 的行；返回 `{"foreshadows_rebound": n, "timeline_events_rebound": m}`。

### R3-2 前端：筛选、标记与重绑入口

文件：`static/js/pages/timeline.js`、`static/js/pages/board.js`

1. **「仅看未归属」开关**：两页筛选栏（timeline 的作品下拉在 `static/js/pages/timeline.js:43` 附近，board 的工具行同级）各加一个切换开关/复选框；开启时对已加载列表做本地过滤 `item.chapter_id == null && item.outline_node_id == null`（两接口的 SELECT 均为 `t.*`/`f.*`，字段已在返回体内，无需新接口）。
2. **「未归属」徽标**：`static/js/pages/timeline.js:105` 处 `chTitle` 为空且两键皆空时，渲染一个小徽标「未归属」（样式参考 `:152` 既有章节徽标，用 `bg-tertiary-fixed text-on-tertiary-fixed` 或 outline 变体均可）；`static/js/pages/board.js:152-153` 同理，`f.chapter_title` 为空且 `f.outline_node_id == null` 时显示。
3. **批量重绑**：在时间线页「仅看未归属」开启时，列表条目加复选框 + 底部「重绑到…」操作（章节下拉 + 大纲节点下拉，二选一或都选），确认后调 `POST /api/works/{work_id}/unbound-assets/rebind`，成功后刷新列表并 toast（`"ok"`）。看板页可复用同一交互，若工作量过大可只在时间线页实现，看板仅做徽标+筛选。

### R3-3（可选，默认跳过）

删章转移选项：`app/api/works.py:224` delete-impact 返回体增加 `chapter_options`/`node_options`；`:241` delete_chapter 支持转移目标参数；前端删除确认弹窗加「转移到…」选项。单独批次执行，本次不强制。

### R3 验收

`pytest -q` 全绿且 ≥ 187（R3-4 三条断言计入）；手测：删一个未绑节点的章节 → 时间线开「仅看未归属」看到该产物（带徽标）→ 勾选重绑到某节点 → 该节点剧情聚合出现它；已绑节点章节删后聚合不消失（回归）。

---

## 6. 引用索引（file:line）

| 引用 | 说明 |
|---|---|
| `app/workflow_assets.py:71` | `SyncAssetsIn.notes` 入参 |
| `app/workflow_assets.py:544` / `:565` | 启发式产出 notes |
| `app/workflow_assets.py:628` | 契约分支 kind/field 列表（R1-2） |
| `app/workflow_assets.py:711` | `sync_assets_to_database` |
| `app/workflow_assets.py:719` | `notes_added` 仅初始化 |
| `app/workflow_assets.py:889` | `# 5. 正文沉淀`，R1-1 插入锚点 |
| `app/services/output_normalizer.py:155` | `valid_keys`（R1-2） |
| `app/services/asset_hub.py:11` | `resolve_binding`（rebind 复用） |
| `app/services/asset_hub.py:349` / `:356-358` | `detach_chapter` 与三个 UPDATE |
| `app/api/works.py:224` / `:241` | delete-impact / delete_chapter（R3-3） |
| `app/api/timeline.py:68-75` | 时间线全量列表（含双键） |
| `app/api/board.py:12-18` / `:51-54` | 看板 LIST_SQL 与列表 |
| `app/api/entities.py:13` / `:492` | CATEGORIES 与 term 兜底口径 |
| `static/js/pages/workflows.js:911-933` | 伏笔分组卡片模板（R1-3 参照） |
| `static/js/pages/workflows.js:938` | `noteChecks` 空声明（R-1 前端断点） |
| `static/js/pages/workflows.js:972` | notes payload（已存在，不改） |
| `static/js/pages/workflows.js:994` | 「设定+N」tips（改「术语+N」） |
| `static/js/pages/entities.js:13` | 术语页签 |
| `static/js/pages/timeline.js:43` / `:105` | 筛选栏锚点 / chTitle 渲染 |
| `static/js/pages/board.js:152-153` | 章节徽标渲染 |
| `AGENTS.md:33` / `:42` / `:84` | 控制字符损坏 3 处 |
| `docs/v2.0.1-development-notes.md:17/:23/:27/:38` | 控制字符损坏 4 处 |
| `README.md:14` / `:126` / `:68-69` | 计数修复 2 处 / 历史记录不改 |
| `app/db.py:630` | `DROP TABLE IF EXISTS notes`（历史成因） |
