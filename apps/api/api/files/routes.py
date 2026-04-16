"""Endpoints de `/files` (API-11).

Lista arquivos do tenant e gera URL pre-assinada para download.

Protegido por:

- `get_tenant_db` (API-03) — isolamento cross-tenant via RLS
  (`files_isolation` em `0011_files.py`). Cross-tenant retorna 404,
  nao 403, porque do ponto de vista do tenant atacante o recurso
  simplesmente nao existe.
- `require_role` (API-04) — leitura e geracao de URL liberadas para
  todos os papeis (owner/admin/operator/viewer), alinhado com a
  entrada "Download de XLSX / artefatos" da matriz.

Filtros do GET /files:
- `kind`   — um dos enums `nfse_xml|export|pfx|report|other`.
- `company`— UUID de company. Como `files` nao tem FK direta para
  companies (ADR-003 preserva tabela enxuta), filtramos via JOIN em
  `executions` usando `files.source_execution_id = executions.id`.
  Files sem execution associada nao aparecem quando esse filtro e
  usado — comportamento desejado (arquivos "daquela company").
- `from_` / `to` — intervalo sobre `created_at` (ISO 8601 UTC).
- `page` / `page_size` — paginacao classica.

GET /files/{id}/url:
- Gera URL pre-assinada GET com expiracao de 3600s (1h) — alinhado
  com DoD do ticket. Nao permite customizar o TTL (evita abuso).
- Audita `file.download_url` em `audit_logs` com metadata publica
  (`file_id`, `kind`, `object_key`, `bytes`, `expires_in`). A URL
  em si NUNCA e logada nem gravada em banco — e uma credencial
  temporaria de leitura.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from ..storage import StorageError, generate_presigned_get_url
from .schemas import FileKind, FileListOut, FileOut, FileUrlOut

logger = logging.getLogger("api.files")

router = APIRouter(prefix="/files", tags=["files"])

# Leitura e geracao de URL liberadas para todos os papeis (matriz RBAC:
# "Download de XLSX / artefatos" = R para todos).
_ReadAccess = require_role("owner", "admin", "operator", "viewer")

# TTL fixo da URL pre-assinada. O ticket API-11 exige "expira em 1h".
_PRESIGN_TTL_SECONDS = 3600

_COLUMNS = (
    "id, tenant_id, kind, object_key, bytes, checksum_sha256, "
    "source_execution_id, expires_at, created_at, updated_at"
)


def _row_to_out(row) -> FileOut:
    return FileOut(
        id=row.id,
        tenant_id=row.tenant_id,
        kind=row.kind,
        object_key=row.object_key,
        bytes=row.bytes,
        checksum_sha256=row.checksum_sha256,
        source_execution_id=row.source_execution_id,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "",
    response_model=FileListOut,
    dependencies=[Depends(_ReadAccess)],
    summary="Lista arquivos do tenant (com filtros)",
)
def list_files(
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    kind: Optional[FileKind] = Query(default=None),
    company: Optional[UUID] = Query(
        default=None,
        description="Filtra por company via JOIN em executions.",
    ),
    from_: Optional[datetime] = Query(
        default=None,
        alias="from",
        description="Inicio do periodo (created_at >=). ISO 8601 UTC.",
    ),
    to: Optional[datetime] = Query(
        default=None,
        description="Fim do periodo (created_at <). ISO 8601 UTC.",
    ),
) -> FileListOut:
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    where: list[str] = []
    join_sql = ""

    if kind is not None:
        where.append("f.kind = :kind")
        params["kind"] = kind

    if company is not None:
        # JOIN em executions: so inclui files cujo source_execution pertence
        # a company alvo. RLS em executions (DATA-03) ja garante o mesmo
        # tenant — reforcamos com explicit `e.tenant_id = f.tenant_id`
        # como defesa em profundidade.
        join_sql = (
            " JOIN executions e ON e.id = f.source_execution_id "
            "                   AND e.tenant_id = f.tenant_id"
        )
        where.append("e.company_id = :company")
        params["company"] = str(company)

    if from_ is not None:
        where.append("f.created_at >= :from_")
        params["from_"] = from_
    if to is not None:
        where.append("f.created_at < :to")
        params["to"] = to

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total_row = db.execute(
        text(
            f"SELECT COUNT(*) AS n FROM files f{join_sql} {where_sql}"
        ),
        params,
    ).one()

    rows = db.execute(
        text(
            f"""
            SELECT {_COLUMNS}
              FROM files f{join_sql}
              {where_sql}
          ORDER BY f.created_at DESC, f.id
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    return FileListOut(
        items=[_row_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total_row.n),
    )


def _audit_download_url(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    file_id: UUID,
    kind: str,
    object_key: str,
    size_bytes: int,
    expires_in: int,
    request: Request,
) -> None:
    """Grava `audit_logs.file.download_url`. Nunca recebe a URL em si."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    metadata = {
        "file_id": str(file_id),
        "kind": kind,
        "object_key": object_key,
        "bytes": size_bytes,
        "expires_in": expires_in,
    }
    db.execute(
        text(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action,
                resource_type, resource_id,
                ip, user_agent, metadata
            ) VALUES (
                :tid, :uid, 'file.download_url',
                'file', :rid,
                CAST(:ip AS inet), :ua, CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "tid": str(tenant_id),
            "uid": str(actor_user_id),
            "rid": str(file_id),
            "ip": ip,
            "ua": user_agent,
            "meta": json.dumps(metadata, default=str, separators=(",", ":")),
        },
    )


@router.get(
    "/{file_id}/url",
    response_model=FileUrlOut,
    summary="Gera URL pre-assinada (1h) para baixar o arquivo",
)
def get_file_download_url(
    file_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_ReadAccess),
) -> FileUrlOut:
    # RLS faz o filtro por tenant; cross-tenant cai naturalmente em 404.
    row = db.execute(
        text(
            """
            SELECT id, tenant_id, kind, object_key, bytes
              FROM files
             WHERE id = :fid
            """
        ),
        {"fid": str(file_id)},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file nao encontrado",
        )

    try:
        url = generate_presigned_get_url(
            row.object_key, expires_seconds=_PRESIGN_TTL_SECONDS
        )
    except StorageError as exc:
        logger.error(
            "files.url.presign_failed",
            extra={
                "tenant_id": str(claims.tid),
                "file_id": str(file_id),
                "object_key": row.object_key,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="falha ao gerar URL pre-assinada",
        ) from exc

    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        seconds=_PRESIGN_TTL_SECONDS
    )

    _audit_download_url(
        db,
        tenant_id=claims.tid,
        actor_user_id=claims.sub,
        file_id=row.id,
        kind=row.kind,
        object_key=row.object_key,
        size_bytes=int(row.bytes),
        expires_in=_PRESIGN_TTL_SECONDS,
        request=request,
    )

    # Log estruturado sem a URL (que e credencial temporaria).
    logger.info(
        "files.url.issued",
        extra={
            "tenant_id": str(claims.tid),
            "file_id": str(file_id),
            "kind": row.kind,
            "expires_in": _PRESIGN_TTL_SECONDS,
        },
    )

    return FileUrlOut(
        url=url,
        expires_in=_PRESIGN_TTL_SECONDS,
        expires_at=expires_at,
    )
