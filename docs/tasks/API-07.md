# API-07 — Criar execucao (enfileira no Redis)

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-05 + INFRA-05)
- **Depende de:** API-05, INFRA-05

## Objetivo

Endpoint que cria um registro `executions` e enfileira job para o
worker.

## Entregaveis

- `POST /executions`:
  - Body: `company_ids[]`, `period_start`, `period_end`, `dry_run`,
    `trigger` (manual por padrao).
  - Valida: empresas pertencem ao tenant, tem credencial valida.
  - Cria 1 `execution` por empresa com status `queued`.
  - Enfileira job `run_execution(execution_id)` no Redis.
- `GET /executions/{id}` retorna status e contadores.

## Definition of Done

- [ ] Request cria N execucoes e N jobs na fila Redis.
- [ ] Worker pode picar o job (integracao em API-13).
