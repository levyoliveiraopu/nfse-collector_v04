"""Smoke test do servidor /healthz (API-13).

Sobe o HealthzServer em uma porta efemera, bate em /healthz via
`urllib.request` e valida 200 + JSON. Sem dep externa.
"""

from __future__ import annotations

import json
import socket
import urllib.request
from contextlib import closing

from worker.healthz import HealthzServer


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_healthz_returns_200_ok() -> None:
    port = _free_port()
    server = HealthzServer(port=port, host="127.0.0.1")
    server.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/healthz", timeout=2.0
        ) as resp:
            body = resp.read().decode("utf-8")
            assert resp.status == 200
            payload = json.loads(body)
            assert payload == {"status": "ok"}
    finally:
        server.stop()


def test_healthz_404_em_path_desconhecido() -> None:
    port = _free_port()
    server = HealthzServer(port=port, host="127.0.0.1")
    server.start()
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/outro", timeout=2.0
            )
            raise AssertionError("deveria ter levantado 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.stop()


def test_healthz_start_stop_idempotente() -> None:
    port = _free_port()
    server = HealthzServer(port=port, host="127.0.0.1")
    server.start()
    server.start()  # nao deve levantar
    server.stop()
    server.stop()  # nao deve levantar
