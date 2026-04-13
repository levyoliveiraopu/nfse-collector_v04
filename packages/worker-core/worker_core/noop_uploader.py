"""
Backend de armazenamento "noop" (sem persistência).

Este módulo mantém a mesma interface do backend de upload para permitir
execução do pipeline sem gravar ou enviar arquivos.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

_MIMETYPE_PASTA = "application/vnd.google-apps.folder"
_MIMETYPE_XML = "application/xml"
_MIMETYPE_EXCEL = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def inicializar_drive(credentials_path: str):
    """Inicializa backend noop (não usa credenciais externas)."""
    logger.info(
        "STORAGE_BACKEND=noop ativo — nenhum upload será realizado "
        "(credentials_path='%s').",
        credentials_path,
    )
    return {"backend": "noop"}


def criar_ou_encontrar_pasta(service, nome: str, parent_id: str) -> str:
    """Retorna ID sintético de pasta sem criar nada externamente."""
    _ = service
    pasta_id = f"noop-folder-{hashlib.md5(f'{parent_id}/{nome}'.encode()).hexdigest()[:10]}"  # noqa: S324
    logger.info(
        "[noop] Pasta simulada: nome='%s' parent='%s' -> id='%s'.",
        nome,
        parent_id,
        pasta_id,
    )
    return pasta_id


def upload_ou_substituir(
    service,
    nome_arquivo: str,
    conteudo: bytes,
    mimetype: str,
    pasta_id: str,
) -> str:
    """Registra no log os metadados do arquivo e retorna ID sintético."""
    _ = service
    arquivo_id = f"noop-file-{hashlib.md5(f'{pasta_id}/{nome_arquivo}'.encode()).hexdigest()[:10]}"  # noqa: S324
    logger.info(
        "[noop] Upload simulado: arquivo='%s' bytes=%d mimetype='%s' pasta='%s'.",
        nome_arquivo,
        len(conteudo),
        mimetype,
        pasta_id,
    )
    return arquivo_id


def organizar_e_enviar_cliente(
    service,
    root_folder_id: str,
    cnpj: str,
    razao_social: str,
    ano: int,
    mes: int,
    lista_xmls: list[tuple[str, bytes]],
    excel_bytes: bytes,
) -> None:
    """Simula organização e upload, registrando nomes e contagens."""
    periodo = f"{ano:04d}-{mes:02d}"
    nome_cliente = f"{cnpj} - {razao_social}"
    nome_excel = f"NFSe_{cnpj}_{periodo}.xlsx"

    logger.info(
        "[noop] Cliente='%s' período=%s | excel='%s' | xml_qtd=%d.",
        nome_cliente,
        periodo,
        nome_excel,
        len(lista_xmls),
    )
    logger.info(
        "[noop] XMLs: %s",
        ", ".join(nome_xml for nome_xml, _ in lista_xmls) if lista_xmls else "(nenhum)",
    )

    pasta_cliente_id = criar_ou_encontrar_pasta(service, nome_cliente, root_folder_id)
    pasta_mes_id = criar_ou_encontrar_pasta(service, periodo, pasta_cliente_id)
    upload_ou_substituir(
        service,
        nome_arquivo=nome_excel,
        conteudo=excel_bytes,
        mimetype=_MIMETYPE_EXCEL,
        pasta_id=pasta_mes_id,
    )
    for nome_xml, conteudo_xml in lista_xmls:
        upload_ou_substituir(
            service,
            nome_arquivo=nome_xml,
            conteudo=conteudo_xml,
            mimetype=_MIMETYPE_XML,
            pasta_id=pasta_mes_id,
        )
