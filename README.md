# NFS-e SaaS (monorepo)

Plataforma multi-tenant de automacao fiscal para coleta de NFS-e recebidas
(ADN + NSU, mTLS A1), geracao de exportacoes e operacao centralizada de
multiplos CNPJs.

> Nome comercial: **a definir**. Placeholder tecnico: `nfse-saas`.

## Status atual (29/04/2026)

A trilha de produto **API + Worker + painel web** esta funcional em `main`:

- API FastAPI multi-tenant com auth completa (signup/login/refresh/logout +
  argon2id + JWT 15min + refresh opaco rotativo), RLS no Postgres,
  CRUD de companies/credentials/executions/files/exports/occurrences/
  schedules/users.
- Worker RQ ponta-a-ponta: pega execucao da fila, decifra PFX (AES-GCM +
  HKDF por tenant), coleta NFS-e via ADN, grava XML no S3 e fecha a
  execucao com contadores + occurrences categorizadas.
- Scheduler APScheduler dispara coletas cron por agendamento (API-14).
- Export ZIP assincrono (`POST /exports`) com `download_url` pre-assinada
  1h e retencao 30d para artefatos derivados.
- Painel Next.js com paginas `/dashboard`, `/empresas`, `/execucoes`,
  `/agendamentos`, `/ocorrencias` (com runbook inline), `/arquivos`,
  `/usuarios`, `/assinatura` e wizard de onboarding em 3 passos.
- Infra: Docker Compose base + override de deploy, Nginx host com
  hostnames apex/www/app/api/ops, observabilidade (Loki + Promtail +
  Grafana + Uptime Kuma), backup diario do Postgres para S3 com cifra
  age, pipeline GitHub Actions -> SSH para staging/prod com rollback.

**O que ainda falta** (ver `STATE.md` -> "Proximas Destravadas"):

1. Aplicar as 3 correcoes criticas da auditoria 2026-04-22
   (revogacao em cadeia de refresh token, race no scheduler, escopo do
   pytest no CI). Documentadas em `docs/auditoria-tecnica-2026-04-22.md`.
2. Setup manual do bucket Backblaze B2 (issue #8) — destrava DoDs
   manuais de upload real, download via URL pre-assinada e smoke E2E.
3. Provisionar VPS + secrets de deploy (`SSH_HOST`/`SSH_USER`/`SSH_KEY`)
   e `/srv/nfse/<env>` no host. Apos isso, descomentar `proxy_pass` em
   `infra/nginx/sites-available/{app,api}.conf`.
4. Trilha **SITE** (landing publica) — bloqueada apenas pelo nome
   comercial / dominio definitivo.
5. Delivery real de notificacoes SMTP/push (consumer da outbox).
6. Endpoint REST de credenciais agregado (`GET /credentials?
   expiring_in_days=30`) para destravar o KPI "Certificados a vencer"
   no dashboard.

## Estrutura do monorepo

```
apps/
  api/          FastAPI (Python) - API multi-tenant
  worker/       Consumer Redis - RQ worker + scheduler APScheduler
  web-app/      Next.js 14 - painel logado
packages/
  worker-core/  Motor ADN reusavel (auth mTLS, fetcher NSU, NSU source,
                S3 client, jobs run_execution + build_export)
infra/
  compose/      docker-compose base + deploy + obs
  local/        Bootstrap da stack completa no Docker Desktop
  deploy/       Script idempotente + runbook (INFRA-09)
  nginx/        Server blocks dos 5 hostnames + ops.conf (INFRA-04/07)
  scripts/      backup-postgres.sh, restore-postgres.sh, s3-smoke-test.sh
  systemd/      timer + service do backup
docs/
  adrs/         Architecture Decision Records (5 ADRs ativos)
  tasks/        Tickets com DoD (1 arquivo por TASK-ID)
  architecture/ overview, occurrence-codes, rbac-matrix
  runbooks/     11 runbooks (5 de dominio + 4 de infra + 2 placeholders)
  legal/        terms, privacy, ropa
  pendencias-manuais.md
  auditoria-tecnica-2026-04-22.md
config/
  .env.example  Template completo (auth, DB, Redis, S3, KEK, SMTP, etc.)
  clientes.csv.example  Apenas para o coletor legado
src/, main.py, scripts/   Coletor legado single-tenant (ver SETUP.md +
                          docs/LEGACY_COLLECTOR.md)
tests/        Testes do coletor legado (worker-core herdou no monorepo)
```

O motor ADN legado ja foi extraido para `packages/worker-core/` na
tarefa **CORE-01**; `src/` virou shim retro-compativel para `main.py`
continuar funcionando como CLI single-tenant.

## Orientacao rapida

- **docs/deploy-oracle-free.md** — subir o sistema inteiro (com HTTPS) em uma
  VM gratuita para testes, via `infra/oracle/setup.sh` (self-host: Postgres +
  Redis + MinIO + Caddy, sem servico externo pago).
- **STATE.md** — estado atual do projeto (fonte unica de verdade).
- **CHANGELOG.md** — historico de merges, agrupado por PR.
- **SETUP.md** — guia do **coletor legado** (CLI single-tenant). Para
  o SaaS multi-tenant, ver `infra/deploy/README.md` e
  `apps/api/README.md`.
- **infra/local/README.md** - sobe o SaaS completo no Docker Desktop e
  abre o painel local com uma conta de demonstracao pronta.
- **TROUBLESHOOTING.md** — cenarios de erro do coletor legado. Para
  o SaaS, ver `docs/runbooks/`.
- **docs/tasks/** — tickets com DoD e prompt pronto (~80 tickets).
- **docs/adrs/** — decisoes arquiteturais.
- **docs/auditoria-tecnica-2026-04-22.md** — debito tecnico aberto.

## Como continuar em uma nova sessao (prompt padrao)

> "Leia STATE.md e docs/tasks/<TASK-ID>.md. Execute a tarefa seguindo o DoD,
> abra branch `task/<TASK-ID>-<slug>`, commite, atualize STATE.md e
> CHANGELOG.md, e abra PR com 'Closes #<issue>'."

## Stack alvo

- **Frontend:** Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **Backend API:** FastAPI + SQLAlchemy + Alembic
- **Worker:** Python + RQ/Redis + APScheduler
- **Banco:** PostgreSQL 16 (RLS multi-tenant)
- **Cache/Fila:** Redis
- **Storage:** S3-compativel (Backblaze B2 ou similar)
- **Deploy:** Docker Compose em VPS Hostinger (Ubuntu 24.04)
- **Edge:** Nginx + Let's Encrypt
- **Observabilidade:** Loki + Promtail + Grafana + Uptime Kuma

## Licenca

Proprietario. Todos os direitos reservados.

## Legal

- Termos de Uso: `docs/legal/terms.md` (DOCS-01).
- Requisito de produto: referenciar os Termos no signup e na rota `/legal`
  do app/site quando essas trilhas estiverem ativas.
