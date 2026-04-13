# NFS-e SaaS (monorepo)

Plataforma multi-tenant de automacao fiscal para coleta de NFS-e recebidas (ADN + NSU, mTLS A1),
geracao de exportacoes e operacao centralizada de multiplos CNPJs.

> Nome comercial: **a definir**. Placeholder tecnico: `nfse-saas`.

## Estrutura do monorepo

```
apps/
  api/          FastAPI (Python) - API multi-tenant
  worker/       Consumer Redis - orquestra worker-core
  web-app/      Next.js - painel logado
  web-site/     Next.js - landing publica
packages/
  worker-core/  Motor ADN (extraido de src/) - reuso dos fetchers/auth/NSU
infra/          Docker Compose, Nginx, scripts de deploy
docs/
  adrs/         Architecture Decision Records
  tasks/        Tickets de tarefas (1 arquivo por TASK-ID)
  architecture/ Visao geral e diagramas
```

O codigo legado do coletor ainda reside em `src/`, `main.py`, `scripts/` e esta
documentado em `docs/LEGACY_COLLECTOR.md`. Sera migrado para
`packages/worker-core/` na tarefa **CORE-01**.

## Orientacao rapida

- **STATE.md** — estado atual do projeto (fonte unica de verdade).
- **CHANGELOG.md** — historico de merges.
- **docs/tasks/** — tickets com DoD e prompt pronto.
- **docs/adrs/** — decisoes arquiteturais.

## Como continuar em uma nova sessao (prompt padrao)

> "Leia STATE.md e docs/tasks/<TASK-ID>.md. Execute a tarefa seguindo o DoD,
> abra branch `task/<TASK-ID>-<slug>`, commite, atualize STATE.md e
> CHANGELOG.md, e abra PR com 'Closes #<issue>'."

## Stack alvo

- **Frontend:** Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **Backend API:** FastAPI + SQLAlchemy + Alembic
- **Worker:** Python + RQ/Redis
- **Banco:** PostgreSQL 16 (RLS multi-tenant)
- **Cache/Fila:** Redis
- **Storage:** S3-compativel (Backblaze B2 ou similar)
- **Deploy:** Docker Compose em VPS Hostinger (Ubuntu 24.04)
- **Edge:** Nginx + Let's Encrypt

## Licenca

Proprietario. Todos os direitos reservados.
