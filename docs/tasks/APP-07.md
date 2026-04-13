# APP-07 — /agendamentos

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda API-12)
- **Depende de:** API-12

## Objetivo

UI para criar e gerenciar agendamentos.

## Entregaveis

- Lista de agendamentos (empresa, cron humanizado, proximo run, toggle
  on/off).
- Criar/editar com builder amigavel
  (ex: "Todo dia as 03:00" -> cron).
- Visao previa: "proximos 5 runs".

## Definition of Done

- [ ] Toggle on/off reflete em `next_run_at`.
- [ ] Cron invalido bloqueado com mensagem clara.
