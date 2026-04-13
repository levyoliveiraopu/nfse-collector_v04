# DATA-04 — Schema: occurrences + reprocess_jobs + notifications

- **Trilha:** data
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-02)
- **Depende de:** DATA-02

## Objetivo

Tabelas de ocorrencias operacionais, jobs de reprocessamento e
notificacoes.

## Entregaveis

- Migration `0006_occurrences.py`:
  - `occurrences` (id, tenant_id, company_id, execution_id,
    severity, code, title, detail, status, assignee_user_id,
    first_seen_at, last_seen_at, resolved_at).
- Migration `0007_reprocess_jobs.py`:
  - `reprocess_jobs` (id, tenant_id, created_by_user_id,
    scope jsonb, status, result_execution_ids text[]).
- Migration `0008_notifications.py`:
  - `notifications` (id, tenant_id, user_id nullable, channel,
    type, payload jsonb, status, sent_at, read_at).
- RLS em todas.

## Definition of Done

- [ ] Migrations sobem/descem.
- [ ] FKs validas.
