"""Cliente Redis + enqueue de jobs do worker (API-07).

A API enfileira `run_execution(execution_id)` numa fila RQ consumida
pelo worker (CORE-05 / API-13). Enfileirar por string (`job_func`)
**nao** exige que a funcao esteja importavel pelo processo da API —
RQ serializa nome + args, e o worker resolve o import no momento do
pick. Isso mantem a API desacoplada do `worker_core`.

Pontos de design:

- `get_redis_client()` retorna um singleton por processo (cache em
  modulo). Construido lazy para nao exigir Redis disponivel nos
  imports (testes unitarios podem mockar/substituir).
- `ping_redis()` e usado como pre-check em `POST /executions`: se o
  Redis estiver offline, a API devolve 502 sem sequer tocar o DB.
- `enqueue_run_execution()` e a unica funcao publica usada pelo router.
  Em caso de falha de rede ou erro do RQ, levanta `QueueError` — o
  router decide como reportar (marca a execution como `failed`).
- `reset_queue_client_for_tests()` permite trocar o Redis em testes
  (fakeredis) sem vazar estado entre casos.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from .config import get_settings

logger = logging.getLogger("api.queue")


class QueueError(RuntimeError):
    """Erro agnostico para falhas ao enfileirar jobs.

    Mascaras detalhes da conexao/driver para evitar vazamento em logs
    estruturados. O router converte em 502.
    """


_redis_client: Any | None = None
_rq_queue: Any | None = None


def _build_redis_client(url: str) -> Any:
    """Constroi cliente Redis. Lazy import para nao obrigar a dep em testes unitarios."""
    try:
        import redis  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - defensivo
        raise QueueError("biblioteca `redis` nao instalada") from exc
    return redis.from_url(url, socket_timeout=5, socket_connect_timeout=3)


def _build_queue(client: Any, name: str) -> Any:
    """Constroi fila RQ. Lazy import pelo mesmo motivo."""
    try:
        from rq import Queue  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - defensivo
        raise QueueError("biblioteca `rq` nao instalada") from exc
    return Queue(name=name, connection=client)


def get_redis_client() -> Any:
    """Devolve o cliente Redis singleton (cria na primeira chamada)."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        if not settings.redis_url:
            raise QueueError("API_REDIS_URL nao definida: nao e possivel enfileirar jobs")
        _redis_client = _build_redis_client(settings.redis_url)
    return _redis_client


def get_queue() -> Any:
    """Devolve a fila RQ singleton (cria na primeira chamada)."""
    global _rq_queue
    if _rq_queue is None:
        settings = get_settings()
        client = get_redis_client()
        _rq_queue = _build_queue(client, settings.queue_name)
    return _rq_queue


def reset_queue_client_for_tests() -> None:
    """Limpa os singletons. Use apenas em fixtures de teste."""
    global _redis_client, _rq_queue
    _redis_client = None
    _rq_queue = None


def set_queue_client_for_tests(client: Any, queue: Any) -> None:
    """Injeta Redis e fila fakes (fakeredis + RQ real sobre ele)."""
    global _redis_client, _rq_queue
    _redis_client = client
    _rq_queue = queue


def ping_redis() -> None:
    """Bate no Redis e levanta `QueueError` se indisponivel."""
    try:
        client = get_redis_client()
        client.ping()
    except QueueError:
        raise
    except Exception as exc:  # noqa: BLE001 - queremos encapsular tudo
        logger.warning("queue.ping_failed", extra={"error": str(exc)})
        raise QueueError("redis indisponivel") from exc


def _job_timeout_seconds() -> int:
    settings = get_settings()
    raw = getattr(settings, "job_timeout_seconds", 60 * 60)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 60 * 60
    return value if value > 0 else 60 * 60


def enqueue_run_execution(
    execution_id: UUID,
    *,
    tenant_id: UUID,
    dry_run: bool = False,
) -> str:
    """Enfileira `worker_core.jobs.run_execution(execution_id)`.

    O `dry_run` vai no `meta` do job (nao persistido em
    `executions` — decisao documentada no ticket API-07); o worker
    le e decide o comportamento quando picar o job (API-13).

    Retorna o `job.id` do RQ. Levanta `QueueError` em falha.
    """
    try:
        queue = get_queue()
        job = queue.enqueue(
            "worker_core.jobs.run_execution",
            str(execution_id),
            job_timeout=_job_timeout_seconds(),
            result_ttl=60 * 60 * 24,  # 24h de resultado
            failure_ttl=60 * 60 * 24 * 7,  # 7d de failure p/ diagnostico
            meta={
                "tenant_id": str(tenant_id),
                "dry_run": bool(dry_run),
            },
        )
    except QueueError:
        raise
    except Exception as exc:  # noqa: BLE001 - encapsula driver errors
        logger.warning(
            "queue.enqueue_failed",
            extra={"execution_id": str(execution_id), "error": str(exc)},
        )
        raise QueueError("falha ao enfileirar job") from exc

    job_id = getattr(job, "id", None) or ""
    logger.info(
        "queue.enqueued",
        extra={
            "execution_id": str(execution_id),
            "tenant_id": str(tenant_id),
            "job_id": job_id,
            "dry_run": bool(dry_run),
        },
    )
    return str(job_id)
