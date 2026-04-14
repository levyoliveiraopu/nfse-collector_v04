# Infra

Scripts, configs e documentacao de infraestrutura.

## Estrutura futura

- `compose/` — arquivos Docker Compose (base + obs + overrides).
- `scripts/` — backup, restore, deploy helpers.
- `backup.md` — politica de backup (INFRA-08).

## Arquivos existentes

- `vps-hardening.md` — runbook de hardening da VPS Hostinger (INFRA-01).
- `vps-docker.md` — instalacao Docker Engine + Compose v2 (INFRA-02).
- `dns.md` — configuracao DNS no Cloudflare (INFRA-03).
- `nginx.md` + `nginx/` — Nginx no host + Let's Encrypt (INFRA-04):
  runbook manual e configs versionadas (snippets TLS/headers/rate-limit,
  server blocks por subdominio, placeholder "em breve").
- `s3-bucket.md` + `s3-lifecycle.json` + `scripts/s3-smoke-test.sh` —
  bucket S3 Backblaze B2 (INFRA-06).

Inicializado em GOV-01; conteudo preenchido pelos tickets INFRA-*.
