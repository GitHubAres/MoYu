# 墨语 MoYu「AI 修撰使」完整功能与底层代码架构逻辑报告

> **编制日期**：2026-10-01  
> **适用版本**：墨语 MoYu v1.2.5+  
> **模块定位**：核心创作工作台 · AI 辅助写作引擎与安全编排中枢  

---

## 一、 功能定位与设计哲学

「**AI 修撰使**」是墨语（MoYu）长篇小说创作工作台最核心的 AI 辅助引擎。它面向网络文学与长篇严肃创作者，旨在充当作者身侧的**文笔推演助手与智囊参谋**。

区别于市面上多数 AI 写作工具“端到端黑盒生成、自动覆盖正文、容易崩坏人设”的粗暴模式，墨语确立了三项铁律安全原则：

1. **绝对内容安全**：AI 生成的任何段落均首先呈现在独立的预览候选卡片中，只有经作者明确确认并点击“采纳”，才会正式写入正文；严禁任何形式的静默覆盖。
2. **全流程可逆无损**：采纳 AI 内容前系统自动创建正文快照；采纳后原地提供“撤销采纳”按钮，随时支持一键原子回滚。
3. **精准上下文感知**：拒绝无依据的盲写，自动联动**当前章节、前情摘要、细纲节点、作品设定库（人物/物品/势力）**协同生成。

---

## 二、 交互全景与功能矩阵

```
+---------------------------------------------------------------------------------+
|                                 墨语写作工作台                                    |
| +---------------------+ +-----------------------------+ +---------------------+ |
| |      卷章目录        | |         正文编辑区          | |      AI 修撰使       | |
| |                     | |                             | |                     | |
| | - 第一卷            | | 选中高亮文本 ──────────┐    | | [已挂载上下文]      | |
| |   - 第1章 寒夜惊变  | |                        ▼    | |  ☑ 当前章前3000字   | |
| |   - 第2章 灵台蒙尘  | |                  [选区浮动工具条] |  ☑ 上一章末500字    | |
| |                     | |                  [续写|扩写|缩写|改写]|  ☑ 关联细纲节点   | |
| |                     | |                             | |  ☑ 设定:沈墨(主角)  | |
| |                     | |                             | | [任务模式] [续/扩/缩/改]|
| |                     | |                             | | [提示词模板选择]     | |
| |                     | |                             | | [字数:短/中/长]      | |
| |                     | |                             | | [候选数量: 1 ~ 3]   | |
| |                     | |                             | | [生成按钮]          | |
| |                     | |                             | | ------------------- | |
| |                     | |                             | | [候选卡片 1 (流式)] | |
| |                     | |                             | |  LCS双栏行级差异对比 | |
| |                     | |                             | |  [采纳] [复制] [放弃]| |
+---------------------+ +-----------------------------+ +---------------------+ |
+---------------------------------------------------------------------------------+
```

### 2.1 四大创作任务模式
- **续写·顺延文势 (`continue`)**：通读前情与设定，顺着作者既有文风、叙事节奏自然延伸后续情节，拒绝重复已有内容。
- **扩写·充实细节 (`expand`)**：对选中的粗略骨干或动作白描进行细节充实，丰富环境烘托、动作分解、心理与感官描摹，保持情节走向不变。
- **缩写·凝练取舍 (`condense` / `shorten`)**：压缩冗余叙事与注水段落，剔除无力铺陈，保留主线冲突与核心意象。
- **改写润色·字句打磨 (`polish` / `rewrite`)**：修正病句与语病、替换平淡动词、调整行文呼吸感与张力，保持原叙事视角不变。

### 2.2 上下文挂载体系与设定库感知
- **基础上下文层**：
  - **当前章节**：提取当前章节前 3000 字正文，保留最近铺垫；
  - **前情摘要**：提取上一章末尾 500 字，确保章节更替平滑承接；
  - **大纲细纲**：自动匹配当前章节在全书大纲树中绑定的细纲节点（`synopsis`），确保剧情不偏航。
- **设定库（Entities）动态感知**：
  - 后台探测算法实时比对当前正文提及的角色、地点、物品、功法与势力；
  - 自动呈现提及实体的属性卡片（如身份境界、性格标签、持有法宝），支持作者自由勾选/取消，作为世界观硬约束注入模型。

### 2.3 选区浮动工具栏（Floating Toolbar）
- 在编辑器内选中任意文本，光标上方约 48px 位置毫秒级唤出黑色轻量浮动条，提供快捷入口（`续写`、`扩写`、`缩写`、`改写`），点击即可携带当前选区直接触发生成，作者视线无需脱离编辑区。

