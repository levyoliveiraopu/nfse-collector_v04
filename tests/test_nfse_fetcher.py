"""Testes para o módulo nfse_fetcher."""

import base64
import gzip
from datetime import datetime

from src import nfse_fetcher


def _doc_arquivo_xml(xml: str, nsu: int = 1, tipo_doc: str = "NFSE") -> dict:
    """Cria um doc DistribuicaoNSU com ArquivoXml (base64+gzip) a partir de XML string."""
    compressed = gzip.compress(xml.encode("utf-8"))
    return {
        "ArquivoXml": base64.b64encode(compressed).decode("ascii"),
        "NSU": nsu,
        "TipoDocumento": tipo_doc,
        "ChaveAcesso": f"CHAVE{nsu}",
    }


def _doc_zip(xml: str) -> dict:
    """Cria um doc com campo docZip legado (base64+gzip) a partir de um XML string."""
    compressed = gzip.compress(xml.encode("utf-8"))
    return {"docZip": base64.b64encode(compressed).decode("ascii"), "NSU": 1}


class TestExtrairXmlDoDoc:
    def test_campo_arquivo_xml(self):
        """ArquivoXml deve ser decodificado com prioridade máxima."""
        xml = "<nfse>arquivo_xml</nfse>"
        doc = _doc_arquivo_xml(xml)
        assert nfse_fetcher.extrair_xml_do_doc(doc) == xml

    def test_campo_arquivo_xml_prioridade_sobre_doczip(self):
        """ArquivoXml tem prioridade sobre docZip."""
        xml_arq = "<nfse>via-arquivo-xml</nfse>"
        doc = _doc_arquivo_xml(xml_arq)
        xml_zip = "<nfse>via-doczip</nfse>"
        compressed = gzip.compress(xml_zip.encode("utf-8"))
        doc["docZip"] = base64.b64encode(compressed).decode("ascii")
        assert nfse_fetcher.extrair_xml_do_doc(doc) == xml_arq

    def test_campo_doczip_legado(self):
        """docZip deve funcionar como fallback quando ArquivoXml ausente."""
        xml = "<nfse>doczip</nfse>"
        doc = _doc_zip(xml)
        assert nfse_fetcher.extrair_xml_do_doc(doc) == xml

    def test_campo_doczip_prioridade_sobre_texto(self):
        """docZip tem prioridade sobre campos de texto plano."""
        xml_zip = "<nfse>via-zip</nfse>"
        doc = _doc_zip(xml_zip)
        doc["xmlNfse"] = "<nfse>via-texto</nfse>"
        assert nfse_fetcher.extrair_xml_do_doc(doc) == xml_zip

    def test_campo_doczip_invalido_cai_no_fallback(self):
        """Se docZip não puder ser decodificado, usa campo de texto."""
        doc = {"docZip": "nao-e-base64-valido!!!@@@", "xmlNfse": "<nfse>ok</nfse>", "NSU": 1}
        assert nfse_fetcher.extrair_xml_do_doc(doc) == "<nfse>ok</nfse>"

    def test_campo_xml(self):
        doc = {"xml": "<nfse>conteudo</nfse>"}
        assert nfse_fetcher.extrair_xml_do_doc(doc) == "<nfse>conteudo</nfse>"

    def test_campo_xmlNfse(self):
        doc = {"xmlNfse": "<nfse>ok</nfse>"}
        assert nfse_fetcher.extrair_xml_do_doc(doc) == "<nfse>ok</nfse>"

    def test_campo_nfseXml(self):
        doc = {"nfseXml": "<nfse>ok</nfse>"}
        assert nfse_fetcher.extrair_xml_do_doc(doc) == "<nfse>ok</nfse>"

    def test_campo_documento(self):
        doc = {"documento": "<nfse>ok</nfse>"}
        assert nfse_fetcher.extrair_xml_do_doc(doc) == "<nfse>ok</nfse>"

    def test_nenhum_campo_retorna_none(self):
        doc = {"id": 123, "NSU": 456}
        assert nfse_fetcher.extrair_xml_do_doc(doc) is None

    def test_campo_vazio_retorna_none(self):
        doc = {"xml": "   "}
        assert nfse_fetcher.extrair_xml_do_doc(doc) is None


