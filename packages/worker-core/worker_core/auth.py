"""
Autenticação mTLS para a API ADN do Sistema Nacional NFS-e.

Cada cliente possui um certificado digital e-CNPJ A1 (.pfx). Este módulo
carrega esse certificado a partir de **bytes em memória** (vindos do banco
cifrado em AES-GCM — ADR-003), extrai a chave privada e o certificado
público, materializa arquivos PEM temporários em `tmpfs` (/dev/shm) com
permissão 600 e devolve uma ``requests.Session`` pronta para fazer chamadas
autenticadas via mTLS.

Uso recomendado (CORE-02+):
    with mtls_session(pfx_bytes, pfx_password) as session:
        resp = session.get(url)
    # PEMs removidos automaticamente ao sair do with (sucesso ou excecao).

Uso legado (path em disco) — preservado como wrapper de compat enquanto os
chamadores (batch_processor, diagnostico) não migram para a API nova:
    session, cert_tmp, key_tmp, cert = criar_session_cliente(path, senha)
    try:
        ...
    finally:
        limpar_temporarios(cert_tmp, key_tmp)
"""

import contextlib
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Iterator

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

# URLs base por ambiente — Sistema Nacional NFS-e
_URLS_BASE = {
    "PRODUCAO": "https://adn.nfse.gov.br/contribuintes",
    "HOMOLOGACAO": "https://adn.producaorestrita.nfse.gov.br/contribuintes",
}


def _get_base_url() -> str:
    """Retorna a URL base conforme o ambiente configurado em NFSE_AMBIENTE."""
    ambiente = os.getenv("NFSE_AMBIENTE", "PRODUCAO").upper()
    url = _URLS_BASE.get(ambiente)
    if url is None:
        raise ValueError(
            f"NFSE_AMBIENTE inválido: '{ambiente}'. "
            f"Valores aceitos: {', '.join(_URLS_BASE.keys())}"
        )
    return url

# Timeout padrão para todas as requisições (segundos)
_TIMEOUT_PADRAO = 30


def _obter_timeout_http() -> int:
    """Lê timeout HTTP do .env com fallback seguro.

    Variável suportada:
        - HTTP_TIMEOUT_SECONDS (int > 0)
    """
    valor = os.getenv("HTTP_TIMEOUT_SECONDS", str(_TIMEOUT_PADRAO)).strip()
    try:
        timeout = int(valor)
        if timeout <= 0:
            raise ValueError
        return timeout
    except ValueError:
        logger.warning(
            "HTTP_TIMEOUT_SECONDS inválido ('%s'). Usando padrão de %ds.",
            valor,
            _TIMEOUT_PADRAO,
        )
        return _TIMEOUT_PADRAO


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
# API nova (CORE-02): mtls_session — PFX em memória + tmpfs + context manager
# ---------------------------------------------------------------------------

# Diretório preferido para PEMs temporários. tmpfs (volátil, sem paginar para
# disco) reduz a janela de exposição da chave privada caso o processo receba
# SIGKILL antes do cleanup.
_TMPFS_PREFERIDO = "/dev/shm"


def _escolher_dir_tmpfs() -> str:
    """Retorna `/dev/shm` se disponível/gravável, senão o tempdir padrão.

    `/dev/shm` não existe em macOS (dev local de alguns agentes) nem em
    alguns runners de CI containerizados. Quando indisponível, caímos para
    ``tempfile.gettempdir()`` — seguro em VPS Linux de produção (nosso
    target — ADR-005), mas registrado em debug para auditoria.
    """
    if os.path.isdir(_TMPFS_PREFERIDO) and os.access(_TMPFS_PREFERIDO, os.W_OK):
        return _TMPFS_PREFERIDO
    fallback = tempfile.gettempdir()
    logger.debug(
        "tmpfs '%s' indisponivel; usando fallback '%s' para PEM temporario.",
        _TMPFS_PREFERIDO,
        fallback,
    )
    return fallback


def _gravar_pem_seguro(dados_pem: bytes, sufixo: str) -> str:
    """Grava bytes PEM em tmpfs com permissão 0600 desde a criação do inode.

    Usa ``O_CREAT|O_EXCL|O_WRONLY`` com mode 0o600 para evitar janela de
    corrida onde outro processo no mesmo host poderia abrir o arquivo antes
    do `chmod` (defense-in-depth — ADR-003).
    """
    diretorio = _escolher_dir_tmpfs()
    # tempfile.mkstemp já cria com 0600 e garante nome único, mas não permite
    # escolher o diretório de forma totalmente portável com os flags que
    # queremos; usamos mkstemp + fchmod defensivo.
    fd, caminho = tempfile.mkstemp(suffix=sufixo, dir=diretorio)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(dados_pem)
    except Exception:
        # Se falhar na escrita, remove o inode vazio para não vazar arquivo.
        try:
            os.remove(caminho)
        except OSError:
            pass
        raise
    return caminho


