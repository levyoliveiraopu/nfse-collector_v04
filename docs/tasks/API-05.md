# API-05 — CRUD /companies

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-03 + DATA-02)
- **Depende de:** API-03, DATA-02

## Objetivo

Endpoints para gerenciar CNPJs do tenant.

## Entregaveis

- `GET /companies` (paginado, filtros: status, uf).
- `GET /companies/{id}`.
- `POST /companies` (valida CNPJ com digito verificador).
- `PATCH /companies/{id}`.
- `DELETE /companies/{id}` (soft delete).
- OpenAPI documentado.

## Definition of Done

- [ ] OpenAPI visivel em `/docs`.
- [ ] Testes: CRUD completo, cross-tenant bloqueado.
- [ ] Limite de plano aplicado (bloqueia criacao acima do cap).
