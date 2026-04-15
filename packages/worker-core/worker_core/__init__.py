"""worker-core — motor de coleta NFS-e ADN Nacional.

Pacote extraido de `src/` pela tarefa CORE-01 (lift-and-shift).
Refactor funcional acontece nos tickets CORE-02/03/04 e a integracao
com S3 em CORE-05.
"""

from worker_core.fetcher import buscar_todos_dfe_novos as fetch_nfse
from worker_core.nsu_tracker import FileNsuSource, InMemoryNsuSource, NsuSource
from worker_core.storage import (
    S3Settings,
    S3StorageClient,
    StorageError,
    UploadResult,
    export_object_key,
    xml_object_key,
)

__version__ = "0.1.0"

__all__ = [
    "fetch_nfse",
    "NsuSource",
    "InMemoryNsuSource",
    "FileNsuSource",
    "S3StorageClient",
    "S3Settings",
    "UploadResult",
    "StorageError",
    "xml_object_key",
    "export_object_key",
    "__version__",
]
