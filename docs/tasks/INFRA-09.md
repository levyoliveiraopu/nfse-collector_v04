# INFRA-09 — Pipeline de deploy (GitHub Actions -> SSH)

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready (apos INFRA-02 + GOV-06)
- **Depende de:** INFRA-02, GOV-06

## Objetivo

Deploy automatizado de cada app ao dar merge em `main` (ou push de tag).

## Entregaveis

- `.github/workflows/deploy-staging.yml`: merge em `main` -> deploy
  staging.
- `.github/workflows/deploy-prod.yml`: push de tag `v*` -> deploy prod.
- Build e push de imagens Docker para GHCR.
- Action SSH (appleboy/ssh-action) conecta na VPS e roda:
  - `git pull` no `/srv/nfse/<env>` do repo de infra (ou pull de imagens).
  - `docker compose pull && docker compose up -d --remove-orphans`.
  - Health check pos-deploy (curl no `/health`).
  - Rollback automatico se health falhar (rollback para tag anterior).
- Secrets no repo: `SSH_HOST`, `SSH_USER`, `SSH_KEY`, `GHCR_TOKEN`.

## Definition of Done

- [ ] PR de teste em main dispara deploy staging com sucesso.
- [ ] Push de tag v0.0.1 dispara deploy prod.
- [ ] Rollback testado manualmente ok.
