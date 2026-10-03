# 墨语MoYu · AI 模型配置自动识别与下拉选择开发计划书

- **版本**：V1.0（草案）
- **日期**：2026-10-03
- **目标版本**：墨语 V1.7.0（当前基线 V1.6.1）
- **依据**：`app/ai_client.py`、`app/features.py`、`app/api/prefs.py`、`static/js/pages/settings.js` 现状代码
- **约束**：本计划书只做设计，不改代码；交付对象为 Codex，按本文档可直接开工

---

## 1. 背景与目标

### 1.1 背景
当前「系统设置 → AI 模型配置」的模型名是**纯手填文本框**（`settings.js` 第 112 行），存在四个痛点：
1. **易填错**：模型名大小写/后缀写错（如 `deepseek-chat` 写成 `deepseek_chat`），要到生成时才报错，排错链路长
2. **不可发现**：用户不知道自己的 Key 在上游能用什么模型；服务商模型上新/下旧频繁，界面信息滞后
3. **预设提示是静态硬编码**：`AI_PROVIDERS` 里的 `models` 字段是写死的字符串（如 `kimi-k2.6 / kimi-k2-0905-preview`），仅供展示，无法选择，维护成本高
4. **与"测试连接"割裂**：`/api/ai/test` 能验证连通性，但验证不了"这个模型名是否存在"

OpenAI 兼容协议提供标准模型列表接口 `GET {base_url}/models`，DeepSeek / Kimi(Moonshot) / 智谱 / 通义兼容模式 / OpenAI 均支持，具备落地条件。

### 1.2 目标
- **一键识别**：设置页点击即可用当前 Base URL + API Key 从上游拉取真实模型清单
- **下拉选择**：模型字段从"手填"升级为"可下拉浏览、点选回填"，同时保留手填能力（自定义/内测模型仍可输入）
- **缓存降噪**：24 小时内重复打开不重复请求上游；切换服务商自动失效
- **优雅降级**：上游不支持 `/models`（404）或网络异常时，回退到服务商预设的静态常用模型列表，功能不中断

### 1.3 非目标（本版不做）
- 生图配置（`img_base_url/img_model`）的同款下拉——架构预留，后续照抄即可
- 按任务路由（`route_{task}_base_url`）的独立模型字段
- 模型计费/上下文长度/能力标签等元信息展示
- 模型可用性实测（逐个模型 ping）——成本过高，靠生成时报错兜底

---

## 2. 现状分析（关键事实，开发前必读）

### 2.1 配置链路
```
app_settings 表（key-value）
  ai_base_url   默认 https://api.openai.com/v1
  ai_api_key    默认空
  ai_model      默认空
        │ get_ai_config()  ← app/ai_client.py
        ▼
AIOrchestrator.generate() / chat.py      ← cfg["ai_model"] 直接作为 payload.model
```

### 2.2 现有设置页（`static/js/pages/settings.js`）
- `AI_PROVIDERS` 预设数组（第 102–107 行）：deepseek / kimi / zhipu / qwen / openai / custom，含硬编码 `base_url`、`model`、`models`（展示用 hint）、`site`
- 三个输入框：`aiUrl` / `aiKey`（password）/ `aiModel`，均 `change` 失焦即存（`save()` → `PATCH /api/settings`）
- 预设按钮：回填 url+model，toast 提示填 Key
- 「测试连接」按钮：保存后 `POST /api/ai/test`（真实 chat 调用 `max_tokens=1`）
- 按任务路由区：`route_{task}_base_url` 仅覆盖 Base URL，Key 与模型始终跟随主配置

### 2.3 后端路由（`app/features.py`）
- `AIOrchestrator.build_router()` 挂 `prefix="/ai"`，现有 `POST /generate`、`POST /test`
- `app/api/ai.py` 仅一行：`router = get_orchestrator().build_router()`
- httpx 客户端封装在 `app/ai_client.py`：`_client(cfg)` 设 `base_url` + Bearer Key，`_check_status()` 已做 401/404 友好化

