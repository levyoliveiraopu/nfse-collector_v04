"""Validacao de CNPJ (API-05).

Algoritmo oficial da Receita Federal, com dois digitos verificadores
calculados pelo resto da divisao por 11 de uma soma ponderada. Rejeita
sequencias com todos os digitos iguais (`00000000000000`,
`11111111111111`, ...) — elas passam pelo calculo matematico mas sao
invalidas por convencao.

Normalizacao e validacao sao separadas propositalmente:
- `normalize_cnpj` tira qualquer formatacao (pontos, barras, traco,
  espacos) e devolve apenas os 14 digitos esperados pelo CHECK da
  migration 0002_companies (`cnpj ~ '^[0-9]+$'`).
- `is_valid_cnpj` faz a checagem de DV sobre um CNPJ ja normalizado.
"""

from __future__ import annotations

import re

_ONLY_DIGITS = re.compile(r"\D+")

# Pesos oficiais para os dois digitos verificadores.
_WEIGHTS_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_DV2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_cnpj(raw: str) -> str:
    """Remove qualquer caractere nao-digito. Nao valida comprimento."""
    if raw is None:
        return ""
    return _ONLY_DIGITS.sub("", raw)


def _check_digit(digits: str, weights: tuple[int, ...]) -> str:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    rest = total % 11
    return "0" if rest < 2 else str(11 - rest)


def is_valid_cnpj(cnpj: str) -> bool:
    """Valida um CNPJ ja em formato de 14 digitos numericos.

    Retorna False para:
    - comprimento != 14
    - presenca de caracteres nao-digito
    - sequencias repetidas (ex.: 00000000000000)
    - digitos verificadores incorretos
    """
    if not isinstance(cnpj, str):
        return False
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False
    # Sequencia repetida (11111111111111 etc.) passaria no DV mas nao e
    # um CNPJ real — convencao da Receita.
    if cnpj == cnpj[0] * 14:
        return False
    dv1 = _check_digit(cnpj[:12], _WEIGHTS_DV1)
    if cnpj[12] != dv1:
        return False
    dv2 = _check_digit(cnpj[:13], _WEIGHTS_DV2)
    return cnpj[13] == dv2
