# 墨语 MoYu 生产环境部署指南 (VPS & 容器化)



> **发布版本**：v1.2.3  

> **适用架构**：Linux VPS（Ubuntu 20.04/22.04/24.04, Debian 11/12, CentOS 8/9 等）



---



## 1. 方案一：Docker 与 Docker Compose 一键部署（推荐）



该方案采用多阶段轻量镜像（基于 `python:3.11-slim`，镜像大小约 150MB），以非 root 用户安全运行，自动配置数据卷持久化与健康检查。



### 1.1 准备与克隆

```bash

git clone https://github.com/GitHubAres/MoYu.git /opt/moyu

cd /opt/moyu

```



### 1.2 启动容器

```bash

docker compose up -d --build

```



### 1.3 验证与运维

- 查看容器状态与健康检查：`docker compose ps`

- 查看实时日志：`docker compose logs -f`

- 数据持久化位置：Docker 命名数据卷 `moyu-data`（可映射至宿主机 `/opt/moyu/data`）

- 访问：浏览器打开 `http://<VPS_IP>:8321`



---



## 2. 方案二：传统裸机部署（Nginx 反向代理 + systemd 常驻守护）



适合无 Docker 环境或要求极致性能的原生 Linux 服务器。



### 2.1 环境配置与依赖安装

```bash

# 1. 准备运行目录与系统用户

sudo mkdir -p /var/www/moyu /var/lib/moyu/data

sudo chown -R www-data:www-data /var/www/moyu /var/lib/moyu/data



# 2. 部署代码并建立 Python 虚拟环境

cd /var/www/moyu

python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt

```



### 2.2 配置 systemd 守护服务

将仓库中的 `deploy/systemd/moyu.service` 复制到系统服务目录：

```bash

sudo cp deploy/systemd/moyu.service /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable --now moyu

sudo systemctl status moyu

```



### 2.3 配置 Nginx 反向代理

将仓库中的 `deploy/nginx/moyu.conf` 复制到 Nginx 配置目录：

```bash

sudo cp deploy/nginx/moyu.conf /etc/nginx/conf.d/moyu.conf

# 编辑 moyu.conf 替换 server_name

sudo nginx -t && sudo systemctl reload nginx

```

> **注意**：配置中已默认包含 `proxy_buffering off;`，这是保障 AI 润色与流式输出（SSE/Streaming）不卡顿的关键参数。



---



## 3. 环境变量与安全配置



墨语支持以下生产级环境变量覆盖：



| 环境变量 | 默认值 | 说明 |

|---|---|---|

| `HOST` | `127.0.0.1` | 监听地址（容器内设为 `0.0.0.0`，裸机 Nginx 反代设为 `127.0.0.1`） |

| `PORT` | `8321` | HTTP 服务监听端口 |

| `MOYU_DATA_DIR` | `<APP_DIR>/data` | 作品与配置数据库（`moyu.db`）存放目录 |

| `MOYU_DB` | `<DATA_DIR>/moyu.db` | 单独覆盖 SQLite 数据库文件绝对路径 |



---



## 4. 软件自动更新与持续维护 (Auto Update)



墨语自 **v1.4.0** 起内置了自动化版本检查与一键更新模块。针对两种生产部署形态，提供对应的维护机制：



### 4.1 方案一 (Docker)：Watchtower 容器全自动更新（推荐）



在容器化环境中，由于容器具备文件系统隔离性，墨语遵循工业标准实践，由宿主机侧 **Watchtower** 容器进行外部托管升级：



在 `docker-compose.yml` 中追加 watchtower 服务：

```yaml

services:

  moyu:

    # 你的 moyu 容器服务配置...

    image: ghcr.io/githubares/moyu:latest

    restart: unless-stopped



  watchtower:

    image: containrrr/watchtower:latest

    restart: unless-stopped

    volumes:

      - /var/run/docker.sock:/var/run/docker.sock

    environment:

      - WATCHTOWER_CLEANUP=true

      - WATCHTOWER_POLL_INTERVAL=86400  # 每 24 小时巡检一次新镜像

      - WATCHTOWER_INCLUDE_STOPPED=false

    command: moyu

```

- **工作机制**：Watchtower 自动拉取最新构建镜像，并优雅停止旧容器、原地启动新容器，挂载的数据卷 `moyu-data` 完全不受影响。



### 4.2 方案二 (systemd)：设置页应用内一键更新



对于通过 `git` + `systemd` 部署的原生 Linux 服务器：

1. 管理员登录后，进入「系统设置」→「软件更新」；

2. 点击「检查新版本」，若有更新将展示发布日志与「立即在 VPS 执行一键更新」按钮；

3. **数据备份保障**：点击一键更新后，后端会自动将当前数据库完整拷贝至 `data/backups/moyu_pre_update_<timestamp>.db`；

4. 随后自动在后台执行 `git pull`、`pip install -r requirements.txt`，并通过 `systemctl restart moyu` 平滑重启服务；

5. 前端实时轮询并展示更新进度条与状态。



> **免密重启权限配置（仅需一次）**：  

> 为允许 www-data 用户重启墨语服务，请在 VPS 执行 `sudo visudo` 添加一行：  

> `www-data ALL=(ALL) NOPASSWD: /bin/systemctl restart moyu`

