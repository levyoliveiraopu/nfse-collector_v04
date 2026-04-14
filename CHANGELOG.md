# Changelog

Formato: uma linha por PR mergeado em `main`.
Segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added
- DS-03: `<AppShell>` em `apps/web-app/components/app-shell/` (sidebar colapsavel 256px/64px em desktop e drawer em <1024px, topbar fixa com breadcrumbs derivados de `usePathname`, tenant switcher placeholder, bell de notificacoes, theme toggle e user menu); dropdowns leves sem Radix (fecham em click-outside e Esc); rota `/dashboard` com layout que envolve children no shell + pagina de exemplo com KPIs e tabela placeholder; landmarks ARIA (`aside`/`header`/`main`/`nav`), skip-link "Pular para o conteudo" e `focus-visible:ring` em elementos interativos.
- DATA-01: Alembic configurado em `apps/api/alembic/` + migration `0001_initial_identity.py` criando extensao `pgcrypto`, roles `app_admin` (BYPASSRLS) / `app_user` (NOBYPASSRLS), tabelas `tenants`, `users` e `tenant_users`, indices (`LOWER(email)` unico, `(tenant_id, role)`, `(user_id)`) e RLS com politicas em `tenants` e `tenant_users` via GUC `app.current_tenant`; `API_DATABASE_URL` em `config/.env.example`.
- GOV-06: workflow `.github/workflows/ci.yml` com jobs `lint-python` (ruff), `test-python` (pytest), `lint-ts` (eslint + typecheck) em todo PR e push em `main`; cache pip/pnpm; `ruff.toml` conservador na raiz (regras E/F/W, E501 ignorada, isort desligado).
- DOCS-03: runbook de credencial invalida em `docs/runbooks/credencial-invalida.md` e link no APP-06 para ocorrencias `CERT_EXPIRED`, `CRED_INVALID` e `CERT_REVOKED`.
- GOV-01: estrutura do monorepo (pnpm workspaces + Turborepo).
- GOV-02: 5 ADRs iniciais (monolito modular, RLS, storage 90d, billing adiado, deploy compose).
- GOV-03: backlog completo em `docs/tasks/` + templates GitHub + STATE.md.
- GOV-07: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` para mergear em main.
- INFRA-06: bucket S3 (Backblaze B2) — template de lifecycle (`infra/s3-lifecycle.json`), variaveis `S3_*` em `config/.env.example`, smoke test (`infra/scripts/s3-smoke-test.sh`) e runbook em `infra/s3-bucket.md` (criacao de conta/key e aplicacao das rules ficam manuais).
- DOCS-01: Termos de Uso em `docs/legal/terms.md`, com clausula de retencao de 90 dias e diretriz de referencia no signup e em `/legal`.
- DOCS-02: politica de privacidade LGPD em `docs/legal/privacy.md` + RoPA minima em `docs/legal/ropa.md`.
- DOCS-04: runbook de incidentes para `PORTAL_5XX`, `PORTAL_TIMEOUT` e `RATE_LIMIT` com triagem, backoff, comunicação ao cliente e critério de status page (`docs/runbooks/portal-indisponivel.md`).
- INFRA-01: runbook de hardening da VPS Hostinger em `infra/vps-hardening.md` (usuario `deploy`, SSH chave-only, UFW, fail2ban, unattended-upgrades, TZ `America/Sao_Paulo`).
- API-01: bootstrap FastAPI em `apps/api/` com config via `pydantic-settings` (prefixo `API_`), logging JSON estruturado, endpoints `/health` e `/version`, Dockerfile multi-stage com usuario nao-root.
- DS-01: bootstrap do `apps/web-app` com Next.js 14 App Router + TS strict, Tailwind, shadcn/ui, Lucide, Sonner e pagina `/` "Hello painel" (PR #84).

### Changed
- CORE-01: motor ADN legado extraido de `src/` para pacote Python instalavel em `packages/worker-core/` (modulos `auth`, `fetcher`, `nsu_tracker`, `batch_processor`, `excel_builder`, `storage_backend`, `local_uploader`, `gdrive_uploader`, `noop_uploader`); `src/` vira shim fino retro-compativel. `main.py` e testes existentes preservados. `pip install -e packages/worker-core` habilita `from worker_core import fetch_nfse`.