class TestExtrairDataEmissao:
    def test_formato_iso_com_timezone(self):
        xml = '<nfse><dhEmi>2025-03-15T10:30:00-03:00</dhEmi></nfse>'
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.year == 2025
        assert data.month == 3
        assert data.day == 15

    def test_formato_iso_sem_timezone(self):
        xml = '<nfse><dhEmi>2025-06-20T14:00:00</dhEmi></nfse>'
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.year == 2025
        assert data.month == 6

    def test_formato_data_simples(self):
        xml = '<nfse><dhEmi>2025-01-10</dhEmi></nfse>'
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.year == 2025
        assert data.month == 1
        assert data.day == 10

    def test_formato_brasileiro(self):
        xml = '<nfse><dhEmi>15/03/2025</dhEmi></nfse>'
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.year == 2025
        assert data.month == 3

    def test_campo_dtEmissao(self):
        xml = '<nfse><dtEmissao>2025-07-01</dtEmissao></nfse>'
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.month == 7

    def test_xml_sem_data_retorna_none(self):
        xml = '<nfse><numero>123</numero></nfse>'
        assert nfse_fetcher.extrair_data_emissao(xml) is None

    def test_xml_invalido_retorna_none(self):
        assert nfse_fetcher.extrair_data_emissao("nao e xml") is None

    def test_namespace_sped(self):
        xml = (
            '<nfse xmlns="http://www.sped.fazenda.gov.br/nfse">'
            '<dhEmi>2025-04-10T08:00:00</dhEmi>'
            '</nfse>'
        )
        data = nfse_fetcher.extrair_data_emissao(xml)
        assert data is not None
        assert data.month == 4


