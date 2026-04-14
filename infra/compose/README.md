# Compose base — Postgres + Redis (INFRA-05)

Stack de infraestrutura que sobe **Postgres 16** e **Redis 7** com volumes
persistentes, healthchecks e network privada `internal`. E a base sobre a
qual os overrides futuros (`api`, `worker`, `web-app`, `nginx-host`) vao
compor os stacks `prod` e `staging` descritos no ADR-005.

> Pre-requisitos: INFRA-01 (VPS endurecida) e INFRA-02 (Docker Engine +
> Compose v2 + `/srv/nfse/{prod,staging}/{data,backups,logs,config}`).

## 1. Setup

```bash
cd infra/compose
cp .env.example .env
# edite .env e substitua POSTGRES_PASSWORD e REDIS_PASSWORD por valores fortes:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Em producao o `.env` real vive em `/srv/nfse/<env>/config/.env` e e montado
read-only pelo Compose (ver INFRA-02). **Nunca** commitar o `.env` (ha um
`.gitignore` neste diretorio como guarda).

## 2. Subir

```bash
docker compose --env-file .env -f docker-compose.base.yml up -d
```

Confirmar que os dois servicos ficaram `healthy`:

```bash
docker compose -f docker-compose.base.yml ps
# Esperado: STATUS "Up ... (healthy)" em postgres e redis.
```

## 3. Verificacao (Definition of Done do ticket)

```bash
# [x] `docker compose up -d` sobe os dois servicos
docker compose -f docker-compose.base.yml ps --status=running

# [x] `psql` conecta do host (loopback)
psql "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_HOST_PORT:-5432}/${POSTGRES_DB}" -c 'select version();'

# [x] `redis-cli ping` retorna PONG
redis-cli -h 127.0.0.1 -p "${REDIS_HOST_PORT:-6379}" -a "${REDIS_PASSWORD}" --no-auth-warning ping
# PONG

# [x] Volumes sobrevivem a down/up
docker compose -f docker-compose.base.yml down
docker compose --env-file .env -f docker-compose.base.yml up -d
# Os volumes `nfse_pgdata` e `nfse_redisdata` permanecem; os dados do passo
# anterior devem reaparecer.
```

> Se `psql` ou `redis-cli` nao estiverem no host, dispara pelo container:
>
> ```bash
> docker exec -it nfse-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'select 1;'
> docker exec -it nfse-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping
> ```

## 4. Operacao

### Derrubar

```bash
docker compose -f docker-compose.base.yml down
```

`down` **preserva** os volumes nomeados (`nfse_pgdata`, `nfse_redisdata`).
Para apagar tudo (DESTRUTIVO, apenas em dev):

```bash
docker compose -f docker-compose.base.yml down -v
```

### Logs

Rotacao ja vem do `daemon.json` fixado em INFRA-02 (10m/3). Para ver em tempo
real:

```bash
docker compose -f docker-compose.base.yml logs -f postgres
docker compose -f docker-compose.base.yml logs -f redis
```

## 5. Backup / retention dos volumes

A politica final de backup e automacao saem em **INFRA-08**. Ate la, vale o
procedimento manual abaixo — suficiente para dev e para o primeiro deploy em
staging. Alinhado ao **ADR-003** (retencao operacional de 90 dias sem
arquivamento):

- **Postgres — logico (preferido):**

  ```bash
  # Dump diario em /srv/nfse/<env>/backups/postgres/
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  docker exec nfse-postgres pg_dumpall -U "$POSTGRES_USER" \
    | gzip -9 \
    > "/srv/nfse/<env>/backups/postgres/pg_dumpall_${ts}.sql.gz"
  ```

- **Postgres — snapshot do volume (ultimo recurso, requer downtime):**

  ```bash
  docker compose -f docker-compose.base.yml stop postgres
  sudo tar -czf "/srv/nfse/<env>/backups/postgres/pgdata_${ts}.tar.gz" \
    -C /var/lib/docker/volumes/nfse_pgdata _data
  docker compose -f docker-compose.base.yml start postgres
  ```

- **Redis — snapshot RDB:**

  ```bash
  docker exec nfse-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning save
  sudo cp /var/lib/docker/volumes/nfse_redisdata/_data/dump.rdb \
    "/srv/nfse/<env>/backups/redis/dump_${ts}.rdb"
  ```

- **Retencao:** manter dumps locais por 90 dias; limpar dumps/snapshots mais
  antigos com `find /srv/nfse/<env>/backups -type f -mtime +90 -delete`.
  Nao replicar para S3/B2 a menos que o owner decida — o bucket B2 do
  INFRA-06 e para execucoes/exports, nao para dumps de banco.

- **Restore (smoke test):** em staging, restaurar um dump recente para um
  Postgres temporario e rodar `alembic upgrade head` + um `SELECT count(*)`
  nas tabelas-chave antes de qualquer mudanca de versao do Postgres.

## 6. Decisoes / notas

- **Volumes nomeados**, nao bind mounts. Mais portavel entre dev/VPS e evita
  problemas de permissao com o usuario `postgres` interno. Em producao, os
  backups (secao 5) copiam de `/var/lib/docker/volumes/nfse_*/_data` para
  `/srv/nfse/<env>/backups/` — o topo de `/srv/nfse/<env>/data/` fica
  reservado para bind mounts de servicos que precisem (ex.: Nginx configs).
- **Porta publicada em loopback** (`127.0.0.1:5432` e `127.0.0.1:6379`).
  Permite `psql`/`redis-cli` do host sem expor o servico a internet. UFW
  (INFRA-01) ja bloqueia, mas publicar em `0.0.0.0` nao passaria por
  revisao mesmo assim.
- **Redis com `requirepass`** mesmo estando em rede privada. Defesa em
  profundidade para o dia em que outro container com AUTHZ fraca for
  adicionado a mesma network.
- **`POSTGRES_INITDB_ARGS`** fixa locale `C.UTF-8` para indices de texto
  deterministicos (migrations DATA-* fazem unique em `LOWER(email)` etc.).
- **Upgrade de versao do Postgres** e operacao manual (dump + restore em
  volume novo); nao fazer `image: postgres:17` sem `pg_upgrade` planejado.
