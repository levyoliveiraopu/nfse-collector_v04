# ADR-005 — Deploy Docker Compose em VPS Hostinger + Nginx host

- **Status:** Aceito
- **Data:** 2026-04-13

## Contexto

- 1 VPS Hostinger (ja contratada).
- Solo founder, sem time de DevOps.
- Necessidade de subir MVP rapido com possibilidade de deploy sem
  downtime em fase posterior.

## Decisao

- SO base: **Ubuntu 24.04 LTS**.
- Orquestracao: **Docker Compose v2** (sem Kubernetes).
- **Nginx roda no host** (nao em container) para simplificar gerencia
  de Let's Encrypt via `certbot --nginx`.
- Containers gerenciados:
  - `postgres:16`
  - `redis:7`
  - `api` (FastAPI)
  - `worker` (RQ)
  - `scheduler` (rq-scheduler ou APScheduler)
  - `web-app` (Next.js)
  - `web-site` (Next.js)
  - `grafana`, `loki`, `promtail` (observabilidade)
  - `uptime-kuma`
- Diretorio raiz em prod: `/srv/nfse/prod/` com `docker-compose.yml`,
  `.env`, `data/` (volumes), `backups/`.
- Deploy via GitHub Actions → SSH → `docker compose pull && up -d`.
- Migrations Alembic rodadas **antes** do novo codigo subir
  (compatibilidade N/N-1 obrigatoria).

## Rollback
- Tag Docker anterior documentada.
- Dump Postgres pre-deploy via hook do pipeline para deploys de risco.

## Consequencias

**Positivas**
- Simplicidade maxima.
- Baixo custo (1 VPS).
- Certbot simples no host.

**Negativas**
- Single point of failure ate adicionarmos uma VPS secundaria.
- Deploy de API tem blip de 1-5s (aceitavel no MVP).
- Fallback/failover manual.

## Reavaliacao

Quando MRR justificar: VPS secundaria + balanceador (Nginx a frente com
2 upstreams) para deploy zero-downtime; backups WAL-G para PITR.
