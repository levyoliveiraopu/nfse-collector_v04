"""Healthz HTTP server embutido no worker (API-13).

Um ``ThreadingHTTPServer`` em thread daemon expoe ``/healthz`` para o
Uptime Kuma (INFRA-07). Mantemos leve e sem dependencias externas (stdlib)
para nao competir com FastAPI do ``apps/api``.

Semantica de liveness:

- Enquanto o processo do worker estiver vivo, ``/healthz`` devolve 200 +
  ``{"status":"ok"}``. Nao checamos Redis nem Postgres aqui — isso e
  "readiness" e o Uptime Kuma ja monitora a API separadamente.
- Em SIGTERM, o worker inicia graceful shutdown e o servidor continua
  200 enquanto o processo drena. Pos-exit, o socket fecha e o Kuma
  detecta queda.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("worker.healthz")


class _HealthzHandler(BaseHTTPRequestHandler):
    server_version = "nfse-worker-healthz/1"

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Suprime o log default do BaseHTTPRequestHandler (ruidoso); usamos
        # o logger estruturado do worker em lugar disso.
        if self.path != "/healthz" or not args or args[1] != "200":
            logger.debug("healthz.%s %s", self.command, self.path)


class HealthzServer:
    """Servidor HTTP em thread daemon, start()/stop() idempotente."""

    def __init__(self, port: int = 8080, host: str = "0.0.0.0") -> None:
        self._host = host
        self._port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._httpd is not None:
            return
        self._httpd = ThreadingHTTPServer((self._host, self._port), _HealthzHandler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="healthz",
            daemon=True,
        )
        self._thread.start()
        logger.info("healthz.start", extra={"port": self._port, "host": self._host})

    def stop(self, *, timeout: float = 5.0) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._httpd = None
        self._thread = None
        logger.info("healthz.stop")

    @property
    def port(self) -> int:
        return self._port
