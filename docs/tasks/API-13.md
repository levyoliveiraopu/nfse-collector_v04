# API-13 — Worker consumer (Redis -> worker-core E2E)

- **Trilha:** api
- **Tamanho:** L
- **Status:** blocked (aguarda API-07 + CORE-04 + CORE-05 + API-06)
- **Depende de:** API-07, CORE-04, CORE-05, API-06

## Objetivo

Servico `apps/worker/` que consome fila Redis e orquestra uma execucao
ponta-a-ponta.

## Entregaveis

- `apps/worker/` com:
  - `worker/main.py` (RQ worker).
  - Handler `run_execution(execution_id)`:
    1. Busca `executions` + `companies` + `company_credentials`.
    2. Decifra PFX (usa `api.crypto.decrypt` ou contrato equivalente).
    3. Chama `worker_core.fetch_nfse(...)` com callback.
    4. Callback persiste cada `execution_item` + upload XML S3.
    5. Atualiza `companies.last_nsu` no fim.
    6. Marca execucao como `success`/`partial`/`failed`.
    7. Cria `occurrences` para erros categorizados.
- Implementa `NsuSource` DB-backed.
- Healthz endpoint para Uptime Kuma.
- Dockerfile.

## Definition of Done

- [ ] E2E: POST /executions -> fila -> worker -> items no DB + XML no S3.
- [ ] Crash no meio do job: retry com idempotencia
  (nao duplica items via unique `(tenant_id, chave_nfse)`).
- [ ] Graceful shutdown (SIGTERM drena jobs em andamento ate 60s).
