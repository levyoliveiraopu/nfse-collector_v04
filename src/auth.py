"""
Autenticação mTLS para a API ADN do Sistema Nacional NFS-e.

Cada cliente possui um certificado digital e-CNPJ A1 (.pfx). Este módulo
carrega esse certificado, extrai a chave privada e o certificado público em
memória, os grava em arquivos PEM temporários e devolve uma requests.Session
pronta para fazer chamadas autenticadas via mTLS.

Uso típico:
    session, cert_tmp, key_tmp = criar_session_cliente(cert_path, senha)
    try:
        resultado = testar_autenticacao(session)
    finally:
        limpar_temporarios(cert_tmp, key_tmp)
"""

import logging
import os
import re
import tempfile
from datetime import datetime, timezone

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

# URL base da API ADN — Sistema Nacional NFS-e
_URL_TESTE_AUTENTICACAO = "https://adn.nfse.gov.br/contribuintes/nfse/DFe/1"

# Timeout padrão para todas as requisições (segundos)
_TIMEOUT_PADRAO = 30


# ---------------------------------------------------------------------------
# HTTPAdapter com timeout fixo
# ---------------------------------------------------------------------------

class _TimeoutAdapter(HTTPAdapter):
    """HTTPAdapter que injeta um timeout padrão em todas as requisições."""

    def __init__(self, timeout: int = _TIMEOUT_PADRAO, **kwargs):
        self._timeout = timeout
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return super().send(request, **kwargs)


# ---------------------------------------------------------------------------
# Função principal: criar_session_cliente
# ---------------------------------------------------------------------------

def criar_session_cliente(
    cert_pfx_path: str,
    cert_password: str,
) -> tuple[requests.Session, str, str]:
    """Cria uma requests.Session autenticada via mTLS usando o certificado .pfx.

    O certificado e a chave privada são extraídos do .pfx e gravados em
    arquivos PEM temporários no disco (necessário porque requests não aceita
    dados em memória para o parâmetro `cert`). Os caminhos dos temporários são
    retornados para que o chamador possa removê-los com `limpar_temporarios`
    após o uso.

    Args:
        cert_pfx_path: Caminho para o arquivo .pfx do cliente.
        cert_password: Senha do arquivo .pfx.

    Returns:
        Tupla (session, caminho_cert_pem_tmp, caminho_key_pem_tmp).

    Raises:
        FileNotFoundError: Se o arquivo .pfx não existir no caminho informado.
        ValueError: Se a senha estiver incorreta ou o certificado estiver vencido.
    """
    if not os.path.isfile(cert_pfx_path):
        raise FileNotFoundError(
            f"Arquivo de certificado não encontrado: {cert_pfx_path}"
        )

    # --- Carregar o .pfx ---
    with open(cert_pfx_path, "rb") as f:
        pfx_data = f.read()

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data, cert_password.encode()
        )
    except Exception as exc:
        # A biblioteca cryptography levanta ValueError ou exceções internas
        # quando a senha é inválida ou o arquivo está corrompido.
        raise ValueError(
            f"Senha incorreta para o certificado: {cert_pfx_path}"
        ) from exc

    # --- Verificar validade do certificado ---
    _verificar_validade(certificate, cert_pfx_path)

    # --- Serializar para PEM em memória ---
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    # Incluir certificados intermediários se existirem
    if additional_certs:
        for extra in additional_certs:
            cert_pem += extra.public_bytes(serialization.Encoding.PEM)

    # --- Gravar PEMs em arquivos temporários ---
    cert_tmp = _gravar_temporario(cert_pem, sufixo="_cert.pem")
    key_tmp = _gravar_temporario(key_pem, sufixo="_key.pem")

    # --- Montar a Session ---
    session = requests.Session()
    session.cert = (cert_tmp, key_tmp)
    session.verify = True
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    adapter = _TimeoutAdapter(timeout=_TIMEOUT_PADRAO)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    logger.debug(
        "Session mTLS criada para o certificado '%s'.", os.path.basename(cert_pfx_path)
    )
    return session, cert_tmp, key_tmp


# ---------------------------------------------------------------------------
# Função 2: extrair_cnpj_do_certificado
# ---------------------------------------------------------------------------

