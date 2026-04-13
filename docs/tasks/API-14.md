# API-14 — Scheduler (dispara execucoes agendadas)

- **Trilha:** api
- **Tamanho:** M
- **Status:** blocked (aguarda API-12 + API-13)
- **Depende de:** API-12, API-13

## Objetivo

Servico que le `schedules` e enfileira jobs quando `next_run_at`
chega.

## Entregaveis

- Processo `apps/worker/scheduler.py` (APScheduler) rodando em
  container separado OU job periodico RQ scheduler.
- A cada 1min: busca schedules com `enabled=true AND next_run_at <= now`,
  cria executions e atualiza `next_run_at` (proximo cron).
- Se execucao anterior daquela empresa ainda esta `running`, **skip**
  com occurrence `SCHEDULE_OVERLAP`.
- Logs claros de cada disparo.

## Definition of Done

- [ ] Agendamento cron `* * * * *` (a cada minuto) dispara e log aparece.
- [ ] Overlap criar occurrence sem duplicar execucao.
