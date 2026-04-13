"""worker-core — motor de coleta NFS-e ADN Nacional.

Pacote extraido de `src/` pela tarefa CORE-01 (lift-and-shift).
Refactor funcional acontece nos tickets CORE-02/03/04.
"""

from worker_core.fetcher import buscar_todos_dfe_novos as fetch_nfse

__version__ = "0.1.0"

__all__ = ["fetch_nfse", "__version__"]
