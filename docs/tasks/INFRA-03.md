# INFRA-03 — DNS dos subdominios no Cloudflare

- **Trilha:** infra
- **Tamanho:** S
- **Status:** ready (paraleliza com INFRA-01/02)
- **Depende de:** nada (dominio temporario ja contratado)

## Objetivo

Apontar subdominios para a VPS.

## Entregaveis

- Zona DNS configurada no Cloudflare com registros A para:
  - `app.<dominio>`
  - `api.<dominio>`
  - `ops.<dominio>`
  - `www.<dominio>`
  - `<dominio>` (apex)
- Proxy Cloudflare: **DNS only** (nuvem cinza) para `api` e `ops`
  (evita MITM no mTLS do ADN — importante).
- Proxy ativo (nuvem laranja) permitido para `app`, `www`, apex.
- `infra/dns.md` documenta configuracao.

## Definition of Done

- [ ] `dig app.<dominio>` retorna IP da VPS.
- [ ] `api.<dominio>` e `ops.<dominio>` em DNS-only confirmado.
- [ ] Documentacao commitada.

## Notas

Quando o nome final sair, recriar registros no novo dominio e migrar.
