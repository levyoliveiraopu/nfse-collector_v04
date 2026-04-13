# DATA-02 — Schema: companies + company_credentials

- **Trilha:** data
- **Tamanho:** M
- **Status:** blocked (aguarda DATA-01)
- **Depende de:** DATA-01

## Objetivo

Tabelas que representam cada CNPJ e sua credencial PFX cifrada.

## Entregaveis

- Migration `0002_companies.py`:
  - `companies` (id, tenant_id, cnpj, razao_social, nome_fantasia,
    municipio_ibge, uf, status, last_nsu, last_success_at,
    portal_provider, notes, timestamps).
  - Unico `(tenant_id, cnpj)`.
- Migration `0003_company_credentials.py`:
  - `company_credentials` (id, tenant_id, company_id, type,
    pfx_object_key, pfx_password_ciphertext, cert_fingerprint,
    cert_not_before, cert_not_after, status, last_used_at,
    last_tested_at, timestamps).
  - Indice em `cert_not_after` (alerta de vencimento).
- RLS ativada em ambas.

## Definition of Done

- [ ] Migrations sobem/descem limpas.
- [ ] FK para `tenants` e `companies` validadas.
- [ ] Teste RLS cross-tenant verde.
