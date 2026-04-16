"""Pacote de endpoints de exports assincronos (API-15).

- `routes.py` expoe `POST /exports` e `GET /exports/{id}`.
- `schemas.py` define os DTOs Pydantic.

O worker que executa o job vive em `worker_core.jobs.build_export`
(pacote independente). O router enfileira pelo nome (string) — nao
importa o modulo do worker, mantendo a API desacoplada do motor.
"""
