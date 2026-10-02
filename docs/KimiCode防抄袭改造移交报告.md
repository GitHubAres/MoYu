> ⚠️ **历史存档提示**：本文档记录已于 2026-09-29 放弃的防抄袭方案，项目已全面回归纯 MIT 开源。保留本文档仅供历史考古与技术参考，其中“LICENSE 已换 AGPL”、“moyu-core 私有库”、“License Key 激活”、“PyArmor 混淆”等描述在当前仓库中已不再成立，相关代码及私钥均已彻底摘除销毁。



# 墨语 MoYu「防抄袭改造」工作移交报告



**移交日期：** 2026-09-29  

**移交人：** Kimi Code（当前会话 agent）  

**接收人：** 下一任开发协作者 / 项目负责人  

**对应任务书：** `moyu/docs/MoYu_防抄袭改造_开发任务书.md`



---



## 1. 项目概况



本次任务是对「墨语 MoYu」本地版进行防抄袭改造，核心目标：



1. 将商业增强能力从开源核心拆出，形成独立私有仓库 `moyu-core`；

2. 开源核心改用 AGPL-3.0 许可证；

3. 建立 License Key（Ed25519 签名）激活体系；

4. 打包加固（PyArmor + PyInstaller）；

5. 增加服务端激活验证与版本更新检查；

6. 完成 GitHub 仓库迁移与 Release 发布。



项目分为两个代码库：



| 代码库 | 路径 | 性质 | 远端仓库 |

|---|---|---|---|

| `moyu` | `D:/KimiCode工作区/moyu/` | 开源核心（AGPL-3.0） | 待新建 `GitHubAres/MoYu` |

| `moyu-core` | `D:/KimiCode工作区/moyu-core/` | 私有核心（商业闭源） | 已创建 `GitHubAres/moyu-core`（私有） |



---



## 2. 交付内容清单



本压缩包包含以下内容：



```

moyu-handover-20260929/

├── handover-report.md          # 本报告

├── PRD-墨语-AI小说写作工具-优化稿.md  # 产品需求文档

├── moyu/                         # 开源核心当前工作副本

│   ├── docs/MoYu_防抄袭改造_开发任务书.md

│   ├── docs/security_scan_report.md

│   ├── docs/InkOS对比与开发方向规划.md

│   ├── AGENTS.md

│   ├── README.md

│   ├── LICENSE

│   ├── app/                      # FastAPI 后端

│   ├── static/                   # 原生 JS 前端

│   ├── tests/                    # pytest 回归测试

│   ├── core_api/                 # 私有包抽象层 + 回退实现

│   ├── licensing/                # License Key 客户端逻辑

│   ├── build_exe.py              # PyArmor + PyInstaller 打包

│   └── ...

└── moyu-core/                    # 私有核心当前工作副本

    ├── src/moyu_core/            # 增强能力源码

    ├── server/app.py             # License/更新服务端

    ├── keygen.py                 # 密钥生成工具

    ├── verify.py                 # 验签逻辑

    └── pyproject.toml

```



> **注意：** 出于安全考虑，压缩包已排除 `.git`、`.venv`、`build`、`dist`、`.pytest_cache`、`__pycache__`、`data/`、`keys/`、`issued_keys.csv` 等大体积或敏感目录/文件。



---



## 3. 当前完成状态



| 阶段 | 任务 | 状态 | 备注 |

|---|---|---|---|

| 0 | 决策确认与执行计划 | ✅ 完成 | 已按任务书默认值执行（AGPL-3.0、Ed25519、1 天离线宽限等） |

| 1.0 | 全历史敏感信息扫描 | ✅ 完成 | 报告见 `moyu/docs/security_scan_report.md`，仅 2 处 tailwind.js 误报 |

| 1.1 | 创建私有仓库 `moyu-core` | ✅ 完成 | GitHub 私有仓库已创建，core-v0.1.0 已提交 |

| 1.2 | 开源侧抽象层改造 | ✅ 完成 | `core_api/` 完成，无私有包时自动回退 |

| 1.3 | 许可证与声明更换 | ✅ 完成 | `moyu/LICENSE` 已换 AGPL-3.0；39 个 `.py` 文件已加版权头 |

| 2 | License Key 激活体系 | ✅ 完成 | Ed25519 密钥对、`licensing/manager.py`、API 路由、服务端接口、启动校验 |

| 3 | 打包发布加固 | ✅ 完成 | PyArmor + PyInstaller；`--onedir` 构建验证通过 |

| 4 | 服务端与更新检查 | ⚠️ 部分完成 | `app/api/update.py` 已创建，**尚未注册到 `app/api/__init__.py`**；前端「检查更新」按钮未添加 |

| 5 | GitHub 发布操作 | ⏸️ 待执行 | 需用户确认或网络恢复后执行 |



---



## 4. 关键实现说明



### 4.1 License Key 体系



- **算法：** Ed25519 非对称签名。

- **公钥：** 内嵌在 `moyu/licensing/public_key.py`（raw base64）。

- **私钥：** 仅存于 `moyu-core/keys/license_private.pem`，**未进入任何 git 仓库**。

- **客户端：** `moyu/licensing/manager.py` 负责激活、离线验签、离线宽限判断、解绑。

