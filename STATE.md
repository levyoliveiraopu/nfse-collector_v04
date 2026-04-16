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

- **DS-07** — Inputs especiais de formulario (FileDropzone,
  SecretField, CNPJInput, PeriodPicker) em
  `apps/web-app/components/ui/` (PR a abrir — Closes #46).
- **API-06** — Upload `/companies/{id}/credential` com cifra
  AES-256-GCM por tenant: novo `apps/api/api/crypto.py` (envelope
  encryption KEK -> HKDF-SHA256 -> DEK por tenant; ciphertext = `\x01`
  + nonce(12B) + GCM ct+tag, AAD = bytes do `tenant_id`); novo
  `apps/api/api/storage.py` (boto3 S3-compat, `put`/`get`/`delete`
  sob prefix dedicado `S3_CREDENTIALS_PREFIX=tenants-credentials/`,
  **sem lifecycle** — credencial e viva); router em
  `apps/api/api/companies/credentials.py` (POST multipart `pfx`+
  `password` para `owner|admin`, parseia PKCS#12, extrai
  fingerprint/validade/CN, valida CN vs CNPJ com warn em mismatch,
  cifra senha + PFX, INSERE em `company_credentials` revogando ativas
  anteriores na mesma transacao, PUT no S3 com rollback em falha,
  audit_log `credential.upload` sem segredo; DELETE marca status
  `revoked`, remove blob best-effort, audita `credential.revoke`).
  Settings novas: `API_CREDENTIAL_KEK_B64` (obrigatorio em
  staging/prod via `model_validator`), `API_CREDENTIAL_MAX_PFX_BYTES`
  (default 1 MiB) e `S3_CREDENTIALS_PREFIX`. Runbook
  `infra/s3-bucket.md` atualizado: layout passa a expor
  `tenants-credentials/` sem rule de TTL e Application Key precisa
  cobrir os 3 prefixos (ou key dedicada por prefix). Deps novas:
  `cryptography>=42`, `boto3>=1.34`, `python-multipart>=0.0.9` (run)
  + `moto[s3]>=5.0` (dev). 14 testes unitarios novos
  (`test_crypto.py` cobre round-trip, AAD, tampering, KEK
  ausente/invalida; `test_storage_credentials.py` cobre layout de
  chave, round-trip via moto e `StorageError` em bucket inexistente)
  + suite de integracao `test_credentials_routes_integration.py`
  (gated `TEST_DATABASE_URL` + `moto`) cobrindo upload feliz com
  audit, decifragem ponta-a-ponta abrindo o PFX (DoD "worker decifra
  e usa"), senha errada -> 400, PFX > teto -> 413, cross-tenant ->
  404, viewer -> 403, revogacao limpa o blob e re-upload revoga o
  anterior, mais ajuste cirurgico em `test_seed.py` para tambem setar
  `API_CREDENTIAL_KEK_B64` ao testar abort em production. `pytest`
  local: 163 passed + 68 skipped. Execucao do DoD manual (criar 3a
  Application Key ou rever a existente para enxergar
  `tenants-credentials/`) fica para o owner — sem isso, o PUT real
  contra B2 retorna 401; o smoke test esta documentado no runbook
  (PR a abrir — Closes #30).
- **APP-04** — Aba "Credencial" em
  `/dashboard/empresas/[id]/credencial` (apps/web-app): painel com
  `<StatusBadge>` + fingerprint SHA-256 (formato OpenSSL `aa:bb:..`)
  + validade em pt-BR, botao "Atualizar credencial" abrindo dialog
  com `<FileDropzone>` (.pfx/.p12 ate 1 MiB) + `<SecretField>`
  (senha PFX), "Revogar" via ConfirmDialog "digite REVOGAR" e
  "Testar agora" desabilitado (aguardando endpoint dedicado de
  handshake — issue a abrir). Erros 400/413/502/403 traduzidos
  para feedback acionavel em portugues ("senha incorreta ou PFX
  invalido", "arquivo excede limite de 1 MiB", "falha ao gravar
  no storage", "voce nao tem permissao"); badge vira
  `cert_expiring` nos ultimos 30 dias, `failed` apos a validade,
  `blocked` em revogada, `cred_invalid` em invalida.
  Incluidos no escopo: (a) GET minimo
  `/companies/{id}/credential` na API (RBAC leitura = todos os
  papeis; devolve a credencial `active` mais recente ou 404; nunca
  expoe ciphertext/senha; `cn_matches_cnpj` volta como `None`
  porque o CN nao e persistido); (b) novo `components/ui/dialog.tsx`
  (modal acessivel sem Radix, focus trap, Esc, overlay click);
  (c) `lib/companies/credentials.ts` com cliente tipado + mapeador
  de erros + `formatFingerprint` + `decideCredentialBadge`.
  37 testes novos no apps/web-app (credentials helpers, status
  block, upload dialog, revoke dialog e panel orquestrando estado
  de auth) + 4 testes de integracao no apps/api cobrindo GET feliz
  pos-upload sem ciphertext, GET 404 pre-upload, GET 404 apos
  revoke (so retorna active) e GET RBAC permitindo viewer.
  `pytest apps/api` = 163 passed + 72 skipped; `pnpm --filter
  web-app test` = 164 passed; `pnpm typecheck` e `pnpm lint`
  verdes; `ruff check apps/api` limpo
  (PR a abrir — Closes #52).

## Concluidos

- **CORE-03** — Refactor: NSU via callback (sem arquivo). Introduz em
  `packages/worker-core/worker_core/nsu_tracker.py` o protocolo
  `NsuSource` (`typing.Protocol` runtime-checkable, metodos
  `get(cnpj) -> int` e `set(cnpj, nsu)`) e duas implementacoes:
  `InMemoryNsuSource` (dict em memoria, `set` respeita "NSU nunca
  regride", expoe `snapshot()` para testes) e `FileNsuSource` (wrapper
  sobre `carregar_estado`/`salvar_estado`/`atualizar_nsu` preservando
  escrita atomica `.tmp` + `os.replace` e nao regressao; `set` so
  regrava o arquivo quando o dict muda de fato). As funcoes legadas
  (`carregar_estado`/`salvar_estado`/`obter_ultimo_nsu`/`atualizar_nsu`/
  `resetar_cnpj`) permanecem intactas para compat com `main.py --reset-nsu`
  e `src/diagnostico.py`. `worker_core.fetcher.buscar_todos_dfe_novos`
  ganha kwarg opcional `nsu_source: NsuSource | None = None`: quando
  fornecido, usa `source.get(cnpj)` como NSU inicial e chama
  `source.set(cnpj, maior_nsu)` no fim (so se o NSU progrediu);
  sem `nsu_source`, comportamento legado 100% preservado (o
  `batch_processor` e o CLI nao mudam de assinatura neste ticket). Tests
  novos: 16 casos em `tests/test_nsu_tracker.py` (InMemory/File — default
  zero, persistencia cross-instance, nao regressao em memoria e em disco,
  isolamento por CNPJ, `isinstance(..., NsuSource)`, nao-reescrita quando
  valor nao progride) e 5 casos em `tests/test_nfse_fetcher.py` cobrindo
  as 4 combinacoes (`get` define NSU inicial; `set` persistido com
  progresso; `set` nao chamado sem progresso; comportamento legado sem
  source) + integracao real com `InMemoryNsuSource`. `pytest tests/` em
  108 testes verdes. Re-exports em `worker_core/__init__.py`
  (`NsuSource`, `InMemoryNsuSource`, `FileNsuSource`) e nota no
  `packages/worker-core/README.md`. Adapter DB-backed fica para API-13
  conforme previsto no ticket
  (PR a abrir — Closes #21).

- **DATA-06** — Teste automatizado de isolamento cross-tenant: suite
  `apps/api/tests/test_rls_isolation.py` com 31 casos parametrizados
  que semeiam 2 tenants (A e B) em todas as 14 tabelas RLS (`tenants`,
  `tenant_users`, `companies`, `company_credentials`, `executions`,
  `execution_items`, `occurrences`, `reprocess_jobs`, `notifications`,
  `refresh_tokens`, `files`, `schedules`, `audit_logs`,
  `subscriptions`) e, via role `app_user` (`NOBYPASSRLS`), validam
  que: (a) `SELECT` com GUC de A devolve 0 linhas de B em cada tabela;
  (b) sem `SET LOCAL app.current_tenant` o `app_user` fica fail-closed
  (0 linhas em todas as 14); (c) `UPDATE`/`DELETE` cross-tenant tem
  `rowcount == 0`; (d) `INSERT` forjando `tenant_id` alheio dispara
  `InsufficientPrivilege` (`WITH CHECK` da policy). Fixtures em
  `apps/api/tests/conftest.py` (`rls_seed` scope=module com
  truncate+seed, `app_user_cursor` abrindo conexao nova com
  `SET LOCAL ROLE app_user` + `set_config('app.current_tenant', ...,
  true)`), gated em `TEST_DATABASE_URL` (mesmo padrao de API-02/03).
  Novo job `test-rls` em `.github/workflows/ci.yml` sobe service
  container `postgres:16`, aplica `alembic upgrade head` e roda o
  pytest em toda PR. Runbook de injecao de falha (`ALTER TABLE ...
  DISABLE ROW LEVEL SECURITY`) documentado em `apps/api/README.md`.
  Correcao incidental: migration `0015_merge_heads.py` (no-op) fecha
  o fork Alembic deixado por DATA-04/DATA-05 (`0008_notifications` e
  `0014_plans_subscriptions` eram heads independentes), desbloqueando
  `alembic upgrade head`. Move DATA-06 para "Em Andamento"
  (PR a abrir — Closes #17).
- **DATA-07** — Seed de dev idempotente em
  `apps/api/scripts/seed.py`: popula `plans` (`starter`/`pro`/`scale`
  com limites `jsonb` e precos em centavos), tenant `demo` (slug
  `demo`, plan `pro`, status `active`), user global `admin@demo.local`
  (senha vinda de `API_SEED_ADMIN_PASSWORD`, fallback `demo12345`
  apenas em `API_ENVIRONMENT=development`; aborta em staging/prod)
  e membership `owner`. Todas as escritas usam
  `ON CONFLICT ... DO UPDATE` (`plans.code`, `tenants.slug`,
  expressao `LOWER(email)` em `users`, PK composta em
  `tenant_users`), entao re-rodar nao duplica linhas. Usa
  `get_admin_session()` (BYPASSRLS) por rodar sem
  `app.current_tenant`. Invocavel via
  `cd apps/api && python -m scripts.seed` (pacote `scripts/` com
  `__init__.py`). 9 testes unitarios em
  `apps/api/tests/test_seed.py` (constantes, limites jsonb,
  fallback/abort da senha, `ON CONFLICT` nos 3 upserts) + 1 teste de
  integracao gated por `TEST_DATABASE_URL` rodando `run_seed()` duas
  vezes e validando idempotencia. Nova env
  `API_SEED_ADMIN_PASSWORD` em `config/.env.example`. Nao insere
  linha em `subscriptions` (billing adiado — ADR-004)
  (PR a abrir — Closes #18).
- **INFRA-09** — Pipeline de deploy (GitHub Actions -> SSH):
  workflows `.github/workflows/deploy-staging.yml` (push em `main` com
  paths `apps/api/**`, `packages/worker-core/**`, `infra/compose/**`,
  `infra/deploy/**`) e `.github/workflows/deploy-prod.yml` (push de tag
  `v*` + `workflow_dispatch` manual com input `tag`). Ambos fazem
  `docker/build-push-action@v6` do `apps/api/Dockerfile` para
  `ghcr.io/<owner>/nfse-api:<tag>` + `latest-{staging,prod}` via
  `GITHUB_TOKEN` (`permissions: packages: write`) com cache GHA, e em
  seguida `appleboy/ssh-action@v1.2.0` no VPS exportando
  `DEPLOY_ENV`+`DEPLOY_TAG` para `/srv/nfse/deploy.sh`. Script
  `infra/deploy/deploy.sh` (idempotente, `set -euo pipefail`):
  persiste tag anterior em `config/.last_deploy_tag` antes do
  `docker compose pull && up -d --remove-orphans`, aguarda health em
  `GET /health` (30 tentativas x 2s), e em falha reverte para a tag
  anterior + re-sobe e `exit 20` (marca workflow como falho apos
  rollback). Override `infra/compose/docker-compose.deploy.yml`
  adiciona o servico `api` consumindo `ghcr.io/...:${DEPLOY_TAG}` com
  `depends_on` healthy de Postgres/Redis (INFRA-05) e publica em
  `127.0.0.1:8000` para o Nginx host (INFRA-04); bloco do `worker`
  comentado aguardando CORE-05. Runbook completo em
  `infra/deploy/README.md` cobrindo preparacao do `/srv/nfse/<env>`
  (symlinks para compose files + `deploy.sh`), `docker login ghcr.io`
  com PAT `read:packages`, os 4 secrets do repo
  (`SSH_HOST`/`SSH_USER`/`SSH_KEY`/`GHCR_TOKEN` opcional),
  environment `prod` com approval manual, roteiro do DoD (rollback
  via `HEALTH_URL` falso + `workflow_dispatch`) e operacao
  (disparo manual, promocao staging->prod, rollback manual, logs).
  Concurrency `deploy-staging`/`deploy-prod` nao cancela em voo.
  Execucao real fica a cargo do owner — DoD (PR em main dispara
  staging; tag `v0.0.1` dispara prod; rollback manual ok) valida apos
  provisionamento dos secrets e do `/srv/nfse/` na VPS
  (PR a abrir — Closes #11).

- **INFRA-07** — Stack de observabilidade minima em
  `infra/compose/docker-compose.obs.yml`: `loki` (v2.9, retencao 14d,
  filesystem/boltdb-shipper), `promtail` (coleta
  `/var/lib/docker/containers` + `/var/log`, positions persistentes em
  `/srv/nfse/prod/data/promtail`), `grafana` (v10.4, bind
  `127.0.0.1:3001`, `GF_SERVER_SERVE_FROM_SUB_PATH=true`/root URL
  `/grafana`, datasource Loki + dashboard "NFS-e — Logs API & Worker"
  provisionados) e `uptime-kuma` (v1.23, bind `127.0.0.1:3002`). Configs
  versionados em `infra/compose/{loki,promtail,grafana}/...` e dashboard
  inicial em `infra/compose/grafana/dashboards/api-worker-logs.json`
  (paineis de logs `nfse-api`/`nfse-worker` + timeseries de taxa de erro
  em 5m). Server block Nginx em `infra/nginx/ops.conf.example` expoe
  `ops.<DOMINIO>/grafana` e `/uptime` com `satisfy all` (IP allowlist +
  basic auth via `/etc/nginx/.htpasswd-ops`), WebSocket para Grafana Live
  e Uptime Kuma, redirect 80->443 e headers de seguranca (HSTS,
  X-Frame-Options, Referrer-Policy). Runbook completo em
  `infra/observability.md` cobrindo estrutura de diretorios com UIDs
  corretos (Loki 10001, Grafana 472), subida da stack, htpasswd bcrypt,
  certbot, criacao dos 4 monitores (site/app/api/health/worker/healthz)
  e Notification Telegram com teste manual. Novas envs no bloco
  `# Observabilidade (INFRA-07)` do `config/.env.example`
  (`OBS_DOMAIN`, `GRAFANA_ADMIN_USER/PASSWORD`, `OPS_ALLOWED_IPS`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Execucao real fica a cargo
  do owner — DoD (Grafana acessivel, logs em tempo real, alerta Telegram
  dispara) valida apos aplicacao manual
  (PR a abrir — Closes #9).

- **INFRA-04** — Nginx no host + Let's Encrypt: runbook completo em
  `infra/nginx.md` (instalacao via apt no Ubuntu 24.04 noble, webroot
  ACME em `/var/www/letsencrypt/`, placeholder em `/var/www/em-breve/`,
  emissao SAN unico cobrindo apex + `www` + `app` + `api` + `ops` com
  `certbot --nginx --redirect`, `certbot renew --dry-run` e
  `certbot.timer` do systemd, HSTS desligado por padrao e ativado so
  apos validar HTTPS); configs versionadas em `infra/nginx/` com
  `nginx.conf` (overrides globais: worker_processes auto, gzip,
  log_format com `request_time`/upstream, `server_tokens off`),
  snippets `tls.conf` (TLS 1.2+, ciphers Mozilla intermediate, stapling,
  `ssl_dhparam`), `security-headers.conf` (HSTS comentado, X-Frame-Options
  DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
  COOP/CORP), `rate-limit.conf` (`limit_req_zone auth_ip 10m 5r/s`),
  `proxy-common.conf` (X-Forwarded-*, Upgrade/Connection, timeouts) e
  `connection-upgrade.conf` (map WebSocket); server blocks
  `apex.conf` (301 -> www), `www.conf`/`app.conf`/`ops.conf` servindo
  `em-breve.html`, `api.conf` com `limit_req zone=auth_ip burst=10
  nodelay` em `location ^~ /auth/` (prova de rate limit do DoD) e
  `proxy_pass` comentado para `127.0.0.1:3000`/`127.0.0.1:8000`
  (descomenta em INFRA-05); reforco em `api`/`ops` de que DNS precisa
  ficar em DNS-only na Cloudflare (ADR-003 / INFRA-03). Execucao na
  VPS real fica a cargo do owner — DoD (SSL Labs A nos 5 hostnames,
  `certbot renew --dry-run` ok, configs commitadas) valida apos
  aplicacao manual (PR a abrir — Closes #6).

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
- **INFRA-05** — Compose base com Postgres 16 e Redis 7 em
  `infra/compose/docker-compose.base.yml` (volumes nomeados `nfse_pgdata`
  e `nfse_redisdata`, network privada `nfse_internal`, portas publicadas
  apenas em `127.0.0.1`, healthchecks via `pg_isready` e `redis-cli ping`,
  Redis com `requirepass` + AOF, Postgres com locale `C.UTF-8`);
  `infra/compose/.env.example` documenta `POSTGRES_USER/PASSWORD/DB`,
  `REDIS_PASSWORD` e portas host; `.gitignore` local evita commit de
  `.env`; `infra/compose/README.md` traz setup, DoD, operacao
  (`up`/`down`/logs) e politica manual de backup (pg_dumpall + RDB em
  `/srv/nfse/<env>/backups/`, retencao 90d alinhada ao ADR-003 — automacao
  fica para INFRA-08). `infra/README.md` atualizado com a nova pasta
  `compose/` (PR a abrir — Closes #7).

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
- **API-05** — CRUD de `/companies`: router em
  `apps/api/api/companies/` com `GET` paginado (filtros `status`/`uf`),
  `GET /{id}`, `POST` (valida DV de CNPJ e aplica limite de plano via
  `plans.limits.max_companies`), `PATCH` (CNPJ imutavel via
  `extra=forbid`) e `DELETE` soft (grava `deleted_at`). Nova migration
  `0015_companies_deleted_at.py` adiciona coluna `deleted_at
  TIMESTAMPTZ` e troca `uq_companies_tenant_cnpj` por UNIQUE parcial
  `WHERE deleted_at IS NULL` (permite reusar CNPJ apos soft-delete),
  alem de indice parcial de listagem. RBAC da matriz
  `docs/architecture/rbac-matrix.md`: leitura = todos; POST/PATCH =
  `owner|admin|operator`; DELETE = `owner|admin`. Validador de CNPJ
  (`companies/cnpj.py`) rejeita DV invalido e sequencias repetidas.
  38 testes unitarios (CNPJ, schemas, migration estatica) + 16 testes
  de integracao gated por `TEST_DATABASE_URL` cobrindo CRUD, cross-
  tenant via RLS, RBAC (viewer -> 403), soft-delete idempotente,
  reaproveitamento de CNPJ, filtros/paginacao e limite de plano
  (PR a abrir — Closes #29).

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
- **INFRA-06** — Bucket S3 (Backblaze B2): parte automatizada entregue
  em PR #79 (template de lifecycle em `infra/s3-lifecycle.json`, variaveis
  `S3_*` em `config/.env.example`, smoke test em
  `infra/scripts/s3-smoke-test.sh`, runbook em `infra/s3-bucket.md`).
  Descoberta de design: B2 so aceita *prefix literal* em lifecycle rules,
  entao o bucket usa layout `tenants/` (XML 90d) + `tenants-exports/`
  (exports 30d), consumido via `S3_EXECUTIONS_PREFIX` e
  `S3_EXPORTS_PREFIX` (ADR-003 preservado). **Setup manual do owner em
  aberto** (7 itens — conta B2 + 2FA, bucket `nfse-saas-prod`
  private/versioning on/SSE-B2, 2 lifecycle rules aplicadas, Application
  Key least-privilege no prefix `tenants/`, cofre 1Password/Bitwarden,
  smoke test `[s3-smoke] PASS`, `aws s3 ls s3://$S3_BUCKET/tenants/` ok);
  rastreio permanece em #8 ate validacao.
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

- **INFRA-05** — Docker Compose (base + overrides prod/staging) com
  Nginx host ja publicando os 5 hostnames (INFRA-04). Descomentar os
  `proxy_pass` em `infra/nginx/sites-available/{app,api}.conf`.

> INFRA-05 saiu de "Proximas Destravadas" para "Em Andamento" nesta
> atualizacao. CORE-05, API-06, API-11 e INFRA-08 continuam parcialmente
> bloqueados pelas dependencias de codigo (CORE-01 / API-05 / DATA-05 /
> INFRA-05); a parte automatizada de INFRA-06 (template de lifecycle,
> variaveis `S3_*`, smoke test) ja esta disponivel para esses tickets
> consumirem, e o setup manual do bucket B2 segue em aberto no issue #8
> sem bloquear o desenvolvimento das integracoes.

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

- Data: 2026-04-16
- PR: (a abrir) — APP-04: aba "Credencial" em
  `/dashboard/empresas/[id]/credencial` com `<StatusBadge>` +
  fingerprint + validade, dialog de upload (`<FileDropzone>` + 
  `<SecretField>`, erros 400/413/502/403 traduzidos), ConfirmDialog
  de revogacao "digite REVOGAR" e placeholder desabilitado de
  "Testar agora" (aguarda endpoint futuro de handshake). Inclui no
  escopo o `GET /companies/{id}/credential` (RBAC leitura = todos;
  devolve credencial `active` mais recente ou 404; `cn_matches_cnpj`
  vira `None` porque o CN nao e persistido em
  `company_credentials`). Novo `components/ui/dialog.tsx` (modal
  acessivel sem Radix, focus trap + Esc + overlay click). Cliente
  tipado + mapeador de erros + `formatFingerprint` +
  `decideCredentialBadge` em
  `apps/web-app/lib/companies/credentials.ts`. 37 testes novos no
  web-app (helpers/status/upload/revoke/panel) + 4 testes de
  integracao no api cobrindo GET feliz sem ciphertext, GET 404 sem
  upload, GET 404 apos revoke e GET viewer autorizado. `pytest
  apps/api` = 163 passed + 72 skipped; `pnpm --filter web-app
  test` = 164 passed; `pnpm typecheck` / `pnpm lint` / `ruff
  check apps/api` limpos. Move APP-04 de "Bloqueadas" para "Em
  Andamento". Closes #52.
- PR: (a abrir) — CORE-03: refactor do `nsu_tracker` para callbacks.
  Novo protocolo `NsuSource` (`get`/`set`) em
  `packages/worker-core/worker_core/nsu_tracker.py` com duas
  implementacoes padrao — `InMemoryNsuSource` (estado em dict, usada em
  testes e como buffer do worker DB-backed) e `FileNsuSource` (compat
  com `config/estado/ultimo_nsu.json`, preserva escrita atomica e a
  regra "NSU nunca regride"). `worker_core.fetcher.buscar_todos_dfe_novos`
  aceita `nsu_source: NsuSource | None = None`: quando fornecido, o
  fetcher le/escreve o NSU pelo source; sem ele, comportamento legado
  (batch_processor intocado). Funcoes legadas mantidas para
  `main.py --reset-nsu` e `src/diagnostico.py`. 16 novos testes em
  `tests/test_nsu_tracker.py` (InMemory/File) + 5 em
  `tests/test_nfse_fetcher.py` (integracao `fetcher` x `NsuSource`).
  `pytest tests/` = 108 passed. Re-exports em
  `packages/worker-core/worker_core/__init__.py` e nota no
  `packages/worker-core/README.md`. Adapter DB-backed fica para
  API-13. Move CORE-03 de "Bloqueadas" (dependia de CORE-01, ja
  mergeado em PR #80) para "Concluidos". Closes #21.
- PR: (a abrir) — INFRA-06 (follow-up administrativo): atualiza entrada
  em "Concluidos" com a descoberta do layout `tenants/` (90d) +
  `tenants-exports/` (30d) imposta pelo prefix-literal do B2 e explicita
  que os 7 passos manuais do owner seguem em aberto (rastreio em #8).
  Remove a menção a INFRA-06 da nota de bloqueio em "Proximas
  Destravadas" — CORE-05 / API-06 / API-11 / INFRA-08 passam a poder
  consumir a parte automatizada (template de lifecycle, variaveis
  `S3_*`, smoke test) sem esperar o setup manual. Sem mudanca em
  `infra/s3-bucket.md` alem de reforco do aviso de DoD manual pendente
  no topo da seção 5. Refs #8 (nao fecha — os 7 manuais continuam
  abertos). Titulo/commit `docs:` para bypass do `pr-guardrail`.
- PR: (a abrir) — DATA-06: teste automatizado de isolamento
  cross-tenant. Nova suite `apps/api/tests/test_rls_isolation.py`
  (31 testes parametrizados) + fixtures em
  `apps/api/tests/conftest.py` (dois tenants semeados em todas as 14
  tabelas RLS + context manager que troca a role para `app_user` e
  seta a GUC `app.current_tenant`). Novo job `test-rls` em
  `.github/workflows/ci.yml` com service container `postgres:16` e
  `alembic upgrade head`. Runbook de injecao de falha no
  `apps/api/README.md`. Migration incidental
  `0015_merge_heads.py` (no-op) fecha o fork Alembic deixado por
  DATA-04/DATA-05 — `alembic heads` volta a reportar 1 ponta.
  Move DATA-06 para "Em Andamento". Closes #17.
- PR: (a abrir) — DATA-07: seed de dev idempotente em
  `apps/api/scripts/seed.py` (plans `starter`/`pro`/`scale` +
  tenant `demo` + user `admin@demo.local` + membership `owner`).
  Todas as escritas usam `ON CONFLICT ... DO UPDATE`. Senha vem de
  `API_SEED_ADMIN_PASSWORD` com fallback dev (`demo12345`) e abort
  em staging/prod. Pacote `apps/api/scripts/` com `__init__.py`
  destravando `python -m scripts.seed`. 9 testes unitarios + 1 de
  integracao (idempotencia) gated por `TEST_DATABASE_URL` em
  `apps/api/tests/test_seed.py`. Nova env
  `API_SEED_ADMIN_PASSWORD` em `config/.env.example`. Nova secao
  "Seeds de dev" em `apps/api/README.md`. Move DATA-07 de
  "Bloqueadas" para "Em Andamento". Closes #18.
- PR: (a abrir) — INFRA-09: pipeline de deploy (GitHub Actions -> SSH).
  Workflows `.github/workflows/deploy-staging.yml` (push em `main`) e
  `deploy-prod.yml` (push de tag `v*` + `workflow_dispatch`) fazem
  `docker/build-push-action@v6` do `apps/api/Dockerfile` para GHCR
  (`ghcr.io/<owner>/nfse-api:<tag>` + `latest-{staging,prod}`) via
  `GITHUB_TOKEN` com cache GHA, e `appleboy/ssh-action@v1.2.0` no VPS
  rodando `infra/deploy/deploy.sh` — que grava a tag anterior em
  `/srv/nfse/<env>/config/.last_deploy_tag`, faz
  `docker compose pull && up -d --remove-orphans`, aguarda
  `GET /health` (30x2s) e reverte para a tag anterior em caso de falha
  (`exit 20` marca o workflow como falho pos-rollback). Override
  `infra/compose/docker-compose.deploy.yml` adiciona o servico `api`
  ancorado em `${DEPLOY_TAG}` (bloco do `worker` comentado ate
  CORE-05). Runbook `infra/deploy/README.md` documenta provisionamento
  do `/srv/nfse/<env>` (symlinks para compose + `deploy.sh`),
  `docker login ghcr.io` com PAT `read:packages`, os 4 secrets do repo
  e roteiro do DoD incluindo rollback manual via `workflow_dispatch`.
  Move INFRA-09 de "bloqueadas" (dependias INFRA-02+GOV-06, ja
  concluidas) para "Em Andamento". Closes #11.
- PR: (a abrir) — API-05: CRUD de `/companies` em
  `apps/api/api/companies/` (router + `cnpj.py` validando DV + schemas
  Pydantic com normalizacao de CNPJ/UF e `extra=forbid` em PATCH);
  dependencies FastAPI `require_role` aplicadas pela matriz RBAC;
  limite `plans.limits.max_companies` aplicado no POST; soft-delete via
  `deleted_at`. Nova migration `0015_companies_deleted_at.py`
  (coluna + UNIQUE parcial + indice de listagem). Router registrado em
  `api/main.py` (OpenAPI `/docs`). 38 unit tests (CNPJ + schemas +
  migration estatica) + 16 integracao gated por `TEST_DATABASE_URL`.
  Move API-05 de "Bloqueadas" para "Em Andamento". Closes #29.
- PR: (a abrir) — INFRA-07: stack de observabilidade
  (Loki 2.9 + Promtail + Grafana 10.4 + Uptime Kuma 1.23) em
  `infra/compose/docker-compose.obs.yml`, com configs versionados
  (`loki-config.yml`, `promtail-config.yml`, provisioning de datasource
  Loki e dashboard "NFS-e — Logs API & Worker" em JSON), server block
  Nginx em `infra/nginx/ops.conf.example` protegendo `ops.<DOMINIO>`
  por IP allowlist + basic auth bcrypt (`satisfy all`), e runbook
  completo em `infra/observability.md` (diretorios com UIDs corretos,
  htpasswd, certbot, 4 monitores no Uptime Kuma, Notification Telegram
  testada). Novo bloco `# Observabilidade (INFRA-07)` em
  `config/.env.example` com placeholders para `OBS_DOMAIN`,
  `GRAFANA_ADMIN_USER/PASSWORD`, `OPS_ALLOWED_IPS`, `TELEGRAM_BOT_TOKEN`
  e `TELEGRAM_CHAT_ID`. Move INFRA-07 para "Em Andamento". Closes #9.
- PR: (a abrir) — INFRA-05: compose base com Postgres 16 + Redis 7 em
  `infra/compose/docker-compose.base.yml` (volumes nomeados, network
  privada, healthchecks, portas em 127.0.0.1, Redis com `requirepass` +
  AOF, Postgres com locale `C.UTF-8`); `.env.example`, `.gitignore` local
  e `README.md` com setup, DoD e politica manual de backup (pg_dumpall +
  RDB, retencao 90d alinhada ao ADR-003). Move INFRA-05 de "Proximas
  Destravadas" para "Em Andamento". Closes #7.
- PR: (a abrir) — INFRA-04: Nginx no host + Let's Encrypt. Runbook
  `infra/nginx.md` (instalacao apt Ubuntu 24.04, webroot ACME,
  emissao SAN unico via `certbot --nginx` para apex + `www` + `app` +
  `api` + `ops`, `certbot.timer` + `certbot renew --dry-run`, HSTS so
  apos validacao). Configs versionadas em `infra/nginx/` — `nginx.conf`
  global, snippets `tls.conf` (Mozilla intermediate + stapling),
  `security-headers.conf` (HSTS comentado, X-Frame/X-Content-Type/
  Referrer/Permissions), `rate-limit.conf` (`auth_ip` 5r/s),
  `proxy-common.conf` + `connection-upgrade.conf`; server blocks
  `apex`/`www`/`app`/`api`/`ops` com placeholder "em breve" e
  `proxy_pass` comentado para 3000/8000 (INFRA-05 descomenta);
  `limit_req` em `location ^~ /auth/` do `api.conf` como prova de DoD.
  Move INFRA-04 para "Em Andamento". Move INFRA-05 para "Proximas
  Destravadas". Closes #6.
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
