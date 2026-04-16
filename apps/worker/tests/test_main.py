"""Smoke tests de `worker.main` (API-13).

- Resolve URL/nome-de-fila/porta de env (+ defaults + validacao).
- `build_worker` cria um RQ Worker com fakeredis.
- `_install_signal_handlers` registra handlers sem levantar.

Nao executa o loop do worker (`work()`) — isso exigiria Redis real
consumindo jobs, o que e coberto pelo E2E gated por `TEST_DATABASE_URL`.
"""

from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock

import pytest

from worker import main as worker_main


def test_resolve_queue_name_default(monkeypatch) -> None:
    monkeypatch.delenv("API_QUEUE_NAME", raising=False)
    assert worker_main._resolve_queue_name() == "nfse-executions"


def test_resolve_queue_name_respeita_env(monkeypatch) -> None:
    monkeypatch.setenv("API_QUEUE_NAME", "outra-fila")
    assert worker_main._resolve_queue_name() == "outra-fila"


def test_resolve_redis_url_exige_env(monkeypatch) -> None:
    monkeypatch.delenv("API_REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="API_REDIS_URL"):
        worker_main._resolve_redis_url()


def test_resolve_redis_url_strip(monkeypatch) -> None:
    monkeypatch.setenv("API_REDIS_URL", "  redis://localhost:6379/0  ")
    assert worker_main._resolve_redis_url() == "redis://localhost:6379/0"


def test_resolve_healthz_port_default(monkeypatch) -> None:
    monkeypatch.delenv("WORKER_HEALTHZ_PORT", raising=False)
    assert worker_main._resolve_healthz_port() == 8080


def test_resolve_healthz_port_invalido(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_HEALTHZ_PORT", "abc")
    with pytest.raises(RuntimeError, match="WORKER_HEALTHZ_PORT invalido"):
        worker_main._resolve_healthz_port()


def test_resolve_healthz_port_fora_de_intervalo(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_HEALTHZ_PORT", "0")
    with pytest.raises(RuntimeError, match="fora do intervalo"):
        worker_main._resolve_healthz_port()


def test_build_worker_com_fakeredis(monkeypatch) -> None:
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeStrictRedis()
    monkeypatch.setenv("API_REDIS_URL", "redis://fake")
    monkeypatch.setenv("API_QUEUE_NAME", "test-queue")
    worker = worker_main.build_worker(redis_client=client, queue_name="test-queue")
    # O Worker conhece a fila pelo nome.
    assert any(q.name == "test-queue" for q in worker.queues)


def test_install_signal_handlers_registra_handlers() -> None:
    worker = MagicMock()
    # Preserva handlers atuais pra restaurar.
    prev_term = signal.getsignal(signal.SIGTERM)
    prev_int = signal.getsignal(signal.SIGINT)
    try:
        worker_main._install_signal_handlers(worker)
        assert callable(signal.getsignal(signal.SIGTERM))
        assert callable(signal.getsignal(signal.SIGINT))
    finally:
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)
