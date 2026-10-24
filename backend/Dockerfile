# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.5-python3.12-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Bake the embedding model at a pinned revision (own layer, before the code copy)
ARG BGE_REVISION=5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
ENV MODEL_DIR=/opt/models/bge-small-en-v1.5
RUN HF_HOME=/tmp/hf HF_HUB_DISABLE_TELEMETRY=1 /app/.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-small-en-v1.5', revision='${BGE_REVISION}', local_dir='${MODEL_DIR}', ignore_patterns=['onnx/*', 'pytorch_model.bin', '*.md', '.gitattributes'])" \
 && rm -rf /tmp/hf ${MODEL_DIR}/.cache \
 && HF_HUB_OFFLINE=1 /app/.venv/bin/python -c "from sentence_transformers import SentenceTransformer as S; v = S('${MODEL_DIR}', device='cpu').encode(['smoke']); assert v.shape == (1, 384), v.shape"

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

FROM python:3.12-slim-trixie
RUN groupadd --system --gid 10001 app \
 && useradd --system --gid 10001 --uid 10001 --create-home app \
 && mkdir -p /app/data && chown app:app /app/data
COPY --from=builder --chown=app:app /app /app
COPY --from=builder --chown=app:app /opt/models /opt/models
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    EMBEDDING_MODEL_PATH=/opt/models/bge-small-en-v1.5 DATA_DIR=/app/data \
    OMP_NUM_THREADS=2 WEB_CONCURRENCY=1
USER app
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=12 \
  CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0 if r.status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--forwarded-allow-ips", "*"]
