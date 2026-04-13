# INFRA-08 — Backup Postgres para S3

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready (apos INFRA-05 + INFRA-06)
- **Depende de:** INFRA-05, INFRA-06

## Objetivo

Backup diario do Postgres com upload para S3 e politica de retencao.

## Entregaveis

- Script `infra/scripts/backup-postgres.sh`:
  - `pg_dump -Fc` comprimido.
  - Upload para `s3://<bucket>/backups/postgres/YYYY-MM-DD.dump`.
  - Deleta dumps locais > 3 dias.
- Cron (systemd timer) diario as 03:00 UTC-3.
- Lifecycle do bucket: retencao 30d para dailies +
  retencao 12 meses para backups do dia 1 de cada mes (manual tag).
- Script de restore `infra/scripts/restore-postgres.sh`.
- Drill de restore em staging documentado.

## Definition of Done

- [ ] Backup roda via cron por 2 dias seguidos.
- [ ] Restore em staging recupera dados intactos (checksum tabela).
- [ ] Documentado em `infra/backup.md`.
