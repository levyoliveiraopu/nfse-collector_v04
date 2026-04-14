# STATE — NFS-e SaaS

> Fonte unica de verdade sobre o estado atual do projeto.
> Toda PR deve atualizar este arquivo antes do merge.

## Decisoes Ativas

| ID | Decisao | Status |
|----|---------|--------|
| ADR-001 | Monolito modular Python (FastAPI) + Next.js | ativo |
| ADR-002 | Multi-tenant single-DB com Row Level Security | ativo |
| ADR-003 | Storage S3 externo, cifra PFX AES-GCM, retencao 90d sem arquivamento | ativo |
| ADR-004 | Billing adiado: schema pronto, integracao depois | ativo |
| ADR-005 | Deploy Docker Compose em VPS Hostinger + Nginx host | ativo |

## Em Andamento

- **DATA-01** — Schema inicial de identidade: Alembic configurado em
  `apps/api/alembic/`, migration `0001_initial_identity.py` cria
  extensao `pgcrypto`, roles `app_admin` (BYPASSRLS) / `app_user`
  (NOBYPASSRLS), tabelas `tenants`, `users`, `tenant_users`, RLS +
  politicas em `tenants` e `tenant_users` via GUC `app.current_tenant`
  (PR a abrir, issue #12).
- **DS-03** — Layout shell: componente `<AppShell>` em
  `apps/web-app/components/app-shell/` com sidebar colapsavel
  (256px/64px em desktop, drawer em <1024px), topbar fixa com
  breadcrumbs (derivados de `usePathname`), tenant switcher placeholder,
  bell de notificacoes, theme toggle e user menu; dropdowns leves sem
  Radix (fecham em click-outside/Esc); rota `/dashboard` consumindo o
  shell com KPIs e tabela placeholder; landmarks ARIA + skip-link
  "Pular para o conteudo" + `focus-visible:ring`. Typecheck e
  `next lint` verdes (PR a abrir, issue #42).

## Concluidos

- **DS-02** — Design tokens + tema base: CSS vars para cores (paleta neutra +
  primaria azul + critica vermelha + success/warning) em light/dark,
  tipografia (Inter + JetBrains Mono via `next/font/google` com variaveis
  `--font-sans`/`--font-mono`), espacamento, radius e sombras em
  `apps/web-app/styles/tokens.css`; Tailwind estendido em
  `apps/web-app/tailwind.config.ts` mapeando os tokens; rota `/styleguide`
  (app router ignora diretorios com `_`, ajustado de `_styleguide` para
  `styleguide`) com amostras de todos os tokens; toggle light/dark
  (`components/theme-toggle.tsx`) com persistencia em `localStorage` e
  script inline anti-FOUC no `layout.tsx` (PR a abrir — Closes #41).

- **GOV-01/02/03** — Setup do monorepo (pnpm workspaces + Turborepo),
  5 ADRs iniciais e backlog completo em `docs/tasks/` com STATE.md e
  templates GitHub (PR #1).
- **GOV-07** — Workflow `.github/workflows/pr-guardrail.yml` exige
  STATE.md + CHANGELOG.md + `Closes #N` em todo PR para `main`
  (entregue junto com o setup inicial).
- **DS-01** — Bootstrap do `apps/web-app` (Next.js 14 App Router + TS
  strict, Tailwind, shadcn/ui, Lucide, Sonner) com pagina `/`
  "Hello painel" (PR #84).
- **API-01** — Bootstrap FastAPI em `apps/api/`: config via
  `pydantic-settings` (prefixo `API_`), logging JSON estruturado,
  endpoints `/health` e `/version`, Dockerfile multi-stage com usuario
  nao-root. Desbloqueia DATA-01.
- **CORE-01** — Motor ADN legado extraido de `src/` para pacote Python
  instalavel em `packages/worker-core/`; `src/` vira shim retro-compativel
  (PR #80).
- **INFRA-06** — Bucket S3 (Backblaze B2): template de lifecycle,
  `.env.example`, runbook manual e smoke test prontos; aplicacao no
  console/CLI da Backblaze e geracao da Application Key ficam a cargo
  do owner (ver `infra/s3-bucket.md` secao 2).
- **INFRA-01** — Hardening inicial da VPS Hostinger: runbook completo
  em `infra/vps-hardening.md` (usuario `deploy`, SSH chave-only, UFW,
  fail2ban, unattended-upgrades, TZ `America/Sao_Paulo`). Execucao na
  VPS real fica a cargo do owner — DoD dos checks `ssh`/`ufw`/`fail2ban`/
  `timedatectl` e validado apos aplicacao manual.
- **INFRA-03** — Runbook de DNS no Cloudflare em `infra/dns.md`: tabela
  de registros A para `app`/`api`/`ops`/`www`/apex com DNS-only
  obrigatorio em `api` e `ops` (preservar mTLS das prefeituras — ADR-003),
  passos via UI + API, checks `dig` e plano de migracao quando o nome
  comercial sair. Aplicacao na zona real (owner) — DoD valida apos
  propagacao.
- **DOCS-01** — Termos de Uso criado em `docs/legal/terms.md`, incluindo
  clausula de retencao de 90 dias (ADR-003), pagamento/renovacao/cancelamento,
  limitacao de responsabilidade, foro/legislacao e orientacao de referencia
  para signup e rota `/legal` do app/site (PR #81).
- **DOCS-02** — Politica de Privacidade (LGPD) publicada em
  `docs/legal/privacy.md` + RoPA minima em `docs/legal/ropa.md` (PR #87).
- **DOCS-03** — Runbook de credencial invalida criado em
  `docs/runbooks/credencial-invalida.md` e linkado no ticket APP-06 para
  uso inline nas ocorrencias `CERT_EXPIRED`, `CRED_INVALID` e
  `CERT_REVOKED` (PR #88).
- **DOCS-04** — Runbook de incidentes para indisponibilidade de portal
  e rate-limit documentado em `docs/runbooks/portal-indisponivel.md`
  (triagem, backoff, comunicacao e criterio de status page) (PR #89).
- **GOV-06** — CI base: workflow `.github/workflows/ci.yml` com jobs
  `lint-python` (ruff), `test-python` (pytest), `lint-ts` (eslint +
  typecheck) em todo PR e push em `main`; cache pip + pnpm;
  `ruff.toml` conservador na raiz. `test-ts` (vitest) fica como TODO
  ate o primeiro spec em `apps/web-app`. Branch protection com os
  checks `lint-python`, `test-python`, `lint-ts` obrigatorios em
  `main` precisa ser habilitada manualmente no GitHub (owner).

## Proximas Destravadas (prontas para iniciar)

- **INFRA-03** — DNS dos subdominios no Cloudflare (`app`, `api`, `ops`,
  `www`, apex) (issue #5).

> Nota: CORE-05, API-06, API-11 e INFRA-08 dependem de INFRA-06 **e**
> de outros tickets (CORE-01 / API-05 / DATA-05 / INFRA-05), portanto
> continuam bloqueados ate que essas dependencias sejam concluidas.

## Bloqueadas

- **SITE-00..10** — aguardando definicao do nome comercial.

## Limite de WIP

Maximo **4 tarefas** em "Em Andamento" simultaneamente.

## Pendencias de Decisao

| Item | Prazo sugerido | Bloqueia |
|------|----------------|----------|
| Nome comercial / dominio definitivo | antes da Fase 7 | Trilha SITE inteira |
| Gateway de pagamento (Asaas/Stripe/Iugu) | antes do primeiro cliente pago | API de billing |

## Ultima atualizacao

- Data: 2026-04-14
- PR: (a abrir) — DS-03: `<AppShell>` (sidebar colapsavel + topbar com
  breadcrumbs, tenant switcher, bell, theme toggle e user menu) e rota
  `/dashboard` consumindo o shell. Move DS-03 para "Em Andamento".
- Autor: @LevyOliveirabr
- Nota: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` em todo PR para main.

## Links Rapidos

- Backlog completo: `docs/tasks/`
- Como usar os tickets: `docs/tasks/README.md`
- ADRs: `docs/adrs/`
- Contribuicao: `CONTRIBUTING.md`