def extrair_cnpj_do_certificado(cert_pfx_path: str, cert_password: str) -> str:
    """Extrai os 14 dígitos do CNPJ contido no Subject do certificado .pfx.

    Trata os formatos mais comuns encontrados em certificados e-CNPJ A1:
    - "CNPJ:12345678000199"
    - "12.345.678/0001-99"
    - "12345678000199" (14 dígitos seguidos, possivelmente em OU ou CN)

    Args:
        cert_pfx_path: Caminho para o arquivo .pfx.
        cert_password: Senha do arquivo .pfx.

    Returns:
        String com os 14 dígitos do CNPJ, sem formatação.
        Retorna string vazia se nenhum CNPJ for encontrado no Subject.

    Raises:
        FileNotFoundError: Se o arquivo .pfx não existir.
        ValueError: Se a senha estiver incorreta ou o certificado estiver vencido.
    """
    if not os.path.isfile(cert_pfx_path):
        raise FileNotFoundError(
            f"Arquivo de certificado não encontrado: {cert_pfx_path}"
        )

    with open(cert_pfx_path, "rb") as f:
        pfx_data = f.read()

    try:
        _, certificate, _ = pkcs12.load_key_and_certificates(
            pfx_data, cert_password.encode()
        )
    except Exception as exc:
        raise ValueError(
            f"Senha incorreta para o certificado: {cert_pfx_path}"
        ) from exc

    _verificar_validade(certificate, cert_pfx_path)

    # 1) Priorizar CN (Common Name), que costuma trazer o CNPJ do titular
    #    no formato "RAZAO SOCIAL:12345678000199".
    cnpj_cn = _extrair_cnpj_do_cn(certificate.subject)
    if cnpj_cn:
        return cnpj_cn

    # 2) Fallback: buscar em todos os atributos do Subject
    subject_str = _subject_para_str(certificate.subject)
    logger.debug("Subject do certificado '%s': %s", os.path.basename(cert_pfx_path), subject_str)

    return _extrair_cnpj_da_string(subject_str)


# ---------------------------------------------------------------------------
# Função 3: testar_autenticacao
# ---------------------------------------------------------------------------

def testar_autenticacao(session: requests.Session) -> dict:
    """Faz uma chamada à API ADN para confirmar que o mTLS está funcionando.

    Qualquer resposta HTTP do servidor (mesmo 404) confirma que o certificado
    foi apresentado e aceito na camada TLS. Erros de conexão ou respostas 496
    indicam falha de autenticação.

    Args:
        session: Session criada por `criar_session_cliente`.

    Returns:
        Dicionário com as chaves:
            "ok"          → bool, True se a autenticação mTLS foi bem-sucedida
            "status_code" → int, código HTTP recebido (ou None em caso de erro de rede)
            "mensagem"    → str, descrição legível do resultado
    """
    try:
        resposta = session.get(_URL_TESTE_AUTENTICACAO)
        codigo = resposta.status_code

        if codigo in (200, 404, 400, 422):
            # O servidor respondeu — certificado aceito na camada mTLS
            return {
                "ok": True,
                "status_code": codigo,
                "mensagem": (
                    f"Autenticação mTLS bem-sucedida (HTTP {codigo}). "
                    "Certificado aceito pelo servidor ADN."
                ),
            }

        if codigo == 403:
            return {
                "ok": False,
                "status_code": codigo,
                "mensagem": (
                    "HTTP 403 — Certificado sem permissão de acesso. "
                    "Verifique se o CNPJ está habilitado na plataforma ADN."
                ),
            }

        if codigo == 496:
            return {
                "ok": False,
                "status_code": codigo,
                "mensagem": (
                    "HTTP 496 — Certificado não apresentado corretamente. "
                    "Verifique a montagem do cert= na session (arquivos PEM)."
                ),
            }

        if codigo == 401:
            return {
                "ok": False,
                "status_code": codigo,
                "mensagem": (
                    "HTTP 401 — Não autorizado. "
                    "Certificado rejeitado ou credenciais inválidas."
                ),
            }

        # Qualquer outro código 2xx/3xx também indica que o servidor respondeu
        if 200 <= codigo < 400:
            return {
                "ok": True,
                "status_code": codigo,
                "mensagem": f"Autenticação mTLS bem-sucedida (HTTP {codigo}).",
            }

        return {
            "ok": False,
            "status_code": codigo,
            "mensagem": f"Resposta inesperada do servidor ADN: HTTP {codigo}.",
        }

    except requests.exceptions.SSLError as exc:
        return {
            "ok": False,
            "status_code": None,
            "mensagem": f"Erro SSL/TLS — certificado rejeitado pelo servidor: {exc}",
        }

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "status_code": None,
            "mensagem": (
                f"Timeout após {_TIMEOUT_PADRAO}s aguardando resposta do servidor ADN. "
                "Verifique a conectividade da VPS."
            ),
        }

    except requests.exceptions.ConnectionError as exc:
        return {
            "ok": False,
            "status_code": None,
            "mensagem": f"Erro de conexão com o servidor ADN: {exc}",
        }

    except requests.exceptions.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "mensagem": f"Erro inesperado na requisição: {exc}",
        }


