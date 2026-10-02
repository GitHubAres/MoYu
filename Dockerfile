# ==============================================================================
# 墨语 MoYu 生产级轻量容器构建 (Python 3.11-slim)
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产运行阶段
FROM python:3.11-slim AS runner

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/moyu/.local/bin:$PATH" \
    HOST="0.0.0.0" \
    PORT="8321" \
    MOYU_DATA_DIR="/app/data"

# 创建非 root 运行用户
RUN useradd -m -u 1000 moyu && \
    mkdir -p /app/data && \
    chown -R moyu:moyu /app

# 从构建层拷贝已安装的 python 包
COPY --from=builder --chown=moyu:moyu /root/.local /home/moyu/.local

# 拷贝项目应用资产
COPY --chown=moyu:moyu app/ ./app/
COPY --chown=moyu:moyu static/ ./static/
COPY --chown=moyu:moyu run.py ./

USER moyu

# 声明持久化数据卷与对外端口
VOLUME ["/app/data"]
EXPOSE 8321

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8321/api/health')" || exit 1

CMD ["python", "run.py"]