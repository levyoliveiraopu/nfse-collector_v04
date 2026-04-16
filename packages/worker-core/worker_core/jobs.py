"""Jobs RQ executados pelo worker (API-15).

Modulo dedicado a funcoes que a API enfileira no Redis via string —
o worker resolve o import no momento do pick. Vive em `worker_core`
para manter a API desacoplada do motor.

Entregas atuais:

- `build_export(export_id)`: baixa XMLs do S3 do tenant/company num
  periodo, zipa em `tmpfs`, faz upload do ZIP no bucket e atualiza
  `exports` + `files` + `notifications`. Limite de 2 GB (ticket
  API-15) para proteger tmpfs/RAM.

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
from typing import Optional

from worker_core.storage import S3StorageClient, StorageError

logger = logging.getLogger("worker_core.jobs")

# Hard cap do export (DoD do ticket API-15: "aborta export > 2GB").
DEFAULT_MAX_EXPORT_BYTES = 2 * 1024**3  # 2 GiB


class ExportError(RuntimeError):
    """Erro estruturado para encerrar `build_export` com codigo claro."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _normalize_dsn(url: str) -> str:
    """Converte SQLAlchemy DSN para `psycopg.connect` (mesma forma que conftest)."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def _db_url() -> str:
    url = (
        os.environ.get("WORKER_DATABASE_URL")
        or os.environ.get("API_DATABASE_URL")
        or ""
    ).strip()
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
        os.environ.get("EXPORT_TMPFS_DIR")
        or ("/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir())
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


def _mark_failed(
    conn, export_id: uuid.UUID, *, code: str, message: str
) -> None:
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
    conn, *, tenant_id: uuid.UUID, company_id: uuid.UUID,
    period_start, period_end,
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
            raise ExportError(
                "kind_not_implemented", f"kind {export.kind!r} nao suportado"
            )

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
        zip_fd, zip_path_str = tempfile.mkstemp(
            dir=str(tmpdir), prefix="export-", suffix=".zip"
        )
        os.close(zip_fd)  # ZipFile abre pelo nome.
        zip_path = Path(zip_path_str)

        try:
            written_bytes = 0
            with zipfile.ZipFile(
                zip_path, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as zf:
                for nsu, object_key in items:
                    try:
                        body = storage.download_bytes(object_key)
                    except StorageError as exc:
                        raise ExportError(
                            "s3_error", f"falha ao baixar {object_key}: {exc}"
                        ) from exc
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
