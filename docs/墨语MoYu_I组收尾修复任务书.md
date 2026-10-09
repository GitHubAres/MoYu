# 墨语MoYu I组收尾修复任务书

> 适用版本：v2.0.1（提交 `2449ad4` 之后）
> 测试基线：`.venv/Scripts/python.exe -m pytest -q` → **196 passed**，修改后不降
> 提交前缀：`fix(docs-I2)` / `fix(contract-I1)`
> 本组定位：H/R+D 组执行审核中发现的两个遗留缺陷收尾，工作量小

---

## 0. 红线

同既有任务书：无打包、不动 DDL、不碰 `data/`、AI 内容先预览后写入、只改本任务书列出的文件。

---

## 1. 问题清单

### I-1【P2】编辑保存链路丢失契约块（H-4 的衍生回归）

- **现象**：`static/js/pages/workflows.js:1107` 的编辑 textarea 展示的是 `stripMoyuAssetsBlock(s.output)`（剥离契约块后），而「以修改稿继续」按钮（`workflows.js:1114`）提交的是 `content: ta.value` —— 即剥离后的文本。用户一旦走"编辑→以修改稿继续"路径，该步骤存储的 output **永久丢失契约块**，后续 `{{steps.N.assets}}` 引用与全流程汇总资产抽取对该步骤降级为启发式。
- **根因**：H-4 规格只约束了展示层剥离，未覆盖编辑回写链路。
- **注意**：用户在编辑框里**看不到**契约块，因此不存在"故意删除"的场景，追加回填不会违背用户意图。

### I-2【P2】文档守护断言私自缩小扫描范围，19 处历史损坏未修

- **现象**：`tests/test_doc_integrity.py:19` 用 `re.match(r"^v1..*-development-notes.md$", p.name)` 排除了历史开发说明，而 `docs/v1.2.0-development-notes.md`（4 处）、`docs/v1.8.3-development-notes.md`（4 处）、`docs/v1.9.1-development-notes.md`（1 处）、`docs/v1.9.7-development-notes.md`（5 处）共 **14 行 19 个控制字符**（`\x07`×12、`\x08`×7）仍在库中。任务书要求扫描全部 md，此处属未授权缩小范围。
- **损坏映射规律（已验证全部 19 处）**：`\x07`(BEL) 还原为 `a`、`\x08`(BS) 还原为 `b` —— `\x07pp/...`→`app/...`、`\x08uild_exe.py`→`build_exe.py`、`\x08ash`→`bash`、`SHA256: \x0783086...`→`SHA256: a83086...`。
- **修法**：机械替换 14 行（只动这 19 个字符，不重排整行），然后**删除排除规则**，让守护断言覆盖全部历史文档。

---

## 2. 执行顺序（断言先行）

```
I-2a（删守护排除规则 → 跑 test_doc_integrity 应红）
→ I-2b（修复 14 行 19 处 → 转绿）
→ I-1（前端编辑回写追加契约块）
→ 全量回归（196 不降）
```

---

## 3. I-2 详细步骤

1. `tests/test_doc_integrity.py`：删除 `test_no_control_characters_in_markdown` 中的排除分支（原 `:18-20` 三行：注释 + `if re.match(...)` + `continue`），只保留 screenshots 排除。
2. 运行 `.venv/Scripts/python.exe -m pytest tests/test_doc_integrity.py -q` → 应**红**，报出的文件/行号应与下表一致（共 14 行）：

| 文件 | 行号 | 控制字符 |
|---|---|---|
| `docs/v1.2.0-development-notes.md` | 38 | `\x08`（→`build_exe.py`） |
| `docs/v1.2.0-development-notes.md` | 62 | `\x08`（→`bash`） |
| `docs/v1.2.0-development-notes.md` | 71 | `\x07`（→哈希 `a83086...`） |
| `docs/v1.2.0-development-notes.md` | 84 | `\x08`（→`build_exe.py`） |
| `docs/v1.8.3-development-notes.md` | 11 / 29 / 30 / 31 | `\x07`（→`app/...`） |
| `docs/v1.9.1-development-notes.md` | 116 | `\x08`（→`bash`） |
| `docs/v1.9.7-development-notes.md` | 22 / 26 / 37 / 38 / 39 | `\x07`（→`app/...`） |

3. 逐处替换：`\x07` → 字符 `a`，`\x08` → 字符 `b`。替换时**只动该字符本身**，行内其余内容（含原有空格、缩进、标点）一律保持原样。
4. 复跑 `pytest tests/test_doc_integrity.py -q` → 应**绿**。
5. 提交：`fix(docs-I2): 修复历史开发说明控制字符损坏并扩大守护断言扫描范围`

## 4. I-1 详细步骤

文件：`static/js/pages/workflows.js`

位置：「以修改稿继续」按钮 onclick（`workflows.js:1112-1120` 附近，`await api.post(.../review, { action: "edit", content: ta.value })` 处）。

改法：提交前构造回填逻辑（写死如下，可直接采用）：

```js
                  let submitContent = ta.value;
                  const origBlockMatch = String(s.output || "").match(/<!--\s*MOYU:ASSETS[\s\S]*?-->/i);
                  if (origBlockMatch && !/MOYU:ASSETS/i.test(submitContent)) {
                    submitContent = submitContent.trimEnd() + "\n\n" + origBlockMatch[0].trim();
                  }
                  await api.post(`/workflows/runs/${runId}/steps/${s.step_seq}/review`, { action: "edit", content: submitContent });
```

要点：
- 判定条件双保险：原文含契约块 **且** 编辑稿里没有（防止用户在别处自己粘了块导致重复追加）。
- 追加位置在编辑稿末尾，中间隔一个空行。
- `parseWorkflowOptions`、`pre` 展示、textarea 展示等其余链路**一律不动**。

提交：`fix(contract-I1): 编辑稿保存时回填契约块避免结构化资产丢失`

## 5. 验收

1. `.venv/Scripts/python.exe -m pytest -q` → **196 passed**（断言数不变，只扩大了既有断言的扫描范围）。
2. `git status` 只出现本任务书列出的 3 个文件：`tests/test_doc_integrity.py`、`static/js/pages/workflows.js`、4 个历史 md。
3. 手测（可选）：跑一个含契约块输出的工作流步骤 → 编辑框改几个字 → 以修改稿继续 → 重新打开该步骤查看，资产抽取仍为 `contract` 来源。
