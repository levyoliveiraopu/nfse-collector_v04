"""Shim retro-compat: re-exporta worker_core.gdrive_uploader.

Requer as dependencias opcionais de Google Drive (ver
`packages/worker-core/pyproject.toml` extra `gdrive` ou
`requirements-gdrive.txt`).
"""

from worker_core.gdrive_uploader import *  # noqa: F401,F403