# ---------------------------------------------------------------------------
# Limpeza dos arquivos temporários
# ---------------------------------------------------------------------------

def limpar_temporarios(cert_file_path: str, key_file_path: str) -> None:
    """Remove os arquivos PEM temporários criados por `criar_session_cliente`.

    Deve ser chamado pelo batch_processor após o processamento de cada cliente,
    independente de sucesso ou falha (use bloco try/finally).

    Args:
        cert_file_path: Caminho do arquivo .pem do certificado público.
        key_file_path:  Caminho do arquivo .pem da chave privada.
    """
    for caminho in (cert_file_path, key_file_path):
        if caminho and os.path.isfile(caminho):
            try:
                os.remove(caminho)
                logger.debug("Arquivo temporário removido: %s", caminho)
            except OSError as exc:
                # Não propaga — falha na limpeza não deve interromper o fluxo
                logger.warning("Não foi possível remover temporário '%s': %s", caminho, exc)


# ---------------------------------------------------------------------------
# Funções auxiliares privadas
# ---------------------------------------------------------------------------

def _verificar_validade(certificate: x509.Certificate, cert_pfx_path: str) -> None:
    """Levanta ValueError se o certificado estiver vencido."""
    agora = datetime.now(tz=timezone.utc)

    # A partir da versão 42 da biblioteca cryptography, not_valid_after foi
    # substituído por not_valid_after_utc (timezone-aware). Suportamos ambos.
    try:
        expiracao = certificate.not_valid_after_utc
    except AttributeError:
        # Versões anteriores retornam datetime sem tzinfo — adicionamos UTC
        expiracao = certificate.not_valid_after.replace(tzinfo=timezone.utc)

    if agora > expiracao:
        data_formatada = expiracao.strftime("%d/%m/%Y")
        raise ValueError(
            f"Certificado vencido em {data_formatada}: {cert_pfx_path}"
        )


def _gravar_temporario(dados_pem: bytes, sufixo: str) -> str:
    """Grava bytes PEM num arquivo temporário e retorna o caminho."""
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=sufixo, mode="wb"
    ) as tmp:
        tmp.write(dados_pem)
        return tmp.name


def _subject_para_str(subject: x509.Name) -> str:
    """Converte o objeto Subject do certificado numa string única para busca."""
    partes = []
    for atributo in subject:
        partes.append(f"{atributo.oid.dotted_string}={atributo.value}")
    return " ".join(partes)


def _extrair_cnpj_do_cn(subject: x509.Name) -> str:
    """Extrai CNPJ a partir do atributo CN (Common Name), se presente.

    Estratégia:
    1) Tenta localizar CNPJ no valor do CN (ex.: "EMPRESA:12345678000199").
    2) Se não encontrar em nenhum CN, retorna string vazia.
    """
    atributos_cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    for atributo in atributos_cn:
        valor_cn = (atributo.value or "").strip()
        if not valor_cn:
            continue
        cnpj = _extrair_cnpj_da_string(valor_cn)
        if cnpj:
            return cnpj
    return ""


def _extrair_cnpj_da_string(texto: str) -> str:
    """Retorna os 14 dígitos do CNPJ encontrado em `texto`, ou string vazia.

    Formatos suportados (em ordem de prioridade):
    1. Prefixo explícito: "CNPJ:12345678000199" ou "CNPJ:12.345.678/0001-99"
    2. Formatação CNPJ: "12.345.678/0001-99"
    3. 14 dígitos seguidos: "12345678000199"
    """
    # 1) Prefixo CNPJ: (aceita com ou sem formatação após o prefixo)
    padrao_prefixo = re.search(
        r"CNPJ[:\s]+([\d]{2}\.?[\d]{3}\.?[\d]{3}[/\.]?[\d]{4}[-\s]?[\d]{2})",
        texto,
        re.IGNORECASE,
    )
    if padrao_prefixo:
        return re.sub(r"\D", "", padrao_prefixo.group(1))

    # 2) Formatação padrão de CNPJ: XX.XXX.XXX/XXXX-XX
    padrao_formatado = re.search(
        r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto
    )
    if padrao_formatado:
        return re.sub(r"\D", "", padrao_formatado.group(0))

    # 3) Sequência de exatamente 14 dígitos (com fronteira de não-dígito)
    padrao_bruto = re.search(r"(?<!\d)(\d{14})(?!\d)", texto)
    if padrao_bruto:
        return padrao_bruto.group(1)

    return ""
