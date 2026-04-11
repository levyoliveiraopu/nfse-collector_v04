"""Backend de armazenamento local em disco."""

from __future__ import annotations

import logging
import os
import re

from src.storage_backend import StorageBackend

logger = logging.getLogger(__name__)


class LocalUploader(StorageBackend):
    """Salva arquivos em estrutura de pastas local."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def salvar_cliente(
        self,
        cnpj: str,
        razao_social: str,
        periodo: str,
        lista_xmls: list[tuple[str, bytes]],
        excel_bytes: bytes,
    ) -> None:
        nome_cliente = _normalizar_nome(f"{cnpj} - {razao_social}")
        pasta_destino = os.path.join(self.base_dir, nome_cliente, periodo)
        os.makedirs(pasta_destino, exist_ok=True)

        nome_excel = f"NFSe_{cnpj}_{periodo}.xlsx"
        caminho_excel = os.path.join(pasta_destino, nome_excel)
        with open(caminho_excel, "wb") as f:
            f.write(excel_bytes)

        for nome_xml, conteudo_xml in lista_xmls:
            caminho_xml = os.path.join(pasta_destino, _normalizar_nome(nome_xml))
            with open(caminho_xml, "wb") as f:
                f.write(conteudo_xml)

        logger.info(
            "Arquivos salvos localmente em '%s' (Excel + %d XML(s)).",
            pasta_destino,
            len(lista_xmls),
        )


def _normalizar_nome(valor: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", valor).strip()
