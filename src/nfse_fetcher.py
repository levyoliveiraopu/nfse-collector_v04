"""Shim retro-compat: re-exporta worker_core.fetcher.

O modulo foi renomeado para `worker_core.fetcher` na extracao do
pacote (ticket CORE-01). Mantido aqui para nao quebrar
`tests/test_nfse_fetcher.py` e demais consumidores legados.
"""

from worker_core.fetcher import *  # noqa: F401,F403
from worker_core.fetcher import (  # noqa: F401
    _buscar_campo_xml,
    _extrair_float,
    _extrair_situacao,
    _get_base_url,
    _max_nsu_do_lote,
    _parsear_data,
    _parsear_data_hora_geracao,
    _RateLimitError,
)
