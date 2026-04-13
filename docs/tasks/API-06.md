# API-06 — Upload /company_credentials com cifra AES-GCM

- **Trilha:** api
- **Tamanho:** L
- **Status:** blocked (aguarda API-05 + INFRA-06)
- **Depende de:** API-05, INFRA-06

## Objetivo

Endpoint seguro para upload de PFX. Extracao de fingerprint/validade,
cifra AES-256-GCM, upload do blob cifrado no S3, senha cifrada em
coluna separada.

## Entregaveis

- `POST /companies/{id}/credential` (multipart: `pfx` + `password`).
- Modulo `api/crypto.py`:
  - KEK via env (validar em boot).
  - HKDF para derivar DEK por tenant.
  - `encrypt(plaintext, tenant_id) -> ciphertext`.
  - `decrypt(ciphertext, tenant_id) -> plaintext`.
- Validacao: PFX parseia, senha correta, CN casa com CNPJ (warn se nao).
- Registra `audit_log` de upload (sem segredo).
- Endpoint `DELETE /companies/{id}/credential` revoga.

## Definition of Done

- [ ] Upload real funciona e blob cifrado aparece no S3.
- [ ] Worker consegue decifrar e usar (teste E2E simples).
- [ ] Senha e PFX nunca aparecem em logs/banco em claro.
