# API-10 — Reprocess jobs

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-08)
- **Depende de:** API-08

## Objetivo

Permitir reprocessamento seletivo de itens falhos.

## Entregaveis

- `POST /reprocess` com body:
  - `scope`: `{ "execution_item_ids": [...] }` ou
    `{ "company_id": ..., "nsus": [...] }` ou
    `{ "company_id": ..., "period": {...}, "statuses": ["fail"] }`.
- Cria `reprocess_jobs` + 1+ executions filhas com `trigger=reprocess`.
- `GET /reprocess/{id}` mostra progresso.

## Definition of Done

- [ ] E2E: forca falha em 3 items, reprocessa 1, v2 atualiza status.
