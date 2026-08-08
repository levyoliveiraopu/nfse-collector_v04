"""Testes para funções auxiliares do módulo auth (sem certificados reais)."""

import logging
import os
import re
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from src import auth


def _gerar_pfx_em_memoria(
    password: str = "s3nh@-teste",
    cnpj: str = "12345678000199",
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
) -> bytes:
    """Gera um PFX self-signed em memória para uso em fixtures de teste.

    Não toca o disco; todos os artefatos intermediários ficam em memória.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.COMMON_NAME, f"EMPRESA TESTE LTDA:{cnpj}"),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CNPJ:{cnpj}"),
    ])

    now = datetime.now(tz=timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or now - timedelta(days=1))
        .not_valid_after(not_valid_after or now + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )

    return pkcs12.serialize_key_and_certificates(
        name=b"teste",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )


@pytest.fixture
def pfx_valido() -> tuple[bytes, str]:
    """PFX self-signed em memória, válido por 365 dias."""
    senha = "s3nh@-teste"
    return _gerar_pfx_em_memoria(password=senha), senha


@pytest.fixture
def pfx_vencido() -> tuple[bytes, str]:
    """PFX self-signed já expirado (ontem)."""
    senha = "s3nh@-teste"
    ontem = datetime.now(tz=timezone.utc) - timedelta(days=1)
    antes = datetime.now(tz=timezone.utc) - timedelta(days=10)
    pfx = _gerar_pfx_em_memoria(
        password=senha, not_valid_before=antes, not_valid_after=ontem
    )
    return pfx, senha


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


# ---------------------------------------------------------------------------
# CORE-02: mtls_session (PFX em memória)
# ---------------------------------------------------------------------------

_SENHA_SENTINELA_REGEX = re.compile(
    r"(?:-----BEGIN|PRIVATE KEY|s3nh@-teste)",
    re.IGNORECASE,
)


class TestMtlsSession:
    """Testa o context manager mtls_session (CORE-02)."""

    def test_yield_session_com_cert_valido(self, pfx_valido):
        pfx_bytes, senha = pfx_valido
        with auth.mtls_session(pfx_bytes, senha) as session:
            assert session.cert is not None
            cert_tmp, key_tmp = session.cert
            assert os.path.isfile(cert_tmp)
            assert os.path.isfile(key_tmp)
            # Permissão 0600 — somente owner.
            if os.name != "nt":
                assert (os.stat(cert_tmp).st_mode & 0o777) == 0o600
                assert (os.stat(key_tmp).st_mode & 0o777) == 0o600
            # Objeto certificate exposto para consumidores.
            assert isinstance(session.nfse_certificate, x509.Certificate)

    def test_limpa_pem_no_sucesso(self, pfx_valido):
        pfx_bytes, senha = pfx_valido
        paths: list[str] = []
        with auth.mtls_session(pfx_bytes, senha) as session:
            paths = list(session.cert)
        for p in paths:
            assert not os.path.exists(p), f"PEM nao removido apos sucesso: {p}"

    def test_limpa_pem_em_excecao(self, pfx_valido):
        pfx_bytes, senha = pfx_valido
        paths: list[str] = []

        class BoomError(RuntimeError):
            pass

        with pytest.raises(BoomError):
            with auth.mtls_session(pfx_bytes, senha) as session:
                paths = list(session.cert)
                assert all(os.path.isfile(p) for p in paths)
                raise BoomError("falha simulada dentro do with")

        for p in paths:
            assert not os.path.exists(p), f"PEM nao removido apos excecao: {p}"

    def test_senha_errada_levanta_value_error(self, pfx_valido):
        pfx_bytes, _senha = pfx_valido
        with pytest.raises(ValueError) as excinfo:
            with auth.mtls_session(pfx_bytes, "senha-errada"):
                pass
        # Mensagem não pode vazar senha nem o path (não existe path aqui).
        assert "senha-errada" not in str(excinfo.value)

    def test_pfx_vazio_levanta_value_error(self):
        with pytest.raises(ValueError):
            with auth.mtls_session(b"", "qualquer"):
                pass

    def test_pfx_nao_bytes_levanta_type_error(self):
        with pytest.raises(TypeError):
            with auth.mtls_session("isso-nao-e-bytes", "qualquer"):  # type: ignore[arg-type]
                pass

    def test_certificado_vencido_levanta_value_error(self, pfx_vencido):
        pfx_bytes, senha = pfx_vencido
        with pytest.raises(ValueError) as excinfo:
            with auth.mtls_session(pfx_bytes, senha):
                pass
        msg = str(excinfo.value)
        assert "vencido" in msg.lower()
        # Mensagem sem path — PFX veio de memória.
        assert ".pfx" not in msg

    def test_logs_nao_contem_senha_nem_pem(self, pfx_valido, caplog):
        pfx_bytes, senha = pfx_valido
        caplog.set_level(logging.DEBUG, logger="worker_core.auth")
        with auth.mtls_session(pfx_bytes, senha):
            pass
        texto = caplog.text
        assert senha not in texto, "Senha vazou para logs"
        assert not _SENHA_SENTINELA_REGEX.search(texto), (
            f"Conteudo sensivel detectado em logs: {texto!r}"
        )

    def test_pem_gravado_em_tmpfs_quando_disponivel(self, pfx_valido):
        """Se /dev/shm existir e for gravavel, PEMs devem ficar la."""
        if not (os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK)):
            pytest.skip("/dev/shm indisponivel neste ambiente")
        pfx_bytes, senha = pfx_valido
        with auth.mtls_session(pfx_bytes, senha) as session:
            for p in session.cert:
                assert p.startswith("/dev/shm/"), (
                    f"PEM nao foi gravado em tmpfs: {p}"
                )


class TestCriarSessionClienteWrapper:
    """API legada mantida como wrapper de compat (CORE-02)."""

    def test_wrapper_retorna_tupla_compativel(self, pfx_valido, tmp_path):
        pfx_bytes, senha = pfx_valido
        pfx_path = tmp_path / "teste.pfx"
        pfx_path.write_bytes(pfx_bytes)

        session, cert_tmp, key_tmp, certificate = auth.criar_session_cliente(
            str(pfx_path), senha
        )
        try:
            assert session.cert == (cert_tmp, key_tmp)
            assert os.path.isfile(cert_tmp)
            assert os.path.isfile(key_tmp)
            if os.name != "nt":
                assert (os.stat(cert_tmp).st_mode & 0o777) == 0o600
                assert (os.stat(key_tmp).st_mode & 0o777) == 0o600
            assert isinstance(certificate, x509.Certificate)
        finally:
            auth.limpar_temporarios(cert_tmp, key_tmp)
            session.close()

        assert not os.path.exists(cert_tmp)
        assert not os.path.exists(key_tmp)

    def test_wrapper_arquivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            auth.criar_session_cliente("/tmp/nao-existe-xyz.pfx", "x")

    def test_wrapper_senha_errada(self, pfx_valido, tmp_path):
        pfx_bytes, _ = pfx_valido
        pfx_path = tmp_path / "teste.pfx"
        pfx_path.write_bytes(pfx_bytes)
        with pytest.raises(ValueError):
            auth.criar_session_cliente(str(pfx_path), "senha-errada")
