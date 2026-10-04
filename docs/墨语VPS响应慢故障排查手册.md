# 墨语（MoYu）VPS 部署响应慢 · 故障排查手册

> 适用对象：交给 Codex（或人工 SSH）在 VPS 上按阶段执行。
> 目标：在 30 分钟内定位"慢在哪一层"，输出结论报告，而不是盲目改配置。
> 前置：SSH 能登录 VPS；墨语以 Docker（推荐方案，容器名 `moyu`）或 systemd（服务名 `moyu`）运行。

---

## 阶段 0：先把"慢"说清楚（1 分钟）

不同的"慢"对应完全不同的病因，先确认现象（让用户描述或亲自复现）：

| 现象 | 大概率层 |
|---|---|
| 打开页面转圈很久，但打开后操作流畅 | 静态资源 / 网络链路 |
| 每个 API 请求都慢（列表、保存都要等） | 应用 / 数据库 / 反代 |
| AI 生成等待久、点了没反应 | 上游大模型 API / 生成队列 |
| 人多的时候才慢，一个人用不慢 | 单 worker 阻塞 / 带宽 / 连接数 |
| 慢的同时 VPS 风扇狂转或负载飙升 | 资源耗尽（CPU/内存/磁盘 IO） |

**配套动作**：让用户在浏览器 F12 → Network 里截一张请求的瀑布图（重点看 TTFB 还是 Content Download 占时间），这能省掉一半排查。

---

## 阶段 1：服务与资源快照（2 分钟，先排除"机器不行了"）

```bash
# 负载与运行时间（load average 超过 CPU 核数说明排队严重）
uptime

# 内存：看 free 列（可用内存）；swap 大量使用 = 内存不足在换页
free -h

# 磁盘：墨语数据盘是否写满（SQLite 写满会直接卡死写入）
df -h

# CPU/IO 瞬时采样（按 1，看 us/sy/wa；wa 高 = 磁盘慢）
top -b -n 1 | head -20

# 是否被 OOM Killer 杀过（dmesg 里有 Out of memory 记录 = 内存不够）
sudo dmesg -T | grep -iE "oom|killed process" | tail -20

# Docker 部署：容器状态 + 资源占用
docker ps -a
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# systemd 部署：服务状态
systemctl status moyu --no-pager -l
```

**判读**：
- 磁盘 100% → 直接转「阶段 6 收尾」，清日志/旧备份。
- 容器 CPU 长期 >80% 或内存逼近 limit → 资源不足，转阶段 4 查谁在吃资源。
- dmesg 有 OOM → 加内存或降 worker 数，属于容量问题。

---

## 阶段 2：分层计时定位（5 分钟，核心步骤）

墨语链路：**浏览器 → 反向代理(Caddy/nginx) → uvicorn(FastAPI) → SQLite**。
逐层绕过，用同一条 curl 在三个位置测，比较耗时：

```bash
# 取三个关键 URL 备用（把域名换成实际值）
URL_PUBLIC="https://你的域名"
IP=127.0.0.1   # 本机测试

# ---- A. 本机直连 uvicorn（绕过反代和网络）----
# Docker：先确认映射端口
docker port moyu        # 常见为 8000
curl -o /dev/null -s -w "静态 /        DNS:%{time_namelookup}s TCP:%{time_connect}s TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" http://$IP:8000/
curl -o /dev/null -s -w "健康 /health   DNS:%{time_namelookup}s TCP:%{time_connect}s TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" http://$IP:8000/api/health
curl -o /dev/null -s -w "数据 /works    DNS:%{time_namelookup}s TCP:%{time_connect}s TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" http://$IP:8000/api/works

# ---- B. 本机经反代 ----
curl -o /dev/null -sk -w "经反代静态    TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" $URL_PUBLIC/
curl -o /dev/null -sk -w "经反代health  TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" $URL_PUBLIC/api/health

# ---- C. 从你自己的电脑访问（绕过一切，含公网链路）----
# 在你本地电脑执行同样的两条 curl（Windows 用 curl.exe 一样）
```

**判读矩阵**：

| A 慢 | 瓶颈在应用本身（uvicorn/SQLite）→ 阶段 3 |
|---|---|
| A 快、B 慢 | 瓶颈在反代（Caddy/nginx 配置、TLS、压缩）→ 阶段 3.5 |
| A、B 都快、C 慢 | 瓶颈在公网链路（VPS 带宽、跨境丢包）→ 阶段 5 |
| 三者都快但用户喊慢 | 现象不可复现，查时段性因素（定时任务、备份、别人在打满带宽）→ 阶段 4/5 |