class TestExtrairDadosNfse:
    _XML_COMPLETO = """
    <nfse>
        <nNFSe>12345</nNFSe>
        <dhEmi>2025-03-15T10:00:00</dhEmi>
        <chNFSe>NFSe123456789</chNFSe>
        <prest>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Empresa Prestadora</xNome>
        </prest>
        <toma>
            <CNPJ>98765432000111</CNPJ>
            <xNome>Empresa Tomadora</xNome>
        </toma>
        <serv>
            <xDisc>Consultoria em TI</xDisc>
            <vServ>1500.00</vServ>
            <vISS>75.00</vISS>
            <indISSRet>1</indISSRet>
        </serv>
    </nfse>
    """

    def test_extrai_todos_campos(self):
        dados = nfse_fetcher.extrair_dados_nfse(self._XML_COMPLETO)
        assert dados["numero_nfse"] == "12345"
        assert dados["data_emissao"] == "15/03/2025"
        assert dados["chave_acesso"] == "NFSe123456789"
        assert dados["cnpj_prestador"] == "12345678000199"
        assert dados["razao_social_prestador"] == "Empresa Prestadora"
        assert dados["cnpj_tomador"] == "98765432000111"
        assert dados["razao_social_tomador"] == "Empresa Tomadora"
        assert dados["descricao_servico"] == "Consultoria em TI"
        assert dados["valor_servico"] == 1500.00
        assert dados["valor_iss"] == 75.00
        assert dados["iss_retido"] is True

    def test_xml_vazio_retorna_nones(self):
        dados = nfse_fetcher.extrair_dados_nfse("<nfse></nfse>")
        assert dados["numero_nfse"] is None
        assert dados["valor_servico"] is None
        assert dados["cnpj_tomador"] is None

    def test_xml_invalido_retorna_nones(self):
        dados = nfse_fetcher.extrair_dados_nfse("lixo")
        assert dados["numero_nfse"] is None

    def test_iss_nao_retido(self):
        xml = '<nfse><serv><indISSRet>2</indISSRet></serv></nfse>'
        dados = nfse_fetcher.extrair_dados_nfse(xml)
        assert dados["iss_retido"] is False

    def test_leiaute_nacional_v101(self):
        xml = """
        <NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
          <infNFSe Id="NFS00000000000000000000000000000000000000000000000001">
            <nNFSe>00042</nNFSe>
            <DPS>
              <infDPS>
                <dhEmi>2026-06-15T10:30:00-03:00</dhEmi>
                <prest><CNPJ>40131594000194</CNPJ><xNome>Prestador</xNome></prest>
                <toma><CPF>00100200304</CPF><xNome>Tomador</xNome></toma>
                <serv><cServ><xDescServ>Serviço nacional</xDescServ></cServ></serv>
                <valores>
                  <vServPrest><vServ>1234.56</vServ></vServPrest>
                  <trib><tribMun><tpRetISSQN>2</tpRetISSQN></tribMun></trib>
                </valores>
              </infDPS>
            </DPS>
          </infNFSe>
        </NFSe>
        """
        dados = nfse_fetcher.extrair_dados_nfse(xml)
        assert dados["numero_nfse"] == "00042"
        assert dados["chave_acesso"] == "0" * 49 + "1"
        assert dados["descricao_servico"] == "Serviço nacional"
        assert dados["valor_servico"] == 1234.56
        assert dados["valor_iss"] is None
        assert dados["iss_retido"] is True

    def test_tp_ret_issqn_segue_semantica_oficial(self):
        for codigo, esperado in (("1", False), ("2", True), ("3", True)):
            xml = (
                "<NFSe><valores><trib><tribMun>"
                f"<tpRetISSQN>{codigo}</tpRetISSQN>"
                "</tribMun></trib></valores></NFSe>"
            )
            assert nfse_fetcher.extrair_dados_nfse(xml)["iss_retido"] is esperado

    def test_situacao_cancelada(self):
        xml = '<nfse><nfseCanc>true</nfseCanc></nfse>'
        dados = nfse_fetcher.extrair_dados_nfse(xml)
        assert dados["situacao"] == "Cancelada"

    def test_situacao_ativa_padrao(self):
        xml = '<nfse><nNFSe>1</nNFSe></nfse>'
        dados = nfse_fetcher.extrair_dados_nfse(xml)
        assert dados["situacao"] == "Ativa"


class TestFiltrarPorCompetencia:
    def _doc_com_data(self, data_str: str) -> dict:
        xml = f'<nfse><dhEmi>{data_str}</dhEmi></nfse>'
        return _doc_arquivo_xml(xml)

    def _doc_com_data_hora_geracao(self, data_str: str) -> dict:
        """Cria doc com DataHoraGeracao no envelope (sem precisar do XML)."""
        doc = _doc_arquivo_xml("<nfse></nfse>")
        doc["DataHoraGeracao"] = data_str
        return doc

    def test_filtra_corretamente(self):
        docs = [
            self._doc_com_data("2025-03-15T10:00:00"),
            self._doc_com_data("2025-04-01T08:00:00"),
            self._doc_com_data("2025-03-28T23:59:59"),
        ]
        resultado = nfse_fetcher.filtrar_por_competencia(docs, 2025, 3)
        assert len(resultado) == 2

    def test_nenhum_no_periodo(self):
        docs = [self._doc_com_data("2025-01-10T10:00:00")]
        resultado = nfse_fetcher.filtrar_por_competencia(docs, 2025, 3)
        assert len(resultado) == 0

    def test_lista_vazia(self):
        resultado = nfse_fetcher.filtrar_por_competencia([], 2025, 3)
        assert resultado == []

    def test_filtra_por_data_hora_geracao(self):
        """DataHoraGeracao do envelope deve ser usada quando disponível."""
        docs = [
            self._doc_com_data_hora_geracao("2025-03-15T10:00:00"),
            self._doc_com_data_hora_geracao("2025-04-01T08:00:00"),
        ]
        resultado = nfse_fetcher.filtrar_por_competencia(docs, 2025, 3)
        assert len(resultado) == 1


