"""Jobs RQ executados pelo worker (API-13 e API-15).

Modulo dedicado a funcoes que a API enfileira no Redis via string —
o worker resolve o import no momento do pick. Vive em `worker_core`
para manter a API desacoplada do motor.

Entregas atuais:

- `build_export(export_id)`: baixa XMLs do S3 do tenant/company num
  periodo, zipa em `tmpfs`, faz upload do ZIP no bucket e atualiza
  `exports` + `files` + `notifications`. Limite de 2 GB (ticket
  API-15) para proteger tmpfs/RAM.
- `run_execution(execution_id)`: orquestra a coleta ponta-a-ponta,
  com decrypt de credencial, coleta NFSe, upload XML e escrita de
  `execution_items`/`occurrences`.

Fluxo resumido do `run_execution`:
1. carrega contexto de `executions`/`companies`/`company_credentials`;
2. decifra PFX + senha com envelope AES-256-GCM;
3. coleta NFSe e persiste `execution_items` com `ON CONFLICT DO NOTHING`;
4. atualiza status final (`succeeded`/`partial`/`failed`) e ocorrencias.

O pacote nao depende de `apps/api` — fala com Postgres via `psycopg`
e com S3 via `worker_core.storage.S3StorageClient`. URL do banco vem
de `WORKER_DATABASE_URL` (fallback: `API_DATABASE_URL`). O worker
deve rodar como role com `BYPASSRLS` (tipicamente `app_admin`); como
defesa em profundidade as queries filtram explicitamente por
`tenant_id`.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

import requests
from rq import get_current_job
from sqlalchemy import text

from worker_core.collector import FetchSummary, NfseItem, fetch_nfse
from worker_core.fetcher import PortalRequestError
from worker_core.crypto import CryptoError, decrypt
from worker_core.db import get_admin_session, get_tenant_session
from worker_core.db_nsu import DbNsuSource
from worker_core.storage import S3StorageClient, StorageError

logger = logging.getLogger("worker_core.jobs")

# Hard cap do export (DoD do ticket API-15: "aborta export > 2GB").
DEFAULT_MAX_EXPORT_BYTES = 2 * 1024**3  # 2 GiB


def _resolve_job_dry_run(explicit: Optional[bool]) -> bool:
    """Resolve dry_run do argumento explicito ou do meta do job RQ atual."""
    if explicit is not None:
        return bool(explicit)
    job = get_current_job()
    meta = getattr(job, "meta", None) if job is not None else None
    return bool(meta.get("dry_run")) if isinstance(meta, dict) else False


class _DryRunNsuSource:
    """Proxy que permite leitura de NSU, mas bloqueia persistencia em dry-run."""

    def __init__(self, inner: DbNsuSource) -> None:
        self._inner = inner

    def get(self, cnpj: str) -> int:
        return self._inner.get(cnpj)

    def set(self, cnpj: str, nsu: int) -> None:  # noqa: ARG002
        logger.info("jobs.run_execution.dry_run_skip_nsu_update", extra={"cnpj": cnpj})


class ExportError(RuntimeError):
    """Erro estruturado para encerrar `build_export` com codigo claro."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _normalize_dsn(url: str) -> str:
    """Converte SQLAlchemy DSN para `psycopg.connect` (mesma forma que conftest)."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def _db_url() -> str:
    url = (os.environ.get("WORKER_DATABASE_URL") or os.environ.get("API_DATABASE_URL") or "").strip()
    if not url:
        raise ExportError(
            "config_missing",
            "WORKER_DATABASE_URL / API_DATABASE_URL nao definida",
        )
    return _normalize_dsn(url)


def _max_export_bytes() -> int:
    raw = os.environ.get("EXPORT_MAX_BYTES")
    if not raw:
        return DEFAULT_MAX_EXPORT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_EXPORT_BYTES
    return value if value > 0 else DEFAULT_MAX_EXPORT_BYTES


def _tmpfs_dir() -> Path:
    """Diretorio para montar o ZIP. Prefere tmpfs (`/dev/shm`), cai para tmp."""
    candidate = Path(
        os.environ.get("EXPORT_TMPFS_DIR") or ("/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir())
    )
    if not candidate.is_dir():
        return Path(tempfile.gettempdir())
    return candidate


@contextmanager
def _connect():
    """Abre conexao psycopg. Requer lazy import para nao obrigar psycopg em tests unitarios."""
    try:
        import psycopg  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise ExportError("config_missing", "psycopg nao instalado no worker") from exc

    conn = psycopg.connect(_db_url())
    try:
        yield conn
    finally:
        conn.close()


@dataclass(frozen=True)
class _ExportRow:
    id: uuid.UUID
    tenant_id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    period_start: datetime
    period_end: datetime
    status: str


def _load_export(conn, export_id: uuid.UUID) -> Optional[_ExportRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, company_id, kind,
                   period_start, period_end, status
              FROM exports WHERE id = %s
            """,
            (str(export_id),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _ExportRow(
        id=uuid.UUID(str(row[0])),
        tenant_id=uuid.UUID(str(row[1])),
        company_id=uuid.UUID(str(row[2])),
        kind=row[3],
        period_start=row[4],
        period_end=row[5],
        status=row[6],
    )


def _mark_running(conn, export_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exports
               SET status = 'running',
                   started_at = COALESCE(started_at, now()),
                   updated_at = now()
             WHERE id = %s
            """,
            (str(export_id),),
        )
    conn.commit()


def _mark_failed(conn, export_id: uuid.UUID, *, code: str, message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exports
               SET status = 'failed',
                   error_code = %s,
                   error_message = %s,
                   finished_at = now(),
                   updated_at = now()
             WHERE id = %s
            """,
            (code, message[:500], str(export_id)),
        )
    conn.commit()


def _mark_empty(conn, export_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exports
               SET status = 'empty',
                   finished_at = now(),
                   updated_at = now()
             WHERE id = %s
            """,
            (str(export_id),),
        )
    conn.commit()


def _list_items(
    conn,
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    period_start,
    period_end,
) -> list[tuple[int, str]]:
    """Lista (nsu, xml_object_key) dos itens do periodo."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ei.nsu, ei.xml_object_key
              FROM execution_items ei
              JOIN executions e
                ON e.id = ei.execution_id
               AND e.tenant_id = ei.tenant_id
             WHERE ei.tenant_id = %s
               AND e.company_id = %s
               AND ei.status = 'ok'
               AND ei.xml_object_key IS NOT NULL
               AND ei.data_emissao >= %s
               AND ei.data_emissao < (%s::date + INTERVAL '1 day')
             ORDER BY ei.nsu
            """,
            (str(tenant_id), str(company_id), period_start, period_end),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def _insert_file(
    conn,
    *,
    file_id: uuid.UUID,
    tenant_id: uuid.UUID,
    object_key: str,
    size_bytes: int,
    checksum_sha256: str,
    expires_at: datetime,
) -> uuid.UUID:
    """Insere 1 linha em `files` com UUID explicito.

    O UUID precisa ser o mesmo usado para compor o `object_key` no
    S3 (export_object_key): se deixassemos o default `gen_random_uuid`
    do banco gerar, o id da linha divergiria da chave no bucket.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO files (
                id, tenant_id, kind, object_key, bytes,
                checksum_sha256, expires_at
            ) VALUES (%s, %s, 'export', %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(file_id),
                str(tenant_id),
                object_key,
                size_bytes,
                checksum_sha256,
                expires_at,
            ),
        )
        return uuid.UUID(str(cur.fetchone()[0]))


def _mark_ready(
    conn,
    export_id: uuid.UUID,
    *,
    file_id: uuid.UUID,
    items_count: int,
    total_bytes: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exports
               SET status = 'ready',
                   file_id = %s,
                   items_count = %s,
                   total_bytes = %s,
                   finished_at = now(),
                   updated_at = now()
             WHERE id = %s
            """,
            (str(file_id), items_count, total_bytes, str(export_id)),
        )
    conn.commit()


def _enqueue_notifications(
    conn,
    *,
    tenant_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    export_id: uuid.UUID,
    file_id: uuid.UUID,
    kind: str,
) -> None:
    """Enfileira 2 notificacoes (inapp + email) com payload comum.

    Delivery real (SMTP / push) fica para ticket futuro — mesmo padrao
    do APP-09. A UI/worker de entrega consumira daqui.
    """
    payload = json.dumps(
        {
            "export_id": str(export_id),
            "file_id": str(file_id),
            "kind": kind,
        },
        separators=(",", ":"),
    )
    with conn.cursor() as cur:
        for channel in ("inapp", "email"):
            cur.execute(
                """
                INSERT INTO notifications (
                    tenant_id, user_id, channel, type, payload, status
                ) VALUES (%s, %s, %s, 'export.ready', %s::jsonb, 'pending')
                """,
                (
                    str(tenant_id),
                    str(user_id) if user_id else None,
                    channel,
                    payload,
                ),
            )
    conn.commit()


def _requested_by(conn, export_id: uuid.UUID) -> Optional[uuid.UUID]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT requested_by_user_id FROM exports WHERE id = %s",
            (str(export_id),),
        )
        row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    return uuid.UUID(str(row[0]))


def build_export(
    export_id: str,
    *,
    storage: Optional[S3StorageClient] = None,
) -> dict:
    """Entrypoint RQ para construir um export assincrono.

    Fluxo:
    1. Carrega `exports` e marca `status='running'`.
    2. Lista `execution_items` do tenant/company/periodo com XML.
    3. Se lista vazia -> `status='empty'` e encerra.
    4. Cria ZIP em tmpfs, streamando XMLs do S3 um por um. Aborta
       com `size_limit_exceeded` se ultrapassar `EXPORT_MAX_BYTES`.
    5. Faz upload do ZIP final como export, registra `files` com
       `expires_at = now + 30d`, marca export como `ready`.
    6. Enfileira notificacoes `inapp`+`email` tipo `export.ready`.

    Retorna dict resumindo o resultado (util em testes). Em erro,
    levanta `ExportError` — RQ persiste no failed registry.
    """
    eid = uuid.UUID(str(export_id))
    max_bytes = _max_export_bytes()
    storage = storage or S3StorageClient()

    with _connect() as conn:
        export = _load_export(conn, eid)
        if export is None:
            raise ExportError("not_found", f"export {eid} nao encontrado")
        if export.status not in {"queued", "running"}:
            # Idempotencia: se ja terminou, nao refaz.
            logger.info(
                "jobs.build_export.skip_terminal",
                extra={"export_id": str(eid), "status": export.status},
            )
            return {"status": export.status, "reason": "already_finalized"}
        if export.kind != "zip_xml":
            _mark_failed(
                conn,
                eid,
                code="kind_not_implemented",
                message=f"kind {export.kind!r} nao implementado neste release",
            )
            raise ExportError("kind_not_implemented", f"kind {export.kind!r} nao suportado")

        _mark_running(conn, eid)

        try:
            items = _list_items(
                conn,
                tenant_id=export.tenant_id,
                company_id=export.company_id,
                period_start=export.period_start,
                period_end=export.period_end,
            )
        except Exception as exc:  # noqa: BLE001
            _mark_failed(conn, eid, code="db_error", message=str(exc))
            raise ExportError("db_error", str(exc)) from exc

        if not items:
            _mark_empty(conn, eid)
            logger.info(
                "jobs.build_export.empty",
                extra={"export_id": str(eid)},
            )
            return {"status": "empty", "items": 0}

        tmpdir = _tmpfs_dir()
        tmpdir.mkdir(parents=True, exist_ok=True)
        zip_fd, zip_path_str = tempfile.mkstemp(dir=str(tmpdir), prefix="export-", suffix=".zip")
        os.close(zip_fd)  # ZipFile abre pelo nome.
        zip_path = Path(zip_path_str)

        try:
            written_bytes = 0
            with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for nsu, object_key in items:
                    try:
                        body = storage.download_bytes(object_key)
                    except StorageError as exc:
                        raise ExportError("s3_error", f"falha ao baixar {object_key}: {exc}") from exc
                    # Projecao: limite conservador pelo tamanho dos XMLs
                    # (ZIP sempre sera menor ou igual com deflate); se ja
                    # passou do cap no payload bruto, aborta.
                    written_bytes += len(body)
                    if written_bytes > max_bytes:
                        raise ExportError(
                            "size_limit_exceeded",
                            f"export excede {max_bytes} bytes",
                        )
                    zf.writestr(f"{nsu}.xml", body)

            zip_bytes = zip_path.read_bytes()
            file_id = uuid.uuid4()
            upload = storage.upload_export(
                tenant_id=export.tenant_id,
                file_id=file_id,
                path_or_bytes=zip_bytes,
                ext="zip",
            )
        except ExportError as exc:
            _mark_failed(conn, eid, code=exc.code, message=str(exc))
            logger.warning(
                "jobs.build_export.failed",
                extra={"export_id": str(eid), "code": exc.code},
            )
            raise
        except Exception as exc:  # noqa: BLE001
            _mark_failed(conn, eid, code="unexpected", message=str(exc))
            logger.exception(
                "jobs.build_export.unexpected",
                extra={"export_id": str(eid)},
            )
            raise ExportError("unexpected", str(exc)) from exc
        finally:
            try:
                zip_path.unlink(missing_ok=True)
            except OSError:
                pass

        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)
        _insert_file(
            conn,
            file_id=file_id,
            tenant_id=export.tenant_id,
            object_key=upload.object_key,
            size_bytes=upload.size,
            checksum_sha256=upload.sha256,
            expires_at=expires_at,
        )

        _mark_ready(
            conn,
            eid,
            file_id=file_id,
            items_count=len(items),
            total_bytes=upload.size,
        )

        requested_by = _requested_by(conn, eid)
        _enqueue_notifications(
            conn,
            tenant_id=export.tenant_id,
            user_id=requested_by,
            export_id=eid,
            file_id=file_id,
            kind=export.kind,
        )

        logger.info(
            "jobs.build_export.ok",
            extra={
                "export_id": str(eid),
                "items": len(items),
                "bytes": upload.size,
                "object_key": upload.object_key,
            },
        )
        return {
            "status": "ready",
            "items": len(items),
            "bytes": upload.size,
            "file_id": str(file_id),
            "object_key": upload.object_key,
        }


# Codigos de ocorrencia (docs/architecture/occurrence-codes.md).
OCC_CRED_INVALID = "CRED_INVALID"
OCC_CERT_EXPIRED = "CERT_EXPIRED"
OCC_PORTAL_5XX = "PORTAL_5XX"
OCC_PORTAL_TIMEOUT = "PORTAL_TIMEOUT"
OCC_PORTAL_RATE_LIMIT = "PORTAL_RATE_LIMIT"
OCC_PORTAL_HTTP_ERROR = "PORTAL_HTTP_ERROR"
OCC_PARSE_ERROR = "PARSE_ERROR"
OCC_STORAGE_ERROR = "STORAGE_ERROR"
OCC_UNKNOWN = "UNKNOWN"


def _classify_mtls_value_error(exc: ValueError) -> tuple[str, str]:
    msg = str(exc).lower()
    if "vencid" in msg or "expir" in msg:
        return OCC_CERT_EXPIRED, "mtls_cert_expired"
    if "cnpj" in msg or "cn" in msg or "diverg" in msg:
        return OCC_CRED_INVALID, "mtls_cert_subject_mismatch"
    if "senha" in msg or "password" in msg:
        return OCC_CRED_INVALID, "mtls_pfx_password_invalid"
    if "pfx" in msg or "pkcs" in msg or "certificado" in msg:
        return OCC_CRED_INVALID, "mtls_pfx_invalid"
    return OCC_CRED_INVALID, "mtls_session_failed"


def _portal_occurrence_code(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, requests.Timeout):
        return OCC_PORTAL_TIMEOUT, "collector_portal_timeout"
    if isinstance(exc, requests.ConnectionError):
        return OCC_PORTAL_HTTP_ERROR, "collector_portal_connection_error"
    if isinstance(exc, PortalRequestError):
        if exc.code == "ADN_HTTP_5XX":
            return OCC_PORTAL_5XX, "collector_portal_5xx"
        if exc.code == "ADN_RATE_LIMIT":
            return OCC_PORTAL_RATE_LIMIT, "collector_portal_rate_limit"
        return OCC_PORTAL_HTTP_ERROR, "collector_portal_http_error"
    return OCC_UNKNOWN, "collector_error"


class JobError(RuntimeError):
    """Erro de orquestracao do worker. Marca execucao como `failed`."""


@dataclass(frozen=True)
class _ExecutionContext:
    """Snapshot das linhas lidas no inicio do job."""

    execution_id: UUID
    tenant_id: UUID
    company_id: UUID
    cnpj: str
    pfx_object_key: str
    pfx_password_ciphertext: bytes
    credential_id: UUID


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_execution(
    execution_id: str,
    *,
    storage_client: Optional[S3StorageClient] = None,
    read_credential_blob: Optional[Callable[[str], bytes]] = None,
    dry_run: Optional[bool] = None,
) -> dict:
    """Handler picado pelo RQ worker.

    Args:
        execution_id:         UUID da linha em `executions` (string, como
                              serializado pelo RQ).
        storage_client:       Injecao para testes. Default: `S3StorageClient()`.
        read_credential_blob: Injecao para testes. Default: usa boto3 para
                              ler o blob cifrado do prefixo de credenciais.
        dry_run:              Quando True, coleta e contabiliza, mas nao faz
                              upload dos XMLs nem persiste execution_items/NSU.
                              Se omitido, le `job.meta["dry_run"]` do RQ.

    Retorna um dict com o status final e os contadores — expoe para o
    RQ result_ttl. Excecoes nao-capturadas marcam a execucao como `failed`
    e propagam para o RQ (que gravara em failure_ttl).
    """
    eid = _coerce_uuid(execution_id, "execution_id")
    logger.info("jobs.run_execution.start", extra={"execution_id": str(eid)})

    ctx = _load_execution_context(eid)
    if ctx is None:
        # Execucao sumiu entre o enqueue e o pick. Nao temos tenant_id pra
        # marcar como failed — apenas loga e sai (DB e RLS mantem auditoria).
        logger.warning("jobs.run_execution.not_found", extra={"execution_id": str(eid)})
        return {"status": "not_found", "execution_id": str(eid)}

    dry_run_enabled = _resolve_job_dry_run(dry_run)
    storage = storage_client
    if storage is None and not dry_run_enabled:
        storage = S3StorageClient()
    read_blob = read_credential_blob or _default_read_credential_blob

    _mark_running(ctx)

    try:
        pfx_bytes, pfx_password = _decrypt_credential(ctx, read_blob)
    except CryptoError as exc:
        _mark_failed(ctx, error_summary="credential_decrypt_failed")
        _create_occurrence(
            ctx, code=OCC_CRED_INVALID, severity="error", title="Credencial nao pode ser decifrada", detail=str(exc)
        )
        raise JobError("credential_decrypt_failed") from exc
    except StorageError as exc:
        _mark_failed(ctx, error_summary="credential_blob_missing")
        _create_occurrence(
            ctx, code=OCC_CRED_INVALID, severity="error", title="Blob de credencial ausente no storage", detail=str(exc)
        )
        raise JobError("credential_blob_missing") from exc

    db_nsu_source = DbNsuSource(
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        session_factory=get_tenant_session,
    )
    nsu_source = _DryRunNsuSource(db_nsu_source) if dry_run_enabled else db_nsu_source

    items_ok = 0
    items_fail = 0
    storage_errors = 0

    def _on_progress(item: NfseItem) -> None:
        nonlocal items_ok, items_fail, storage_errors
        try:
            if dry_run_enabled:
                if item.status == "ok":
                    items_ok += 1
                else:
                    items_fail += 1
                logger.info(
                    "jobs.run_execution.dry_run_item",
                    extra={
                        "execution_id": str(ctx.execution_id),
                        "nsu": item.nsu,
                        "status": item.status,
                    },
                )
                return

            xml_key: Optional[str] = None
            if item.xml_bytes is not None:
                try:
                    if storage is None:
                        raise StorageError("storage indisponivel")
                    result = storage.upload_xml(
                        ctx.tenant_id,
                        ctx.execution_id,
                        item.nsu,
                        item.xml_bytes,
                    )
                    xml_key = result.object_key
                except StorageError as exc:
                    storage_errors += 1
                    logger.warning(
                        "jobs.run_execution.xml_upload_failed",
                        extra={
                            "execution_id": str(ctx.execution_id),
                            "nsu": item.nsu,
                            "error": str(exc),
                        },
                    )

            inserted = _insert_execution_item(ctx, item, xml_key)
            if not inserted:
                # Duplicata via unique `(tenant_id, chave_nfse)`. Nao conta
                # nem como ok nem como fail — e um retry idempotente.
                logger.info(
                    "jobs.run_execution.item_duplicate",
                    extra={
                        "execution_id": str(ctx.execution_id),
                        "chave_nfse": item.chave_nfse,
                        "nsu": item.nsu,
                    },
                )
                return

            if item.status == "ok":
                items_ok += 1
            else:
                items_fail += 1
        except Exception:  # noqa: BLE001 — loga e continua
            items_fail += 1
            logger.exception(
                "jobs.run_execution.progress_callback_error",
                extra={"execution_id": str(ctx.execution_id), "nsu": item.nsu},
            )

    def _on_log(evento: str, payload: dict) -> None:
        logger.info("jobs.fetch.%s", evento, extra={"payload": payload})

    try:
        summary = fetch_nfse(
            pfx_bytes=pfx_bytes,
            pfx_password=pfx_password,
            cnpj=ctx.cnpj,
            nsu_source=nsu_source,
            on_progress=_on_progress,
            on_log=_on_log,
            persist_nsu=False,
        )
    except ValueError as exc:
        code, error_summary = _classify_mtls_value_error(exc)
        _mark_failed(ctx, error_summary=error_summary)
        _create_occurrence(ctx, code=code, severity="error", title="Falha na sessao mTLS", detail=str(exc))
        raise JobError(error_summary) from exc
    except (requests.Timeout, requests.ConnectionError, PortalRequestError) as exc:
        code, error_summary = _portal_occurrence_code(exc)
        _mark_failed(ctx, error_summary=error_summary)
        _create_occurrence(ctx, code=code, severity="error", title="Falha no portal ADN", detail=str(exc))
        raise JobError(error_summary) from exc
        # mtls_session levanta ValueError para PFX invalido / senha errada /
        # cert vencido. Diferenciamos via mensagem para classificar ocorrencia.
        msg = str(exc).lower()
        code = OCC_CERT_EXPIRED if "vencid" in msg or "expir" in msg else OCC_CRED_INVALID
        _mark_failed(ctx, error_summary="mtls_session_failed")
        _create_occurrence(ctx, code=code, severity="error", title="Falha na sessao mTLS", detail=str(exc))
        raise JobError("mtls_session_failed") from exc
    except Exception as exc:  # noqa: BLE001 — erro inesperado do coletor
        _mark_failed(ctx, error_summary="collector_error")
        _create_occurrence(
            ctx, code=OCC_UNKNOWN, severity="error", title="Erro nao categorizado no coletor", detail=str(exc)
        )
        raise JobError("collector_error") from exc

    final_status = _decide_final_status(summary, items_ok, items_fail, storage_errors)
    _mark_finished(
        ctx,
        status=final_status,
        summary=summary,
        items_ok=items_ok,
        items_fail=items_fail,
    )

    if final_status == "succeeded" and not dry_run_enabled and summary.nsu_to > summary.nsu_from:
        db_nsu_source.set(ctx.cnpj, int(summary.nsu_to))

    if storage_errors:
        _create_occurrence(
            ctx,
            code=OCC_STORAGE_ERROR,
            severity="warning",
            title=f"{storage_errors} XML(s) falharam no upload para S3",
            detail=f"storage_errors={storage_errors}",
        )
    if summary.fatal_rejected:
        _create_occurrence(
            ctx,
            code=OCC_PORTAL_5XX,
            severity="error",
            title="Portal ADN rejeitou a paginacao",
            detail="fatal_rejected=True",
        )
    if summary.total_erro:
        _create_occurrence(
            ctx,
            code=OCC_PARSE_ERROR,
            severity="warning",
            title=f"{summary.total_erro} XML(s) com parse_error",
            detail=f"total_erro={summary.total_erro}",
        )

    logger.info(
        "jobs.run_execution.ok",
        extra={
            "execution_id": str(ctx.execution_id),
            "tenant_id": str(ctx.tenant_id),
            "status": final_status,
            "items_ok": items_ok,
            "items_fail": items_fail,
            "storage_errors": storage_errors,
            "dry_run": dry_run_enabled,
            "nsu_from": summary.nsu_from,
            "nsu_to": summary.nsu_to,
        },
    )

    return {
        "execution_id": str(ctx.execution_id),
        "status": final_status,
        "items_ok": items_ok,
        "items_fail": items_fail,
        "storage_errors": storage_errors,
        "dry_run": dry_run_enabled,
        "nsu_from": summary.nsu_from,
        "nsu_to": summary.nsu_to,
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _load_execution_context(execution_id: UUID) -> Optional[_ExecutionContext]:
    """Le tenant_id da execution (admin) e depois carrega o resto via RLS."""
    with get_admin_session() as session:
        row = session.execute(
            text(
                """
                SELECT id, tenant_id, company_id
                  FROM executions
                 WHERE id = :eid
                """
            ),
            {"eid": str(execution_id)},
        ).one_or_none()
        if row is None:
            return None
        tenant_id = UUID(str(row.tenant_id))
        company_id = UUID(str(row.company_id))

    with get_tenant_session(tenant_id) as session:
        company_row = session.execute(
            text("SELECT cnpj FROM companies WHERE id = :cid"),
            {"cid": str(company_id)},
        ).one_or_none()
        cred_row = session.execute(
            text(
                """
                SELECT id, pfx_object_key, pfx_password_ciphertext
                  FROM company_credentials
                 WHERE company_id = :cid
                   AND status = 'active'
                 ORDER BY created_at DESC
                 LIMIT 1
                """
            ),
            {"cid": str(company_id)},
        ).one_or_none()
        if company_row is None or cred_row is None:
            return None

    return _ExecutionContext(
        execution_id=execution_id,
        tenant_id=tenant_id,
        company_id=company_id,
        cnpj=str(company_row.cnpj),
        pfx_object_key=str(cred_row.pfx_object_key),
        pfx_password_ciphertext=bytes(cred_row.pfx_password_ciphertext),
        credential_id=UUID(str(cred_row.id)),
    )


def _mark_running(ctx: _ExecutionContext) -> None:
    with get_tenant_session(ctx.tenant_id) as session:
        session.execute(
            text(
                """
                UPDATE executions
                   SET status = 'running',
                       started_at = COALESCE(started_at, now()),
                       updated_at = now()
                 WHERE id = :eid
                """
            ),
            {"eid": str(ctx.execution_id)},
        )


def _mark_failed(ctx: _ExecutionContext, *, error_summary: str) -> None:
    try:
        with get_tenant_session(ctx.tenant_id) as session:
            session.execute(
                text(
                    """
                    UPDATE executions
                       SET status = 'failed',
                           finished_at = now(),
                           error_summary = :err,
                           updated_at = now()
                     WHERE id = :eid
                    """
                ),
                {"eid": str(ctx.execution_id), "err": error_summary},
            )
    except Exception:  # noqa: BLE001 — nao podemos mascarar a excecao original
        logger.exception(
            "jobs.run_execution.mark_failed_error",
            extra={"execution_id": str(ctx.execution_id)},
        )


def _mark_finished(
    ctx: _ExecutionContext,
    *,
    status: str,
    summary: FetchSummary,
    items_ok: int,
    items_fail: int,
) -> None:
    with get_tenant_session(ctx.tenant_id) as session:
        session.execute(
            text(
                """
                UPDATE executions
                   SET status = :st,
                       finished_at = now(),
                       nsu_from = :nsu_from,
                       nsu_to = :nsu_to,
                       items_total = :total,
                       items_ok = :ok,
                       items_fail = :fail,
                       updated_at = now()
                 WHERE id = :eid
                """
            ),
            {
                "st": status,
                "nsu_from": int(summary.nsu_from),
                "nsu_to": int(summary.nsu_to),
                "total": int(items_ok + items_fail),
                "ok": int(items_ok),
                "fail": int(items_fail),
                "eid": str(ctx.execution_id),
            },
        )


def _insert_execution_item(
    ctx: _ExecutionContext,
    item: NfseItem,
    xml_object_key: Optional[str],
) -> bool:
    """INSERT em `execution_items` com ON CONFLICT DO NOTHING.

    Retorna `True` quando a linha foi inserida e `False` quando a unique
    `(tenant_id, chave_nfse)` ja cobriu uma execucao anterior.
    """
    # Converte `status` do NfseItem ("ok"/"cancelada"/"parse_error") para
    # o dominio do CHECK `ck_execution_items_status` ("ok"/"failed"/
    # "skipped"/"pending"): cancelada -> skipped, parse_error -> failed.
    status_map = {"ok": "ok", "cancelada": "skipped", "parse_error": "failed"}
    item_status = status_map.get(item.status, "failed")

    with get_tenant_session(ctx.tenant_id) as session:
        inserted = session.execute(
            text(
                """
                INSERT INTO execution_items (
                    execution_id, tenant_id, nsu, chave_nfse,
                    cnpj_emitente, data_emissao, valor,
                    xml_object_key, status, error_code, error_message
                ) VALUES (
                    :eid,
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    :nsu, :chave,
                    :cnpj_em, :data_em, :valor,
                    :okey, :st, :ecode, :emsg
                )
                ON CONFLICT (tenant_id, chave_nfse)
                  WHERE chave_nfse IS NOT NULL
                  DO NOTHING
                RETURNING id
                """
            ),
            {
                "eid": str(ctx.execution_id),
                "nsu": int(item.nsu),
                "chave": item.chave_nfse,
                "cnpj_em": item.cnpj_emitente,
                "data_em": _parse_data_emissao(item.data_emissao),
                "valor": item.valor,
                "okey": xml_object_key,
                "st": item_status,
                "ecode": item.error_code,
                "emsg": item.error_message,
            },
        ).one_or_none()
    return inserted is not None


def _parse_data_emissao(value: Optional[str]):
    """Converte `DD/MM/AAAA` para ISO date; devolve None em falha."""
    if not value:
        return None
    try:
        dia, mes, ano = value.split("/")
        return f"{ano}-{int(mes):02d}-{int(dia):02d}"
    except (ValueError, AttributeError):
        return None


def _create_occurrence(
    ctx: _ExecutionContext,
    *,
    code: str,
    severity: str,
    title: str,
    detail: Optional[str] = None,
) -> None:
    try:
        with get_tenant_session(ctx.tenant_id) as session:
            session.execute(
                text(
                    """
                    INSERT INTO occurrences (
                        tenant_id, company_id, execution_id,
                        severity, code, title, detail, status
                    ) VALUES (
                        NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                        :cid, :eid, :sev, :code, :title, :detail, 'open'
                    )
                    """
                ),
                {
                    "cid": str(ctx.company_id),
                    "eid": str(ctx.execution_id),
                    "sev": severity,
                    "code": code,
                    "title": title,
                    "detail": detail,
                },
            )
    except Exception:  # noqa: BLE001 — ocorrencia e best-effort
        logger.exception(
            "jobs.run_execution.occurrence_insert_failed",
            extra={"execution_id": str(ctx.execution_id), "code": code},
        )


# ---------------------------------------------------------------------------
# Credential decrypt
# ---------------------------------------------------------------------------


def _decrypt_credential(
    ctx: _ExecutionContext,
    read_blob: Callable[[str], bytes],
) -> tuple[bytes, str]:
    """Le o blob cifrado no S3 e devolve `(pfx_bytes, pfx_password)`."""
    encrypted_pfx = read_blob(ctx.pfx_object_key)
    pfx_bytes = decrypt(encrypted_pfx, ctx.tenant_id)
    password_bytes = decrypt(ctx.pfx_password_ciphertext, ctx.tenant_id)
    return pfx_bytes, password_bytes.decode("utf-8")


def _default_read_credential_blob(object_key: str) -> bytes:
    """Le o blob no bucket default (mesmo usado pelo S3StorageClient)."""
    from worker_core.storage import S3Settings
    import boto3
    from botocore.client import Config as BotoConfig
    from botocore.exceptions import ClientError

    settings = S3Settings.from_env()
    kwargs = {
        "service_name": "s3",
        "region_name": settings.region or "us-east-1",
        "config": BotoConfig(
            s3={"addressing_style": "path" if settings.force_path_style else "auto"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }
    if settings.endpoint:
        kwargs["endpoint_url"] = settings.endpoint
    if settings.key_id and settings.application_key:
        kwargs["aws_access_key_id"] = settings.key_id
        kwargs["aws_secret_access_key"] = settings.application_key
    client = boto3.client(**kwargs)
    try:
        resp = client.get_object(Bucket=settings.bucket, Key=object_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        raise StorageError(f"falha ao ler credencial no storage (code={code!r})") from exc
    return resp["Body"].read()


# ---------------------------------------------------------------------------
# Status decision
# ---------------------------------------------------------------------------


def _decide_final_status(
    summary: FetchSummary,
    items_ok: int,
    items_fail: int,
    storage_errors: int,
) -> str:
    """Decide o status final a partir do resumo + contadores."""
    if summary.fatal_rejected:
        return "failed"
    if items_ok == 0 and items_fail == 0 and storage_errors == 0:
        # Nada coletado e sem falha — execucao "succeeded" vazia (sem NFSE
        # novas no periodo). `nsu_to == nsu_from` sinaliza isso.
        return "succeeded"
    if items_fail > 0 or storage_errors > 0:
        if items_ok == 0:
            return "failed"
        return "partial"
    return "succeeded"


def _coerce_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise JobError(f"{field} invalido: {value!r}") from exc
