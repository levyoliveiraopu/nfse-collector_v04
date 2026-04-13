# CORE-03 — Refactor: NSU via callback (sem arquivo)

- **Trilha:** worker
- **Tamanho:** M
- **Status:** blocked (aguarda CORE-01)
- **Depende de:** CORE-01

## Objetivo

`nsu_tracker` deixa de ler/escrever arquivo. Torna-se interface
abstrata que recebe callbacks `get_last_nsu()` e `update_last_nsu()`.

## Entregaveis

- `worker_core/nsu_tracker.py` expondo protocolo:
  ```
  class NsuSource(Protocol):
      def get(self, cnpj: str) -> int: ...
      def set(self, cnpj: str, nsu: int) -> None: ...
  ```
- Implementacao `InMemoryNsuSource` para testes.
- Implementacao `FileNsuSource` para compat com o legado.
- Adapter que sera usado pelo worker (DB-backed) definido em API-13,
  nao aqui.

## Definition of Done

- [ ] Protocolo + 2 implementacoes + testes.
- [ ] Fetcher aceita NsuSource injetado.