class TestFiltrarPorTipoDocumento:
    def test_filtra_apenas_nfse(self):
        docs = [
            _doc_arquivo_xml("<nfse/>", nsu=1, tipo_doc="NFSE"),
            _doc_arquivo_xml("<nfse/>", nsu=2, tipo_doc="EVENTO"),
            _doc_arquivo_xml("<nfse/>", nsu=3, tipo_doc="DPS"),
            _doc_arquivo_xml("<nfse/>", nsu=4, tipo_doc="NFSE"),
        ]
        resultado = nfse_fetcher.filtrar_por_tipo_documento(docs)
        assert len(resultado) == 2
        assert all(d["TipoDocumento"] == "NFSE" for d in resultado)

    def test_filtra_tipos_customizados(self):
        docs = [
            _doc_arquivo_xml("<nfse/>", nsu=1, tipo_doc="NFSE"),
            _doc_arquivo_xml("<nfse/>", nsu=2, tipo_doc="EVENTO"),
        ]
        resultado = nfse_fetcher.filtrar_por_tipo_documento(docs, tipos=("NFSE", "EVENTO"))
        assert len(resultado) == 2

    def test_lista_vazia(self):
        resultado = nfse_fetcher.filtrar_por_tipo_documento([])
        assert resultado == []

    def test_nenhum_do_tipo(self):
        docs = [
            _doc_arquivo_xml("<nfse/>", nsu=1, tipo_doc="EVENTO"),
            _doc_arquivo_xml("<nfse/>", nsu=2, tipo_doc="DPS"),
        ]
        resultado = nfse_fetcher.filtrar_por_tipo_documento(docs)
        assert len(resultado) == 0


class TestMaxNsuDoLote:
    def test_retorna_maior_nsu(self):
        docs = [{"NSU": 10}, {"NSU": 50}, {"NSU": 30}]
        assert nfse_fetcher._max_nsu_do_lote(docs) == 50

    def test_lista_vazia(self):
        assert nfse_fetcher._max_nsu_do_lote([]) == 0

    def test_sem_campo_nsu(self):
        docs = [{"ChaveAcesso": "abc"}, {"ChaveAcesso": "def"}]
        assert nfse_fetcher._max_nsu_do_lote(docs) == 0


# ---------------------------------------------------------------------------
# buscar_todos_dfe_novos com NsuSource injetado (CORE-03)
# ---------------------------------------------------------------------------


class _StubSource:
    """NsuSource mínimo para tests — registra chamadas feitas pelo fetcher."""

    def __init__(self, inicial: int = 0) -> None:
        self._estado: dict[str, int] = {}
        self._inicial = inicial
        self.gets: list[str] = []
        self.sets: list[tuple[str, int]] = []

    def get(self, cnpj: str) -> int:
        self.gets.append(cnpj)
        return self._estado.get(cnpj, self._inicial)

    def set(self, cnpj: str, nsu: int) -> None:
        self.sets.append((cnpj, nsu))
        atual = self._estado.get(cnpj, 0)
        if nsu > atual:
            self._estado[cnpj] = nsu


