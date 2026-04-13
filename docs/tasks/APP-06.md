# APP-06 — /ocorrencias inbox + runbooks inline

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda API-09)
- **Depende de:** API-09

## Objetivo

Inbox de ocorrencias estilo helpdesk.

## Entregaveis

- Lista filtravel (status, severity, empresa).
- Detalhe: descricao, historico, runbook do `code` (renderiza
  `docs/runbooks/<code>.md` embutido).
- Acoes: acknowledge, resolve (com nota), assign, reprocessar (abre
  pre-preenchido em APP-05).

## Definition of Done

- [ ] 10 codigos de ocorrencia tem runbook.
- [ ] Acoes atualizam estado sem reload.
