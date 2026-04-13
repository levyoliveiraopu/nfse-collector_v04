# GOV-03 — Templates de Issue/PR + labels + Projects + issues iniciais

- **Trilha:** governance
- **Tamanho:** M
- **Status:** in-progress (entregue neste PR de setup)
- **Depende de:** GOV-01

## Objetivo

Configurar GitHub para servir como quadro de controle.

## Entregaveis

- `.github/ISSUE_TEMPLATE/{task,bug,spike}.md`
- `.github/pull_request_template.md`
- `.github/labels.yml`
- Todas as labels aplicadas no repo.
- ~60 issues criadas (uma por ticket em `docs/tasks/`).
- Milestones: `MVP-Infra`, `MVP-Data-API`, `MVP-App`, `MVP-Piloto`.
- Projects board (Kanban: Backlog / Ready / In Progress / Review / Done).
- Branch protection em `main` (1 approval + CI verde).

## Definition of Done

- [x] Templates commitados.
- [ ] Labels criadas (via MCP apos merge).
- [ ] Issues criadas e linkadas aos tickets.
- [ ] Milestones criadas.
- [ ] Board criado.
- [ ] Branch protection ativa.

## Notas

Parte da execucao acontece via GitHub MCP apos o merge deste PR.
