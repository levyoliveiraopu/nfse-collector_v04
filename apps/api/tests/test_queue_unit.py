"""Testes unitarios do helper de fila (API-07).

Usa `fakeredis` como backend do `redis.Redis`, permitindo exercitar
RQ (que por baixo e apenas um `rpush` em listas Redis) sem depender
de um Redis real.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

fakeredis = pytest.importorskip("fakeredis")
rq = pytest.importorskip("rq")


@pytest.fixture()
def fake_queue(monkeypatch):
    """Instala um Redis fake + Queue RQ em cima dele.

    Recria tudo por teste para nao vazar jobs entre casos.
    """
    from api import queue as queue_mod

    fake = fakeredis.FakeStrictRedis()
    q = rq.Queue(name="nfse-executions-test", connection=fake)
    queue_mod.set_queue_client_for_tests(fake, q)
    yield fake, q
    queue_mod.reset_queue_client_for_tests()


def test_ping_ok(fake_queue) -> None:
    from api.queue import ping_redis

    ping_redis()  # nao deve levantar


def test_enqueue_cria_job_na_fila(fake_queue) -> None:
    from api.queue import enqueue_run_execution

    _, q = fake_queue
    eid = uuid4()
    tid = uuid4()
    job_id = enqueue_run_execution(eid, tenant_id=tid, dry_run=True)
    assert job_id, "job_id deve ser retornado pelo RQ"
    assert q.count == 1

    job = q.jobs[0]
    # Funcao referenciada por string (worker resolve o import).
    assert job.func_name == "worker_core.jobs.run_execution"
    assert job.args == (str(eid),)
    assert job.meta == {"tenant_id": str(tid), "dry_run": True}


def test_enqueue_dry_run_false_por_default(fake_queue) -> None:
    from api.queue import enqueue_run_execution

    _, q = fake_queue
    eid = uuid4()
    tid = uuid4()
    enqueue_run_execution(eid, tenant_id=tid)
    assert q.jobs[0].meta["dry_run"] is False


def test_enqueue_multiplo_acumula_na_fila(fake_queue) -> None:
    from api.queue import enqueue_run_execution

    _, q = fake_queue
    tid = uuid4()
    for _ in range(3):
        enqueue_run_execution(uuid4(), tenant_id=tid)
    assert q.count == 3


def test_ping_redis_levanta_queue_error_com_redis_quebrado(monkeypatch) -> None:
    """Se o Redis levanta, `ping_redis` converte em `QueueError`."""
    from api import queue as queue_mod
    from api.queue import QueueError, ping_redis

    class BrokenRedis:
        def ping(self):
            raise ConnectionError("redis offline")

    queue_mod.set_queue_client_for_tests(BrokenRedis(), None)
    try:
        with pytest.raises(QueueError):
            ping_redis()
    finally:
        queue_mod.reset_queue_client_for_tests()


def test_enqueue_levanta_queue_error_com_redis_quebrado(monkeypatch) -> None:
    from api import queue as queue_mod
    from api.queue import QueueError, enqueue_run_execution

    class BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise ConnectionError("redis offline no enqueue")

    queue_mod.set_queue_client_for_tests(object(), BrokenQueue())
    try:
        with pytest.raises(QueueError):
            enqueue_run_execution(uuid4(), tenant_id=uuid4())
    finally:
        queue_mod.reset_queue_client_for_tests()


def test_get_redis_client_sem_url_configurada(monkeypatch) -> None:
    """Sem `API_REDIS_URL`, `get_redis_client` levanta `QueueError`."""
    from api import queue as queue_mod
    from api.config import get_settings
    from api.queue import QueueError, get_redis_client

    queue_mod.reset_queue_client_for_tests()
    monkeypatch.setenv("API_REDIS_URL", "")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        with pytest.raises(QueueError):
            get_redis_client()
    finally:
        queue_mod.reset_queue_client_for_tests()
        get_settings.cache_clear()  # type: ignore[attr-defined]
