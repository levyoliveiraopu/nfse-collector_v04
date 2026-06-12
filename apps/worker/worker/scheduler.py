"""Scheduler de execucoes agendadas (API-14).

Processo separado do RQ worker (API-13) que varre `schedules` a cada
minuto e enfileira execucoes quando `next_run_at <= now()`. O handler
picado pelo consumer (`worker_core.jobs.run_execution`) e **o mesmo**
enfileirado pela API em `POST /executions` (API-07) — o scheduler so
adiciona o disparo automatico baseado em cron.

Fluxo do tick (a cada 1 min, cron `* * * * *`):

    1. SELECT schedules WHERE enabled = true
                         AND next_run_at IS NOT NULL
                         AND next_run_at <= now()
       (via `get_admin_session`, BYPASSRLS; schedules vive em varios
       tenants e o tick e cross-tenant).

    2. Para cada schedule devido:
        a. Resolve companies alvo:
           - `company_id` preenchido -> 1 company.
           - NULL -> todas as companies ativas (nao soft-deleted) do
             tenant (schedule "tenant-wide").
        b. Para cada company alvo:
           - Se ja existe execution em `queued`/`running` para aquela
             (tenant, company), **pula** e insere occurrence
             `SCHEDULE_OVERLAP` (severity warning).
           - Senao, INSERT em `executions` (trigger=`schedule`, status
             `queued`) e enfileira `worker_core.jobs.run_execution` no
             mesmo Redis/fila usados pela API.
        c. Recalcula `next_run_at` via `compute_next_run(cron, tz)`.
           `last_run_at = now()` apenas se pelo menos 1 execucao foi
           criada (nao "relogia" o schedule em tick so de overlap).
           UPDATE na mesma tx com RLS ativa (`get_tenant_session`).

    3. Loga o tick (tempo, numero de schedules picados, criados,
       overlaps).

Idempotencia:

- O scheduler avanca `next_run_at` com base no cron, entao um tick que
  rode duas vezes por crash-resume nao dispararia o mesmo schedule
  duas vezes (o segundo SELECT nao veria `next_run_at <= now()` se a
  primeira pegada ja avancou o ponteiro).
- Overlap nao duplica execucao por construcao: o check
  `EXISTS queued|running` e feito dentro da mesma tx que faz o INSERT
  do `executions`; RLS + unique de execucao por si so nao bloqueariam
  (nao existe unique (tenant, company) em executions), por isso o
  check e parte do contrato do ticket.

Entry point: `python -m worker.scheduler` (ou `nfse-scheduler` via
pyproject script). Variaveis de ambiente reusadas do worker:

- `API_REDIS_URL`, `API_QUEUE_NAME`            — mesma fila do API-07.
- `API_DATABASE_URL` / `WORKER_DATABASE_URL`   — Postgres (via worker_core.db).
- `LOG_LEVEL`                                  — INFO por default.

Dev local:

    python -m worker.scheduler

Graceful shutdown: SIGTERM/SIGINT param o APScheduler (`shutdown(wait=True)`)
e encerram o processo. No compose, combine com `stop_grace_period: 30s`
para garantir que o tick em curso conclua.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from worker_core.logging import configure_json_logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from worker_core.db import get_admin_session, get_tenant_session

from worker.cron_utils import CronValidationError, compute_next_run

logger = logging.getLogger("worker.scheduler")


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DueSchedule:
    id: UUID
    tenant_id: UUID
    company_id: Optional[UUID]
    cron_expr: str
    timezone: str


@dataclass(frozen=True)
class _TickSummary:
    """Resumo do tick — util em testes e em logs estruturados."""

    picked: int = 0
    executions_created: int = 0
    overlaps: int = 0
    enqueue_failed: int = 0


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------


def _resolve_redis_url() -> str:
    url = (os.environ.get("API_REDIS_URL") or "").strip()
    if not url:
        raise RuntimeError("API_REDIS_URL nao definida; scheduler nao consegue enfileirar jobs.")
    return url


def _resolve_queue_name() -> str:
    raw = (os.environ.get("API_QUEUE_NAME") or "nfse-executions").strip()
    return raw or "nfse-executions"


# ---------------------------------------------------------------------------
# Redis / RQ helpers (lazy imports — permite unit tests sem deps reais)
# ---------------------------------------------------------------------------


def _build_redis_client(url: str) -> Any:
    import redis  # type: ignore[import-untyped]

    return redis.from_url(url, socket_timeout=5, socket_connect_timeout=3)


def _build_queue(client: Any, name: str) -> Any:
    from rq import Queue  # type: ignore[import-untyped]

    return Queue(name=name, connection=client)


def _enqueue_run_execution(queue: Any, *, execution_id: UUID, tenant_id: UUID) -> str:
    """Enfileira `worker_core.jobs.run_execution` — mesmo contrato de API-07."""
    job = queue.enqueue(
        "worker_core.jobs.run_execution",
        str(execution_id),
        job_timeout=60 * 60,
        result_ttl=60 * 60 * 24,
        failure_ttl=60 * 60 * 24 * 7,
        meta={
            "tenant_id": str(tenant_id),
            "trigger": "schedule",
        },
    )
    return str(getattr(job, "id", "") or "")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _select_due_schedules(session: Session, *, now: datetime) -> list[_DueSchedule]:
    rows = session.execute(
        text(
            """
            SELECT id, tenant_id, company_id, cron_expr, timezone
              FROM schedules
             WHERE enabled = true
               AND next_run_at IS NOT NULL
               AND next_run_at <= :now
             ORDER BY next_run_at ASC, id
            """
        ),
        {"now": now},
    ).all()
    return [
        _DueSchedule(
            id=UUID(str(r.id)),
            tenant_id=UUID(str(r.tenant_id)),
            company_id=UUID(str(r.company_id)) if r.company_id else None,
            cron_expr=str(r.cron_expr),
            timezone=str(r.timezone),
        )
        for r in rows
    ]


def _resolve_target_companies(session: Session, *, schedule: _DueSchedule) -> list[UUID]:
    """Lista as companies alvo do schedule (RLS ativa na session)."""
    if schedule.company_id is not None:
        row = session.execute(
            text(
                """
                SELECT id FROM companies
                 WHERE id = :cid AND deleted_at IS NULL
                """
            ),
            {"cid": str(schedule.company_id)},
        ).one_or_none()
        return [UUID(str(row.id))] if row else []

    rows = session.execute(
        text(
            """
            SELECT id FROM companies
             WHERE deleted_at IS NULL
             ORDER BY created_at ASC, id
            """
        )
    ).all()
    return [UUID(str(r.id)) for r in rows]


def _lock_company_execution_slot(session: Session, *, tenant_id: UUID, company_id: UUID) -> None:
    """Serializa check+insert de execution aberta por tenant/company.

    Dois processos de scheduler podem pegar o mesmo schedule no mesmo minuto.
    O advisory lock transacional usa uma chave deterministica e vale ate o fim
    da transacao da sessao tenant, impedindo que ambos passem simultaneamente
    pelo par `_has_inflight_execution` + `_insert_execution`.
    """
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"scheduler:{tenant_id}:{company_id}"},
    )


def _has_inflight_execution(session: Session, *, company_id: UUID) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1 FROM executions
             WHERE company_id = :cid
               AND status IN ('queued','running')
             LIMIT 1
            """
        ),
        {"cid": str(company_id)},
    ).one_or_none()
    return row is not None


