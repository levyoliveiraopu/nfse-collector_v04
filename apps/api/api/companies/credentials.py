"""Endpoints de upload/revogacao de credencial PFX (API-06).

Fluxo do POST:

    1. RBAC `owner|admin` (matriz `docs/architecture/rbac-matrix.md`).
    2. Confere que a `company_id` existe no tenant corrente (RLS).
    3. Le o multipart `pfx` com teto em bytes; recusa se exceder.
    4. Parseia o PFX com `cryptography.pkcs12` (senha errada -> 400).
    5. Extrai metadados do cert (fingerprint, validade, CN).
    6. Cifra senha + PFX com AES-256-GCM (DEK derivada por tenant).
    7. INSERE em `company_credentials` revogando as ativas anteriores
       da mesma company (na mesma transacao).
    8. PUT do blob cifrado no S3. Em falha, faz rollback e devolve 502.
    9. Registra `audit_logs` com `action='credential.upload'` (sem
       senha, sem PFX, sem ciphertext).

DELETE marca `status='revoked'`, deleta o blob no S3 (best-effort) e
audita.

Garantias de seguranca (DoD do ticket):
- Senha e PFX em claro NUNCA tocam log nem banco. So existem em memoria
  durante o handler — `pfx_bytes` e `password` saem de escopo no fim.
- Logs com `extra={...}` nao incluem nem senha nem ciphertext.
- O `audit_logs.metadata` recebe apenas metadados publicos do cert.
"""

from __future__ import annotations

import logging
import re
from datetime import timezone
from typing import Optional
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import CryptoError, encrypt
from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from ..storage import (
    StorageError,
    credential_object_key,
    delete_credential_blob,
    put_credential_blob,
)
from .credential_schemas import CredentialOut

logger = logging.getLogger("api.credentials")

router = APIRouter(prefix="/companies/{company_id}/credential", tags=["credentials"])

_ReadAccess = require_role(min_role="viewer")
_WriteAccess = require_role("owner", "admin")
_DeleteAccess = require_role("owner", "admin")

_DIGITS_RE = re.compile(r"\D+")


def _digits(value: str) -> str:
    return _DIGITS_RE.sub("", value or "")


def _extract_cert_metadata(cert: x509.Certificate) -> dict:
    """Lê CN, validade e fingerprint SHA-256 do certificado A1."""
    fingerprint = cert.fingerprint(hashes.SHA256()).hex()
    not_before = cert.not_valid_before_utc.replace(tzinfo=timezone.utc) \
        if cert.not_valid_before_utc.tzinfo is None else cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc.replace(tzinfo=timezone.utc) \
        if cert.not_valid_after_utc.tzinfo is None else cert.not_valid_after_utc

    cn = ""
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            cn = cn_attrs[0].value or ""
    except Exception:  # noqa: BLE001 - subject malformado: ignora
        cn = ""

    return {
        "fingerprint": fingerprint,
        "not_before": not_before,
        "not_after": not_after,
        "cn": cn,
    }


def _cn_matches_cnpj(cn: str, company_cnpj: str) -> bool:
    """Confere se o CN do cert contem o CNPJ da company.

    Padrao e-CNPJ: o CN costuma ser `<RAZAO_SOCIAL>:<CNPJ>` (14 digitos).
    Aceitamos qualquer ocorrencia dos 14 digitos limpos no CN.
    """
    target = _digits(company_cnpj)
    if not target or len(target) != 14:
        return False
    haystack = _digits(cn)
    return target in haystack


def _fetch_company(db: Session, company_id: UUID) -> tuple[UUID, str]:
    """Devolve `(tenant_id, cnpj)` da company viva, ou 404."""
    row = db.execute(
        text(
            """
            SELECT tenant_id, cnpj
              FROM companies
             WHERE id = :cid AND deleted_at IS NULL
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="company nao encontrada",
        )
    return UUID(str(row.tenant_id)), str(row.cnpj)


def _audit(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    action: str,
    resource_id: str,
    request: Request,
    metadata: dict,
) -> None:
    """Insere uma linha em `audit_logs`. Nunca recebe segredo."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action,
                resource_type, resource_id,
                ip, user_agent, metadata
            ) VALUES (
                :tid, :uid, :action,
                'company_credential', :rid,
                CAST(:ip AS inet), :ua, CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "tid": str(tenant_id),
            "uid": str(actor_user_id),
            "action": action,
            "rid": resource_id,
            "ip": ip,
            "ua": user_agent,
            # Serializacao via psycopg adapter de jsonb: aceitamos string JSON.
            "meta": _to_json(metadata),
        },
    )


def _to_json(value: dict) -> str:
    import json

    # `default=str` cobre datetime sem perder precisao ISO.
    return json.dumps(value, default=str, separators=(",", ":"))