### 2.4 UI 组件约束（`static/js/ui.js`）
- 仅有 `el / toast / confirm / prompt / modal`，**无现成下拉组件**——下拉面板需在 settings.js 内自实现（约 80 行），不改动 ui.js，降低回归面

---

## 3. 总体设计

### 3.1 数据流
```
[设置页] 用户点击「浏览模型」/ 打开面板
    │  先 save 当前 ai_base_url/ai_api_key（沿用现有失焦保存，确保服务端配置最新）
    ▼
GET /api/ai/models?refresh=0|1        ← 服务端读已保存配置，不接收前端传 Key
    ▼
httpx GET {ai_base_url}/models        ← Bearer ai_api_key，超时 15s
    ▼
归一化 + 过滤 + 截断 + 排序            ← 见 4.1.3
    ▼
{ ok, models:[{id, owned_by}], total, fetched_at, cached, source:"remote"|"cache"|"preset" }
    ▼
[设置页] 渲染下拉面板；选中 → 回填 aiModel 输入框 → 触发 save({ai_model})
```

### 3.2 缓存策略
- 新设置键 `ai_models_cache`（DEFAULT_SETTINGS 默认 `""`），内容 JSON：
  ```json
  {"base_url": "...", "fetched_at": "2026-10-03T08:00:00", "models": [{"id": "...", "owned_by": "..."}]}
  ```
- 命中条件：`base_url` 与当前保存值完全一致 **且** 距今 < 24h → 直接返回 `cached=true, source="cache"`，不请求上游
- `?refresh=1` 或 base_url 变更 → 强制重新拉取并覆盖缓存
- 拉取失败**不覆盖**旧缓存（缓存继续兜底）；仅当旧缓存也失效时返回错误

### 3.3 降级策略（三级）
| 级别 | 触发 | 行为 |
|---|---|---|
| L1 远程列表 | `/models` 200 | 展示真实列表 |
| L2 静态预设 | `/models` 404/超时/401，或 provider 匹配 | 展示 `AI_PROVIDERS` 中当前 provider 的 `models` 字段拆分为选项，`source="preset"`，面板顶部提示"无法获取上游列表，已显示常用模型" |
| L3 纯手填 | provider=custom 且无预设 | 面板显示"请手动输入模型名"引导，输入框照常可用 |

三级降级对 UI 透明：面板接口与数据结构完全一致，仅 `source` 字段不同。

---

## 4. 详细设计

### 4.1 后端

#### 4.1.1 `app/ai_client.py` 新增
```python
MODELS_TIMEOUT = 15.0
NON_CHAT_PATTERNS = ("embed", "rerank", "bge-", "whisper", "tts", "moderation",
                     "dall-e", "omni-moderation", "text-moderation", "voice", "realtime")

async def list_models(cfg: dict, *, refresh: bool = False,
                      cache_get=None, cache_set=None) -> dict:
    """返回 {ok, models, total, fetched_at, cached, source, message}。

    cache_get/cache_set 为可选的同步存取钩子（由调用方注入 settings 存取），
    本函数不直接依赖 db 层，便于测试。
    """
```
- 先查缓存（`refresh=False` 且命中）→ 直接返回 `source="cache"`
- `async with _client(cfg) as c: resp = await c.get("/models", timeout=MODELS_TIMEOUT)`
- 401 → `{"ok": False, "code": "auth", "message": "API Key 无效或已过期（401）"}`（**不清缓存**）
- 404 → `{"ok": False, "code": "unsupported", "message": "该服务商未提供模型列表接口"}`（**不清缓存**）
- 网络/超时 → `code: "network"`，复用 `_friendly()` 文案
- 成功 → 解析 `data[].id`/`owned_by` → 过滤 `NON_CHAT_PATTERNS`（大小写不敏感、子串匹配）→ 截断至 500 → 排序（`owned_by` 字典序 → `id` 字典序）→ 写缓存 → `source="remote"`

