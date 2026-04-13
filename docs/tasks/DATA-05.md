# DATA-05 — Schema: files + schedules + audit_logs + plans/subscriptions

- **Trilha:** data
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-01/02)
- **Depende de:** DATA-01, DATA-02

## Objetivo

Completar as tabelas de suporte do MVP.

## Entregaveis

- Migration `0009_files.py`:
  - `files` (id, tenant_id, kind, object_key, bytes,
    checksum_sha256, source_execution_id, expires_at, timestamps).
  - **Sem `storage_tier`** (ADR-003).
- Migration `0010_schedules.py`:
  - `schedules` (id, tenant_id, company_id nullable, cron_expr,
    timezone, enabled, last_run_at, next_run_at,
    created_by_user_id).
  - Indice `(enabled, next_run_at)`.
- Migration `0011_audit_logs.py`:
  - `audit_logs` (id bigserial, tenant_id, actor_user_id, action,
    resource_type, resource_id, ip, user_agent, metadata jsonb,
    created_at).
  - Indice `(tenant_id, created_at DESC)`, `(resource_type, resource_id)`.
- Migration `0012_plans_subscriptions.py`:
  - `plans` (code, name, limits jsonb, price_cents, active).
  - `subscriptions` (tenant_id, plan_id, status,
    current_period_start/end, gateway, gateway_customer_id,
    gateway_subscription_id).
- RLS em `files`, `schedules`, `audit_logs`, `subscriptions`.

## Definition of Done

- [ ] Migrations sobem/descem.
- [ ] Audit logs testados em insercao massiva (10k rows).
