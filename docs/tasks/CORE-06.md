# CORE-06 — Smoke test E2E com CNPJ real

- **Trilha:** worker
- **Tamanho:** L
- **Status:** blocked (aguarda CORE-02..05)
- **Depende de:** CORE-02, CORE-03, CORE-04, CORE-05

## Objetivo

Validar que o `worker-core` refatorado funciona fim-a-fim contra o
ADN real, usando 1 CNPJ de teste com PFX valido.

## Entregaveis

- Script CLI `packages/worker-core/scripts/smoke.py` que:
  - Recebe PFX por path + senha via env var.
  - Consulta 1 CNPJ, 7 dias recentes.
  - Faz upload de cada XML para bucket de teste.
  - Imprime resumo ao final.
- Documentacao de como rodar em `packages/worker-core/README.md`.

## Definition of Done

- [ ] Smoke rodado com 1 CNPJ real.
- [ ] XML aparece no bucket com object key correto.
- [ ] Sem dados sensiveis em logs (revisao manual).
