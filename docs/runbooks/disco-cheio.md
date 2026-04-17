# Runbook — disco cheio na VPS

> Alvo: VPS Hostinger rodando a stack Docker Compose (INFRA-05 + INFRA-07).
> Disco unico em `/` com `/srv/nfse/` (dados persistentes) e
> `/var/lib/docker/` (imagens + volumes).

## Escopo

Use este runbook quando houver indicacao de disco quase cheio ou cheio
na VPS. Sintomas operacionais tipicos:

- API/worker retornam 500 em operacoes de escrita (Postgres recusa `INSERT`).
- Uploads de XML/export para o S3 aparecem, mas o `pg_dump` local falha.
- Containers reiniciam em loop com `no space left on device` nos logs.
- Dashboards do Grafana param de atualizar (Loki nao consegue gravar).

## 1. Como detectar

### 1.1 Fontes de alerta

- **Uptime Kuma** (INFRA-07): monitores `api` / `app` / `worker` caem em
  cascata quando o disco enche — notificacao Telegram dispara.
- **Grafana / Loki**: painel "Taxa de erros (5m)" do dashboard
  `NFS-e — Logs API & Worker` sobe quando aparecem mensagens com
  `no space left on device` ou `could not extend file` (Postgres).
- **Alerta futuro** (quando criado): alert rule em cima da metrica de
  filesystem do host ou de contagem de log `|~ "no space left"` em Loki
  deve referenciar este runbook via `runbook_url` nas annotations.

### 1.2 Checagem manual rapida

```bash
# Uso de todas as particoes.
df -h

# Inodes (disco pode estar "cheio" por inode mesmo com bytes livres).
df -i

# Top 20 maiores diretorios dentro de /srv/nfse e /var/lib/docker.
sudo du -xh --max-depth=2 /srv/nfse 2>/dev/null | sort -h | tail -20
sudo du -xh --max-depth=2 /var/lib/docker 2>/dev/null | sort -h | tail -20
```

> Gatilho operacional: agir quando `df -h /` mostrar `Use% >= 80%` ou
> `df -i /` mostrar `IUse% >= 80%`.

## 2. Diagnostico

### 2.1 Quem cresceu?

```bash
# Imagens e volumes do Docker.
sudo docker system df -v

# Volumes orfaos (containers removidos, volume continua).
sudo docker volume ls -qf dangling=true

# Logs dos containers (podem virar GB sem rotacao).
sudo du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -h | tail -10

# Tamanho do volume do Postgres.
sudo du -sh /srv/nfse/prod/data/postgres 2>/dev/null

# Backups locais (INFRA-08).
sudo du -sh /srv/nfse/prod/backups 2>/dev/null

# Loki (retencao 14d — INFRA-07).
sudo du -sh /srv/nfse/prod/data/loki 2>/dev/null
```

### 2.2 Postgres crescendo?

```bash
# Top 10 tabelas por tamanho dentro do container do Postgres.
cd /srv/nfse/prod/config
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT schemaname, relname,
             pg_size_pretty(pg_total_relation_size(relid)) AS total
      FROM pg_catalog.pg_statio_user_tables
      ORDER BY pg_total_relation_size(relid) DESC
      LIMIT 10;"
```

Suspeitos frequentes: `audit_logs` (volume alto em tenant grande),
`execution_items` (1 linha por NFS-e), `occurrences`.

### 2.3 WAL travado?

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT slot_name, active, wal_status, pg_size_pretty(
        pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
      FROM pg_replication_slots;"
```

Slot inativo retem WAL indefinidamente — enche disco rapido.

## 3. Mitigacao

Ordem de acao: comecar pelo de menor blast radius. Depois de cada passo,
rodar `df -h /` para ver se o ponteiro se moveu.

### 3.1 Drenar logs e imagens orfas do Docker (seguro)

```bash
# Remove containers parados, imagens dangling, networks nao usadas.
sudo docker system prune -f

# Remove builder cache (pode liberar GB em uma VPS com muitos rebuilds).
sudo docker builder prune -f

# Remove imagens sem nenhum container usando (mais agressivo).
sudo docker image prune -af
```

### 3.2 Rotacionar logs de container

Editar `/etc/docker/daemon.json` (criar se nao existir):

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Aplicar:

```bash
sudo systemctl reload docker
# Re-criar containers para o novo driver valer neles.
cd /srv/nfse/prod/config
docker compose up -d
```

### 3.3 Aparar backups locais antigos (INFRA-08)

```bash
# BACKUP_RETENTION_LOCAL_DAYS default 3; script ja limpa, mas pode
# acumular se execucoes seguidas falharem.
sudo find /srv/nfse/prod/backups/postgres -type f \
  \( -name '*.dump' -o -name '*.dump.age' \) -mtime +3 -delete
```

Dumps remotos no S3 **nao** sao tocados — lifecycle do bucket trata
retencao (`backups/postgres/daily/` 30d, `monthly/` 365d).

### 3.4 VACUUM e reindex no Postgres (se espaco grande esta em tabela/indice)

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "VACUUM (VERBOSE, ANALYZE);"

# Em tabelas especificas que cresceram muito (ex.: execution_items):
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "VACUUM (FULL, VERBOSE, ANALYZE) execution_items;"
```

> `VACUUM FULL` pede lock exclusivo e bloqueia escritas na tabela —
> avaliar impacto antes. Preferir janela de baixa atividade.

### 3.5 Liberar WAL se ha slot inativo

```bash
# So para slot comprovadamente orfao (verificado em 2.3).
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT pg_drop_replication_slot('<slot_name>');"
```

Conferir com o owner antes — remocao de slot ativo quebra replica.

### 3.6 Cortar retencao do Loki (temporario)

Quando Loki e o culpado (`/srv/nfse/prod/data/loki` grande), reduzir
`retention_period` em `infra/compose/loki/loki-config.yml` (ex.: `168h` =
7d), subir de volta a stack obs. Restaurar para 14d depois da crise.

### 3.7 Ultimo recurso: expandir o disco

VPS Hostinger permite upgrade de plano com disco maior. Requer reboot —
agendar janela. Documentar no post-mortem.

## 4. Prevencao

- [ ] **Rotacao de logs Docker** aplicada globalmente via `daemon.json`
  (secao 3.2) — evita `json-file` sem teto.
- [ ] **Monitoramento de disco**: futura alert rule Grafana ou check
  periodico (cron em `/etc/cron.daily/disk-alert.sh`) que dispara webhook
  em `Use% >= 80%`. Ate existir, manter revisao manual semanal.
- [ ] **INFRA-08 saudavel**: garantir que `BACKUP_RETENTION_LOCAL_DAYS`
  (default 3) + lifecycle B2 estao aplicados; sem isso os dumps
  acumulam.
- [ ] **Retencao de dados**: ADR-003 define 90d de retencao dos XMLs
  (lifecycle do bucket S3) — como XML vive no B2 e nao na VPS, isso
  **nao** pesa no disco local; manter a regra.
- [ ] **Audit_logs**: revisar plano de expurgo quando a tabela passar
  de 10 GiB (ticket futuro — nao coberto por esta entrega).

## Referencias

- `infra/vps-docker.md` — instalacao da engine + `daemon.json`.
- `infra/observability.md` — stack Loki + Grafana (INFRA-07).
- `infra/backup.md` — retencao local/remota (INFRA-08).
- ADR-003 — retencao 90d (XMLs no S3, nao na VPS).