class TestBuscarTodosDfeNovosComNsuSource:
    def test_get_define_nsu_inicial(self, monkeypatch):
        """Quando `nsu_source` é passado, o fetcher consulta get() em vez de usar ultimo_nsu_salvo."""
        source = _StubSource(inicial=500)
        chamadas: list[int] = []

        def fake_buscar_lote(session, ultimo_nsu, cnpj):
            chamadas.append(ultimo_nsu)
            return {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []}

        import worker_core.fetcher as wc_fetcher

        monkeypatch.setattr(wc_fetcher, "buscar_lote_dfe", fake_buscar_lote)

        lista, maior = nfse_fetcher.buscar_todos_dfe_novos(
            session=None,
            cnpj="12345678000199",
            ultimo_nsu_salvo=0,  # ignorado quando source é passado
            rate_limit_delay=0,
            nsu_source=source,
        )

        assert chamadas == [500]
        assert source.gets == ["12345678000199"]
        assert lista == []
        assert maior == 500
        # Sem progressão, não deve persistir.
        assert source.sets == []

    def test_set_persiste_quando_nsu_progride(self, monkeypatch):
        source = _StubSource(inicial=100)
        lotes = iter([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    {"NSU": 150, "TipoDocumento": "NFSE", "ChaveAcesso": "c1"},
                    {"NSU": 200, "TipoDocumento": "NFSE", "ChaveAcesso": "c2"},
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])

        import worker_core.fetcher as wc_fetcher

        monkeypatch.setattr(
            wc_fetcher,
            "buscar_lote_dfe",
            lambda session, nsu, cnpj: next(lotes),
        )

        lista, maior = nfse_fetcher.buscar_todos_dfe_novos(
            session=None,
            cnpj="12345678000199",
            rate_limit_delay=0,
            nsu_source=source,
        )

        assert maior == 200
        assert len(lista) == 2
        assert source.sets == [("12345678000199", 200)]

    def test_set_nao_chamado_sem_progresso(self, monkeypatch):
        """Se `maior_nsu` não avança, o fetcher não chama set()."""
        source = _StubSource(inicial=300)
        import worker_core.fetcher as wc_fetcher

        monkeypatch.setattr(
            wc_fetcher,
            "buscar_lote_dfe",
            lambda session, nsu, cnpj: {
                "StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO",
                "LoteDFe": [],
            },
        )

        nfse_fetcher.buscar_todos_dfe_novos(
            session=None,
            cnpj="12345678000199",
            rate_limit_delay=0,
            nsu_source=source,
        )

        assert source.sets == []

    def test_sem_nsu_source_comportamento_legado(self, monkeypatch):
        """Sem `nsu_source`, usa `ultimo_nsu_salvo` e não tenta persistir."""
        chamadas: list[int] = []

        def fake_buscar_lote(session, ultimo_nsu, cnpj):
            chamadas.append(ultimo_nsu)
            return {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []}

        import worker_core.fetcher as wc_fetcher

        monkeypatch.setattr(wc_fetcher, "buscar_lote_dfe", fake_buscar_lote)

        lista, maior = nfse_fetcher.buscar_todos_dfe_novos(
            session=None,
            cnpj="12345678000199",
            ultimo_nsu_salvo=777,
            rate_limit_delay=0,
        )

        assert chamadas == [777]
        assert maior == 777
        assert lista == []

    def test_integracao_com_in_memory_nsu_source(self, monkeypatch):
        """InMemoryNsuSource real deve persistir o progresso do fetcher."""
        from worker_core.nsu_tracker import InMemoryNsuSource

        source = InMemoryNsuSource({"12345678000199": 50})
        lotes = iter([
            {
                "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                "LoteDFe": [
                    {"NSU": 80, "TipoDocumento": "NFSE"},
                    {"NSU": 120, "TipoDocumento": "NFSE"},
                ],
            },
            {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []},
        ])
        import worker_core.fetcher as wc_fetcher

        monkeypatch.setattr(
            wc_fetcher,
            "buscar_lote_dfe",
            lambda session, nsu, cnpj: next(lotes),
        )

        _, maior = nfse_fetcher.buscar_todos_dfe_novos(
            session=None,
            cnpj="12345678000199",
            rate_limit_delay=0,
            nsu_source=source,
        )

        assert maior == 120
        assert source.get("12345678000199") == 120
