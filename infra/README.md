# Infra

Scripts, configs e documentacao de infraestrutura.

## Estrutura futura

- `compose/` — arquivos Docker Compose (base + obs + overrides).
- `nginx/` — server blocks e configs.
- `scripts/` — backup, restore, deploy helpers.
- `vps-docker.md` — instalacao Docker (INFRA-02).
- `dns.md` — configuracao DNS (INFRA-03).
- `backup.md` — politica de backup (INFRA-08).

## Arquivos existentes

- `vps-hardening.md` — runbook de hardening da VPS Hostinger (INFRA-01).
- `s3-bucket.md` + `s3-lifecycle.json` + `scripts/s3-smoke-test.sh` —
  bucket S3 Backblaze B2 (INFRA-06).

Inicializado em GOV-01; conteudo preenchido pelos tickets INFRA-*.
