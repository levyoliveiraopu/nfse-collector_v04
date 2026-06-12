"""Entry point do RQ worker (API-13).

Uso:

    python -m worker.main

Le as envs (``API_REDIS_URL``, ``API_QUEUE_NAME``, ``WORKER_HEALTHZ_PORT``,
``DATABASE_URL``/``API_DATABASE_URL``, ``S3_*``, ``API_CREDENTIAL_KEK_B64``)
e pica jobs enfileirados pela API em ``worker_core.jobs.run_execution``.

Sinais:
- SIGTERM / SIGINT: requisita graceful shutdown. O RQ termina o job atual
  (se houver) e sai. O Docker compose envia SIGTERM no ``docker stop``;
  usar ``stop_grace_period: 60s`` no compose para cumprir o DoD "drena
  ate 60s" — depois disso o SIGKILL encerra o processo.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from typing import Optional

logger = logging.getLogger("worker.main")


def _configure_logging() -> None:
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    # Log JSON quando o pacote estiver instalado (produzido pela INFRA-07);
    # fallback para formato humano caso contrario (dev local sem as deps).
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level"},
            )
        )
        logging.basicConfig(level=level, handlers=[handler], force=True)
    except ImportError:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
            force=True,
        )


def _resolve_redis_url() -> str:
    url = (os.environ.get("API_REDIS_URL") or "").strip()
    if not url:
        raise RuntimeError("API_REDIS_URL nao definida; impossivel iniciar o worker.")
    return url


def _resolve_queue_name() -> str:
    return (os.environ.get("API_QUEUE_NAME") or "nfse-executions").strip() or "nfse-executions"


def _resolve_healthz_port() -> int:
    raw = (os.environ.get("WORKER_HEALTHZ_PORT") or "8080").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"WORKER_HEALTHZ_PORT invalido: {raw!r}") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"WORKER_HEALTHZ_PORT fora do intervalo: {port}")
    return port


def _patch_redis_client_for_rq(redis_client) -> None:
    """Compatibiliza fakeredis com RQ >= 2.9 em testes.

    O RQ consulta ``CLIENT LIST`` na inicializacao do worker e espera o
    campo ``addr``. Algumas versoes de fakeredis retornam a lista sem esse
    campo, o que quebra a suite local apesar de nao acontecer com Redis real.
    A correcao e restrita ao cliente injetado em testes.
    """
    if redis_client is None or not hasattr(redis_client, "client_list"):
        return

    original_client_list = redis_client.client_list

    def _client_list_with_addr(*args, **kwargs):
        clients = original_client_list(*args, **kwargs)
        if isinstance(clients, list):
            for client in clients:
                if isinstance(client, dict):
                    client.setdefault("addr", "fakeredis:0")
        return clients

    try:
        redis_client.client_list = _client_list_with_addr
    except Exception:  # noqa: BLE001 - cliente Redis real pode nao permitir monkeypatch
        return


def build_worker(*, redis_client=None, queue_name: Optional[str] = None):
    """Constroi o ``rq.Worker`` sobre a fila configurada.

    Injecao opcional do `redis_client` (usada em testes com fakeredis).
    """
    import redis as _redis
    from rq import Queue, Worker

    client = redis_client or _redis.from_url(_resolve_redis_url())
    if redis_client is not None:
        _patch_redis_client_for_rq(client)
    qname = queue_name or _resolve_queue_name()
    queue = Queue(name=qname, connection=client)
    # `name=None` faz o RQ gerar um nome aleatorio por worker (OK em K8s
    # e em compose com replicas > 1). `disable_default_exception_handler`
    # fica False para que erros sejam gravados em failure_ttl.
    worker = Worker([queue], connection=client)
    return worker


def _install_signal_handlers(worker) -> None:
    """Instala handlers de SIGTERM/SIGINT para graceful shutdown.

    O RQ ja escuta esses sinais via `Worker.work()` (que chama
    `install_signal_handlers()` no setup). Aqui adicionamos um hook extra
    para logar a intencao e garantir idempotencia em testes.
    """

    def _handle(signum, frame):  # noqa: ARG001
        logger.info("worker.signal.received", extra={"signal": signum})
        # `request_stop` e a API publica do RQ para pedir shutdown. Se o
        # RQ ja instalou seu handler antes, o nosso corre em seguida — OK.
        try:
            worker.request_stop(signum, frame)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            logger.exception("worker.signal.request_stop_failed")

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)


def main() -> int:
    _configure_logging()
    logger.info(
        "worker.boot",
        extra={
            "queue": _resolve_queue_name(),
            "redis_url_present": bool(os.environ.get("API_REDIS_URL")),
        },
    )

    # Imports tardios para permitir _configure_logging() setar o formato antes.
    from worker.healthz import HealthzServer

    healthz = HealthzServer(port=_resolve_healthz_port())
    healthz.start()

    try:
        worker = build_worker()
    except Exception:  # noqa: BLE001
        logger.exception("worker.boot.failed")
        healthz.stop()
        return 1

    _install_signal_handlers(worker)

    try:
        # `with_scheduler=False` — o scheduler so seria necessario se
        # a API usasse `queue.enqueue_in`/`enqueue_at`, o que nao e o caso.
        worker.work(with_scheduler=False)
    except Exception:  # noqa: BLE001
        logger.exception("worker.work.failed")
        return 1
    finally:
        healthz.stop()

    logger.info("worker.exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
