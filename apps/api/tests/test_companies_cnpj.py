"""Testes unitarios do validador de CNPJ (API-05).

Sem Postgres: contratos puros sobre `normalize_cnpj` e `is_valid_cnpj`.
"""

from __future__ import annotations

import pytest

from api.companies.cnpj import is_valid_cnpj, normalize_cnpj


# CNPJs publicos validos (com DV correto).
VALID_CNPJS = [
    "11222333000181",
    "04252011000110",  # Google Brasil (dominio publico)
    "00000000000191",  # Banco Central (raiz 0 com DV valido)
]

INVALID_CNPJS = [
    "11222333000180",  # DV2 errado
    "11222333000191",  # DV1 errado
    "1234567890123",   # 13 digitos
    "123456789012345",  # 15 digitos
    "abcdefghijklmn",  # nao-digitos
    "",
]


class TestNormalizeCnpj:
    def test_remove_pontuacao(self) -> None:
        assert normalize_cnpj("11.222.333/0001-81") == "11222333000181"

    def test_remove_espacos(self) -> None:
        assert normalize_cnpj(" 11 222 333 0001 81 ") == "11222333000181"

    def test_preserva_somente_digitos(self) -> None:
        assert normalize_cnpj("abc123def") == "123"

    def test_aceita_string_vazia(self) -> None:
        assert normalize_cnpj("") == ""

    def test_aceita_none(self) -> None:
        # Defesa para evitar AttributeError em caminhos de validacao
        # externa.
        assert normalize_cnpj(None) == ""  # type: ignore[arg-type]


class TestIsValidCnpj:
    @pytest.mark.parametrize("cnpj", VALID_CNPJS)
    def test_aceita_cnpjs_validos(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is True

    @pytest.mark.parametrize("cnpj", INVALID_CNPJS)
    def test_rejeita_cnpjs_invalidos(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is False

    @pytest.mark.parametrize(
        "cnpj",
        [
            "00000000000000",
            "11111111111111",
            "22222222222222",
            "99999999999999",
        ],
    )
    def test_rejeita_sequencias_repetidas(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is False

    def test_rejeita_tipo_errado(self) -> None:
        assert is_valid_cnpj(None) is False  # type: ignore[arg-type]
        assert is_valid_cnpj(11222333000181) is False  # type: ignore[arg-type]

    def test_rejeita_string_com_formatacao(self) -> None:
        # `is_valid_cnpj` exige CNPJ ja normalizado; `.` quebra o
        # `isdigit()` e nao e um erro de DV.
        assert is_valid_cnpj("11.222.333/0001-81") is False
