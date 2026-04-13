"""Shim retro-compat: re-exporta worker_core.local_uploader."""

from worker_core.local_uploader import *  # noqa: F401,F403
from worker_core.local_uploader import LocalUploader  # noqa: F401
