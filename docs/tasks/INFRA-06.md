# INFRA-06 — Bucket S3 (Backblaze B2 primeiro)

- **Trilha:** infra
- **Tamanho:** S
- **Status:** ready (paraleliza)
- **Depende de:** nada

## Objetivo

Provisionar bucket de objetos com lifecycle e credenciais minimas.

## Entregaveis

- Conta Backblaze B2 criada.
- Bucket `nfse-saas-prod` (nome pode mudar se colidir).
- Application Key com permissao apenas neste bucket
  (least privilege: read/write/list no prefix `tenants/`).
- Lifecycle rules:
  - Objetos sob `tenants/*/executions/*.xml`: expirar em 90 dias (delete).
  - Objetos sob `tenants/*/exports/*`: expirar em 30 dias.
- Bucket versioning **on**.
- Endpoint e keyID/keySecret gravados no cofre local (1Password/Bitwarden).
- `infra/storage.md` documenta o setup.

## Definition of Done

- [ ] `aws s3 ls s3://<bucket>/` funciona com a key restrita.
- [ ] Lifecycle rules visiveis no console.
- [ ] Documentacao commitada (sem segredos).
