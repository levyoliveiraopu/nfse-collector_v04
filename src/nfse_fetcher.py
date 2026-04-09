"""
Consulta à API ADN do Sistema Nacional NFS-e e extração de documentos fiscais.

Este módulo é responsável por:
  - Buscar lotes de DFe (Documentos Fiscais Eletrônicos) a partir de um NSU.
  - Paginar automaticamente até esgotar os documentos disponíveis.
  - Filtrar documentos por competência (ano/mês) a partir do XML.
  - Extrair campos estruturados da NFS-e.

A autenticação mTLS é realizada externamente pelo módulo auth.py, que fornece
a requests.Session já configurada com o certificado do cliente.

BASE URL de produção: https://adn.nfse.gov.br/contribuintes
Endpoint: GET /nfse/DFe/{UltimoNSU}?cnpjConsulta={CNPJ}
"""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://adn.nfse.gov.br/contribuintes"


class _RateLimitError(Exception):
    """Exceção interna para sinalizar HTTP 429 ao tenacity."""

# Namespaces conhecidos da NFS-e Nacional (tentados em ordem)
_NAMESPACES_NFSE = [
    "http://www.sped.fazenda.gov.br/nfse",
    "http://www.abrasf.org.br/nfse.v2.01.xsd",
    "http://www.abrasf.org.br/nfse.v1.00.xsd",
    "",  # sem namespace
]

# Campos de data de emissão tentados em ordem
_CAMPOS_DATA_EMISSAO = ["dhEmi", "dtEmissao", "dEmi", "DataEmissao", "dataEmissao"]


# ---------------------------------------------------------------------------
# Função 1: buscar_lote_dfe
# ---------------------------------------------------------------------------

def buscar_lote_dfe(session: requests.Session, ultimo_nsu: int, cnpj: str) -> dict:
    """Consulta um lote de DFe a partir do NSU informado.

    Faz GET em /nfse/DFe/{ultimo_nsu}?cnpjConsulta={cnpj} e retorna o JSON
    da resposta. Utiliza tenacity para retry automático em caso de timeout ou
    erro de conexão. HTTP 429 provoca espera de 60 segundos antes de nova
    tentativa.

    Args:
        session:     requests.Session com mTLS configurado (via auth.py).
        ultimo_nsu:  NSU a partir do qual a consulta deve ser feita.
        cnpj:        CNPJ de 14 dígitos do contribuinte (sem formatação).

    Returns:
        Dicionário com a resposta JSON da API ADN, contendo ao menos os
        campos ``maxNSU`` e a lista de documentos do lote.

    Raises:
        requests.HTTPError: Para erros HTTP não recuperáveis (4xx exceto 429,
                            5xx após esgotamento das tentativas).
        requests.Timeout:   Após esgotamento das tentativas de retry.
        requests.ConnectionError: Após esgotamento das tentativas de retry.
    """
    url = f"{_BASE_URL}/nfse/DFe/{ultimo_nsu}"
    params = {"cnpjConsulta": cnpj}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(
            (requests.Timeout, requests.ConnectionError, _RateLimitError)
        ),
    )
    def _executar_requisicao() -> dict:
        logger.debug(
            "GET %s | CNPJ=%s | NSU=%d", url, cnpj, ultimo_nsu
        )
        resposta = session.get(url, params=params)

        if resposta.status_code == 429:
            logger.warning(
                "HTTP 429 (rate limit) para CNPJ=%s NSU=%d — retry via tenacity.",
                cnpj,
                ultimo_nsu,
            )
            raise _RateLimitError(
                f"HTTP 429 para CNPJ={cnpj} NSU={ultimo_nsu}"
            )

        if resposta.status_code == 200:
            return resposta.json()

        if resposta.status_code == 404:
            # Nenhum documento encontrado a partir deste NSU
            logger.debug(
                "HTTP 404 para CNPJ=%s NSU=%d — nenhum documento disponível.",
                cnpj,
                ultimo_nsu,
            )
            return {"maxNSU": ultimo_nsu, "loteNfse": []}

        resposta.raise_for_status()
        return resposta.json()  # inalcançável, mas satisfaz o type checker

    return _executar_requisicao()


# ---------------------------------------------------------------------------
# Função 2: buscar_todos_dfe_novos
# ---------------------------------------------------------------------------

