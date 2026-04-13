# GOV-06 — CI base (lint + test)

- **Trilha:** governance
- **Tamanho:** M
- **Status:** ready
- **Depende de:** GOV-01

## Objetivo

Configurar GitHub Actions para rodar lint e testes em todo PR.

## Pre-requisitos

- Estrutura do monorepo ativa.

## Entregaveis

- `.github/workflows/ci.yml` com jobs:
  - `lint-python` (ruff + mypy opcional).
  - `lint-ts` (eslint + prettier check).
  - `test-python` (pytest).
  - `test-ts` (vitest).
- Cache de pnpm e pip.
- Status checks obrigatorios em `main`.

## Definition of Done

- [ ] PR dummy falha se lint quebrar.
- [ ] Workflow verde no PR de teste.
- [ ] Branch protection referencia os checks.

## Prompt sugerido

```
Leia STATE.md e docs/tasks/GOV-06.md. Execute a tarefa, abra branch
task/GOV-06-ci-base, commite, atualize STATE.md e CHANGELOG.md, e
abra PR com "Closes #<issue>".
```
