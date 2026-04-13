# DATA-06 — Teste automatizado de isolamento cross-tenant

- **Trilha:** data
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-01..05)
- **Depende de:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05

## Objetivo

Garantir que RLS impede vazamento de dados entre tenants, mesmo em bug
de aplicacao.

## Entregaveis

- Fixture pytest que cria 2 tenants, 2 users (um em cada), dados em
  cada tabela com tenant_id.
- Teste para cada tabela com RLS: ao setar `app.current_tenant` do
  tenant A, queries via role `app_user` retornam **0 rows** do tenant B.
- Teste negativo: sem setar o GUC, role `app_user` recebe **0 rows**
  (fail closed).
- CI roda este teste em cada PR.

## Definition of Done

- [ ] Teste verde localmente.
- [ ] Teste incluido no workflow de CI.
- [ ] Falha injetada (remover uma politica) faz o teste quebrar.
