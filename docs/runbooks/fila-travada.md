# Runbook — fila RQ travada (worker nao processa)

> Alvo: fila Redis + RQ consumida por `apps/worker/` (API-13) + scheduler
> cron de API-14. Disparos de `/executions` enfileiam
> `worker_core.jobs.run_execution` em `API_QUEUE_NAME`
> (default `nfse-executions`).

## Escopo

Use este runbook quando:

- `executions` ficam presas em `status='queued'` por mais de alguns minutos.
- Exports (`exports.status='queued'`) nao progridem.
- `/healthz` do worker caiu (Uptime Kuma aciona alerta).
- Scheduler (API-14) roda mas nao enfileira / enfileira sem consumo.

## 1. Como detectar

### 1.1 Fontes de alerta

- **Uptime Kuma** (INFRA-07): monitor `worker` em
  `https://api.<DOMINIO>/healthz` com keyword `"ok"` — queda dispara
  Telegram.
- **Grafana / Loki**: painel de logs do worker para o dashboard
  `NFS-e — Logs API & Worker`. Ausencia de `job.start`/`job.success` em
  janela de 15 min alem da taxa normal indica trava.
- **Alerta futuro**: alert rule contando jobs `queued` em `executions`
  acima de N por >15 min deve linkar para este runbook via `runbook_url`.

### 1.2 Checagem manual rapida

```bash
# Healthcheck do worker (de dentro da rede docker ou via api).
curl -sI http://127.0.0.1:8080/healthz
# Esperado: HTTP/1.1 200 OK + body {"status":"ok"}.

# Via Nginx publico (rota de observabilidade):
curl -s https://api.<DOMINIO>/healthz
```

```sql
-- Executions presas em queued (tempo de espera).
SELECT id, tenant_id, company_id, created_at,
       EXTRACT(EPOCH FROM (now() - created_at))/60 AS min_enfileirado
FROM executions
WHERE status = 'queued'
ORDER BY created_at ASC
LIMIT 20;

-- Exports em queued/running:
SELECT id, status, started_at,
       EXTRACT(EPOCH FROM (now() - COALESCE(started_at, created_at)))/60 AS min
FROM exports
WHERE status IN ('queued', 'running')
ORDER BY created_at ASC;
```

```bash
# Profundidade da fila no Redis.
cd /srv/nfse/prod/config
docker compose exec -T redis redis-cli LLEN rq:queue:nfse-executions
docker compose exec -T redis redis-cli SMEMBERS rq:workers   # workers conhecidos
```

> Gatilho: agir quando `min_enfileirado > 5` com 0 `job.start` no log do
> worker nos ultimos 5 min, ou quando `LLEN` nao cai.

## 2. Diagnostico

### 2.1 Worker vivo?

```bash
# Status do container.
docker compose ps worker

# Ultimas 200 linhas de log estruturado (JSON).
docker compose logs --tail=200 worker

# Se o healthz esta up mas ninguem processa, checar se o Worker RQ
# esta registrado:
docker compose exec -T redis redis-cli HGETALL "rq:worker:<nome>"
```

Estados comuns nos logs:

- `job.start` + `job.success` em serie -> fila saudavel.
- `job.start` sem `job.success` e sem excecao por muito tempo -> job
  pendurado em I/O (portal lento, S3 lento, Postgres).
- Silencio total -> worker caiu ou nao conecta no Redis.
- Excecao repetida na mesma tarefa -> `job.error` com `error_code`
  (ver `worker_core.jobs`).

### 2.2 Redis saudavel?

```bash
docker compose exec -T redis redis-cli PING                # PONG
docker compose exec -T redis redis-cli INFO clients        # connected_clients
docker compose exec -T redis redis-cli INFO memory         # used_memory_human
docker compose logs --tail=100 redis
```

Sintomas: `MISCONF Redis is configured to save RDB snapshots, but ...`
indica disco cheio (ver runbook `disco-cheio.md`).

### 2.3 Job individual travado

```bash
# Lista de jobs da fila.
docker compose exec -T redis redis-cli LRANGE rq:queue:nfse-executions 0 -1

# Detalhes de um job (pela id).
docker compose exec -T redis redis-cli HGETALL "rq:job:<job-id>"

# Failed registry (execucoes que erraram e estao parqueadas).
docker compose exec -T redis redis-cli ZRANGE rq:failed:nfse-executions 0 -1
```

Atencao: jobs em `rq:started_registry:nfse-executions` sem worker
correspondente em `rq:workers` sao fantasmas — worker morreu sem
liberar o job.

### 2.4 Dependencias externas

