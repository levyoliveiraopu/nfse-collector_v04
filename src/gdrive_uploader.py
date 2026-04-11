"""
Integração com o Google Drive via Service Account.

Este módulo autentica com uma Service Account, organiza os arquivos em
subpastas por cliente e competência, e faz upload (ou substituição) dos
relatórios Excel e XMLs das NFS-e.

Estrutura de pastas gerada no Drive:
    [pasta raiz]/
    └── {cnpj} - {razao_social}/
        └── {AAAA-MM}/
            ├── NFSe_{cnpj}_{AAAA-MM}.xlsx
            ├── nfse_{chave_acesso_1}.xml
            └── ...

Pré-requisito: a Service Account deve ter permissão de Editor na pasta raiz
compartilhada, ou a pasta deve ser de propriedade dela.
"""

import logging
import os
from io import BytesIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from src.storage_backend import StorageBackend

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]

_MIMETYPE_PASTA  = "application/vnd.google-apps.folder"
_MIMETYPE_XML    = "application/xml"
_MIMETYPE_EXCEL  = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


# ---------------------------------------------------------------------------
# Função 1: inicializar_drive
# ---------------------------------------------------------------------------

def inicializar_drive(credentials_path: str):
    """Autentica via Service Account e retorna o service do Google Drive.

    Args:
        credentials_path: Caminho para o arquivo JSON de credenciais da
                          Service Account.

    Returns:
        Objeto ``service`` da API Google Drive v3, pronto para uso.

    Raises:
        FileNotFoundError: Se o arquivo de credenciais não existir.
        google.auth.exceptions.MutualTLSChannelError: Falha de autenticação.
    """
    credenciais = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=_SCOPES
    )
    delegated_user = os.getenv("GOOGLE_DELEGATED_USER_EMAIL", "").strip()
    if delegated_user:
        credenciais = credenciais.with_subject(delegated_user)
        logger.info(
            "Google Drive com Domain-Wide Delegation habilitada (usuário delegado: %s).",
            delegated_user,
        )

    service = build("drive", "v3", credentials=credenciais, cache_discovery=False)
    logger.debug(
        "Service Google Drive inicializado com credenciais de '%s'.",
        credentials_path,
    )
    return service


# ---------------------------------------------------------------------------
# Função 2: criar_ou_encontrar_pasta
# ---------------------------------------------------------------------------

def criar_ou_encontrar_pasta(service, nome: str, parent_id: str) -> str:
    """Retorna o ID de uma pasta dentro de ``parent_id``, criando-a se necessário.

    A busca é feita por nome exato dentro do pai informado, excluindo itens
    na lixeira. Isso garante idempotência: execuções repetidas não geram
    pastas duplicadas.

    Args:
        service:   Service autenticado (retornado por ``inicializar_drive``).
        nome:      Nome exato da pasta a buscar ou criar.
        parent_id: ID da pasta pai onde a busca/criação ocorre.

    Returns:
        ID (str) da pasta encontrada ou recém-criada.

    Raises:
        googleapiclient.errors.HttpError: Em caso de erro na API do Drive.
    """
    query = (
        f"name='{_escapar_query(nome)}'"
        f" and '{parent_id}' in parents"
        f" and mimeType='{_MIMETYPE_PASTA}'"
        f" and trashed=false"
    )

    resposta = (
        service.files()
        .list(q=query, fields="files(id, name)", spaces="drive")
        .execute()
    )
    arquivos = resposta.get("files", [])

    if arquivos:
        pasta_id = arquivos[0]["id"]
        logger.debug("Pasta encontrada: '%s' (id=%s).", nome, pasta_id)
        return pasta_id

    # Criar nova pasta
    metadata = {
        "name": nome,
        "mimeType": _MIMETYPE_PASTA,
        "parents": [parent_id],
    }
    pasta = service.files().create(body=metadata, fields="id").execute()
    pasta_id = pasta["id"]
    logger.info("Pasta criada: '%s' (id=%s) em parent=%s.", nome, pasta_id, parent_id)
    return pasta_id


# ---------------------------------------------------------------------------
# Função 3: upload_ou_substituir
# ---------------------------------------------------------------------------

