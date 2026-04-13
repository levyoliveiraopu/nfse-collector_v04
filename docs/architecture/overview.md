# Visao Geral da Arquitetura

## Componentes

```
[ Usuario ] --HTTPS--> [ Nginx (TLS LE) ]
                        |
        +---------------+---------------------+
        v               v                     v
  site.<dom>       app.<dom>             api.<dom>
  (Next.js SSG)    (Next.js SSR/CSR)     (FastAPI)
                                             |
                 +---------------------------+
                 v                           v
            [ PostgreSQL ]             [ Redis ]
                 ^                           ^
                 |                           |
                 +-------- [ Worker ] -------+
                              |
                              v
                        [ worker-core ]  --->  [ S3-compat ]
```

## Decisoes chave

Ver `docs/adrs/` para racional de:

- Monolito modular Python + Next.js (ADR-001)
- Multi-tenant single-DB com RLS (ADR-002)
- Storage S3 + retencao 90d sem arquivamento (ADR-003)
- Billing adiado (ADR-004)
- Deploy Docker Compose em VPS Hostinger (ADR-005)

## Diagramas

Espaco reservado para:

- `dataflow.png` — Fluxo de uma execucao (API -> Redis -> Worker -> S3/DB).
- `rbac-matrix.png` — Permissoes por role.
- `db-erd.png` — ERD (exportado de dbdiagram.io em GOV-02/DATA-01).