def _insert_execution(session: Session, *, company_id: UUID) -> UUID:
    row = session.execute(
        text(
            """
            INSERT INTO executions (
                tenant_id, company_id, trigger, status,
                period_start, period_end
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :cid, 'schedule', 'queued',
                CURRENT_DATE, CURRENT_DATE
            )
            RETURNING id
            """
        ),
        {"cid": str(company_id)},
    ).one()
    return UUID(str(row.id))


def _mark_execution_enqueue_failed(session: Session, *, execution_id: UUID) -> None:
    session.execute(
        text(
            """
            UPDATE executions
               SET status = 'failed',
                   error_summary = 'enqueue_failed',
                   finished_at = now(),
                   updated_at = now()
             WHERE id = :eid
            """
        ),
        {"eid": str(execution_id)},
    )


def _insert_overlap_occurrence(session: Session, *, schedule: _DueSchedule, company_id: UUID) -> None:
    session.execute(
        text(
            """
            INSERT INTO occurrences (
                tenant_id, company_id, severity, code, title, detail, status
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :cid, 'warning', 'SCHEDULE_OVERLAP',
                'Disparo agendado pulado por sobreposicao',
                :detail, 'open'
            )
            """
        ),
        {
            "cid": str(company_id),
            "detail": f"schedule_id={schedule.id} cron={schedule.cron_expr}",
        },
    )


def _update_schedule_after_tick(
    session: Session,
    *,
    schedule_id: UUID,
    next_run_at: datetime,
    touched_last_run: bool,
) -> None:
    if touched_last_run:
        session.execute(
            text(
                """
                UPDATE schedules
                   SET next_run_at = :nxt,
                       last_run_at = now(),
                       updated_at = now()
                 WHERE id = :sid
                """
            ),
            {"nxt": next_run_at, "sid": str(schedule_id)},
        )
    else:
        session.execute(
            text(
                """
                UPDATE schedules
                   SET next_run_at = :nxt,
                       updated_at = now()
                 WHERE id = :sid
                """
            ),
            {"nxt": next_run_at, "sid": str(schedule_id)},
        )


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------


