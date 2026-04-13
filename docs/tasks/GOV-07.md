# GOV-07 — PR Guardrail (bloqueia merge sem STATE.md + CHANGELOG.md + Closes)

- **Trilha:** governance
- **Tamanho:** S
- **Status:** completed (entregue junto com o setup)
- **Depende de:** GOV-01, GOV-03

## Objetivo

Evitar drift da fonte de verdade do projeto quando multiplos agentes
(Claude Code, Codex, Antigravity, etc.) executam tickets em paralelo.

Um PR so pode ser mergeado em `main` se:

1. Alterou `STATE.md` (status do ticket atualizado).
2. Alterou `CHANGELOG.md` (entrada em `[Unreleased]`).
3. Referencia um issue via `Closes #N` / `Fixes #N` / `Resolves #N` no body.

## Entregaveis

- Workflow `.github/workflows/pr-guardrail.yml` com 3 checks obrigatorios.
- Label `skip-guardrail` para exceptions manuais do owner.
- Prefixos de titulo exemptos: `chore(release):`, `docs:`, `ci:`.

## Definition of Done

- [x] Workflow commitado.
- [ ] Protecao de branch em `main` adiciona `pr-guardrail / Require STATE.md + CHANGELOG.md update` como status check obrigatorio (feito manualmente pelo owner em Settings -> Branches).
- [ ] Teste: abrir PR sem tocar STATE.md -> falha com mensagem clara.

## Notas operacionais

- Quando precisar bypassar (ex: hotfix urgente), adicione label
  `skip-guardrail` no PR. Use com moderacao.
- Commits de docs puros que nao fecham ticket podem usar prefixo `docs:`
  no titulo do PR (o workflow ignora).