def buscar_todos_dfe_novos(
    session: requests.Session,
    cnpj: str,
    ultimo_nsu_salvo: int,
    rate_limit_delay: int,
) -> tuple[list[dict], int]:
    """Pagina a API ADN até esgotar os documentos disponíveis para o CNPJ.

    Chama ``buscar_lote_dfe`` repetidamente, avançando o NSU a cada iteração
    conforme o ``maxNSU`` retornado pela API. A paginação para quando o NSU
    consultado é igual ao ``maxNSU`` (não há mais documentos novos).

    Args:
        session:           Session mTLS configurada.
        cnpj:              CNPJ de 14 dígitos do contribuinte.
        ultimo_nsu_salvo:  NSU registrado na última execução bem-sucedida.
        rate_limit_delay:  Segundos a aguardar entre chamadas de paginação.

    Returns:
        Tupla ``(lista_dfe, maior_nsu)`` onde:
          - ``lista_dfe`` é a lista acumulada de dicts de documentos retornados
            pela API.
          - ``maior_nsu`` é o maior NSU encontrado (para persistir no estado).
    """
    todos_dfe: list[dict] = []
    nsu_atual = ultimo_nsu_salvo
    maior_nsu = ultimo_nsu_salvo

    logger.info(
        "Iniciando busca de DFe — CNPJ=%s | NSU inicial=%d", cnpj, nsu_atual
    )

    while True:
        lote = buscar_lote_dfe(session, nsu_atual, cnpj)

        max_nsu_resposta: int = lote.get("maxNSU", nsu_atual)
        documentos: list[dict] = lote.get("loteNfse", [])

        todos_dfe.extend(documentos)

        if max_nsu_resposta > maior_nsu:
            maior_nsu = max_nsu_resposta

        logger.debug(
            "Lote recebido — CNPJ=%s | NSU consultado=%d | maxNSU=%d | docs=%d",
            cnpj,
            nsu_atual,
            max_nsu_resposta,
            len(documentos),
        )

        if max_nsu_resposta <= nsu_atual:
            # Não há documentos além do NSU atual
            logger.debug(
                "Paginação concluída — maxNSU (%d) == NSU atual (%d). "
                "Sem novos documentos.",
                max_nsu_resposta,
                nsu_atual,
            )
            break

        nsu_atual = max_nsu_resposta

        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    logger.info(
        "Busca concluída — CNPJ=%s | NSU inicial=%d | NSU final=%d | total docs=%d",
        cnpj,
        ultimo_nsu_salvo,
        maior_nsu,
        len(todos_dfe),
    )

    return todos_dfe, maior_nsu


# ---------------------------------------------------------------------------
# Função 3: filtrar_por_competencia
# ---------------------------------------------------------------------------

def filtrar_por_competencia(
    lista_dfe: list[dict], ano: int, mes: int
) -> list[dict]:
    """Filtra documentos DFe pelo ano e mês de emissão.

    Como a API ADN não oferece filtro por período, a filtragem é feita
    localmente após extrair a data de emissão do XML de cada documento.

    Args:
        lista_dfe:  Lista de dicts de documentos retornados pela API.
        ano:        Ano de competência desejado (ex.: 2025).
        mes:        Mês de competência desejado (1–12).

    Returns:
        Subconjunto de ``lista_dfe`` cujos documentos têm data de emissão
        correspondente ao ano e mês informados. Documentos sem data
        identificável são descartados.
    """
    resultado: list[dict] = []

    for doc in lista_dfe:
        xml_content = extrair_xml_do_doc(doc)
        if not xml_content:
            logger.warning(
                "Documento sem campo XML identificável — NSU=%s. Ignorado.",
                doc.get("nsu", "?"),
            )
            continue

        data_emissao = extrair_data_emissao(xml_content)
        if data_emissao is None:
            logger.warning(
                "Data de emissão não encontrada no XML — NSU=%s. Ignorado.",
                doc.get("nsu", "?"),
            )
            continue

        if data_emissao.year == ano and data_emissao.month == mes:
            resultado.append(doc)

    logger.debug(
        "Filtro %02d/%d: %d/%d documentos mantidos.",
        mes,
        ano,
        len(resultado),
        len(lista_dfe),
    )
    return resultado


# ---------------------------------------------------------------------------
# Função 4: extrair_data_emissao
# ---------------------------------------------------------------------------

def extrair_data_emissao(xml_content: str) -> datetime | None:
    """Extrai a data de emissão da NFS-e a partir do XML.

    Tenta localizar os campos ``dhEmi``, ``dtEmissao`` e ``dEmi`` nos
    namespaces conhecidos da NFS-e Nacional, em ordem de prioridade.

    Args:
        xml_content: String com o conteúdo XML da NFS-e.

    Returns:
        Objeto ``datetime`` com a data de emissão, ou ``None`` se o campo
        não for encontrado ou o valor não puder ser parseado.
    """
    try:
        raiz = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        logger.warning("Falha ao parsear XML para extração de data: %s", exc)
        return None

    for campo in _CAMPOS_DATA_EMISSAO:
        valor = _buscar_campo_xml(raiz, campo)
        if valor:
            data = _parsear_data(valor)
            if data:
                return data

    logger.warning(
        "Data de emissão não encontrada no XML (campos tentados: %s).",
        ", ".join(_CAMPOS_DATA_EMISSAO),
    )
    return None


