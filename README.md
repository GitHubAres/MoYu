# 墨语 InkWright · 本地 AI 小说写作工作台

> 一支笔、一炉丹、一盏灯——部署在本地、数据不出机的 AI 长篇创作工作台。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Data](https://img.shields.io/badge/data-100%25%20本地-orange)

「墨语」面向网文作者与长篇创作者：从灵感整理、作品规划、正文创作、设定管理到作品导出的完整闭环。**全部数据存储在本地 SQLite**，AI 只是可控的创作助手——所有 AI 内容先预览、由你确认后才入库，绝不静默写入正文。

## ✨ 功能一览

| 模块 | 能力 |
|---|---|
| 📚 书架作品 | 作品管理、字数统计、继续写作、灵感便签 |
| ✍️ 写作工作台 | 三栏编辑器、自动保存、专注模式、查找替换、光标记忆、章节拖拽排序 |
| 🤖 AI 助手 | 续写/扩写/缩写/改写，流式生成可停止，多候选差异预览，采纳可撤销 |
| 🧭 故事大纲 | 树形大纲、章节映射、AI 剧构推演、从节点生成章节草稿 |
| 📖 万象谱 | 角色/地点/势力/物品/术语设定库，章节关联，全局检索 |
| 🕸️ 关系图谱 | 人物关系力导向图，缩放/平移/拖拽 |
| ⏳ 剧情时间线 | AI 从章节提取剧情事件，预览确认后入库 |
| 🏷️ 伏笔看板 | 埋设/待回收/已回收三栏，闭环率统计 |
| 🧪 炼丹炉 | 拆书蒸馏文风 · 资料融汇入库 · 四步开炉炼丹（框架→世界观→人物→大纲） |
| 🎨 丹青阁 | AI 生成作品封面/插图，图库管理，一键设封面 |
| 🕰️ 版本快照 | 自动/手动快照、双栏差异对比、一键恢复（恢复前自动留存） |
| ✅ 一致性检查 | AI 稽核设定矛盾，附原文引用，仅为建议不改动内容 |
| 📦 导入导出 | TXT/DOCX 智能拆章导入，全书/按卷/勾选导出，整库备份 |
| 🔍 全局搜索 | Ctrl+K 唤起，跨作品/章节/设定/大纲秒级检索 |

## 📸 界面预览

| 书架作品 | 写作工作台 |
|---|---|
| ![书架](docs/screenshots/01-bookshelf.png) | ![工作台](docs/screenshots/02-workbench.png) |

| 关系图谱 | 炼丹炉 |
|---|---|
| ![关系图谱](docs/screenshots/03-graph.png) | ![炼丹炉](docs/screenshots/04-alchemy.png) |

## 🚀 安装（Windows，无需任何环境）

1. 从 [Releases](../../releases) 下载 `墨语.exe`
2. 双击运行——自动启动本地服务并打开浏览器
3. 首次运行会在 exe 旁生成 `data/` 文件夹存放全部数据

> 重复双击不会再开实例，直接唤出页面。关闭：任务管理器结束「墨语.exe」。

## ⚙️ 配置 AI（二选一或都要）

**文字 AI（必需）**：系统设置 → AI 模型配置 → 选服务商自动填充，填入 API Key 即可。已预设 DeepSeek / Kimi / 智谱 GLM / 通义千问 / OpenAI，也支持任何 OpenAI 兼容接口。

**生图 AI（可选，丹青阁用）**：系统设置 → 生图接口，推荐 [SiliconFlow](https://platform.siliconflow.cn)（有免费额度），填 Key 即可生成封面插图。

## 📖 五分钟上手

1. **创建作品**：书架 → 新建长篇作品（或点「创建示例作品」体验演示数据）
2. **开始写作**：继续写作 → 进入工作台，输入自动保存，顶栏可见保存状态
3. **AI 续写**：右侧 AI 侧栏勾选上下文 → 选任务 → 生成 → 候选卡预览 → 采纳（可撤销）
4. **维护设定**：万象谱建角色/地点 → 写作时自动进入 AI 上下文
5. **导出成书**：导入导出 → 选范围与格式（TXT/DOCX）→ 生成下载

## 🛠️ 从源码运行

```bash
# 需要 Python 3.12+（推荐用 uv 管理）
pip install -r requirements.txt
python scripts/fetch_vendor.py   # 首次：本地化前端资源
python run.py                    # http://127.0.0.1:8321
```

开发/测试/打包：

```bash
pytest -q                    # 27 项 API 回归测试
python build_exe.py          # 打包单文件 exe（onefile）
python build_exe.py --onedir # 文件夹形态（启动更快）
```

## 🏗️ 技术栈

- **后端**：Python · FastAPI · SQLite（标准库驱动，零 ORM）
- **前端**：原生 JS 单页应用 + Tailwind CSS（全量本地化，断网可用）
- **AI**：OpenAI 兼容协议文字接口 + OpenAI Images 兼容生图接口
- **打包**：PyInstaller 单 exe，数据落盘 exe 旁 `data/`

## 🔒 隐私

- 数据 100% 存于本地 `data/moyu.db`，无任何遥测与上报
- API Key 仅存于本地数据库
- 备份 = 复制 `data/` 文件夹；迁移 = 拷贝整个文件夹

## 📄 许可

MIT License。界面设计基于 Stitch 生成的「Literary Minimalist Ink」设计稿。
