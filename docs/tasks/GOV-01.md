# GOV-01 — Setup do monorepo base

- **Trilha:** governance
- **Tamanho:** S
- **Status:** completed (entregue neste PR de setup)
- **Depende de:** nada

## Objetivo

Criar a estrutura de monorepo com pnpm workspaces + Turborepo, diretorios
padrao (`apps/`, `packages/`, `infra/`, `docs/`) e arquivos base
(`README.md`, `.gitignore`, `.editorconfig`).

## Entregaveis

- `package.json` raiz (workspaces).
- `pnpm-workspace.yaml`.
- `turbo.json`.
- `.editorconfig`.
- `.gitignore` ampliado (Python + Node + secrets).
- `README.md` novo (legado movido para `docs/LEGACY_COLLECTOR.md`).
- Diretorios vazios com `.gitkeep`: `apps/`, `packages/`, `infra/`.

## Definition of Done

- [x] `pnpm install` executa sem erro.
- [x] Estrutura de diretorios criada.
- [x] Legado preservado e documentado.

## Notas

Migracao do codigo em `src/` acontece em CORE-01.