# ---------------------------------------------------------------------------
# Função 5: extrair_dados_nfse
# ---------------------------------------------------------------------------

def extrair_dados_nfse(xml_content: str) -> dict:
    """Extrai campos estruturados de uma NFS-e Nacional a partir do XML.

    Campos ausentes no XML retornam ``None`` sem lançar exceção.

    Args:
        xml_content: String com o conteúdo XML da NFS-e completa.

    Returns:
        Dicionário com os campos::

            numero_nfse            → str  | None
            data_emissao           → str "DD/MM/AAAA" | None
            chave_acesso           → str  | None
            cnpj_prestador         → str (14 dígitos) | None
            razao_social_prestador → str  | None
            cnpj_tomador           → str  | None
            razao_social_tomador   → str  | None
            descricao_servico      → str  | None
            valor_servico          → float | None
            valor_iss              → float | None
            iss_retido             → bool | None
            situacao               → "Ativa" | "Cancelada" | None
    """
    dados: dict = {
        "numero_nfse": None,
        "data_emissao": None,
        "chave_acesso": None,
        "cnpj_prestador": None,
        "razao_social_prestador": None,
        "cnpj_tomador": None,
        "razao_social_tomador": None,
        "descricao_servico": None,
        "valor_servico": None,
        "valor_iss": None,
        "iss_retido": None,
        "situacao": None,
    }

    try:
        raiz = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        logger.warning("Falha ao parsear XML para extração de dados: %s", exc)
        return dados

    # --- Número da NFS-e ---
    dados["numero_nfse"] = _buscar_campo_xml(raiz, "nNFSe") or _buscar_campo_xml(raiz, "Numero")

    # --- Data de emissão ---
    data_emissao = extrair_data_emissao(xml_content)
    if data_emissao:
        dados["data_emissao"] = data_emissao.strftime("%d/%m/%Y")

    # --- Chave de acesso ---
    dados["chave_acesso"] = (
        _buscar_campo_xml(raiz, "chNFSe")
        or _buscar_campo_xml(raiz, "chaveAcesso")
        or _buscar_campo_xml(raiz, "ChaveNFSe")
    )

    # --- Prestador ---
    dados["cnpj_prestador"] = (
        _buscar_campo_xml(raiz, "prest/CNPJ")
        or _buscar_campo_xml(raiz, "Prestador/Cnpj")
        or _buscar_campo_xml(raiz, "CpfCnpjPrestador/Cnpj")
    )
    dados["razao_social_prestador"] = (
        _buscar_campo_xml(raiz, "prest/xNome")
        or _buscar_campo_xml(raiz, "Prestador/RazaoSocial")
        or _buscar_campo_xml(raiz, "RazaoSocialPrestador")
    )

    # --- Tomador ---
    dados["cnpj_tomador"] = (
        _buscar_campo_xml(raiz, "toma/CNPJ")
        or _buscar_campo_xml(raiz, "toma/CPF")
        or _buscar_campo_xml(raiz, "Tomador/CpfCnpj/Cnpj")
        or _buscar_campo_xml(raiz, "Tomador/CpfCnpj/Cpf")
        or _buscar_campo_xml(raiz, "CpfCnpjTomador/Cnpj")
        or _buscar_campo_xml(raiz, "CpfCnpjTomador/Cpf")
    )
    dados["razao_social_tomador"] = (
        _buscar_campo_xml(raiz, "toma/xNome")
        or _buscar_campo_xml(raiz, "Tomador/RazaoSocial")
        or _buscar_campo_xml(raiz, "RazaoSocialTomador")
    )

    # --- Serviço ---
    dados["descricao_servico"] = (
        _buscar_campo_xml(raiz, "serv/xDisc")
        or _buscar_campo_xml(raiz, "Servico/Discriminacao")
        or _buscar_campo_xml(raiz, "Discriminacao")
    )
    dados["valor_servico"] = _extrair_float(
        _buscar_campo_xml(raiz, "serv/vServ")
        or _buscar_campo_xml(raiz, "Servico/Valores/ValorServicos")
        or _buscar_campo_xml(raiz, "ValorServicos")
    )
    dados["valor_iss"] = _extrair_float(
        _buscar_campo_xml(raiz, "serv/vISS")
        or _buscar_campo_xml(raiz, "Servico/Valores/ValorIss")
        or _buscar_campo_xml(raiz, "ValorIss")
    )

    # --- ISS retido ---
    ind_iss_ret = (
        _buscar_campo_xml(raiz, "serv/indISSRet")
        or _buscar_campo_xml(raiz, "Servico/Valores/IssRetido")
        or _buscar_campo_xml(raiz, "IssRetido")
    )
    if ind_iss_ret is not None:
        # indISSRet: 1 = retido, 2 = não retido (padrão nacional)
        # IssRetido: "1" ou "2" (ABRASF) / "true"/"false" (alguns municípios)
        dados["iss_retido"] = ind_iss_ret.strip() in ("1", "true", "True", "S", "s")

    # --- Situação ---
    dados["situacao"] = _extrair_situacao(raiz)

    return dados


