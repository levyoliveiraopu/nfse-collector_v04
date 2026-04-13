# API-12 — Schedules CRUD

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-05)
- **Depende de:** DATA-05

## Objetivo

Gerenciar agendamentos de execucao automatica.

## Entregaveis

- `GET /schedules`.
- `POST /schedules` (valida cron, timezone).
- `PATCH /schedules/{id}` (pause/resume via enabled).
- `DELETE /schedules/{id}`.
- Calculo de `next_run_at` ao criar/editar.
- Presets sugeridos: diario 03:00, semanal segunda 06:00, mensal dia 1 05:00.

## Definition of Done

- [ ] Cron invalido retorna 400 claro.
- [ ] `next_run_at` coerente com cron + TZ informado.
