# API-08 — Listar/detalhar executions + execution_items

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-07 + DATA-03)
- **Depende de:** API-07, DATA-03

## Objetivo

Endpoints para acompanhar execucoes e itens processados.

## Entregaveis

- `GET /executions` (paginado, filtros: empresa, periodo, status).
- `GET /executions/{id}` (detalhe + contadores agregados).
- `GET /executions/{id}/items` (paginado, filtros: status, nsu).
- `GET /companies/{id}/executions` (atalho).

## Definition of Done

- [ ] OpenAPI ok.
- [ ] Paginacao server-side funciona em 10k items.
- [ ] Query valida com `EXPLAIN` (usa indice).
