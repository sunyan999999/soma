# SOMA — Somatic Wisdom Architecture Docker Image
# 一键启动：docker compose up -d

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="SOMA"
LABEL org.opencontainers.image.description="智慧超越记忆 — 为AI Agent构建的框架优先式认知架构"
LABEL org.opencontainers.image.url="https://github.com/sunyan999999/soma"

# 系统依赖：libgomp1 为 ONNX/fastembed 所需
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 层缓存）
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "networkx>=3.0" \
        "litellm>=1.0.0" \
        "pydantic>=2.0" \
        "pyyaml>=6.0" \
        "numpy>=1.24" \
        "jieba>=0.42" \
        "scikit-learn>=1.3.0" \
        "fastembed>=0.4.0" \
        "faiss-cpu>=1.8.0" \
        "uvicorn[standard]>=0.30" \
        "fastapi>=0.115" \
    && pip cache purge

# 复制源码
COPY soma/ ./soma/
COPY dash/ ./dash/
COPY soma_data/ ./soma_data/
COPY wisdom_laws.yaml ./
COPY soma/wisdom_laws.yaml ./soma/

# 预热 fastembed ONNX 模型（避免首次调用超时）
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-zh-v1.5')" 2>/dev/null || true

ENV SOMA_PROD=1
ENV SOMA_DATA_DIR=/app/soma_data

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

CMD ["python", "-u", "dash/server.py"]
