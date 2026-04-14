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

- **DS-06** — Componente `<DataTable>` server-side em
  `apps/web-app/components/ui/data-table/` baseado em TanStack Table +
  `@tanstack/react-query`: paginacao/ordenacao/filtragem manuais, estado
  preservado em `searchParams` (prefixo configuravel), filtros texto/
  select/date-range com draft local aplicado via botao/Enter, saved
  filters por tabela em `localStorage` (chave `dt:<queryKey>`), export
  CSV do resultado atual (RFC 4180 + BOM UTF-8), estados loading
  (skeleton rows), vazio e erro com "Tentar novamente". `AppQueryClient
  Provider` em `apps/web-app/components/providers/query-client-provider.tsx`
  wrappando o `RootLayout`. Demo com 10k linhas mockadas no `/styleguide`
  (`app/styleguide/data-table-demo.tsx` — dataset deterministico via
  Mulberry32, fetcher simulando latencia). Testes vitest: `csv.test.ts`
  (10 casos), `url-state.test.ts` (8 casos, roundtrip parse<->serialize)
  e `data-table.test.tsx` (5 casos — skeleton/vazio/linhas/erro+retry/
  paginacao chamando router.replace). Typecheck, lint e 56 testes verdes.
  Novas deps `@tanstack/react-table` e `@tanstack/react-query`
  (PR a abrir — Closes #45).
- **CORE-02** — Refactor `packages/worker-core/worker_core/auth.py` para
  aceitar PFX em memoria: novo context manager
  `mtls_session(pfx_bytes, pfx_password)` carrega o PFX direto dos bytes
  (vindo do banco cifrado — ADR-003), materializa cert PEM + key PEM em
  tmpfs (`/dev/shm`, fallback `tempfile.gettempdir()`) com `0o600` e
  garante remocao dos dois PEMs no `finally` (sucesso ou excecao);
  `certificate` exposto via `session.nfse_certificate`. Legado
  `criar_session_cliente(path, senha)` mantido como wrapper de compat
  (batch_processor e diagnostico nao mudam). Mensagens de erro sem path/
  senha/bytes quando o PFX vem de memoria. Testes em `tests/test_auth.py`
  (11 novos): fixture gera PFX self-signed em memoria via
  `cryptography.hazmat.primitives.serialization.pkcs12.serialize_key_and_certificates`;
  cobre sucesso, limpeza em excecao, senha errada, PFX vazio/nao-bytes,
  certificado vencido, ausencia de vazamento em logs (`caplog`),
  confirmacao de tmpfs e wrapper legacy. `pytest tests/` = 79 passed
  (PR a abrir — Closes #20).

- **APP-01** — Paginas de auth: `/login`, `/signup`, `/recuperar-senha`,
  `/redefinir-senha/[token]` e `/aceitar-convite/[token]` em
  `apps/web-app/app/(auth)/`; `<AuthProvider>` em
  `apps/web-app/components/auth/` com access token em memoria + refresh
  automatico; refresh token em cookie httpOnly gerenciado pelos Route
  Handlers `apps/web-app/app/api/auth/{signup,login,refresh,logout}/`
  (proxy fino para a API FastAPI — compensa API-02 devolver o refresh no
  body). `/dashboard` protegido por `<RequireAuth>`; user menu faz logout
  de verdade. Spec Playwright em `apps/web-app/e2e/auth.spec.ts`
  (signup->dashboard + refresh automatico) com `page.route` mockando
  `/api/auth/*` — roda local via `pnpm --filter web-app test:e2e`.
  Novas envs `NEXT_PUBLIC_API_BASE_URL` e `API_BASE_URL` em
  `config/.env.example`. Novas deps `zod`, `react-hook-form`,
  `@hookform/resolvers`, `@playwright/test`. Stubs de UI para
  recuperar/redefinir/aceitar-convite (backend correspondente ainda nao
  existe — endpoints a entregar em ticket API futuro).
  (PR a abrir — Closes #49).

- **DATA-02** — Schema de `companies` + `company_credentials`:
  migrations `0002_companies.py` (CNPJs por tenant, unique
  `(tenant_id, cnpj)`, RLS) e `0003_company_credentials.py` (PFX A1
  cifrado, FK composta `(tenant_id, company_id) -> companies`, indice
  em `cert_not_after` para alerta de vencimento, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em `apps/api/tests/`
  e runbook manual de isolamento cross-tenant em `apps/api/README.md`
  (PR a abrir — Closes #13).
- **DATA-05** — Schema das tabelas de suporte do MVP: migrations
  `0011_files.py` (sem `storage_tier` por ADR-003; tambem merge dos
  dois heads Alembic `0003_company_credentials` + `0010_auth_refresh_tokens`),
  `0012_schedules.py` (cron por tenant/company, FK composta, indice
  `(enabled, next_run_at)`), `0013_audit_logs.py` (bigserial, indice
  `(tenant_id, created_at DESC)`, metadata jsonb), e
  `0014_plans_subscriptions.py` (catalogo `plans` sem RLS +
  `subscriptions` com RLS; promove `tenants.plan_id` a FK ->
  `plans.code`). Testes estaticos em `apps/api/tests/test_migration_0011..0014.py`
  e teste de insercao massiva (10k rows) em
  `tests/test_audit_logs_bulk.py` (pulado sem `TEST_DATABASE_URL`)
  (PR a abrir — Closes #16).
- **DATA-03** — Schema de `executions` + `execution_items`:
  migrations `0004_executions.py` (uma corrida de coleta por
  tenant+company com FK composta para `companies`, indice
  `(tenant_id, company_id, started_at DESC)`, CHECKs de
  `trigger`/`status`/ordem do periodo/soma de itens, RLS) e
  `0005_execution_items.py` (um item por NFS-e processada com FK
  composta para `executions`, indices `(execution_id)` e
  `(tenant_id, data_emissao)`, indice unico parcial
  `(tenant_id, chave_nfse) WHERE chave_nfse IS NOT NULL`, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em
  `apps/api/tests/test_migration_0004.py` e `test_migration_0005.py`;
  runbook manual de isolamento cross-tenant + EXPLAIN verde da query
  de listagem por periodo em `apps/api/README.md`
  (PR a abrir — Closes #14).
- **API-03** — Middleware de tenant (GUC para RLS): dependencies
  `get_current_claims` / `assert_tenant_active` / `get_tenant_db` em
  `apps/api/api/deps.py`; endpoint `GET /auth/me` como prova de vida
  (RLS-gated count em `tenant_users`); 15 testes unitarios e 6 de
  integracao (gated por `TEST_DATABASE_URL`) em
  `apps/api/tests/test_tenant_middleware*.py`; runbook manual em
  `apps/api/README.md`. Tenant inexistente/`suspended`/`canceled` ->
  403; token ausente/invalido -> 401 com `WWW-Authenticate: Bearer`
  (PR a abrir — Closes #27).
- **API-04** — RBAC (owner/admin/operator/viewer): dependency
  `require_role(*allowed, min_role=None)` em
  `apps/api/api/security/rbac.py`, encadeando `assert_tenant_active`
  (API-03) e devolvendo 403 claro quando o papel nao e autorizado;
  guarda pura `ensure_can_manage_member` protegendo `owner` (apenas
  outro owner remove/rebaixa owner; admin nao promove acima do proprio
  papel) para uso pelos endpoints de membros a chegar; matriz completa
  em `docs/architecture/rbac-matrix.md` cobrindo tenant, membros,
  companies, executions e auditoria; 31 testes unitarios em
  `apps/api/tests/test_rbac.py` incluindo prova de DoD (viewer -> 403
  em `POST /_probe/companies` via router efemero e `require_role(min_role="owner")`
  somente permitindo owner). (PR a abrir — Closes #28).
- **DATA-04** — Schema de tabelas operacionais:
  migrations `0006_occurrences.py` (ocorrencias por tenant com FKs
  compostas para `companies` e `executions`, FK nullable para
  `users.assignee_user_id`, CHECKs de `severity`/`status`/ordem de
  `first_seen_at`/`last_seen_at`, RLS), `0007_reprocess_jobs.py`
  (jobs de reprocessamento com `scope jsonb`, `result_execution_ids
  text[]`, CHECK de `status`, RLS) e `0008_notifications.py`
  (outbox multicanal com `payload jsonb`, CHECKs de
  `channel`/`status`, indice parcial para pendentes, RLS) em
  `apps/api/alembic/versions/`. Testes estaticos em
  `apps/api/tests/test_migration_000{6,7,8}.py`
  (PR a abrir — Closes #15).

## Concluidos

- **DATA-01** — Schema inicial de identidade: Alembic configurado em
  `apps/api/alembic/`, migration `0001_initial_identity.py` cria
  extensao `pgcrypto`, roles `app_admin` (BYPASSRLS) / `app_user`
  (NOBYPASSRLS), tabelas `tenants`, `users`, `tenant_users`, RLS +
  politicas em `tenants` e `tenant_users` via GUC `app.current_tenant`
  (PR #95). Desbloqueia DATA-02..DATA-07.
  (PR a abrir, issue #12).
- **API-02** — Auth: signup + login + JWT refresh rotativo. Endpoints
  `/auth/signup|login|refresh|logout` em `apps/api/api/auth/`, hash
  argon2id (`api/security/password.py`), JWT access 15min HS256
  (`api/security/jwt.py`), refresh opaco 7d com rotacao e detecao de
  reuso via `replaced_by` (`api/security/tokens.py`), rate limit
  slowapi 5/min/IP no login, migration `0010_auth_refresh_tokens.py`
  com RLS por tenant. Testes unitarios (argon2/JWT/hash) e E2E com
  `TEST_DATABASE_URL` opcional (PR a abrir, issue #26).
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

- **DS-05** — Componente `KPIStatCard` em
  `apps/web-app/components/ui/kpi-stat-card.tsx` (props `title`, `value`,
  `deltaPercent?`, `trendData?`, `icon?`, `state?`, `hint?`,
  `errorMessage?`): card com valor grande, delta colorido (success/
  destructive/muted com seta Lucide), mini-sparkline via SVG inline
  (sem Recharts — evita dep extra e `use client` obrigatorio) e estados
  `ready`/`loading` (skeleton)/`empty` (valor `—`)/`error`
  (AlertTriangle + mensagem). Demo no `/styleguide` com 7 cards (4 em
  `ready` + loading/empty/error) via `app/styleguide/kpi-stat-card-demo.tsx`;
  `app/dashboard/page.tsx` refatorado para consumir o componente.
  Spec `components/ui/kpi-stat-card.test.tsx` com 7 snapshots cobrindo
  ready (sem delta/sparkline, delta positivo, delta negativo, delta
  zero), loading, empty e error, mais asserts de `aria-label`,
  `aria-busy` e de que `trendData` com <2 pontos nao renderiza a
  sparkline. Typecheck e `next lint` verdes (PR a abrir — Closes #44).

- **DS-04** — Componente `StatusBadge` (10 variantes) em
  `apps/web-app/components/ui/status-badge.tsx` com `variant`
  (`success`, `processing`, `pending`, `failed`, `warning`, `blocked`,
  `cert_expiring`, `cred_invalid`, `portal_unstable`, `reprocess_needed`)
  + `size` (`sm`, `md`), icone Lucide por variante e tooltip via
  atributo `title` nativo. Demo no styleguide em
  `apps/web-app/app/styleguide/status-badge-demo.tsx`. Bootstrap de
  vitest + jsdom + `@testing-library/react`/`jest-dom` (primeiro spec
  do `apps/web-app`, destrava o TODO de `test-ts` do GOV-06) com
  `vitest.config.ts` / `vitest.setup.ts` e suite de snapshot cobrindo
  as 10 variantes x 2 tamanhos (20 snapshots) + comportamento de
  override de label/tooltip e `hideIcon` (PR a abrir — Closes #43).

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
- **INFRA-02** — Docker Engine + Compose v2 + diretorios padrao:
  runbook em `infra/vps-docker.md` (repo oficial `download.docker.com`,
  `docker-ce` + `buildx` + `compose-plugin`, `deploy` no grupo `docker`,
  log-driver `json-file` com rotacao 10m/3 e `live-restore`, arvore
  `/srv/nfse/{prod,staging}/{data,backups,logs,config}` com owner
  `deploy:deploy` e mode `0750`). Execucao na VPS real fica a cargo do
  owner — DoD (`docker compose version` >= 2.20, `docker ps` sem sudo,
  permissoes dos diretorios) validado apos aplicacao manual.
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
- PR: (a abrir) — DS-06: componente `<DataTable>` server-side em
  `apps/web-app/components/ui/data-table/` (TanStack Table + react-query)
  com paginacao/ordenacao/filtragem manuais, filtros texto/select/date-
  range, saved filters em localStorage, export CSV (RFC 4180 + BOM UTF-8),
  estados loading/vazio/erro+retry e preservacao de estado em
  `searchParams`. `AppQueryClientProvider` no `RootLayout`. Demo no
  `/styleguide` com 10k linhas mockadas. 23 novos testes vitest
  (csv/url-state/component). Novas deps `@tanstack/react-table` e
  `@tanstack/react-query`. Move DS-06 de "Bloqueadas" (dependia de DS-02,
  ja concluido) para "Em Andamento". Closes #45.
- PR: (a abrir) — API-04: RBAC com dependency `require_role`
  (`apps/api/api/security/rbac.py`) encadeando `assert_tenant_active`
  e devolvendo 403 claro; guarda `ensure_can_manage_member`
  protegendo owner (admin nao remove/rebaixa owner; promocao limitada
  pelo papel do ator); matriz de permissoes em
  `docs/architecture/rbac-matrix.md`; 31 testes em
  `apps/api/tests/test_rbac.py` cobrindo viewer -> 403 ao criar
  empresa via router efemero + guardas de membros. Move API-04 de
  "Bloqueadas" para "Em Andamento". Closes #28.
- PR: (a abrir) — CORE-02: refactor de `worker_core/auth.py` para aceitar
  PFX em memoria. Novo `mtls_session(pfx_bytes, pfx_password)` como
  context manager grava PEM em `/dev/shm` (fallback `tempfile.gettempdir()`)
  com `0o600` e garante cleanup em sucesso/excecao; `certificate` exposto
  em `session.nfse_certificate`. `criar_session_cliente(path, senha)`
  vira wrapper de compat (batch_processor e diagnostico intocados).
  11 novos testes em `tests/test_auth.py` com PFX gerado em memoria
  (sucesso, cleanup em excecao, senha errada, cert vencido, nao-vazamento
  em logs, tmpfs). Move CORE-02 para "Em Andamento". Closes #20.
- PR: (a abrir) — DATA-04: migrations `0006_occurrences`
  (FKs compostas para `companies` e `executions`, FK nullable para
  `users` em `assignee_user_id`, CHECKs de severity/status/ordem
  first_seen/last_seen, RLS), `0007_reprocess_jobs` (`scope jsonb`,
  `result_execution_ids text[]`, CHECK de status, RLS) e
  `0008_notifications` (`payload jsonb`, CHECKs de channel/status,
  indice parcial para pendentes, RLS) + testes estaticos. Move
  DATA-04 de "Bloqueadas" para "Em Andamento". Closes #15.
- PR: (a abrir) — DATA-05: migrations `0011_files`, `0012_schedules`,
  `0013_audit_logs` e `0014_plans_subscriptions` (sem `storage_tier`
  em `files` por ADR-003; merge dos dois heads Alembic em `0011`;
  promocao de `tenants.plan_id` a FK `-> plans.code`). RLS em `files`,
  `schedules`, `audit_logs`, `subscriptions`. Testes estaticos +
  insercao massiva (10k rows) em `audit_logs` atras de
  `TEST_DATABASE_URL`. Move DATA-05 para "Em Andamento". Closes #16.
- PR: (a abrir) — APP-01: paginas de auth (`/login`, `/signup`,
  `/recuperar-senha`, `/redefinir-senha/[token]`,
  `/aceitar-convite/[token]`) + `<AuthProvider>` com access em memoria
  e refresh automatico; Route Handlers `/api/auth/*` proxiam a API e
  guardam o refresh em cookie httpOnly; `/dashboard` protegido por
  `<RequireAuth>`; spec Playwright local; envs
  `NEXT_PUBLIC_API_BASE_URL`/`API_BASE_URL` em `config/.env.example`.
  Move APP-01 de "Bloqueadas" para "Em Andamento". Closes #49.
- PR: (a abrir) — API-03: middleware de tenant via dependencies FastAPI
  (`get_current_claims`/`assert_tenant_active`/`get_tenant_db`) em
  `apps/api/api/deps.py`, reusa `get_tenant_session` para `SET LOCAL
  app.current_tenant` sem vazamento de GUC no pool; `GET /auth/me` como
  prova de vida RLS-gated; 15 testes unitarios + 6 de integracao
  (gated por `TEST_DATABASE_URL`); runbook manual de isolamento
  cross-tenant no `apps/api/README.md`. Move API-03 para "Em Andamento".
- PR: (a abrir) — API-02: autenticacao completa em
  `apps/api/api/auth/` (signup/login/refresh/logout), argon2id, JWT
  access 15min + refresh opaco 7d com rotacao e detecao de reuso,
  migration `0010_auth_refresh_tokens` com RLS, rate limit slowapi no
  login. Move API-02 de "Proximas Destravadas" para "Em Andamento".
- PR: (a abrir) — DATA-02: migrations `0002_companies` e
  `0003_company_credentials` com RLS por tenant, unique
  `(tenant_id, cnpj)`, FK composta `(tenant_id, company_id)` e indice
  em `cert_not_after`. Tambem move DATA-01 de "Em Andamento" para
  "Concluidos" com referencia ao PR #95 (mergeado em main).
- PR: (a abrir) — DATA-03: migrations `0004_executions` (FK composta
  para `companies`, indice `(tenant_id, company_id, started_at DESC)`,
  CHECKs de trigger/status/periodo/soma, RLS) e
  `0005_execution_items` (FK composta para `executions`, indice
  unico parcial em `(tenant_id, chave_nfse)`, RLS). Move DATA-03 de
  "Proximas Destravadas" para "Em Andamento". Closes #14.
- PR: (a abrir) — INFRA-02: runbook `infra/vps-docker.md` instalando
  Docker Engine + Compose v2 pelo repo oficial, adicionando `deploy` ao
  grupo `docker`, fixando log-rotation em `/etc/docker/daemon.json` e
  criando `/srv/nfse/{prod,staging}/{data,backups,logs,config}` com
  owner `deploy:deploy` e mode `0750`. Move INFRA-02 para "Concluidos".
- PR: (a abrir) — DS-03: `<AppShell>` (sidebar colapsavel + topbar com
  breadcrumbs, tenant switcher, bell, theme toggle e user menu) e rota
  `/dashboard` consumindo o shell. Move DS-03 para "Em Andamento".
- PR: (a abrir) — DS-05: componente `KPIStatCard` com estados
  `ready`/`loading`/`empty`/`error`, delta colorido e mini-sparkline
  em SVG inline; demo com 7 cards no `/styleguide` e refactor do
  `/dashboard` para usar o componente; spec com 7 snapshots + asserts
  de acessibilidade. Closes #44.
- PR: (a abrir) — DS-04: componente `StatusBadge` com 10 variantes
  + tamanhos `sm`/`md` em `apps/web-app/components/ui/status-badge.tsx`,
  demo no `/styleguide` e primeiro spec (vitest + RTL) do `apps/web-app`
  cobrindo 20 snapshots (10 variantes x 2 tamanhos). Closes #43.
- Autor: @LevyOliveirabr
- Nota: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` em todo PR para main.

## Links Rapidos

- Backlog completo: `docs/tasks/`
- Como usar os tickets: `docs/tasks/README.md`
- ADRs: `docs/adrs/`
- Contribuicao: `CONTRIBUTING.md`
