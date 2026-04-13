# API-11 — Files: listar + gerar URL pre-assinada

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-05 + INFRA-06)
- **Depende de:** DATA-05, INFRA-06

## Objetivo

Endpoints para listar arquivos gerados e baixa-los com URL pre-assinada.

## Entregaveis

- `GET /files` (filtros: kind, company, periodo).
- `GET /files/{id}/url` -> retorna URL pre-assinada (expira em 1h).
- Audit log de geracao de URL.

## Definition of Done

- [ ] URL funciona no navegador e expira.
- [ ] Tentativa cross-tenant retorna 404.