def run_tick(
    *,
    now: Optional[datetime] = None,
    enqueue: Optional[Callable[[UUID, UUID], str]] = None,
) -> _TickSummary:
    """Executa um tick do scheduler.

    Injection points:
        now:     relogio (default `datetime.now(UTC)`). Util em testes.
        enqueue: funcao(execution_id, tenant_id) -> job_id. Default le
                 `API_REDIS_URL` e conecta ao Redis/RQ. Testes podem
                 passar um stub.
    """
    tick_now = now if now is not None else datetime.now(tz=timezone.utc)
    summary = _TickSummary()

    with get_admin_session() as admin:
        due = _select_due_schedules(admin, now=tick_now)

    if not due:
        logger.info("scheduler.tick.empty", extra={"now": tick_now.isoformat()})
        return summary

    logger.info(
        "scheduler.tick.start",
        extra={"now": tick_now.isoformat(), "picked": len(due)},
    )

    if enqueue is None:
        client = _build_redis_client(_resolve_redis_url())
        queue = _build_queue(client, _resolve_queue_name())

        def _default_enqueue(eid: UUID, tid: UUID) -> str:
            return _enqueue_run_execution(queue, execution_id=eid, tenant_id=tid)

        enqueue = _default_enqueue

    picked = len(due)
    created = 0
    overlaps = 0
    enqueue_failed = 0

    for sched in due:
        # `next_run_at` recalculado mesmo se tudo for overlap — caso
        # contrario o schedule ficaria preso disparando overlap a cada
        # minuto (o cron faria `<= now` ser sempre verdadeiro).
        try:
            next_run_at = compute_next_run(sched.cron_expr, sched.timezone, base=tick_now)
        except CronValidationError:
            logger.exception(
                "scheduler.tick.cron_invalid",
                extra={"schedule_id": str(sched.id), "cron": sched.cron_expr},
            )
            # Sem next_run_at valido, pula a linha inteira (mantem
            # enabled=true para o owner inspecionar). Nao atualiza
            # campos — evita mascarar o problema.
            continue

        with get_tenant_session(sched.tenant_id) as session:
            try:
                companies = _resolve_target_companies(session, schedule=sched)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "scheduler.tick.companies_lookup_failed",
                    extra={"schedule_id": str(sched.id)},
                )
                continue

            created_for_schedule = 0
            for company_id in companies:
                _lock_company_execution_slot(session, tenant_id=sched.tenant_id, company_id=company_id)
                if _has_inflight_execution(session, company_id=company_id):
                    _insert_overlap_occurrence(session, schedule=sched, company_id=company_id)
                    overlaps += 1
                    logger.info(
                        "scheduler.tick.overlap",
                        extra={
                            "schedule_id": str(sched.id),
                            "tenant_id": str(sched.tenant_id),
                            "company_id": str(company_id),
                        },
                    )
                    continue

                execution_id = _insert_execution(session, company_id=company_id)
                try:
                    job_id = enqueue(execution_id, sched.tenant_id)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "scheduler.tick.enqueue_failed",
                        extra={
                            "schedule_id": str(sched.id),
                            "execution_id": str(execution_id),
                            "company_id": str(company_id),
                        },
                    )
                    _mark_execution_enqueue_failed(session, execution_id=execution_id)
                    enqueue_failed += 1
                    continue

                created += 1
                created_for_schedule += 1
                logger.info(
                    "scheduler.tick.fired",
                    extra={
                        "schedule_id": str(sched.id),
                        "tenant_id": str(sched.tenant_id),
                        "company_id": str(company_id),
                        "execution_id": str(execution_id),
                        "job_id": job_id,
                    },
                )

            _update_schedule_after_tick(
                session,
                schedule_id=sched.id,
                next_run_at=next_run_at,
                touched_last_run=created_for_schedule > 0,
            )

    summary = _TickSummary(
        picked=picked,
        executions_created=created,
        overlaps=overlaps,
        enqueue_failed=enqueue_failed,
    )
    logger.info(
        "scheduler.tick.done",
        extra={
            "picked": summary.picked,
            "executions_created": summary.executions_created,
            "overlaps": summary.overlaps,
            "enqueue_failed": summary.enqueue_failed,
        },
    )
    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    configure_json_logging(level)


def build_scheduler(*, tick: Optional[Callable[[], Any]] = None) -> Any:
    """Cria o `BlockingScheduler` com cron `* * * * *`.

    `tick` injeta a funcao disparada a cada minuto — default = `run_tick`
    com enqueue real. Em testes, injete um stub.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
    from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

    scheduler = BlockingScheduler(timezone="UTC")
    job = tick if tick is not None else run_tick
    scheduler.add_job(
        job,
        trigger=CronTrigger(minute="*", timezone="UTC"),
        id="scheduler.tick",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=30,
    )
    return scheduler


def _resolve_scheduler_healthz_port() -> int:
    raw = (os.environ.get("SCHEDULER_HEALTHZ_PORT") or "8081").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"SCHEDULER_HEALTHZ_PORT invalido: {raw!r}") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"SCHEDULER_HEALTHZ_PORT fora do intervalo: {port}")
    return port


def main() -> int:
    _configure_logging()
    logger.info("scheduler.boot", extra={"queue": _resolve_queue_name()})

    from worker.healthz import HealthzServer

    healthz = HealthzServer(port=_resolve_scheduler_healthz_port())
    healthz.start()
    scheduler = build_scheduler()

    def _shutdown(signum, frame):  # noqa: ARG001
        logger.info("scheduler.signal.received", extra={"signal": signum})
        try:
            scheduler.shutdown(wait=True)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler.shutdown_failed")

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    exit_code = 0
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:  # noqa: BLE001
        logger.exception("scheduler.run_failed")
        exit_code = 1
    finally:
        healthz.stop()

    logger.info("scheduler.exit")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