#### 4.1.2 `app/features.py` 路由（挂进 `AIOrchestrator.build_router()`）
```python
@router.get("/models")
async def list_models(refresh: int = 0):
    cfg = get_ai_config()
    if not (cfg.get("ai_base_url") or "").strip() or not (cfg.get("ai_api_key") or "").strip():
        return {"ok": False, "code": "no_config",
                "message": "请先在「AI 模型配置」填写 Base URL 与 API Key"}
    return await ai_client.list_models(cfg, refresh=bool(refresh),
                                       cache_get=..., cache_set=...)
```
- 缓存读写直接复用 `prefs` 同款模式：`get_db()` 读写 `app_settings.ai_models_cache`
- **API Key 只从服务端读取，绝不接收前端传入**（与 `/ai/test` 同策略）

#### 4.1.3 归一化规则
| 规则 | 说明 |
|---|---|
| 提取 | `data` 数组每项取 `id`（缺失跳过）、`owned_by`（缺失补 `""`） |
| 过滤 | id 含非对话关键词即剔除（见 `NON_CHAT_PATTERNS`） |
| 截断 | 过滤后 >500 条时取前 500，并附 `message` 提示"列表过长已截断" |
| 排序 | `owned_by` 升序 → `id` 升序；空 `owned_by` 排最后 |
| 去重 | 按 `id` 去重（部分网关重复上报） |

### 4.2 前端（`static/js/pages/settings.js`，仅改 AI 模型卡片区域）

#### 4.2.1 模型字段改造（原第 112 行 `aiModel` 输入框）
```
┌──────────────────────────────────────┬────────┐
│ 如 gpt-4o-mini / deepseek-chat  (可手填) │ ▼ 浏览 │
└──────────────────────────────────────┴────────┘
                     ▼ 点击「浏览」
        ┌──────────────────────────────┐
        │ 🔍 正在从上游获取模型…  (spinner) │   ← 加载态
        ├──────────────────────────────┤
        │ ✓ deepseek-chat               │ ← 当前值置顶高亮
        │   deepseek-reasoner  deepseek │ ← id + owned_by 副标
        │ …                             │
        └──────────────────────────────┘
```

#### 4.2.2 交互细则
1. **触发**：点「浏览」→ 若 `aiUrl`/`aiKey` 输入框有未保存改动先 `save()` → `api.get("/ai/models?refresh=0")`；面板内提供「刷新」小按钮调 `refresh=1`
2. **渲染**：面板用绝对定位浮层（自实现，基于 `ui.el`），含：加载态 / 错误态（红字 + 重试按钮）/ 列表态 / 空态四态；当前已保存 `ai_model` 若有匹配项置顶并打勾
3. **选择**：点击项 → 回填 `aiModel.value` → 触发既有 `save({ai_model})` → toast「已切换模型：xxx」→ 关闭面板
4. **键盘**：面板打开时 ↑/↓ 移动高亮、Enter 选中、Esc 关闭；输入框本身行为不变
5. **点击外部关闭**：`document` 一次性 click 监听
6. **自动拉取**（可选增强）：provider 预设切换导致 `ai_model` 被回填为空时，自动拉取一次（仅当 Key 已填）
7. **兜底渲染**：响应 `source="preset"` 时面板顶部加一行灰字提示；`ok=false` 且无可渲染列表时，错误态展示后端 `message`

#### 4.2.3 保持不变的约定
- 输入框永远可编辑（自定义模型、网关代理的内部模型名仍需手填）
- 既有 `change` 失焦保存逻辑不动
- 预设按钮、`providerHint`、`/ai/test` 测试连接全部保留

### 4.3 测试（新增 `tests/test_ai_models.py`，目标 ≥8 条用例）
| # | 用例 | 要点 |
|---|---|---|
| 1 | 成功归一化 | mock httpx 返回标准 `{"data":[...]}`，断言过滤/排序/去重/owned_by 补空 |
| 2 | 非对话模型过滤 | 注入含 embed/rerank/whisper 的列表，断言被剔除 |
| 3 | 超长截断 | 600 条 → 返回 500 且带截断提示 |
| 4 | 401 映射 | 断言 `code="auth"` 且**缓存未被清除** |
| 5 | 404 unsupported | 断言 `code="unsupported"` |
| 6 | 网络超时 | mock `httpx.TimeoutException`，断言 `code="network"` 与友好文案 |
| 7 | 缓存命中 | 第二次调用不发起请求（mock 计数断言）、`cached=true` |
| 8 | refresh=1 强制 | 缓存存在仍发起请求并覆盖 |
| 9 | base_url 变更失效 | 缓存中 base_url 不同 → 重新拉取 |
| 10 | 接口层 | 未配置 Key 时 `code="no_config"`；GET `/api/ai/models` 路由可达 |

