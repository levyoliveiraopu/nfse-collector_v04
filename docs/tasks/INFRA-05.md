# INFRA-05 — Compose de producao base (Postgres + Redis)

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready (apos INFRA-02)
- **Depende de:** INFRA-02

## Objetivo

Subir Postgres 16 e Redis 7 com volumes persistentes e healthchecks.

## Entregaveis

- `infra/compose/docker-compose.base.yml` com servicos:
  - `postgres:16-alpine` com volume `pgdata`.
  - `redis:7-alpine` com volume `redisdata`.
- Healthchecks configurados.
- Networks privadas (`internal`).
- Variaveis sensiveis via `.env` (nao commitado).
- `infra/compose/.env.example` documentando variaveis.
- Backup retention snapshot do volume documentado.

## Definition of Done

- [ ] `docker compose up -d` sobe os dois servicos.
- [ ] `psql` conecta do host.
- [ ] `redis-cli ping` retorna PONG.
- [ ] Volumes sobrevivem a `docker compose down && up`.
