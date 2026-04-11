"""Contratos de armazenamento para saídas de coleta."""

from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """Contrato mínimo para persistência de arquivos por cliente."""

    def salvar_cliente(
        self,
        cnpj: str,
        razao_social: str,
        periodo: str,
        lista_xmls: list[tuple[str, bytes]],
        excel_bytes: bytes,
    ) -> None:
        """Persiste arquivos do cliente para um período."""
