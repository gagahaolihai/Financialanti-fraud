# ============================================
# 反诈卫士 - 多阶段构建 Dockerfile
# Anti-Fraud Intelligent Dialogue System
# ============================================

# ---- 构建阶段 ----
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /deps

# ---- 运行阶段 ----
FROM python:3.11-slim

LABEL maintainer="antifraud-team"
LABEL description="多模态智能反诈对话系统"

# 安装系统依赖（TLS证书、时区）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 创建非root用户
RUN groupadd -g 1001 antifraud && \
    useradd -u 1001 -g antifraud -s /bin/bash -m antifraud

WORKDIR /app

# 复制依赖
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p data logs && \
    chown -R antifraud:antifraud /app

# 切换到非root用户
USER antifraud

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# 暴露端口
EXPOSE 5000

# 启动命令（使用gunicorn生产级WSGI）
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", \
     "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", \
     "--worker-class", "gthread", "app:app"]
