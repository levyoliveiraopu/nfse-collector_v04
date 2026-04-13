# API-09 — Occurrences CRUD + acknowledge/resolve

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-04)
- **Depende de:** DATA-04

## Objetivo

Endpoints para inbox de ocorrencias operacionais.

## Entregaveis

- `GET /occurrences` (filtros: status, severity, empresa).
- `GET /occurrences/{id}`.
- `POST /occurrences/{id}/acknowledge`.
- `POST /occurrences/{id}/resolve` (nota obrigatoria).
- `POST /occurrences/{id}/assign` (user_id).
- Codigos de ocorrencia documentados em
  `docs/architecture/occurrence-codes.md` (ex: `CERT_EXPIRED`,
  `PORTAL_5XX`, `RATE_LIMIT`, `CRED_INVALID`).

## Definition of Done

- [ ] Testes cobrem transicoes de status.
- [ ] Audit log registra cada acao.