def _remover_silencioso(caminho: str) -> None:
    """Remove um arquivo, logando apenas em debug se não existir."""
    if not caminho:
        return
    try:
        os.remove(caminho)
        logger.debug("PEM temporario removido.")
    except FileNotFoundError:
        # Já removido — fluxo idempotente, OK.
        pass
    except OSError as exc:
        # Nunca propaga: cleanup não pode mascarar a exceção original.
        logger.warning("Falha ao remover PEM temporario: %s", exc)


def _carregar_pfx(
    pfx_bytes: bytes, pfx_password: str
) -> tuple[object, x509.Certificate, list]:
    """Carrega PFX a partir de bytes e devolve (private_key, cert, cadeia).

    Não inclui o caminho do arquivo em nenhuma mensagem de erro (pode não
    existir — PFX pode vir direto do banco cifrado). Também não inclui a
    senha (obvio, mas reforçado aqui para auditoria de logs).
    """
    if not isinstance(pfx_bytes, (bytes, bytearray)):
        raise TypeError("pfx_bytes deve ser bytes")
    if not pfx_bytes:
        raise ValueError("PFX vazio")

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_bytes, pfx_password.encode()
        )
    except Exception as exc:
        # cryptography levanta ValueError/exceções internas para senha errada
        # ou PFX corrompido. Mensagem neutra — sem path, sem senha, sem bytes.
        raise ValueError("Senha incorreta ou PFX invalido") from exc

    if certificate is None or private_key is None:
        raise ValueError("PFX nao contem certificado ou chave privada")

    return private_key, certificate, additional_certs or []


def _pem_bytes_from_pfx(
    private_key: object,
    certificate: x509.Certificate,
    additional_certs: list,
) -> tuple[bytes, bytes]:
    """Serializa (cert + cadeia) e chave privada em PEM — em memória."""
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    for extra in additional_certs:
        cert_pem += extra.public_bytes(serialization.Encoding.PEM)

    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _montar_session(cert_tmp: str, key_tmp: str) -> requests.Session:
    """Monta ``requests.Session`` mTLS com timeout padrão."""
    session = requests.Session()
    session.cert = (cert_tmp, key_tmp)
    session.verify = True
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    timeout_http = _obter_timeout_http()
    adapter = _TimeoutAdapter(timeout=timeout_http)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


@contextlib.contextmanager
def mtls_session(
    pfx_bytes: bytes, pfx_password: str
) -> Iterator[requests.Session]:
    """Context manager que expõe ``requests.Session`` mTLS a partir de PFX em memória.

    Ciclo:
      1. Carrega e valida o PFX (senha, expiração) direto dos bytes.
      2. Materializa cert PEM (com cadeia) e key PEM em tmpfs (`/dev/shm`)
         com permissão 0600.
      3. Entrega a ``Session`` configurada para mTLS.
      4. Ao sair do ``with`` — em sucesso OU exceção — fecha a session e
         remove os dois PEMs. A limpeza nunca propaga exceção nova.

    Args:
        pfx_bytes: Conteúdo do .pfx já descriptografado (vindo do banco).
        pfx_password: Senha do PFX. Nunca é logada.

    Yields:
        ``requests.Session`` pronta para chamadas mTLS. O objeto
        ``x509.Certificate`` fica acessível em ``session.nfse_certificate``
        para quem precisar (ex.: extrair CNPJ sem reabrir o PFX).

    Raises:
        ValueError: PFX vazio, senha incorreta, PFX corrompido ou certificado
            vencido.
        TypeError: ``pfx_bytes`` não é ``bytes``.
    """
    private_key, certificate, additional_certs = _carregar_pfx(
        pfx_bytes, pfx_password
    )
    # path=None: mensagem de erro de cert vencido não referencia arquivo
    # (PFX pode ter vindo direto do banco).
    _verificar_validade(certificate, None)

    cert_pem, key_pem = _pem_bytes_from_pfx(
        private_key, certificate, additional_certs
    )

    cert_tmp = key_tmp = None
    session: requests.Session | None = None
    try:
        cert_tmp = _gravar_pem_seguro(cert_pem, sufixo="_cert.pem")
        key_tmp = _gravar_pem_seguro(key_pem, sufixo="_key.pem")
        session = _montar_session(cert_tmp, key_tmp)
        # Expõe o certificate para consumidores que precisem sem reabrir PFX.
        setattr(session, "nfse_certificate", certificate)
        logger.debug("Session mTLS criada (PFX em memoria).")
        yield session
    finally:
        if session is not None:
            try:
                session.close()
            except Exception as exc:  # noqa: BLE001 — cleanup não pode levantar
                logger.warning("Falha ao fechar session mTLS: %s", exc)
        if cert_tmp:
            _remover_silencioso(cert_tmp)
        if key_tmp:
            _remover_silencioso(key_tmp)