### 2.4 安全采纳与全生命周期版本保护
- **打字机流式呈现**：支持 1~3 组候选方案，通过 SSE 实时逐字输出，随时可点击停止；
- **行级 LCS 差异对比（Diff）**：点击“预览差异”，基于最长公共子序列算法计算原文与 AI 文本的增删变动，红绿双栏高亮呈现；
- **采纳自动备份**：点击“采纳”，系统在写入正文的瞬间自动生成一份 `snapshot_source="auto"` 的版本快照；
- **原地撤销采纳**：采纳后卡片原地更新为“撤销采纳”按钮，即使离开或继续编辑，也能通过闭包暂存的历史文本无损回退。

---

## 三、 底层代码架构与全链路数据流

AI 修撰使的系统实现跨越了前端交互层、后端编排层、协议通信层与数据保护层：

```
[前端: static/js/pages/workbench.js]
    │
    ├─ 1. 采集上下文 (当前章、前章末尾、大纲细纲、设定实体)
    ├─ 2. 选区文本 (selRange / selText) + 自定义指令 + 提示词模板 ID
    ▼
[POST /api/ai/generate (SSE 流式长连接)]
    │
[后端编排: app/features.py -> AIOrchestrator]
    │
    ├─ 3. 模板匹配 (PromptLibrary: prompts 表优先级 > 内置 BASIC_PROMPTS)
    ├─ 4. 组装结构化 Messages (System Prompt + 长度约束 + User Context Block)
    ├─ 5. 登记异步任务审计 (tasks 表持久化跟踪 token 与耗时)
    ▼
[通信调用: app/ai_client.py -> chat_stream()]
    │
    ├─ 6. 读取 app_settings (Base URL / API Key / Model)
    ├─ 7. 异步非阻塞通信 (httpx.AsyncClient -> POST /chat/completions)
    ▼
[SSE 数据帧回调: static/js/pages/workbench.js]
    │
    ├─ 8. ReadableStream 接收 data: {"candidate": 0, "delta": "..."}
    ├─ 9. DOM 动态增量渲染候选卡片与打字光标
    ▼
[用户采纳决策: workbench.js -> adopt()]
    │
    ├─ 10. 采纳前自动保存正文旧内容快照 (PATCH /api/chapters/{id})
    ├─ 11. 原生 DOM 替换选区或追加文末，触发保存
    └─ 12. 挂载一键撤销（Undo）闭包，保留历史撤销点
```

---

## 四、 核心代码实现深度剖析

### 4.1 前端：上下文提取与流式通信 (`static/js/pages/workbench.js`)

#### (1) 上下文动态组装与请求触发
```javascript
async function runGenerate() {
  if (generating || !chapter) return;
  if (dirty) await saveContent();
  saveRecentInstruction(instrInput.value.trim());

  // 1. 过滤并拼接所有勾选生效的上下文条目
  const context = ctxItems.filter((i) => i.cb.checked)
    .map((i) => i.getText()).filter(Boolean).join("\n\n----\n\n");

  const payload = {
    task: aiTask,
    instruction: instrInput.value.trim(),
    context,
    selection: selText,
    length: aiLength,
    candidates: aiCandidates,
    stream: true,
    prompt_id: aiPromptId,
  };

  abortCtrl = new AbortController();
  const resp = await fetch("/api/ai/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: abortCtrl.signal,
  });
  // ...
}
```

#### (2) SSE 事件流解析与打字机响应
```javascript
const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buf = "";

for (;;) {
  const { done, value } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });
  let idx;
  while ((idx = buf.indexOf("\n\n")) >= 0) {
    const frame = buf.slice(0, idx);
    buf = buf.slice(idx + 2);
    if (!frame.startsWith("data:")) continue;
    const evt = JSON.parse(frame.slice(5).trim());

    if (evt.start) {
      if (curCard) finishCard(curCard);
      curCard = addCandidateCard(evt.candidate);
    } else if (evt.delta !== undefined && curCard) {
      curCard._text += evt.delta;
      curCard._body.textContent = curCard._text;
      curCard.scrollIntoView({ block: "nearest" });
    } else if (evt.done) {
      if (curCard) finishCard(curCard);
    }
  }
}
```

---

### 4.2 后端：提示词编排与任务持久化 (`app/features.py`)

`AIOrchestrator.generate()` 负责处理任务类型、匹配提示词模板，并构建标准的 OpenAI 结构化消息：

