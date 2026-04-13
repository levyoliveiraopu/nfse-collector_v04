# API-01 — Bootstrap FastAPI + pydantic settings + healthcheck

- **Trilha:** api
- **Tamanho:** S
- **Status:** ready (apos GOV-01)
- **Depende de:** GOV-01

## Objetivo

Subir um servico FastAPI minimo com configuracao por env, logging
estruturado e endpoints `/health` + `/version`.

## Entregaveis

- `apps/api/` com:
  - `pyproject.toml`.
  - `api/main.py` (FastAPI app).
  - `api/config.py` (pydantic-settings).
  - `api/logging.py` (JSON structured logs).
  - Dockerfile multi-stage.
- Endpoints:
  - `GET /health` -> `{status: "ok"}`
  - `GET /version` -> `{version, commit}`

## Definition of Done

- [ ] `uvicorn api.main:app --reload` sobe.
- [ ] `curl localhost:8000/health` retorna 200.
- [ ] Container builda e roda.