def upload_ou_substituir(
    service,
    nome_arquivo: str,
    conteudo: bytes,
    mimetype: str,
    pasta_id: str,
) -> str:
    """Faz upload de um arquivo, substituindo-o caso já exista na pasta.

    Se um arquivo com o mesmo nome já existir (e não estiver na lixeira),
    seu conteúdo é atualizado mantendo o mesmo ID do Drive. Caso contrário,
    um novo arquivo é criado.

    Usa tenacity para retry automático em caso de erro HTTP 429 (quota
    excedida) ou erros de transporte transitórios.

    Args:
        service:       Service autenticado.
        nome_arquivo:  Nome do arquivo a criar/substituir.
        conteudo:      Conteúdo do arquivo como bytes.
        mimetype:      MIME type do arquivo (``_MIMETYPE_XML`` ou ``_MIMETYPE_EXCEL``).
        pasta_id:      ID da pasta de destino no Drive.

    Returns:
        ID (str) do arquivo no Drive (existente ou recém-criado).

    Raises:
        googleapiclient.errors.HttpError: Para erros HTTP não recuperáveis
                                          após esgotar as tentativas.
    """
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=5, max=60),
        retry=retry_if_exception(_e_erro_quota_ou_transporte),
    )
    def _executar() -> str:
        media = MediaIoBaseUpload(BytesIO(conteudo), mimetype=mimetype, resumable=False)

        # Verificar se já existe arquivo com esse nome na pasta
        query = (
            f"name='{_escapar_query(nome_arquivo)}'"
            f" and '{pasta_id}' in parents"
            f" and trashed=false"
        )
        resposta = (
            service.files()
            .list(q=query, fields="files(id, name)", spaces="drive")
            .execute()
        )
        existentes = resposta.get("files", [])

        if existentes:
            arquivo_id = existentes[0]["id"]
            service.files().update(
                fileId=arquivo_id,
                media_body=media,
            ).execute()
            logger.debug(
                "Arquivo atualizado: '%s' (id=%s).", nome_arquivo, arquivo_id
            )
            return arquivo_id

        # Criar novo arquivo
        metadata = {"name": nome_arquivo, "parents": [pasta_id]}
        arquivo = (
            service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        arquivo_id = arquivo["id"]
        logger.debug(
            "Arquivo criado: '%s' (id=%s).", nome_arquivo, arquivo_id
        )
        return arquivo_id

    return _executar()


class GDriveUploader(StorageBackend):
    """Backend de armazenamento usando Google Drive."""

    def __init__(self, service, root_folder_id: str):
        self.service = service
        self.root_folder_id = root_folder_id

    def salvar_cliente(
        self,
        cnpj: str,
        razao_social: str,
        periodo: str,
        lista_xmls: list[tuple[str, bytes]],
        excel_bytes: bytes,
    ) -> None:
        ano_str, mes_str = periodo.split("-", maxsplit=1)
        organizar_e_enviar_cliente(
            self.service,
            self.root_folder_id,
            cnpj,
            razao_social,
            int(ano_str),
            int(mes_str),
            lista_xmls,
            excel_bytes,
        )


# ---------------------------------------------------------------------------
# Função 4: organizar_e_enviar_cliente
# ---------------------------------------------------------------------------

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
    """Organiza e envia os arquivos de um cliente no Google Drive.

    Cria (ou reutiliza) a hierarquia de pastas abaixo de ``root_folder_id``,
    faz upload do Excel e de cada XML das NFS-e.

    Hierarquia criada::

        [root_folder_id]/
        └── {cnpj} - {razao_social}/
            └── {AAAA-MM}/
                ├── NFSe_{cnpj}_{AAAA-MM}.xlsx
                ├── nfse_{chave_1}.xml
                └── ...

    Args:
        service:        Service autenticado (``inicializar_drive``).
        root_folder_id: ID da pasta raiz compartilhada no Drive.
        cnpj:           CNPJ de 14 dígitos do prestador (sem formatação).
        razao_social:   Razão social do prestador.
        ano:            Ano de competência.
        mes:            Mês de competência (1–12).
        lista_xmls:     Lista de tuplas ``(nome_arquivo, conteudo_bytes)``
                        para cada XML de NFS-e.
        excel_bytes:    Conteúdo do relatório Excel como bytes.
    """
    periodo = f"{ano:04d}-{mes:02d}"
    nome_cliente = f"{cnpj} - {razao_social}"
    nome_excel   = f"NFSe_{cnpj}_{periodo}.xlsx"

    logger.info(
        "Iniciando envio ao Drive — cliente='%s' | período=%s | XMLs=%d",
        nome_cliente,
        periodo,
        len(lista_xmls),
    )

    # 1. Pasta do cliente
    pasta_cliente_id = criar_ou_encontrar_pasta(service, nome_cliente, root_folder_id)

    # 2. Subpasta do mês
    pasta_mes_id = criar_ou_encontrar_pasta(service, periodo, pasta_cliente_id)

    # 3. Upload do Excel
    arquivo_excel_id = upload_ou_substituir(
        service,
        nome_arquivo=nome_excel,
        conteudo=excel_bytes,
        mimetype=_MIMETYPE_EXCEL,
        pasta_id=pasta_mes_id,
    )
    logger.info("Excel enviado: '%s' (id=%s).", nome_excel, arquivo_excel_id)

    # 4. Upload dos XMLs
    total = len(lista_xmls)
    for i, (nome_xml, conteudo_xml) in enumerate(lista_xmls, start=1):
        arquivo_xml_id = upload_ou_substituir(
            service,
            nome_arquivo=nome_xml,
            conteudo=conteudo_xml,
            mimetype=_MIMETYPE_XML,
            pasta_id=pasta_mes_id,
        )
        logger.info(
            "XML enviado (%d/%d): '%s' (id=%s).",
            i,
            total,
            nome_xml,
            arquivo_xml_id,
        )

    logger.info(
        "Envio concluído — cliente='%s' | período=%s | Excel + %d XML(s).",
        nome_cliente,
        periodo,
        total,
    )


# ---------------------------------------------------------------------------
# Auxiliares privados
# ---------------------------------------------------------------------------

def _escapar_query(valor: str) -> str:
    """Escapa aspas simples em valores usados em queries da API Drive."""
    return valor.replace("\\", "\\\\").replace("'", "\\'")


def _e_erro_quota_ou_transporte(exc: BaseException) -> bool:
    """Retorna True se a exceção for elegível para retry (429 ou transporte)."""
    if isinstance(exc, HttpError):
        return exc.resp.status in (429, 500, 502, 503, 504)
    # Erros de transporte (ConnectionError, TimeoutError, etc.)
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))
