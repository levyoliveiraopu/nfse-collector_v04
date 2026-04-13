"""Shim retro-compat: re-exporta worker_core.storage_backend."""

from worker_core.storage_backend import *  # noqa: F401,F403
from worker_core.storage_backend import StorageBackend  # noqa: F401