# ---------------------------------------------------------------------------
# API legada: criar_session_cliente (wrapper de compat)
# ---------------------------------------------------------------------------

def criar_session_cliente(
    cert_pfx_path: str,
    cert_password: str,
) -> tuple[requests.Session, str, str, x509.Certificate]:
    """Wrapper de compat da API legada baseada em path de arquivo .pfx.

    .. deprecated:: CORE-02
        Novos chamadores devem usar ``mtls_session(pfx_bytes, senha)`` —
        que carrega o PFX direto da memória (vindo do banco cifrado, sem
        trampolim em disco) e garante cleanup via context manager.

    Mantido enquanto ``batch_processor`` e ``diagnostico`` ainda operam com
    paths do filesystem local. Delega a lógica de extração/serialização ao
    mesmo caminho-de-código de ``mtls_session``, mas devolve a tupla
    histórica ``(session, cert_tmp, key_tmp, certificate)`` e deixa o
    cleanup por conta do chamador (``limpar_temporarios``).

    Args:
        cert_pfx_path: Caminho para o arquivo .pfx do cliente.
        cert_password: Senha do arquivo .pfx.

    Returns:
        Tupla ``(session, caminho_cert_pem_tmp, caminho_key_pem_tmp, certificate)``.

    Raises:
        FileNotFoundError: Se o arquivo .pfx não existir no caminho informado.
        ValueError: Se a senha estiver incorreta ou o certificado estiver vencido.
    """
    if not os.path.isfile(cert_pfx_path):
        raise FileNotFoundError(
            f"Arquivo de certificado não encontrado: {cert_pfx_path}"
        )

    with open(cert_pfx_path, "rb") as f:
        pfx_data = f.read()

    private_key, certificate, additional_certs = _carregar_pfx(
        pfx_data, cert_password
    )
    # Path conhecido — mantém mensagem histórica de cert vencido.
    _verificar_validade(certificate, cert_pfx_path)

    cert_pem, key_pem = _pem_bytes_from_pfx(
        private_key, certificate, additional_certs
    )
    cert_tmp = _gravar_pem_seguro(cert_pem, sufixo="_cert.pem")
    key_tmp = _gravar_pem_seguro(key_pem, sufixo="_key.pem")

    session = _montar_session(cert_tmp, key_tmp)
    logger.debug(
        "Session mTLS criada para o certificado '%s'.",
        os.path.basename(cert_pfx_path),
    )
    return session, cert_tmp, key_tmp, certificate


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

    subject = certificate.subject

    # 1) serialNumber (2.5.4.5) costuma carregar o documento do titular:
    #    ex.: "CNPJ:12345678000199".
    cnpj_serial = _extrair_cnpj_do_serial_number(subject)
    if cnpj_serial:
        logger.debug("CNPJ extraído do serialNumber do certificado: %s", cnpj_serial)
        return cnpj_serial

    # 2) CN (Common Name) do titular:
    #    ex.: "RAZAO SOCIAL LTDA:12345678000199".
    cnpj_cn = _extrair_cnpj_do_cn(subject)
    if cnpj_cn:
        logger.debug("CNPJ extraído do CN do certificado: %s", cnpj_cn)
        return cnpj_cn

    # 3) Fallback seguro:
    #    procura apenas formatos explícitos de CNPJ em qualquer atributo
    #    (não aceita "14 dígitos soltos", para evitar capturar OUs da cadeia).
    cnpj_subject = _extrair_cnpj_do_subject_seguro(subject)
    if cnpj_subject:
        logger.debug("CNPJ extraído via fallback seguro do Subject: %s", cnpj_subject)
        return cnpj_subject

    subject_str = _subject_para_str(subject)
    logger.debug(
        "Nenhum CNPJ identificado no Subject do certificado '%s': %s",
        os.path.basename(cert_pfx_path),
        subject_str,
    )
    return ""


