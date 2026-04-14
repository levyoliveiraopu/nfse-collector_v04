# syntax=docker/dockerfile:1.7

# ------------------------------------------------------------------------------
# Stage 1: builder — resolve dependencias e gera wheels.
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY pyproject.toml ./
COPY api ./api

RUN pip install --upgrade pip build && \
    pip wheel --wheel-dir /wheels .

# ------------------------------------------------------------------------------
# Stage 2: runtime — imagem final minima, usuario nao-root.
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ARG GIT_COMMIT=unknown
ENV API_GIT_COMMIT=${GIT_COMMIT} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 1001 api && \
    useradd --system --uid 1001 --gid api --home /app --shell /usr/sbin/nologin api

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels nfse-api && \
    rm -rf /wheels

USER api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
