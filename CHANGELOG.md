# Changelog

Formato: uma linha por PR mergeado em `main`.
Segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added
- GOV-01: estrutura do monorepo (pnpm workspaces + Turborepo).
- GOV-02: 5 ADRs iniciais (monolito modular, RLS, storage 90d, billing adiado, deploy compose).
- GOV-03: backlog completo em `docs/tasks/` + templates GitHub + STATE.md.
- GOV-07: workflow `pr-guardrail` exige STATE.md + CHANGELOG.md + `Closes #N` para mergear em main.
- INFRA-06: bucket S3 (Backblaze B2) — template de lifecycle (`infra/s3-lifecycle.json`), variaveis `S3_*` em `config/.env.example`, smoke test (`infra/scripts/s3-smoke-test.sh`) e runbook em `infra/s3-bucket.md` (criacao de conta/key e aplicacao das rules ficam manuais).
- DOCS-04: runbook de incidentes para `PORTAL_5XX`, `PORTAL_TIMEOUT` e `RATE_LIMIT` com triagem, backoff, comunicação ao cliente e critério de status page (`docs/runbooks/portal-indisponivel.md`).

### Changed
- CORE-01: motor ADN legado extraido de `src/` para pacote Python instalavel em `packages/worker-core/` (modulos `auth`, `fetcher`, `nsu_tracker`, `batch_processor`, `excel_builder`, `storage_backend`, `local_uploader`, `gdrive_uploader`, `noop_uploader`); `src/` vira shim fino retro-compativel. `main.py` e testes existentes preservados. `pip install -e packages/worker-core` habilita `from worker_core import fetch_nfse`.
