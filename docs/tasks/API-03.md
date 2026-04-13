# API-03 — Middleware de tenant (GUC para RLS)

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-02 + DATA-01)
- **Depende de:** API-02, DATA-01

## Objetivo

Garantir que toda request autenticada execute com `app.current_tenant`
setado na conexao Postgres, ativando as politicas RLS.

## Entregaveis

- Middleware FastAPI que:
  - Extrai `tenant_id` do JWT.
  - Em cada request, executa `SET LOCAL app.current_tenant = :id`
    no inicio da transacao.
- Dependency `get_db_session()` que garante o SET.
- Request sem token ou sem tenant: 401.
- Tenant invalido (inexistente/suspenso): 403.

## Definition of Done

- [ ] Teste de integracao: user do tenant A nao acessa dados do B.
- [ ] Conexao devolvida ao pool sem "vazar" GUC (SET LOCAL ok).
