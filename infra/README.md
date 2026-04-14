# Infra

Scripts, configs e documentacao de infraestrutura.

## Estrutura futura

- `compose/` — arquivos Docker Compose (base + obs + overrides).
- `nginx/` — server blocks e configs.
- `scripts/` — backup, restore, deploy helpers.
- `vps-docker.md` — instalacao Docker (INFRA-02).
- `backup.md` — politica de backup (INFRA-08).

## Arquivos existentes

- `vps-hardening.md` — runbook de hardening da VPS Hostinger (INFRA-01).
- `vps-docker.md` — instalacao Docker Engine + Compose v2 + arvore
  `/srv/nfse/{prod,staging}/...` (INFRA-02).
- `dns.md` — configuracao DNS no Cloudflare (INFRA-03).
- `compose/docker-compose.base.yml` + `compose/.env.example` +
  `compose/README.md` — stack base com Postgres 16 e Redis 7, volumes
  persistentes, healthchecks e politica manual de backup (INFRA-05).
- `s3-bucket.md` + `s3-lifecycle.json` + `scripts/s3-smoke-test.sh` —
  bucket S3 Backblaze B2 (INFRA-06).

Inicializado em GOV-01; conteudo preenchido pelos tickets INFRA-*.
