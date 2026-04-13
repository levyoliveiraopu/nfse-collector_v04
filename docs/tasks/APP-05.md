# APP-05 — /execucoes/nova + acompanhamento real-time

- **Trilha:** app
- **Tamanho:** L
- **Status:** blocked (aguarda API-07 + API-08)
- **Depende de:** API-07, API-08

## Objetivo

Criar execucao manual e acompanhar progresso.

## Entregaveis

- `/execucoes/nova`:
  - Multi-select de empresas (so com credencial valida).
  - PeriodPicker (ou "incremental desde ultimo NSU").
  - Toggle dry-run.
  - CTA "Iniciar".
- `/execucoes/[id]`:
  - Barra de progresso (items_ok + items_fail / items_total).
  - Tabela de items com status + filtro por status.
  - Polling 2s ate status final.
  - Botao "Reprocessar selecionados" (integra APP-06/API-10).

## Definition of Done

- [ ] E2E: cria, acompanha, ve itens aparecendo.
