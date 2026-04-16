"""Testes para worker_core.collector.fetch_nfse (CORE-04).

Cobre a DoD do ticket:
  - Callback de progresso chamado N vezes (uma por nota).
  - Erro em um item nao aborta o lote (exceto erros fatais).
"""

from __future__ import annotations

import base64
import gzip
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from worker_core import FetchSummary, NfseItem, fetch_nfse
from worker_core import collector as collector_module
from worker_core import fetcher as fetcher_module
from worker_core.nsu_tracker import InMemoryNsuSource


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _gerar_pfx(password: str = "senha", cnpj: str = "12345678000199") -> bytes:
    """PFX self-signed em memoria (valido por 1 ano)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.COMMON_NAME, f"TESTE:{cnpj}"),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CNPJ:{cnpj}"),
    ])
    now = datetime.now(tz=timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"t",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )


@pytest.fixture
def pfx_valido() -> tuple[bytes, str]:
    senha = "senha"
    return _gerar_pfx(password=senha), senha


def _arquivo_xml(xml: str) -> str:
    """Empacota XML como base64(gzip(xml)) — padrao API ADN."""
    return base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode("ascii")


def _doc(
    nsu: int,
    xml: str,
    tipo: str = "NFSE",
    chave: str | None = None,
) -> dict:
    doc: dict = {
        "NSU": nsu,
        "TipoDocumento": tipo,
        "ArquivoXml": _arquivo_xml(xml),
    }
    if chave is not None:
        doc["ChaveAcesso"] = chave
    return doc


_XML_BASE = """
<nfse>
    <nNFSe>{numero}</nNFSe>
    <dhEmi>2025-03-15T10:00:00</dhEmi>
    <chNFSe>{chave}</chNFSe>
    <prest><CNPJ>12345678000199</CNPJ><xNome>Prestador</xNome></prest>
    <toma><CNPJ>98765432000111</CNPJ><xNome>Tomador</xNome></toma>
    <serv>
        <xDisc>Servico</xDisc>
        <vServ>{valor}</vServ>
        <vISS>0</vISS>
        <indISSRet>2</indISSRet>
    </serv>