# ---------------------------------------------------------------------------
# Funções auxiliares privadas
# ---------------------------------------------------------------------------

def extrair_xml_do_doc(doc: dict) -> str | None:
    """Retorna o conteúdo XML de um documento DFe retornado pela API ADN.

    A API pode entregar o XML em diferentes campos dependendo da versão.
    Tentamos os campos mais prováveis em ordem.
    """
    for campo in ("xmlNfse", "xml", "xmlNFSe", "nfseXml", "documento"):
        valor = doc.get(campo)
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


def _buscar_campo_xml(raiz: ET.Element, caminho: str) -> str | None:
    """Busca um campo no XML tentando múltiplos namespaces conhecidos.

    ``caminho`` pode ser simples ("dhEmi") ou hierárquico ("serv/vServ").
    Retorna o ``text`` do primeiro elemento encontrado, ou ``None``.
    """
    for ns in _NAMESPACES_NFSE:
        prefixo = f"{{{ns}}}" if ns else ""
        caminho_com_ns = "/".join(f"{prefixo}{parte}" for parte in caminho.split("/"))
        elemento = raiz.find(f".//{caminho_com_ns}")
        if elemento is not None and elemento.text and elemento.text.strip():
            return elemento.text.strip()
    return None


def _parsear_data(valor: str) -> datetime | None:
    """Tenta parsear uma string de data nos formatos comuns da NFS-e Nacional.

    Formatos tentados (em ordem):
    - ISO 8601 com timezone:   "2025-01-15T10:30:00-03:00"
    - ISO 8601 sem timezone:   "2025-01-15T10:30:00"
    - Data simples:            "2025-01-15"
    - Data brasileira:         "15/01/2025"
    """
    formatos = (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )
    # Normalizar offsets com dois pontos ("−03:00" → "−0300") para %z
    valor_norm = valor.strip()
    if len(valor_norm) > 19 and valor_norm[-3] == ":":
        valor_norm = valor_norm[:-3] + valor_norm[-2:]

    for fmt in formatos:
        try:
            return datetime.strptime(valor_norm, fmt)
        except ValueError:
            continue

    logger.warning("Não foi possível parsear a data '%s'.", valor)
    return None


def _extrair_float(valor: str | None) -> float | None:
    """Converte uma string monetária para float, ou retorna None."""
    if valor is None:
        return None
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        logger.warning("Valor monetário inválido: '%s'.", valor)
        return None


def _extrair_situacao(raiz: ET.Element) -> str | None:
    """Determina se a NFS-e está Ativa ou Cancelada.

    Estratégias:
    1. Presença de elemento de cancelamento (``nfseCanc``, ``NFSeCanc``,
       ``cSitNFSe`` == "4" ou ``situacao`` == "C" / "Cancelada").
    2. Campo ``cSitNFSe``: "1" = Ativa, "4" = Cancelada (padrão ADN).
    """
    # Verificar elemento de cancelamento explícito
    for ns in _NAMESPACES_NFSE:
        prefixo = f"{{{ns}}}" if ns else ""
        for tag_canc in ("nfseCanc", "NFSeCanc", "Cancelamento", "cancelamento"):
            if raiz.find(f".//{prefixo}{tag_canc}") is not None:
                return "Cancelada"

    # Verificar campo de situação textual
    sit = _buscar_campo_xml(raiz, "situacao") or _buscar_campo_xml(raiz, "Situacao")
    if sit:
        sit_upper = sit.upper()
        if sit_upper in ("C", "CANCELADA", "CANCELADO"):
            return "Cancelada"
        if sit_upper in ("A", "ATIVA", "ATIVO", "N", "NORMAL"):
            return "Ativa"

    # Verificar código de situação numérico (ADN padrão nacional)
    c_sit = (
        _buscar_campo_xml(raiz, "cSitNFSe")
        or _buscar_campo_xml(raiz, "CodigoSituacao")
    )
    if c_sit:
        if c_sit.strip() == "4":
            return "Cancelada"
        if c_sit.strip() in ("1", "2", "3"):
            return "Ativa"

    # Se nenhuma informação de cancelamento encontrada, assume Ativa
    return "Ativa"
