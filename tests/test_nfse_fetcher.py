"""Testes para o módulo nfse_fetcher."""

from datetime import datetime

from src import nfse_fetcher


class TestExtrairXmlDoDoc:
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
        doc = {"id": 123, "nsu": 456}
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
        return {"xmlNfse": xml, "nsu": 1}

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