def _row_to_out(row, *, cn_matches_cnpj: Optional[bool]) -> CredentialOut:
    return CredentialOut(
        id=row.id,
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        type=row.type,
        pfx_object_key=row.pfx_object_key,
        cert_fingerprint=row.cert_fingerprint,
        cert_not_before=row.cert_not_before,
        cert_not_after=row.cert_not_after,
        status=row.status,
        cn_matches_cnpj=cn_matches_cnpj,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "",
    response_model=CredentialOut,
    status_code=status.HTTP_200_OK,
    summary="Le a credencial ativa de uma company (metadados publicos)",
)
def get_credential(
    company_id: UUID,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_ReadAccess),  # noqa: ARG001
) -> CredentialOut:
    """Retorna a credencial `active` mais recente da company.

    Nunca expoe ciphertext, senha ou bytes do PFX — apenas metadados
    publicos do certificado (fingerprint, validade, status, CN match).
    404 quando nao ha credencial ativa (company cross-tenant tambem cai
    aqui por RLS).
    """
    tenant_id, company_cnpj = _fetch_company(db, company_id)

    row = db.execute(
        text(
            """
            SELECT id, tenant_id, company_id, type,
                   pfx_object_key, cert_fingerprint, cert_not_before,
                   cert_not_after, status, created_at, updated_at
              FROM company_credentials
             WHERE company_id = :cid AND status = 'active'
             ORDER BY created_at DESC
             LIMIT 1
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="credencial nao configurada",
        )

    # `cn_matches_cnpj=None` reflete que o valor nao e persistido em
    # `company_credentials` (so o upload conhece o CN). O painel web
    # so renderiza warning quando o POST retorna `False` explicito.
    _ = tenant_id  # ja presente no row; mantido para doc de fluxo
    _ = company_cnpj
    return _row_to_out(row, cn_matches_cnpj=None)


@router.post(
    "",
    response_model=CredentialOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de PFX A1 cifrado para uma company",
)
async def upload_credential(
    request: Request,
    company_id: UUID,
    pfx: UploadFile = File(..., description="Arquivo .pfx (PKCS#12) do certificado A1"),
    password: str = Form(..., min_length=1, description="Senha do PFX"),
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_WriteAccess),
) -> CredentialOut:
    settings = get_settings()

    # 1. Confere company no tenant corrente (RLS).
    tenant_id, company_cnpj = _fetch_company(db, company_id)

    # 2. Le o multipart com teto.
    max_bytes = settings.credential_max_pfx_bytes
    pfx_bytes = await pfx.read(max_bytes + 1)
    if len(pfx_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"pfx excede o limite de {max_bytes} bytes",
        )
    if not pfx_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pfx vazio",
        )

    # 3. Parseia o PFX. Senha errada / formato invalido -> 400.
    try:
        private_key, cert, _additional = pkcs12.load_key_and_certificates(
            pfx_bytes,
            password.encode("utf-8"),
        )
    except ValueError as exc:
        # `cryptography` levanta ValueError com "Invalid password or PKCS12 data"
        # tanto para senha errada quanto para PFX corrompido. Mantemos
        # mensagem agnostica para nao revelar qual foi o problema.
        logger.info(
            "credentials.upload.parse_failed",
            extra={"tenant_id": str(tenant_id), "company_id": str(company_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pfx invalido ou senha incorreta",
        ) from exc

    if private_key is None or cert is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pfx nao contem chave privada ou certificado",
        )

    # 4. Extrai metadados do cert.
    meta = _extract_cert_metadata(cert)
    cn_matches = _cn_matches_cnpj(meta["cn"], company_cnpj)
    if not cn_matches:
        # Warn obrigatoria pelo ticket: aceitamos mas sinalizamos.
        logger.warning(
            "credentials.upload.cn_mismatch",
            extra={
                "tenant_id": str(tenant_id),
                "company_id": str(company_id),
                "cn": meta["cn"],
                # cnpj nao e segredo (esta no payload da company), logamos
                # apenas os 8 primeiros digitos para facilitar diagnostico.
                "company_cnpj_prefix": company_cnpj[:8],
            },
        )

    # 5. Cifra senha + PFX. Falha aqui = 500 (erro de configuracao da KEK).
    try:
        password_ct = encrypt(password.encode("utf-8"), tenant_id)
        pfx_ct = encrypt(pfx_bytes, tenant_id)
    except CryptoError as exc:
        logger.error(
            "credentials.upload.crypto_failed",
            extra={"tenant_id": str(tenant_id), "company_id": str(company_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="erro de criptografia (KEK ausente ou invalida)",
        ) from exc

    # 6. Revoga as ativas anteriores e insere a nova. Tudo na mesma tx.
    db.execute(
        text(
            """
            UPDATE company_credentials
               SET status = 'revoked', updated_at = now()
             WHERE company_id = :cid AND status = 'active'
            """
        ),
        {"cid": str(company_id)},
    )

    inserted = db.execute(
        text(
            """
            INSERT INTO company_credentials (
                tenant_id, company_id, type,
                pfx_object_key, pfx_password_ciphertext,
                cert_fingerprint, cert_not_before, cert_not_after,
                status
            ) VALUES (
                :tid, :cid, 'pfx_a1',
                :okey, :pwd_ct,
                :fp, :nbf, :naf,
                'active'
            )
            RETURNING id
            """
        ),
        {
            "tid": str(tenant_id),
            "cid": str(company_id),
            # Placeholder de object_key — atualizado abaixo apos saber o id.
            "okey": "pending",
            "pwd_ct": password_ct,
            "fp": meta["fingerprint"],
            "nbf": meta["not_before"],
            "naf": meta["not_after"],
        },
    ).one()
    credential_id = UUID(str(inserted.id))

    object_key = credential_object_key(tenant_id, credential_id)

    # Atualiza o object_key calculado com o id recem-criado.
    db.execute(
        text(
            """
            UPDATE company_credentials
               SET pfx_object_key = :okey
             WHERE id = :id
            """
        ),
        {"okey": object_key, "id": str(credential_id)},
    )

    # 7. PUT no S3. Falha aqui forca rollback (transacao da get_tenant_db).
    try:
        put_credential_blob(tenant_id, credential_id, pfx_ct)
    except StorageError as exc:
        # A excecao propaga; get_tenant_db faz rollback automatico.
        logger.error(
            "credentials.upload.s3_failed",
            extra={"tenant_id": str(tenant_id), "company_id": str(company_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="falha ao gravar credencial no storage",
        ) from exc

    # 8. Audit log (sem segredo).
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=claims.sub,
        action="credential.upload",
        resource_id=str(credential_id),
        request=request,
        metadata={
            "company_id": str(company_id),
            "fingerprint": meta["fingerprint"],
            "not_before": meta["not_before"].isoformat(),
            "not_after": meta["not_after"].isoformat(),
            "cn_matches_cnpj": cn_matches,
            "pfx_object_key": object_key,
        },
    )

    # Reconsulta para devolver os defaults (created_at/updated_at).
    row = db.execute(
        text(
            """
            SELECT id, tenant_id, company_id, type,
                   pfx_object_key, cert_fingerprint, cert_not_before,
                   cert_not_after, status, created_at, updated_at
              FROM company_credentials
             WHERE id = :id
            """
        ),
        {"id": str(credential_id)},
    ).one()

    logger.info(
        "credentials.upload.ok",
        extra={
            "tenant_id": str(tenant_id),
            "company_id": str(company_id),
            "credential_id": str(credential_id),
            "fingerprint": meta["fingerprint"],
            "not_after": meta["not_after"].isoformat(),
        },
    )
    return _row_to_out(row, cn_matches_cnpj=cn_matches)


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    summary="Revoga a credencial ativa de uma company",
    response_model=dict,
)
def revoke_credential(
    request: Request,
    company_id: UUID,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_DeleteAccess),
) -> dict:
    # Confere company (404 se nao existe / cross-tenant via RLS).
    tenant_id, _cnpj = _fetch_company(db, company_id)

    rows = db.execute(
        text(
            """
            UPDATE company_credentials
               SET status = 'revoked', updated_at = now()
             WHERE company_id = :cid AND status = 'active'
         RETURNING id, pfx_object_key
            """
        ),
        {"cid": str(company_id)},
    ).all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="nenhuma credencial ativa para revogar",
        )

    revoked_ids: list[str] = []
    for row in rows:
        revoked_ids.append(str(row.id))
        # Best-effort: falha de S3 nao impede a revogacao logica.
        try:
            delete_credential_blob(row.pfx_object_key)
        except StorageError as exc:
            logger.warning(
                "credentials.revoke.s3_delete_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "company_id": str(company_id),
                    "credential_id": str(row.id),
                    "key": row.pfx_object_key,
                    "error": str(exc),
                },
            )

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=claims.sub,
        action="credential.revoke",
        resource_id=revoked_ids[0] if len(revoked_ids) == 1 else ",".join(revoked_ids),
        request=request,
        metadata={
            "company_id": str(company_id),
            "revoked_credential_ids": revoked_ids,
        },
    )

    logger.info(
        "credentials.revoke.ok",
        extra={
            "tenant_id": str(tenant_id),
            "company_id": str(company_id),
            "revoked": revoked_ids,
        },
    )
    return {"revoked": revoked_ids}