- Portal da prefeitura caindo -> ver `portal-indisponivel.md`.
- Credencial invalida -> ocorrencias `CRED_INVALID`/`CERT_EXPIRED` em
  `occurrences`; ver `credencial-invalida.md`.
- S3 (B2) inacessivel -> `S3StorageClient` retorna `StorageError`
  despues de 4 tentativas; erro aparece no worker como
  `storage.put.failed` no Loki.

## 3. Mitigacao

### 3.1 Reiniciar o worker (1a tentativa)

```bash
cd /srv/nfse/prod/config
docker compose restart worker

# Worker tem SIGTERM handler + stop_grace_period: 60s — drena o job atual.
# Acompanhar logs ate ver `job.start` novamente.
docker compose logs -f --tail=50 worker
```

### 3.2 Escalar workers (pico temporario)

```bash
# Rodar 2 replicas do worker ate a fila drenar.
docker compose up -d --scale worker=2

# Depois de voltar ao normal:
docker compose up -d --scale worker=1
```

> Jobs do mesmo `execution_id` nao duplicam porque
> `INSERT ... ON CONFLICT (tenant_id, chave_nfse) DO NOTHING` em
> `execution_items` preserva idempotencia.

### 3.3 Limpar failed registry apos investigar

Para reprocessar manualmente um job `failed`:

```bash
# Lista os failed.
docker compose exec -T redis redis-cli ZRANGE rq:failed:nfse-executions 0 -1

# Re-enfileirar pelo console rq (ou via script Python usando rq.Queue).
docker compose exec -T worker python - <<'PY'
from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry
import os
r = Redis.from_url(os.environ["API_REDIS_URL"])
q = Queue(os.environ.get("API_QUEUE_NAME","nfse-executions"), connection=r)
fr = FailedJobRegistry(queue=q)
for jid in fr.get_job_ids():
    fr.requeue(jid)
PY
```

### 3.4 Job fantasma (started_registry sem worker)

```bash
docker compose exec -T worker python - <<'PY'
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry
import os
r = Redis.from_url(os.environ["API_REDIS_URL"])
q = Queue(os.environ.get("API_QUEUE_NAME","nfse-executions"), connection=r)
sr = StartedJobRegistry(queue=q)
print("started:", sr.get_job_ids())
# Limpa entradas sem worker ativo:
sr.cleanup()
PY
```

### 3.5 Marcar execution abandonada

Quando o job esta perdido e o retry nao traz de volta, encerrar a linha
de `executions` em `failed` para liberar a UI:

```sql
UPDATE executions
SET status = 'failed',
    finished_at = now(),
    error_summary = 'stuck_in_queue'
WHERE id = :execution_id AND status IN ('queued','running');
```

Registrar ocorrencia `UNKNOWN` com `severity='warning'` apontando pra
este runbook.

### 3.6 Redis fora do ar

```bash
docker compose ps redis
docker compose logs --tail=100 redis
docker compose restart redis
```

Se o volume `/srv/nfse/prod/data/redis` encheu: ver `disco-cheio.md`.

Depois que o Redis volta, o worker re-conecta sozinho (retry com
backoff via `redis-py`); jobs persistidos nao se perdem (AOF/RDB).

## 4. Prevencao

- [ ] `job_timeout` configurado em `apps/api/api/queue.py` (3600s para
  `run_execution`, 2h para `build_export`) — jobs travados estouram e
  entram em `failed` em vez de ficar pendurados.
- [ ] `failure_ttl=7d` preserva falhas para investigacao sem entupir o
  Redis.
- [ ] Compose do worker define `stop_grace_period: 60s` para graceful
  shutdown em SIGTERM.
- [ ] Uptime Kuma com monitor do `/healthz` do worker — queda -> Telegram.
- [ ] Futuro: alert rule no Grafana baseado em `executions.queued` por
  mais de N minutos (metrica a ser exportada — ticket de observabilidade
  futura).
- [ ] Scheduler (API-14) roda com `misfire_grace_time` definido em
  `apscheduler` — evita dispararem N jobs atrasados de uma vez apos
  downtime longo.

## Referencias

- `apps/worker/README.md` — entry point + envs do worker RQ.
- `packages/worker-core/worker_core/jobs.py` — handlers `run_execution`
  e `build_export`.
- `infra/observability.md` — dashboard + Uptime Kuma.
- `docs/runbooks/portal-indisponivel.md` — quando o travamento vem do portal.
- `docs/runbooks/credencial-invalida.md` — quando vem da credencial.
- `docs/runbooks/disco-cheio.md` — Redis misconf por disco cheio.
