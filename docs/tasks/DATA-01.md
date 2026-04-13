# DATA-01 — Schema inicial: tenants, users, tenant_users (+ RLS)

- **Trilha:** data
- **Tamanho:** M
- **Status:** ready (apos API-01)
- **Depende de:** API-01 (app FastAPI inicializado para hospedar Alembic)

## Objetivo

Criar as tabelas base de identidade e a infraestrutura de Row Level
Security.

## Entregaveis

- Alembic configurado em `apps/api/alembic/`.
- Migration `0001_initial_identity.py`:
  - Extensao `pgcrypto` para `gen_random_uuid()`.
  - Role `app_user` (sem BYPASSRLS) e `app_admin` (para migrations).
  - Tabela `tenants` (id, name, slug unico, plan_id, status,
    trial_ends_at, billing_email, timestamps).
  - Tabela `users` (id, email unico, password_hash, name, phone,
    mfa_secret, last_login_at, status, timestamps).
  - Tabela `tenant_users` (tenant_id, user_id, role,
    invited_at, accepted_at).
  - RLS habilitada em `tenants` e `tenant_users`.
  - Politicas RLS usando GUC `app.current_tenant`.
- Indices conforme PARTE D do plano.

## Definition of Done

- [ ] `alembic upgrade head` limpo.
- [ ] `alembic downgrade -1` reverte.
- [ ] Teste manual (psql) cria tenant + user + associacao.
- [ ] Teste de RLS: sessao com `SET app.current_tenant` diferente
  nao ve dados do outro.
