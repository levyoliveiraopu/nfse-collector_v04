# apps/worker (API-13)

RQ consumer do SaaS NFS-e. Pica jobs enfileirados pela API
(`apps/api/api/queue.py`) na fila `API_QUEUE_NAME` e delega para
`worker_core.jobs.run_execution`.

## Responsabilidades

1. Carrega execution + company + credential (com RLS).
2. Le o blob cifrado do S3 e decifra PFX + senha
   (`worker_core.crypto.decrypt`).
3. Chama `worker_core.fetch_nfse` com `DbNsuSource` + callback que
   INSERT-a `execution_items` com `ON CONFLICT DO NOTHING`
   (idempotencia) e sobe o XML bruto pro S3.
4. Atualiza `companies.last_nsu` (via `DbNsuSource`) e marca
   `executions.status` como `succeeded` / `partial` / `failed`.
5. Cria `occurrences` categorizadas (`CRED_INVALID`, `CERT_EXPIRED`,
   `PORTAL_5XX`, `PARSE_ERROR`, `STORAGE_ERROR`, `UNKNOWN`).

## Endpoint `/healthz`

Responde `200` + `{"status":"ok"}` enquanto o processo estiver vivo.
Usado pelo Uptime Kuma (INFRA-07). Porta configuravel via
`WORKER_HEALTHZ_PORT` (default `8080`).

## Graceful shutdown

- O RQ instala handler SIGTERM/SIGINT que termina o job atual e sai.
- No compose, use `stop_grace_period: 60s` para cumprir o DoD
  "SIGTERM drena jobs em andamento ate 60s". Depois disso o SIGKILL
  encerra o processo.

## Variaveis de ambiente

| Var                         | Uso                                                 |
|-----------------------------|-----------------------------------------------------|
| `API_REDIS_URL`             | URL do Redis (compartilhada com a API).             |
| `API_QUEUE_NAME`            | Fila RQ (default `nfse-executions`).                |
| `API_DATABASE_URL`          | Postgres (role `app_user`, NOBYPASSRLS).            |
| `WORKER_DATABASE_URL`       | Override opcional da URL de banco do worker.        |
| `API_CREDENTIAL_KEK_B64`    | KEK de 32 bytes base64 (mesma da API — API-06).     |
| `S3_*`                      | Bucket + credenciais do storage (INFRA-06 / CORE-05). |
| `WORKER_HEALTHZ_PORT`       | Porta do `/healthz` (default `8080`).               |
| `LOG_LEVEL`                 | `INFO` default; `DEBUG` em dev.                     |

## Rodar local

```bash
# 1. Instalar as deps em editable mode (a partir da raiz do monorepo):
pip install -e packages/worker-core
pip install -e apps/worker

# 2. Exportar o .env:
set -a && source config/.env && set +a

# 3. Subir Redis + Postgres + MinIO (INFRA-05 — dev compose):
docker compose -f infra/compose/docker-compose.yml up -d redis postgres minio

# 4. Rodar o worker:
python -m worker.main
```

## Build da imagem

```bash
# A partir da raiz do monorepo:
docker build -f apps/worker/Dockerfile -t nfse-worker:dev .
```