- **服务端：** `moyu-core/server/app.py` 提供 `/v1/license/verify` 与 `/v1/update/check`。

- **API 路由：** `moyu/app/api/license.py` 暴露 `/api/license/status`、`/api/license/activate`、`/api/license/deactivate`。

- **启动校验：** `moyu/app/main.py` 启动时异步联网校验，失败不阻塞基础功能。

- **能力开关：** `moyu/core_api/loader.py` 仅在许可证有效时启用 `moyu-core` 增强能力。



### 4.2 开源 / 私有边界



- 基础功能（作品管理、章节、版本、笔记、导出等）完全在 `moyu` 中实现，无需私有包即可运行。

- 增强功能（AI 编排核心、提示词库、炼丹炉、文风档案、连续性审计等）在 `moyu-core` 中。

- `moyu` 通过 `core_api/` 调用 `moyu-core`，导入失败时自动使用基础回退实现。



### 4.3 打包



- `moyu/build_exe.py` 已改为先 PyArmor 混淆、再 PyInstaller 打包。

- 验证命令：

  ```bash

  cd moyu

  python build_exe.py --onedir

  ```

- 产物位于 `moyu/dist/MoYu-v1.1.0-win64/`，包含 `manifest.json` 与 `.sha256` 校验文件。



---



## 5. 验证记录



| 验证项 | 命令 | 结果 |

|---|---|---|

| 开源核心回归测试 | `cd moyu && .venv/Scripts/python.exe -m pytest -q` | **27 passed** |

| License 全链路本地测试 | 服务端 `/v1/license/verify` → 客户端 `activate_license()` → `verify_license()` | active，通过 |

| PyArmor 打包构建 | `python build_exe.py --onedir` | 构建成功 |

| 无私有包独立运行 | 移除 `moyu-core` 后启动 `moyu` | 基础功能正常 |



---



## 6. 待处理问题



### 6.1 必须立即处理



1. **注册更新路由**  

   `moyu/app/api/update.py` 已创建，但**未在 `moyu/app/api/__init__.py` 中注册**。需要添加以下两行：

   ```python

   from app.api import update

   app.include_router(update.router, prefix="/api/update", tags=["update"])

   ```



2. **前端「检查更新」按钮**  

   `moyu/static/js/pages/settings.js` 中许可证/关于区域需要添加「检查更新」按钮，调用 `/api/update/check`。



3. **跑测试**  

   完成上述改动后执行 `pytest -q`，确保 27 项测试全绿。



### 6.2 阶段 5：GitHub 发布



- **老仓库归档：** 在 `GitHubAres/MoYu` 打 tag `v1.0-final-mit`，README 加迁移公告。

- **新仓库发布：** 新建公开仓库 `GitHubAres/MoYu`，推送 v1.1.0 代码。

- **私有仓库推送：** `moyu-core` 最近两次 push 因网络失败（`Recv failure: Connection was reset` / `Could not connect to server`），本地提交已保存，需重试 push。

- **Release 创建：** 在 `MoYu` 仓库创建 Release `v1.1.0`，上传构建产物与 `manifest.json`。



> 阶段 5 需要 GitHub 网络通畅，且涉及公开仓库命名与发布，建议由项目负责人最终确认后执行。



---



## 7. 已知问题



1. **网络问题：** `moyu-core` 向 GitHub 的 push 当前不稳定，需在网络恢复后重试。

2. **Git 换行符警告：** Windows 环境下 Git 提示 LF 将被替换为 CRLF，不影响功能。

3. **前端更新按钮缺失：** 阶段 4 的前端部分尚未完成。

4. **PyInstaller 6 已移除 `--key` 加密：** 已改用 PyArmor 完成混淆打包，符合任务书要求。



---



## 8. 环境要求



### 8.1 开源核心 `moyu`



```bash

cd moyu

python -m venv .venv

.venv/Scripts/pip install -r requirements.txt

python scripts/fetch_vendor.py   # 需联网

python run.py                    # http://127.0.0.1:8321

pytest -q

```



### 8.2 私有核心 `moyu-core`



```bash

cd moyu-core

python -m venv .venv

.venv/Scripts/pip install -e .

.venv/Scripts/uvicorn server.app:app --host 127.0.0.1 --port 8322

```



### 8.3 打包



```bash

cd moyu

python build_exe.py --onedir

```



---



## 9. 安全与操作边界



1. **绝不提交私钥：** `moyu-core/keys/` 与 `issued_keys.csv` 已在 `.gitignore` 中排除。

2. **绝不提交用户数据：** `moyu/data/` 已在 `.gitignore` 中排除。

3. **激活失败不阻塞基础功能：** 这是铁律，任何改动不得破坏。

4. **公开仓库必须能在无私有包环境下独立构建、运行、测试全绿。**



---



## 10. 下一步行动建议



1. 完成阶段 4 剩余工作（注册路由、前端按钮、测试）。

2. 确认 `moyu/` 工作区所有改动已 add/commit/push。

3. 等待网络恢复，重试 `moyu-core` push。

4. 执行阶段 5 GitHub 发布操作。

5. 更新 `AGENTS.md` 与任务书状态（如有需要）。



---







---



**报告结束。** 如有疑问，请优先查阅任务书与 `AGENTS.md`，再查看具体代码文件。

