# DATA-07 — Seeds: plans + tenant demo + user admin

- **Trilha:** data
- **Tamanho:** S
- **Status:** blocked (aguarda DATA-05)
- **Depende de:** DATA-05

## Objetivo

Popular ambiente de dev com dados minimos para iniciar a API e app.

## Entregaveis

- Script `apps/api/scripts/seed.py`:
  - Insere plans `starter`, `pro`, `scale` com limites jsonb.
  - Cria tenant `demo` + user `admin@demo.local` (senha em env).
  - Associa com role `owner`.
- Comando `pnpm --filter api seed` (ou `python -m scripts.seed`).

## Definition of Done

- [ ] Script rodado em dev cria dados.
- [ ] Re-run e idempotente (upsert).
