"""Shim retro-compat: re-exporta worker_core.auth.

Mantido apenas enquanto migramos consumidores de `src.*` para
`worker_core.*` (ver ticket CORE-01). Evite adicionar logica aqui.
"""

from worker_core.auth import *  # noqa: F401,F403
from worker_core.auth import (  # noqa: F401
    _extrair_cnpj_da_string,
    _extrair_cnpj_do_cn,
    _extrair_cnpj_do_serial_number,
    _extrair_cnpj_do_subject_seguro,
    _gravar_temporario,
    _get_base_url,
    _obter_timeout_http,
    _subject_para_str,
    _TimeoutAdapter,
    _verificar_validade,
)
