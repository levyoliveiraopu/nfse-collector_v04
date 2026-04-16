# Infra

Scripts, configs e documentacao de infraestrutura.

## Estrutura futura

- `compose/` — arquivos Docker Compose (base + obs + overrides).
- `scripts/` — backup, restore, deploy helpers.
- `backup.md` — politica de backup (INFRA-08).

## Arquivos existentes

- `vps-hardening.md` — runbook de hardening da VPS Hostinger (INFRA-01).
- `vps-docker.md` — Docker Engine + Compose v2 na VPS (INFRA-02).
- `vps-docker.md` — instalacao Docker Engine + Compose v2 + arvore
  `/srv/nfse/{prod,staging}/...` (INFRA-02).
- `dns.md` — configuracao DNS no Cloudflare (INFRA-03).
- `compose/docker-compose.base.yml` + `compose/.env.example` +
  `compose/README.md` — stack base com Postgres 16 e Redis 7, volumes
  persistentes, healthchecks e politica manual de backup (INFRA-05).
- `vps-docker.md` — instalacao Docker Engine + Compose v2 (INFRA-02).
- `dns.md` — configuracao DNS no Cloudflare (INFRA-03).
- `nginx.md` + `nginx/` — Nginx no host + Let's Encrypt (INFRA-04):
  runbook manual e configs versionadas (snippets TLS/headers/rate-limit,
  server blocks por subdominio, placeholder "em breve").
- `s3-bucket.md` + `s3-lifecycle.json` + `scripts/s3-smoke-test.sh` —
  bucket S3 Backblaze B2 (INFRA-06).
- `observability.md` + `compose/docker-compose.obs.yml` +
  `compose/{loki,promtail,grafana}/...` + `nginx/ops.conf.example` —
  stack Loki/Grafana/Promtail/Uptime Kuma exposta em `ops.<DOMINIO>`
  (INFRA-07).
- `backup.md` + `scripts/backup-postgres.sh` +
  `scripts/restore-postgres.sh` + `systemd/nfse-backup-postgres@.{service,timer}` —
  backup diario do Postgres com `pg_dump -Fc`, cifra age, upload para
  S3 (dailies 30d / monthlies 365d), script de restore e drill em
  staging (INFRA-08).

Inicializado em GOV-01; conteudo preenchido pelos tickets INFRA-*.
