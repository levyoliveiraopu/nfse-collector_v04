# INFRA-02 — Instalar Docker + Compose + diretorios padrao

- **Trilha:** infra
- **Tamanho:** S
- **Status:** ready (apos INFRA-01)
- **Depende de:** INFRA-01

## Objetivo

Instalar Docker Engine + Compose v2 e criar estrutura de diretorios de
producao/staging.

## Entregaveis

- Docker Engine + buildx + compose plugin instalados.
- Usuario `deploy` no grupo `docker`.
- `/srv/nfse/prod/` e `/srv/nfse/staging/` com subpastas
  `data/`, `backups/`, `logs/`, `config/`.
- Permissoes corretas (owner `deploy:deploy`, mode `750`).
- `infra/vps-docker.md` documentando o setup.

## Definition of Done

- [ ] `docker compose version` retorna >= 2.20.
- [ ] `deploy` roda `docker ps` sem sudo.
- [ ] Diretorios criados com permissoes corretas.
