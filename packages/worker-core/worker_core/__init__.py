"""worker-core — motor de coleta NFS-e ADN Nacional.

Pacote extraido de `src/` pela tarefa CORE-01 (lift-and-shift).
Refactor funcional entregue em CORE-02 (PFX em memoria), CORE-03
(NSU via callback) e CORE-04 (callback de progresso por item).
"""

from worker_core.collector import FetchSummary, NfseItem, fetch_nfse
from worker_core.nsu_tracker import FileNsuSource, InMemoryNsuSource, NsuSource

__version__ = "0.1.0"

__all__ = [
    "fetch_nfse",
    "NfseItem",
    "FetchSummary",
    "NsuSource",
    "InMemoryNsuSource",
    "FileNsuSource",
    "__version__",
]