> 注意：`/api/health` 不查库，`/api/works` 查库。如果 health 快而 works 慢，就是 SQLite/磁盘问题。

---

## 阶段 3：应用层深挖（10 分钟）

### 3.1 应用日志找异常

```bash
# Docker
docker logs moyu --tail 300 2>&1 | less
docker logs moyu --since 24h 2>&1 | grep -iE "error|timeout|busy|lock|exception" | tail -50

# systemd
journalctl -u moyu --since today --no-pager | grep -iE "error|timeout|busy|lock|exception" | tail -50
```

**重点搜**：`database is locked`（SQLite 锁竞争）、`Timeout`（上游 API 超时）、大量重复请求日志（前端轮询风暴）。

### 3.2 SQLite 专项（墨语是单文件 SQLite，高并发写的头号嫌疑人）

```bash
# 找到数据库文件（容器内默认 /app/data/moyu.db，或看 MOYU_DATA_DIR）
docker exec moyu ls -lh /app/data/
# 主机挂载的话直接用主机路径，例如：
ls -lh /opt/moyu/data/moyu.db*

# 库是否暴涨（正常写作库是 MB 级；GB 级说明存了大字段或该清理版本历史）
# 锁模式确认（WAL 对并发友好；DELETE/ROLLBACK 模式并发写容易互相卡）
docker exec moyu python -c "
import sqlite3, glob
for f in glob.glob('/app/data/*.db'):
    con = sqlite3.connect(f)
    print(f, con.execute('PRAGMA journal_mode;').fetchone(), con.execute('PRAGMA page_count;').fetchone())
    con.close()
"

# 慢磁盘检测：连续写测试（<50MB/s 的云盘跑 SQLite 会比较吃力）
dd if=/dev/zero of=/opt/moyu/data/.iotest bs=1M count=200 oflag=direct 2>&1 | tail -1
rm -f /opt/moyu/data/.iotest
```

**判读**：`database is locked` 日志 + DELETE 模式 → 并发写冲突；库文件 GB 级 → 数据膨胀；dd 写出速度 <20MB/s → 磁盘 IO 是硬伤。

### 3.3 单 worker 阻塞（AI 生成是流式长连接，默认 1 个 worker 时会被生成请求占满）

```bash
# 确认 worker 数
docker exec moyu ps aux | grep -c "[u]vicorn"
# systemd: grep workers /etc/systemd/system/moyu.service 或启动命令

# 看正在处理的连接（ESTABLISHED 很多且长时间存在 = 长连接占着 worker）
ss -tnp | grep :8000
```

**判读**：worker=1 且有人在生成 → 其他所有请求排队（表现为"点了没反应"）。这是部署模式问题，不是 bug。修复见收尾对照表。

### 3.4 上游大模型 API 延迟（生成慢的独立验证）

```bash
# 直接在 VPS 上测上游 API 的响应速度（用墨语配置的同一家服务商）
curl -o /dev/null -s -w "上游 API TTFB:%{time_starttransfer}s 总计:%{time_total}s\n" \
  -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'

# 墨语侧看最近的生成任务耗时（需要进容器执行）
docker exec moyu python -c "
import sqlite3
con = sqlite3.connect('/app/data/moyu.db')
try:
    for r in con.execute(\"SELECT id, mode, status, created_at, substr(prompt,1,20) FROM gen_tasks ORDER BY id DESC LIMIT 10\"):
        print(r)
except Exception as e:
    print('表结构不同：', e)
"
```

**判读**：上游 TTFB >3s 或总计 >10s → 生成慢是上游问题（换服务商/节点，或检查 VPS 到该 API 的连通质量，跨境常见）；任务表里 status 长期 pending → 队列积压（并发限制 max_concurrent 默认 2）。

### 3.5 反代层（只有阶段 2 判定 B 慢才查）

```bash
# Caddy（Docker 部署默认）：日志位置
docker logs caddy --tail 100 2>&1 | tail -50    # 若有单独 caddy 容器
# nginx（手动部署）：确认日志格式带耗时字段
grep -E "request_time|upstream_response_time" /var/log/nginx/access.log | tail -5
# 若日志格式没带耗时，临时在 log_format 加 $request_time $upstream_response_time 后 reload
```

