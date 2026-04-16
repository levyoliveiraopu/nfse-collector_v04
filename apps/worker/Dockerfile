# syntax=docker/dockerfile:1.7

# ------------------------------------------------------------------------------
# Stage 1: builder — resolve dependencias (worker-core + apps/worker) e gera wheels.
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Copia o pacote worker-core primeiro para que o wheel build do worker
# consiga satisfazer a dep "worker-core" via --find-links.
COPY packages/worker-core /build/packages/worker-core
COPY apps/worker /build/apps/worker

RUN pip install --upgrade pip build && \
    pip wheel --wheel-dir /wheels ./packages/worker-core && \
    pip wheel --wheel-dir /wheels --find-links /wheels ./apps/worker

# ------------------------------------------------------------------------------
# Stage 2: runtime — imagem final minima, usuario nao-root.
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ARG GIT_COMMIT=unknown
ENV WORKER_GIT_COMMIT=${GIT_COMMIT} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 1002 worker && \
    useradd --system --uid 1002 --gid worker --home /app --shell /usr/sbin/nologin worker

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels nfse-worker && \
    rm -rf /wheels

USER worker

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status == 200 else 1)"

# Graceful shutdown: Docker envia SIGTERM; RQ drena o job atual. Combinar
# com `stop_grace_period: 60s` no compose (ver docs/tasks/API-13.md).
STOPSIGNAL SIGTERM

CMD ["python", "-m", "worker.main"]