</nfse>
""".strip()


def _xml(numero: str = "1", chave: str = "CHAVE123", valor: str = "100.00") -> str:
    return _XML_BASE.format(numero=numero, chave=chave, valor=valor)


@pytest.fixture
def stub_mtls(monkeypatch):
    """Substitui mtls_session por um context manager que devolve MagicMock.

    Isso evita carregar PFX real no hot-path dos testes (ja cobrimos isso em
    test_auth.py); aqui foco e o comportamento do collector em cima do fetcher.
    """
    import contextlib

    @contextlib.contextmanager
    def _fake(pfx_bytes, pfx_password):
        yield MagicMock(name="fake_session")

    monkeypatch.setattr(collector_module, "mtls_session", _fake)


@pytest.fixture
def stub_paginacao(monkeypatch):
    """Helper para instalar uma sequencia de lotes em buscar_lote_dfe."""

    def _instalar(lotes: list[dict]) -> list[int]:
        chamadas_nsu: list[int] = []
        it = iter(lotes)

        def fake(session, ultimo_nsu, cnpj):
            chamadas_nsu.append(ultimo_nsu)
            try:
                return next(it)
            except StopIteration:
                return {
                    "StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO",
                    "LoteDFe": [],
                }

        monkeypatch.setattr(fetcher_module, "buscar_lote_dfe", fake)
        return chamadas_nsu

    return _instalar


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestFetchNfseCallback:
    def test_callback_chamado_n_vezes_com_nfse_item(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """DoD: 3 notas -> 3 chamadas de on_progress com NfseItem populados."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource({"12345678000199": 100})

        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    _doc(150, _xml("1", "K1", "100.00")),
                    _doc(200, _xml("2", "K2", "250.50")),
                    _doc(250, _xml("3", "K3", "999.99")),
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []

        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
        )

        assert len(recebidos) == 3
        assert all(isinstance(item, NfseItem) for item in recebidos)
        assert [item.nsu for item in recebidos] == [150, 200, 250]
        assert [item.chave_nfse for item in recebidos] == ["K1", "K2", "K3"]
        assert [item.status for item in recebidos] == ["ok", "ok", "ok"]
        assert [item.valor for item in recebidos] == [100.0, 250.5, 999.99]
        assert all(item.cnpj_emitente == "12345678000199" for item in recebidos)
        assert all(item.xml_bytes is not None for item in recebidos)

        assert isinstance(summary, FetchSummary)
        assert summary.cnpj == "12345678000199"
        assert summary.nsu_from == 100
        assert summary.nsu_to == 250
        assert summary.total_documentos == 3
        assert summary.total_nfse == 3
        assert summary.total_sucesso == 3
        assert summary.total_cancelada == 0
        assert summary.total_erro == 0
        assert summary.callback_errors == 0
        assert summary.fatal_rejected is False

        # NsuSource.set foi chamado pelo fetcher (CORE-03).
        assert source.get("12345678000199") == 250

    def test_erro_no_callback_nao_aborta_o_lote(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """DoD: excecao no callback e capturada; proximos items continuam."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource()

        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    _doc(10, _xml("1", "K1")),
                    _doc(20, _xml("2", "K2")),
                    _doc(30, _xml("3", "K3")),
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        eventos: list[tuple[str, dict]] = []

        def on_progress(item: NfseItem) -> None:
            recebidos.append(item)
            if item.nsu == 10:
                raise RuntimeError("boom no primeiro item")

        def on_log(evento: str, payload: dict) -> None:
            eventos.append((evento, payload))

        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=on_progress,
            on_log=on_log,
        )

        # Todos os 3 items foram emitidos — o boom do primeiro nao parou.
        assert [item.nsu for item in recebidos] == [10, 20, 30]
        assert summary.total_sucesso == 3
        assert summary.callback_errors == 1

        cb_errors = [p for e, p in eventos if e == "callback_error"]
        assert len(cb_errors) == 1
        assert cb_errors[0]["nsu"] == 10
        assert "RuntimeError" in cb_errors[0]["error"]
        assert cb_errors[0]["chave_nfse"] == "K1"

    def test_nota_cancelada_marca_status_cancelada(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        pfx, senha = pfx_valido
        source = InMemoryNsuSource()

        xml_cancelada = "<nfse><nNFSe>1</nNFSe><nfseCanc>1</nfseCanc></nfse>"
        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    _doc(10, _xml("1", "K1")),
                    _doc(20, xml_cancelada, chave="K-CANC"),
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
        )

        assert recebidos[0].status == "ok"
        assert recebidos[1].status == "cancelada"
        assert recebidos[1].chave_nfse == "K-CANC"
        assert summary.total_sucesso == 1
        assert summary.total_cancelada == 1
        assert summary.total_erro == 0

    def test_xml_corrompido_gera_parse_error(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """XML corrompido emite NfseItem(status=parse_error) — nao aborta."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource()

        doc_bad = {
            "NSU": 77,
            "TipoDocumento": "NFSE",
            # Nao ha ArquivoXml nem fallback de texto — dispara XML_NOT_FOUND.
            "ChaveAcesso": "KBAD",
        }

        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    doc_bad,
                    _doc(78, _xml("ok", "KOK")),
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        eventos: list[tuple[str, dict]] = []

        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
            on_log=lambda e, p: eventos.append((e, p)),
        )

        assert len(recebidos) == 2
        assert recebidos[0].status == "parse_error"
        assert recebidos[0].error_code == "XML_NOT_FOUND"
        assert recebidos[0].chave_nfse == "KBAD"
        assert recebidos[0].xml_bytes is None
        assert recebidos[1].status == "ok"

        assert summary.total_erro == 1
        assert summary.total_sucesso == 1

        parse_events = [p for e, p in eventos if e == "item_parse_error"]
        assert len(parse_events) == 1
        assert parse_events[0]["error_code"] == "XML_NOT_FOUND"

    def test_apenas_nfse_dispara_callback(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """EVENTO/DPS sao contados em total_documentos mas nao disparam callback."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource()

        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    _doc(10, _xml("1", "K1"), tipo="NFSE"),
                    _doc(11, "<evento/>", tipo="EVENTO"),
                    _doc(12, "<dps/>", tipo="DPS"),
                    _doc(13, _xml("2", "K2"), tipo="NFSE"),
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
        )

        assert [item.nsu for item in recebidos] == [10, 13]
        assert summary.total_documentos == 4
        assert summary.total_nfse == 2
        assert summary.total_sucesso == 2

    def test_lote_vazio_devolve_summary_vazio(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """Sem novos documentos -> callback nao chamado, summary zerado."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource({"12345678000199": 500})

        stub_paginacao([
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
        )

        assert recebidos == []
        assert summary.nsu_from == 500
        assert summary.nsu_to == 500
        assert summary.total_documentos == 0
        assert summary.total_nfse == 0
        assert summary.callback_errors == 0
        assert summary.fatal_rejected is False

    def test_pfx_invalido_e_erro_fatal(self, stub_paginacao):
        """Senha errada/PFX invalido sao fatais — propaga ValueError."""
        # stub_paginacao nao e usado porque nem chegamos ao fetcher; mas
        # instalamos mesmo assim para evitar hit real caso algo escape.
        stub_paginacao([])

        source = InMemoryNsuSource()
        eventos: list[tuple[str, dict]] = []

        with pytest.raises(ValueError):
            fetch_nfse(
                pfx_bytes=b"nao-e-pfx",
                pfx_password="senha",
                cnpj="12345678000199",
                nsu_source=source,
                on_progress=lambda item: None,
                on_log=lambda e, p: eventos.append((e, p)),
            )

        # Registrou o erro fatal antes de propagar.
        fatal = [p for e, p in eventos if e == "fatal_error"]
        assert len(fatal) == 1
        assert fatal[0]["stage"] == "mtls"

    def test_on_log_opcional_nao_obrigatorio(
        self, pfx_valido, stub_mtls, stub_paginacao
    ):
        """Omitir on_log nao deve quebrar — callback opcional real."""
        pfx, senha = pfx_valido
        source = InMemoryNsuSource()

        stub_paginacao([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [_doc(10, _xml("1", "K1"))],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        recebidos: list[NfseItem] = []
        summary = fetch_nfse(
            pfx_bytes=pfx,
            pfx_password=senha,
            cnpj="12345678000199",
            nsu_source=source,
            on_progress=recebidos.append,
            # on_log omitido de proposito.
        )
        assert len(recebidos) == 1
        assert summary.total_sucesso == 1