---

## 阶段 4：谁在吃资源 / 时段性因素（3 分钟）

```bash
# 带宽瞬时占用（跑 5 秒，Ctrl+C 退出；TX 飙满 = 有人在大量下载/备份）
sudo iftop -t -s 5 2>/dev/null || sudo nethogs -t -c 5

# 连接数统计
ss -s
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn | head

# 有没有定时任务在整点搞事（备份、日志切割、爬数据的 cron）
crontab -l; sudo crontab -l; ls /etc/cron.d/

# Docker 日志是否撑爆（json-file 驱动默认无轮转，能写满盘）
docker system df
du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -rh | head -5
```

**判读**：`-json.log` 单个文件几 GB → 加 log-opts 轮转并清旧日志；整点必慢 → 对上了 cron 时间窗。

---

## 阶段 5：公网链路（只有阶段 2 判定 C 慢才查）

在你本地电脑执行：

```bash
# 到 VPS 的延迟与丢包（跨境链路晚高峰丢包 5%+ 就会明显感觉慢）
ping -n 20 <VPS_IP>
# 有 mtr 更好：mtr -n -c 30 <VPS_IP>

# VPS 出口带宽测试（在 VPS 上跑）
curl -o /dev/null -s -w "下载测速 %{speed_download} B/s\n" https://speed.hetzner.de/100MB.bin
```

**判读**：ping 丢包高/抖动大 → 链路质量差（换线路/加 CDN/上 Anycast）；VPS 出口跑不满标称带宽 → 商家限速或共享口被打满，考虑升级套餐。

---

## 阶段 6：收尾——结论对照表与修复建议

把各阶段结果填进这个表，得出唯一结论：

| 阶段 | 观察到的证据 | 结论 |
|---|---|---|
| 1 资源 | | |
| 2 分层计时 | A: __s / B: __s / C: __s | |
| 3.1 日志 | | |
| 3.2 SQLite | | |
| 3.3 worker | | |
| 3.4 上游 | | |
| 4/5 网络 | | |

### 常见病因 → 修复映射

| 病因 | 修复 |
|---|---|
| 单 worker 被生成请求阻塞 | docker-compose 里 `MOYU_WORKERS: 2`（内存够可到 4），重建容器；注意 SQLite 并发写能力有限，worker 太多适得其反，2-4 为宜 |
| SQLite `database is locked` | 确认 WAL 模式已启用；避免多进程共享同一 db 文件；高峰期减少批量导入 |
| 库文件过大 | 清理版本历史/回收站（应用内有"清理旧版本"），必要时导出重建库 |
| 上游 API 慢（跨境） | 换国内可直连的服务商（DeepSeek/通义/Kimi），或在 VPS 同区域做 API 转发 |
| 反代无压缩/无缓存 | Caddy 默认开 gzip；静态文件加 Cache-Control（墨语静态资源带 hash，可长缓存） |
| Docker json 日志撑爆磁盘 | compose 加 `logging: {driver: json-file, options: {max-size: "10m", max-file: "3"}}`，truncate 旧日志 |
| 带宽打满 | 限制单用户下载速度；大文件走对象存储+CDN |
| 内存不足/OOM | 升配，或减 worker；确认没有内存泄漏（连续观察 RSS 是否只涨不跌，只涨不跌 → 报 bug 给上游） |

### 输出报告模板（交给用户的最终结论）

```
排查时间：YYYY-MM-DD HH:MM（时区）
现象复现：【可复现/不可复现】，慢在【首屏/API/生成】，平均耗时 __s
逐层计时：直连 __s / 反代 __s / 公网 __s
资源水位：CPU __%、内存 __/__G、磁盘 __%、load __
日志异常：【无 / database is locked / timeout ×N / OOM】
根因结论：【一句话】
建议动作：【一条最优先的修复 + 是否需要扩容】
```

---

## 附：给 Codex 的执行纪律

1. **只读优先**：本手册所有命令均为只读/无侵入（唯一的写入是 dd 到数据目录的临时文件，已包含删除步骤）。**不要**在未出报告前改任何配置、重启服务或清数据。
2. **一次一变**：确认修复方案后再动手，一次只改一处，改前 `docker compose config > /root/moyu-config-backup-$(date +%F).yml` 留底。
3. **证据不足就补测**：哪一层数据矛盾，回到阶段 2 重新计时，不要猜。
4. 完成后把「输出报告模板」填好发回。