- mock 手段：`monkeypatch` 替换 `app.ai_client.httpx.AsyncClient` 为假客户端（参考 `tests/test_skills.py` 的纯函数测试风格，不触网）
- 全部用例跑通后 `pytest -q` 应保持 **93 + N 全绿**

### 4.4 变更清单（Codex 执行清单）
| 文件 | 改动 |
|---|---|
| `app/ai_client.py` | 新增 `list_models()` + `NON_CHAT_PATTERNS` + `MODELS_TIMEOUT` |
| `app/features.py` | `build_router()` 内新增 `GET /models`；`import` 处引入 `list_models` |
| `app/db.py` | `DEFAULT_SETTINGS` 增加 `"ai_models_cache": ""` |
| `static/js/pages/settings.js` | 模型输入框改造 + 自实现下拉面板（新函数 `modelPicker()`，不污染全局） |
| `tests/test_ai_models.py` | 新增测试文件 |
| `app/version.py` | `1.6.1` → `1.7.0` |
| `docs/v1.7.0-development-notes.md` | 交付时由实现方按既有格式补写 |

**明确不做**：不改 `ui.js`、不改 `workbench*.js`、不改 `prompts.js`、不动 img 配置区、不动按任务路由区。

---

## 5. 里程碑与预估

| 阶段 | 任务 | 产出 | 预估 |
|---|---|---|---|
| M1 后端 | `ai_client.list_models` + `/api/ai/models` 路由 + 缓存 + 默认设置 | 接口可用 | 0.5 天 |
| M2 前端 | 模型输入框改造 + 下拉面板四态 + 键盘/降级交互 | 页面可用 | 1 天 |
| M3 测试验收 | ≥8 条 pytest + 真机联调（DeepSeek/Kimi 各实测一次拉取与选择）+ 打包走查 | 可发布 | 0.5 天 |

合计约 **2 天**。

---

## 6. 验收标准
1. 已配置 DeepSeek 或 Kimi Key 的情况下，设置页点击「浏览」3 秒内出现真实模型列表，点选即生效（再次打开设置页值已保存）
2. 列表中不包含 embedding/rerank/语音类模型；超过 500 条时截断并提示
3. 连续两次打开（24h 内、未切服务商）第二次不产生新的上游请求（缓存命中）
4. 切到 custom 或无 `/models` 的上游时，降级为静态预设列表并明确提示，输入框可正常手填
5. 清空 API Key 后点「浏览」提示先填写；401 Key 报错与 `/ai/test` 口径一致
6. `pytest -q` 全绿；`build_exe.py` 打包后真机复测通过

---

## 7. 风险与对策
| 风险 | 对策 |
|---|---|
| 部分网关 `/models` 需额外权限或非标准返回 | 归一化层做防御式解析（缺字段降级、非 JSON 报网络错误）；L2 静态兜底保证功能不中断 |
| OpenRouter 等聚合网关列表超千条 | 500 条截断 + 排序把主流服务商排前；后续如需可加搜索过滤（本版不做） |
| 缓存导致"上游已上新模型但看不到" | 面板内置「刷新」按钮；缓存 TTL 仅 24h |
| Key 安全风险 | Key 只从服务端 settings 读取；`/models` 响应本身不含敏感信息；不记录 Key 到日志 |
| 前端下拉自实现引入回归 | 改动集中在一个新函数 + 一处 DOM 替换；`workbench` 等消费方只读 `ai_model` 字符串，不受影响 |

---
*本计划书由 Kimi（OpenClaw 主会话）基于墨语 V1.6.1 现状代码编写，供 Codex 开发参考。与代码实现冲突时以本文档 §1.2 目标与 §6 验收标准为准。*
