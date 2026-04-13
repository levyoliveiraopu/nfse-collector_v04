# APP-02 — Dashboard com KPIs

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda DS-05 + API-08)
- **Depende de:** DS-05, API-08

## Objetivo

Pagina `/dashboard` com visao geral do tenant.

## Entregaveis

- 4 `KPIStatCard`:
  - Notas coletadas (mes atual).
  - Execucoes OK / total.
  - Ocorrencias abertas.
  - Certificados a vencer em 30d.
- Timeline das ultimas 10 execucoes (usa `<Timeline>`).
- Atalhos: "Nova execucao", "Ver ocorrencias".
- Filtro de periodo global.

## Definition of Done

- [ ] Carrega em < 1s com dados de teste.
- [ ] Links levam as telas corretas.
