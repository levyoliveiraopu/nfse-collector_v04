# CORE-01 — Extrair pacote worker-core a partir de src/

- **Trilha:** worker
- **Tamanho:** L
- **Status:** ready
- **Depende de:** GOV-01

## Objetivo

Migrar o motor ADN legado (`src/auth.py`, `src/nfse_fetcher.py`,
`src/nsu_tracker.py`, `src/batch_processor.py`) para um pacote Python
instalavel, sem quebrar o uso atual do coletor.

## Pre-requisitos

- `src/` atual funcional (nao tocar no comportamento).
- Python 3.11+ disponivel.

## Entregaveis

- `packages/worker-core/` com:
  - `pyproject.toml` (build: hatchling ou poetry).
  - `worker_core/` pacote com modulos: `auth.py`, `fetcher.py`,
    `nsu_tracker.py`, `batch_processor.py`, `excel_builder.py`.
  - Importavel: `from worker_core import fetch_nfse`.
- `src/` vira shim fino que importa de `worker_core` (retro-compat
  com `main.py`).
- README do pacote em `packages/worker-core/README.md`.
- Sem mudanca de API neste ticket (refactor "lift and shift" apenas).

## Definition of Done

- [ ] `pip install -e packages/worker-core` funciona.
- [ ] `python main.py --dry-run` (fluxo legado) ainda funciona.
- [ ] Testes existentes em `tests/` continuam passando.

## Notas

Refactor funcional (credenciais por arg, callback de progresso,
NSU sem disco) acontece em CORE-02/03/04 — **nao** neste ticket.
