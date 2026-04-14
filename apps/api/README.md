# apps/api

Servico FastAPI do SaaS NFS-e (API-01).

## Rodar local

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn api.main:app --reload
```

Endpoints:

- `GET /health`  -> `{"status": "ok"}`
- `GET /version` -> `{"version": "...", "commit": "..."}`

## Configuracao

Variaveis de ambiente (prefixo `API_`):

| Variavel          | Default        | Descricao                                   |
|-------------------|----------------|---------------------------------------------|
| `API_ENVIRONMENT` | `development`  | `development` / `staging` / `production`.   |
| `API_LOG_LEVEL`   | `INFO`         | Nivel do root logger.                        |
| `API_VERSION`     | `0.1.0`        | Sobrescreve versao reportada em `/version`.  |
| `API_GIT_COMMIT`  | `unknown`      | Commit SHA; injetado no build Docker.        |

`.env` na raiz do repo e lido automaticamente.

## Build Docker

```bash
docker build \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t nfse-api:dev \
  apps/api
docker run --rm -p 8000:8000 nfse-api:dev
curl http://localhost:8000/health
```
