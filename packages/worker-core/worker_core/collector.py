"""
Coletor NFS-e de alto nivel com callback de progresso por item (CORE-04).

Esta e a API que o worker SaaS (API-13) usa para orquestrar uma execucao:

    from worker_core import fetch_nfse, NfseItem, FetchSummary

    def on_progress(item: NfseItem) -> None:
        # persiste execution_item, upload XML para S3, etc.
        ...

    def on_log(evento: str, payload: dict) -> None:
        logger.info("nfse.%s %s", evento, payload)

    summary = fetch_nfse(
        pfx_bytes=pfx,
        pfx_password=senha,
        cnpj=cnpj,
        nsu_source=source,
        on_progress=on_progress,
        on_log=on_log,
    )

Garantias:

- Abre ``mtls_session`` (CORE-02) a partir dos bytes do PFX — sem trampolim
  em disco fora do tmpfs gerenciado pelo proprio ``mtls_session``.
- Delega a paginacao da API ADN e a persistencia do NSU a
  ``buscar_todos_dfe_novos`` + ``NsuSource`` (CORE-03).
- Emite ``on_progress(NfseItem)`` para **cada nota** processada. Documentos
  de outros tipos (EVENTO, DPS, PEDIDO_REGISTRO_EVENTO, CNC) sao contados
  em ``FetchSummary.total_documentos`` mas nao disparam o callback.
- Erro **no callback** ou parse de um item individual **nao aborta o lote**:
  a falha e registrada via ``on_log`` e a coleta continua no proximo item.
  Erros fatais (PFX invalido, senha errada, certificado vencido) **sao**
  propagados ao chamador — nao ha como coletar nada sem uma session mTLS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from worker_core.auth import mtls_session
from worker_core.fetcher import (
    PortalRequestError,
    buscar_todos_dfe_novos,
    extrair_dados_nfse,
    extrair_xml_do_doc,
    filtrar_por_tipo_documento,
)
from worker_core.nsu_tracker import NsuSource

logger = logging.getLogger(__name__)

# Valores possiveis para NfseItem.status
STATUS_OK = "ok"
STATUS_CANCELADA = "cancelada"
STATUS_PARSE_ERROR = "parse_error"


@dataclass(frozen=True)
class NfseItem:
    """Representacao de uma NFS-e processada, entregue ao callback.

    Campos sempre presentes:
        nsu:           NSU do documento (``int``; 0 se ausente no envelope).
        chave_nfse:    Chave de acesso quando disponivel (envelope ou XML).
        status:        ``"ok"``, ``"cancelada"`` ou ``"parse_error"``.

    Campos que podem ser ``None``:
        cnpj_emitente: 14 digitos do CNPJ do prestador (``None`` se parse falhou).
        data_emissao:  Data de emissao no formato ``"DD/MM/AAAA"``.
        valor:         ``valor_servico`` em float (``None`` se ausente).
        xml_bytes:     Conteudo do XML original em ``bytes`` (UTF-8). ``None``
                       apenas quando nenhum dos campos XML estava presente.
        error_code:    Codigo estruturado quando ``status != "ok"``
                       (ex.: ``"XML_NOT_FOUND"``, ``"XML_PARSE"``).
        error_message: Mensagem humana correspondente a ``error_code``.
    """

    nsu: int
    chave_nfse: Optional[str]
    cnpj_emitente: Optional[str]
    data_emissao: Optional[str]
    valor: Optional[float]
    xml_bytes: Optional[bytes]
    status: str
    error_code: Optional[str]
    error_message: Optional[str]


@dataclass(frozen=True)
class FetchSummary:
    """Resumo agregado de uma execucao de ``fetch_nfse``.

    Campos:
        cnpj:              CNPJ consultado (14 digitos).
        nsu_from:          NSU inicial da paginacao (valor retornado por
                           ``nsu_source.get(cnpj)`` antes da coleta).
        nsu_to:            Maior NSU encontrado nos lotes (ou ``nsu_from``
                           quando nada veio).
        total_documentos:  Total de documentos retornados pelo lote (inclui
                           NFSE + EVENTO + DPS + ...).
        total_nfse:        Apenas documentos ``TipoDocumento == "NFSE"``.
        total_sucesso:     ``NfseItem`` emitidos com ``status="ok"``.
        total_cancelada:   ``NfseItem`` emitidos com ``status="cancelada"``.
        total_erro:        ``NfseItem`` emitidos com ``status="parse_error"``.
        callback_errors:   Quantas vezes ``on_progress`` levantou excecao (o
                           item foi emitido mesmo assim — o contador serve
                           para o worker decidir ``partial``/``success``).
        fatal_rejected:    ``True`` quando a API devolveu ``REJEICAO`` ou a
                           paginacao parou por erro nao recuperavel.
    """

    cnpj: str
    nsu_from: int
    nsu_to: int
    total_documentos: int
    total_nfse: int
    total_sucesso: int
    total_cancelada: int
    total_erro: int
    callback_errors: int
    fatal_rejected: bool


ProgressCallback = Callable[[NfseItem], None]
LogCallback = Callable[[str, dict], None]


def _noop_log(evento: str, payload: dict) -> None:  # pragma: no cover
    return None


def fetch_nfse(
    pfx_bytes: bytes,
    pfx_password: str,
    cnpj: str,
    nsu_source: NsuSource,
    on_progress: ProgressCallback,
    on_log: Optional[LogCallback] = None,
    *,
    max_documentos: int | None = None,
    rate_limit_delay: int = 0,
    persist_nsu: bool = True,
) -> FetchSummary:
    """Coleta NFS-e da API ADN para um CNPJ e emite callback por nota.

    Args:
        pfx_bytes:       Bytes do PFX A1 ja decifrado (ADR-003).
        pfx_password:    Senha do PFX. Nunca e logada.
        cnpj:            14 digitos do CNPJ do contribuinte.
        nsu_source:      Implementacao de ``NsuSource`` (CORE-03) que define
                         o NSU inicial via ``get(cnpj)`` e recebe o NSU
                         final via ``set(cnpj, maior_nsu)`` quando progride.
        on_progress:     Callback chamado para **cada nota** processada.
                         Excecao levantada e capturada, registrada via
                         ``on_log`` e o lote continua no proximo item.
        on_log:          Callback opcional para eventos estruturados.
                         ``None`` equivale a descartar.
        max_documentos:  Limite opcional por execucao (passado ao fetcher).
        rate_limit_delay: Segundos entre chamadas de paginacao.
        persist_nsu:     Quando False, nao persiste `nsu_source.set()` dentro
                         do fetcher; o worker decide apos saber se o job
                         terminou `succeeded` ou `partial/failed`.

    Returns:
        ``FetchSummary`` com contadores e ``nsu_from``/``nsu_to``.

    Raises:
        ValueError: PFX invalido/corrompido, senha errada ou certificado vencido.
        TypeError:  ``pfx_bytes`` nao e ``bytes``.
        requests.RequestException: Erro de rede persistente apos retries do
            ``fetcher`` (nao recuperavel).

    Nao levanta para:
        - XML corrompido de um item -> emite ``NfseItem(status="parse_error")``.
        - ``on_progress`` levantando excecao -> registra e segue.
        - ``REJEICAO`` da API -> registra via ``on_log("fatal_error", ...)``
          e devolve summary com ``fatal_rejected=True`` (paginacao parou).
    """
    log = on_log if on_log is not None else _noop_log
    nsu_inicial = int(nsu_source.get(cnpj))

    log(
        "fetch_start",
        {"cnpj": cnpj, "nsu_from": nsu_inicial, "max_documentos": max_documentos},
    )

    total_documentos = 0
    total_nfse = 0
    total_sucesso = 0
    total_cancelada = 0
    total_erro = 0
    callback_errors = 0
    fatal_rejected = False
    maior_nsu = nsu_inicial

    try:
        with mtls_session(pfx_bytes, pfx_password) as session:
            documentos, maior_nsu = buscar_todos_dfe_novos(
                session=session,
                cnpj=cnpj,
                ultimo_nsu_salvo=nsu_inicial,
                rate_limit_delay=rate_limit_delay,
                max_documentos=max_documentos,
                nsu_source=nsu_source if persist_nsu else None,
            )
    except ValueError:
        # Falhas fatais da camada mTLS (senha, PFX, cert vencido) — proprago.
        log("fatal_error", {"cnpj": cnpj, "stage": "mtls"})
        raise
    except PortalRequestError as exc:
        log("fatal_error", {"cnpj": cnpj, "stage": "adn", "code": exc.code})
        raise

    total_documentos = len(documentos)
    nfse_docs = filtrar_por_tipo_documento(documentos, tipos=("NFSE",))
    total_nfse = len(nfse_docs)

    # Se a API devolveu lote vazio e nao progrediu, sinalizamos fatal_rejected
    # somente quando buscar_todos_dfe_novos nao avancou o NSU nem trouxe docs.
    # O fetcher absorve REJEICAO internamente (apenas para a paginacao), entao
    # detectamos "lote vazio sem progresso" como heuristica de rejeicao.
    if total_documentos == 0 and maior_nsu == nsu_inicial:
        # Pode ser "nada novo" legitimo ou REJEICAO — em ambos os casos
        # nao ha callbacks e o summary e vazio. Nao marcamos fatal_rejected
        # aqui porque "nada novo" e o caso feliz mais comum.
        log("fetch_complete", {"cnpj": cnpj, "nsu_from": nsu_inicial, "nsu_to": maior_nsu, "total_nfse": 0})
        return FetchSummary(
            cnpj=cnpj,
            nsu_from=nsu_inicial,
            nsu_to=maior_nsu,
            total_documentos=0,
            total_nfse=0,
            total_sucesso=0,
            total_cancelada=0,
            total_erro=0,
            callback_errors=0,
            fatal_rejected=False,
        )

    for doc in nfse_docs:
        item = _doc_para_nfse_item(doc, log)

        if item.status == STATUS_OK:
            total_sucesso += 1
        elif item.status == STATUS_CANCELADA:
            total_cancelada += 1
        else:  # STATUS_PARSE_ERROR
            total_erro += 1

        # Callback nao pode abortar o lote — DoD CORE-04.
        try:
            on_progress(item)
        except Exception as exc:  # noqa: BLE001 — isolamento explicito
            callback_errors += 1
            log(
                "callback_error",
                {
                    "cnpj": cnpj,
                    "nsu": item.nsu,
                    "chave_nfse": item.chave_nfse,
                    "error": repr(exc),
                },
            )
            logger.exception(
                "on_progress levantou excecao para NSU=%s (CNPJ=%s); lote continua.",
                item.nsu,
                cnpj,
            )

    log(
        "fetch_complete",
        {
            "cnpj": cnpj,
            "nsu_from": nsu_inicial,
            "nsu_to": maior_nsu,
            "total_documentos": total_documentos,
            "total_nfse": total_nfse,
            "total_sucesso": total_sucesso,
            "total_cancelada": total_cancelada,
            "total_erro": total_erro,
            "callback_errors": callback_errors,
        },
    )

    return FetchSummary(
        cnpj=cnpj,
        nsu_from=nsu_inicial,
        nsu_to=maior_nsu,
        total_documentos=total_documentos,
        total_nfse=total_nfse,
        total_sucesso=total_sucesso,
        total_cancelada=total_cancelada,
        total_erro=total_erro,
        callback_errors=callback_errors,
        fatal_rejected=fatal_rejected,
    )


# ---------------------------------------------------------------------------
# Conversao doc -> NfseItem
# ---------------------------------------------------------------------------


def _nsu_do_doc(doc: dict) -> int:
    """Le NSU do envelope DistribuicaoNSU com coercao segura."""
    nsu = doc.get("NSU")
    if isinstance(nsu, int):
        return nsu
    try:
        return int(nsu) if nsu is not None else 0
    except (TypeError, ValueError):
        return 0


def _doc_para_nfse_item(doc: dict, log: LogCallback) -> NfseItem:
    """Converte um documento DistribuicaoNSU em ``NfseItem``.

    - XML ausente -> ``status="parse_error"``, ``error_code="XML_NOT_FOUND"``.
    - XML invalido -> ``status="parse_error"``, ``error_code="XML_PARSE"``.
    - XML ok + cancelamento detectado -> ``status="cancelada"``.
    - XML ok -> ``status="ok"``.
    """
    nsu = _nsu_do_doc(doc)
    chave_envelope = doc.get("ChaveAcesso") or doc.get("chaveAcesso")

    xml_content = extrair_xml_do_doc(doc)
    if xml_content is None:
        log(
            "item_parse_error",
            {"nsu": nsu, "error_code": "XML_NOT_FOUND"},
        )
        return NfseItem(
            nsu=nsu,
            chave_nfse=chave_envelope,
            cnpj_emitente=None,
            data_emissao=None,
            valor=None,
            xml_bytes=None,
            status=STATUS_PARSE_ERROR,
            error_code="XML_NOT_FOUND",
            error_message="documento sem campo XML decodificavel",
        )

    xml_bytes = xml_content.encode("utf-8")

    try:
        dados = extrair_dados_nfse(xml_content)
    except Exception as exc:  # noqa: BLE001 — parse defensivo
        log(
            "item_parse_error",
            {"nsu": nsu, "error_code": "XML_PARSE", "error": repr(exc)},
        )
        return NfseItem(
            nsu=nsu,
            chave_nfse=chave_envelope,
            cnpj_emitente=None,
            data_emissao=None,
            valor=None,
            xml_bytes=xml_bytes,
            status=STATUS_PARSE_ERROR,
            error_code="XML_PARSE",
            error_message=f"falha ao extrair dados do XML: {exc}",
        )

    situacao = dados.get("situacao")
    status = STATUS_CANCELADA if situacao == "Cancelada" else STATUS_OK

    chave_final = dados.get("chave_acesso") or chave_envelope

    return NfseItem(
        nsu=nsu,
        chave_nfse=chave_final,
        cnpj_emitente=dados.get("cnpj_prestador"),
        data_emissao=dados.get("data_emissao"),
        valor=dados.get("valor_servico"),
        xml_bytes=xml_bytes,
        status=status,
        error_code=None,
        error_message=None,
    )