```python
class AIOrchestrator:
    BASIC_PROMPTS = {
        "continue": "你是中文小说续写助手。请根据上下文续写后续正文，只输出正文。",
        "expand": "你是中文小说扩写助手。请对选区做细节扩充，只输出扩写后的正文。",
        "condense": "你是中文小说缩写助手。请压缩给定文本，只输出缩写后的正文。",
        "polish": "你是中文小说润色助手。请改写润色给定文本，只输出润色后的正文。",
        "outline": "你是小说大纲助手。请根据要求生成简洁的分章大纲。",
        "check": "你是小说设定检查助手。请检查正文与设定是否矛盾，列出问题。",
    }

    LENGTH_HINTS = {
        "short": "控制在 100~200 字。",
        "medium": "控制在 300~500 字。",
        "long": "800 字以上。",
    }

    async def generate(self, body: _GenIn):
        task = body.task if body.task in self.BASIC_PROMPTS else "continue"
        sys_prompt = self.BASIC_PROMPTS[task]

        # 优先读取自定义或官方提示词模板
        if body.prompt_id:
            row = get_db().execute("SELECT task_type, template FROM prompts WHERE id=?", (body.prompt_id,)).fetchone()
            if row:
                sys_prompt = row["template"]

        # 拼接长度约束
        sys_prompt += "\n" + self.LENGTH_HINTS.get(body.length, self.LENGTH_HINTS["medium"])

        # 拼装结构化用户输入
        parts = []
        if body.context:
            parts.append("【上下文】\n" + body.context)
        if body.selection:
            parts.append("【选中文本】\n" + body.selection)
        if body.instruction:
            parts.append("【写作要求】\n" + body.instruction)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "\n\n".join(parts) or "请开始。"},
        ]

        # 注册异步任务，持久化耗时与 Token
        task_id = create_task(body.work_id, body.task, f"{body.task} / {body.length} / {body.candidates} 候选")
        start_task(task_id)

        async def event_stream():
            yield "data: " + json.dumps({"task_id": task_id}, ensure_ascii=False) + "\n\n"
            for i in range(body.candidates):
                yield "data: " + json.dumps({"candidate": i, "start": True}, ensure_ascii=False) + "\n\n"
                async for delta in chat_stream(messages, cfg, {}):
                    yield "data: " + json.dumps({"candidate": i, "delta": delta}, ensure_ascii=False) + "\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

### 4.3 通信层：OpenAI 兼容客户端 (`app/ai_client.py`)

底层使用 `httpx.AsyncClient` 进行原生流式长连接，并对超时、网络中断及各类 HTTP 错误做了标准化友好化转换：

```python
async def chat_stream(messages: list, cfg: dict, usage_box: dict):
    payload = {
        "model": cfg["ai_model"],
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    async with _client(cfg) as c:
        async with c.stream("POST", "/chat/completions", json=payload) as resp:
            _check_status(resp)
            async for line in resp.aiter_lines():
                if not line.startswith("data: "): continue
                raw = line[6:].strip()
                if raw == "[DONE]": break
                chunk = json.loads(raw)
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta
```

---

### 4.4 安全回填与快照闭环 (`static/js/pages/workbench.js`)

在用户决定采纳时，通过 DOM Range 操作或末尾追加实现正文修改，并在前后打入版本保护点：

```javascript
async function adopt(card) {
  const text = card._text;
  if (!text || !chapter) return;
  const old = editorText();
  const useRange = rangeAlive();

  if (useRange) {
    const ok = await ui.confirm("采纳 AI 内容", "将用 AI 生成的内容替换当前选中的正文（替换前会自动留存一份版本快照）。", "替换");
    if (!ok) return;
  }

  // 1. 采纳前向后端打底留存旧正文快照
  try {
    await api.patch(`/chapters/${chapter.id}`, {
      content: old,
      snapshot_source: "auto",
      snapshot_label: "采纳前自动留存"
    });
  } catch (e) {
    console.warn("自动快照留存失败:", e);
  }

  // 2. 写入编辑器
  if (useRange) {
    selRange.deleteContents();
    selRange.insertNode(document.createTextNode(text));
    selRange = null; selText = "";
    hideSelToolbar();
  } else {
    editor.textContent = old ? old.replace(/\s+$/, "") + "\n\n" + text : text;
  }
  dirty = true;
  await saveContent("ai");
  ui.toast("已采纳并写入正文", "ok");

  // 3. 挂载撤销采纳操作
  card._actions.innerHTML = "";
  card._actions.append(ui.el("button", {
    class: "flex items-center gap-0.5 px-2 py-1 rounded-md bg-error-container text-on-error-container font-label-sm",
    onclick: async () => {
      const ok = await ui.confirm("撤销采纳", "将正文恢复到采纳前的内容。", "撤销");
      if (!ok) return;
      editor.textContent = old;
      dirty = true;
      await saveContent("ai");
      ui.toast("已撤销采纳", "ok");
      card.remove();
    }
  }, ui.icon("undo", "text-[14px]"), "撤销采纳"));
}
```

---

## 五、 总结与未来演进

「AI 修撰使」是墨语区别于各类泛娱乐写作插件的核心资产。它将大语言模型的泛化生成能力严密约束在**文学逻辑编排、选区精准控制与数据版本快照**的工程框架中，让创作者既能借助大模型突破灵感瓶颈，又能对最终作品享有 100% 的主权与可控性。

### 后续演进建议：
1. **多候选真并发推演**：利用 Python 异步协程池实现多候选同时流式生成，缩短长文本等待耗时；
2. **设定违背预检（AI 护栏）**：在流式生成结束前，根据挂载的实体设定做轻量违规比对（如反派称谓错误、死者出场等），并标黄提示作者。
