# DOCS-03 — Runbook: credencial invalida

- **Trilha:** docs
- **Tamanho:** S
- **Status:** ready
- **Depende de:** nada

## Objetivo

Runbook consultavel inline em ocorrencias `CERT_EXPIRED`,
`CRED_INVALID`, `CERT_REVOKED`.

## Entregaveis

- `docs/runbooks/credencial-invalida.md` com:
  - Sintomas.
  - Causas comuns (expirou, foi revogado, senha mudou, CN incorreto).
  - Acoes do cliente (atualizar PFX).
  - Acoes do suporte.
  - Como verificar (comandos openssl para validacao local).

## Definition of Done

- [ ] Runbook linkado em APP-06 (ocorrencias).