# ---------------------------------------------------------------------------
# Função 2b: extrair_cnpj_do_certificado_obj
# ---------------------------------------------------------------------------

def extrair_cnpj_do_certificado_obj(certificate: x509.Certificate, cert_pfx_path: str) -> str:
    """Extrai o CNPJ de um objeto certificate já carregado em memória.

    Mesma lógica de ``extrair_cnpj_do_certificado``, mas evita recarregar
    o .pfx do disco quando o chamador já possui o objeto certificate
    (ex.: retornado por ``criar_session_cliente``).

    Args:
        certificate: Objeto x509.Certificate já carregado.
        cert_pfx_path: Caminho do .pfx (usado apenas para logging).

    Returns:
        String com os 14 dígitos do CNPJ, sem formatação.
        Retorna string vazia se nenhum CNPJ for encontrado.
    """
    subject = certificate.subject

    cnpj_serial = _extrair_cnpj_do_serial_number(subject)
    if cnpj_serial:
        logger.debug("CNPJ extraído do serialNumber do certificado: %s", cnpj_serial)
        return cnpj_serial

    cnpj_cn = _extrair_cnpj_do_cn(subject)
    if cnpj_cn:
        logger.debug("CNPJ extraído do CN do certificado: %s", cnpj_cn)
        return cnpj_cn

    cnpj_subject = _extrair_cnpj_do_subject_seguro(subject)
    if cnpj_subject:
        logger.debug("CNPJ extraído via fallback seguro do Subject: %s", cnpj_subject)
        return cnpj_subject

    subject_str = _subject_para_str(subject)
    logger.debug(
        "Nenhum CNPJ identificado no Subject do certificado '%s': %s",
        os.path.basename(cert_pfx_path),
        subject_str,
    )
    return ""


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
        url_teste = f"{_get_base_url()}/DFe/1"
        resposta = session.get(url_teste)
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
                f"Timeout após {_obter_timeout_http()}s aguardando resposta do servidor ADN. "
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

def _verificar_validade(
    certificate: x509.Certificate, cert_pfx_path: str | None
) -> None:
    """Levanta ValueError se o certificado estiver vencido.

    ``cert_pfx_path`` é opcional — quando o PFX vem direto de memória
    (``mtls_session``) não há path associado, e a mensagem de erro omite o
    sufixo ``: <path>`` do caminho legado.
    """
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
        if cert_pfx_path:
            raise ValueError(
                f"Certificado vencido em {data_formatada}: {cert_pfx_path}"
            )
        raise ValueError(f"Certificado vencido em {data_formatada}")


def _gravar_temporario(dados_pem: bytes, sufixo: str) -> str:
    """Grava bytes PEM num arquivo temporário e retorna o caminho."""
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=sufixo, mode="wb"
    ) as tmp:
        tmp.write(dados_pem)
        os.fchmod(tmp.fileno(), 0o600)
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
        cnpj = _extrair_cnpj_da_string(valor_cn, permitir_bruto=True)
        if cnpj:
            return cnpj
    return ""


def _extrair_cnpj_do_serial_number(subject: x509.Name) -> str:
    """Extrai CNPJ do atributo serialNumber (2.5.4.5), se presente."""
    atributos_serial = subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
    for atributo in atributos_serial:
        valor_serial = (atributo.value or "").strip()
        if not valor_serial:
            continue
        # serialNumber normalmente vem como "CNPJ:XXXXXXXXXXXXXX"
        cnpj = _extrair_cnpj_da_string(valor_serial, permitir_bruto=True)
        if cnpj:
            return cnpj
    return ""


def _extrair_cnpj_do_subject_seguro(subject: x509.Name) -> str:
    """Fallback seguro: procura CNPJ explícito em qualquer atributo do Subject.

    Não aceita sequência genérica de 14 dígitos para evitar confundir
    identificadores de OUs da cadeia emissora com CNPJ do titular.
    """
    for atributo in subject:
        valor = (atributo.value or "").strip()
        if not valor:
            continue
        cnpj = _extrair_cnpj_da_string(valor, permitir_bruto=False)
        if cnpj:
            return cnpj
    return ""


def _extrair_cnpj_da_string(texto: str, permitir_bruto: bool = True) -> str:
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

    if permitir_bruto:
        # 3) Sequência de exatamente 14 dígitos (com fronteira de não-dígito)
        padrao_bruto = re.search(r"(?<!\d)(\d{14})(?!\d)", texto)
        if padrao_bruto:
            return padrao_bruto.group(1)

    return ""
