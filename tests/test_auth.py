"""Testes para funções auxiliares do módulo auth (sem certificados reais)."""

from src import auth


class TestExtrairCnpjDaString:
    """Testa a função interna _extrair_cnpj_da_string."""

    def test_prefixo_cnpj_sem_formatacao(self):
        texto = "2.5.4.5=CNPJ:12345678000199"
        assert auth._extrair_cnpj_da_string(texto) == "12345678000199"

    def test_prefixo_cnpj_com_formatacao(self):
        texto = "2.5.4.5=CNPJ:12.345.678/0001-99"
        assert auth._extrair_cnpj_da_string(texto) == "12345678000199"

    def test_formatacao_padrao(self):
        texto = "CN=EMPRESA ABC 12.345.678/0001-99"
        assert auth._extrair_cnpj_da_string(texto) == "12345678000199"

    def test_14_digitos_brutos(self):
        texto = "OU=12345678000199 CN=EMPRESA"
        assert auth._extrair_cnpj_da_string(texto) == "12345678000199"

    def test_sem_cnpj_retorna_vazio(self):
        texto = "CN=Pessoa Fisica CPF=12345678901"
        assert auth._extrair_cnpj_da_string(texto) == ""

    def test_string_vazia(self):
        assert auth._extrair_cnpj_da_string("") == ""


class TestLimparTemporarios:
    def test_remove_arquivos_existentes(self, tmp_path):
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        cert.write_text("cert")
        key.write_text("key")

        auth.limpar_temporarios(str(cert), str(key))

        assert not cert.exists()
        assert not key.exists()

    def test_arquivos_inexistentes_nao_falha(self):
        # Não deve lançar exceção
        auth.limpar_temporarios("/tmp/inexistente_cert.pem", "/tmp/inexistente_key.pem")

    def test_strings_vazias_nao_falha(self):
        auth.limpar_temporarios("", "")
