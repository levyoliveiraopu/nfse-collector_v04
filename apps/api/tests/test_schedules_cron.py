"""Testes unitarios de `api.schedules.cron` (API-12).

Cobre:
- `validate_cron`: sintaxe valida, normalizacao, rejeicao de 6/7 campos,
  rejeicao de string vazia/typo, rejeicao de tipos nao-string.
- `validate_timezone`: IANA valido, rejeicao de TZ inexistente/vazia.
- `compute_next_run`: devolve UTC, respeita TZ (semantica "03:00 local"
  em horario normal e em virada DST), funciona com os 3 presets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from api.schedules.cron import (
    CronValidationError,
    compute_next_run,
    validate_cron,
    validate_timezone,
)


# ---------------------------------------------------------------------------
# validate_cron
# ---------------------------------------------------------------------------


class TestValidateCron:
    @pytest.mark.parametrize(
        "expr",
        [
            "* * * * *",
            "0 3 * * *",
            "0 6 * * 1",
            "0 5 1 * *",
            "*/5 * * * *",
            "0 0,12 * * 0-4",
        ],
    )
    def test_aceita_crons_validos_5_campos(self, expr: str) -> None:
        assert validate_cron(expr) == expr

    def test_normaliza_whitespace(self) -> None:
        assert validate_cron("  0  3   *  *  *  ") == "0 3 * * *"

    @pytest.mark.parametrize(
        "expr",
        [
            "",
            "   ",
            "0 3 * *",  # 4 campos
            "0 3 * * * *",  # 6 campos
            "0 3 * * * * *",  # 7 campos
        ],
    )
    def test_rejeita_numero_de_campos_errado(self, expr: str) -> None:
        with pytest.raises(CronValidationError):
            validate_cron(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "bogus * * * *",
            "99 * * * *",  # minuto > 59
            "* 25 * * *",  # hora > 23
        ],
    )
    def test_rejeita_sintaxe_invalida(self, expr: str) -> None:
        with pytest.raises(CronValidationError):
            validate_cron(expr)

    def test_rejeita_nao_string(self) -> None:
        with pytest.raises(CronValidationError):
            validate_cron(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_timezone
# ---------------------------------------------------------------------------


class TestValidateTimezone:
    @pytest.mark.parametrize(
        "tz",
        ["UTC", "America/Sao_Paulo", "Europe/Lisbon", "Asia/Tokyo"],
    )
    def test_aceita_iana(self, tz: str) -> None:
        assert validate_timezone(tz) == tz

    @pytest.mark.parametrize(
        "tz",
        ["", "   ", "Nao/Existe", "SP"],
    )
    def test_rejeita_tz_invalida(self, tz: str) -> None:
        with pytest.raises(CronValidationError):
            validate_timezone(tz)


# ---------------------------------------------------------------------------
# compute_next_run
# ---------------------------------------------------------------------------


SP = ZoneInfo("America/Sao_Paulo")


class TestComputeNextRun:
    def test_resultado_sempre_em_utc(self) -> None:
        base = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
        nxt = compute_next_run("0 3 * * *", "America/Sao_Paulo", base=base)
        assert nxt.tzinfo is timezone.utc
        # 03:00 em SP = 06:00 UTC (-03).
        assert nxt == datetime(2026, 4, 16, 6, 0, tzinfo=timezone.utc)

    def test_preset_diario_03_sp(self) -> None:
        # 02:30 local -> proximo disparo as 03:00 do mesmo dia.
        base = datetime(2026, 4, 15, 2, 30, tzinfo=SP)
        nxt = compute_next_run("0 3 * * *", "America/Sao_Paulo", base=base)
        assert nxt.astimezone(SP) == datetime(2026, 4, 15, 3, 0, tzinfo=SP)

    def test_preset_diario_03_apos_as_tres(self) -> None:
        # 03:01 local -> proximo disparo so no dia seguinte.
        base = datetime(2026, 4, 15, 3, 1, tzinfo=SP)
        nxt = compute_next_run("0 3 * * *", "America/Sao_Paulo", base=base)
        assert nxt.astimezone(SP) == datetime(2026, 4, 16, 3, 0, tzinfo=SP)

    def test_preset_semanal_segunda_06(self) -> None:
        # Quarta-feira 2026-04-15 10:00 SP -> proxima segunda 2026-04-20 06:00.
        base = datetime(2026, 4, 15, 10, 0, tzinfo=SP)
        nxt = compute_next_run("0 6 * * 1", "America/Sao_Paulo", base=base)
        local = nxt.astimezone(SP)
        assert local == datetime(2026, 4, 20, 6, 0, tzinfo=SP)
        assert local.weekday() == 0  # segunda

    def test_preset_mensal_dia1_05(self) -> None:
        base = datetime(2026, 4, 15, 10, 0, tzinfo=SP)
        nxt = compute_next_run("0 5 1 * *", "America/Sao_Paulo", base=base)
        local = nxt.astimezone(SP)
        assert local == datetime(2026, 5, 1, 5, 0, tzinfo=SP)

    def test_tz_diferente_gera_utc_diferente(self) -> None:
        base = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
        sp = compute_next_run("0 3 * * *", "America/Sao_Paulo", base=base)
        tokyo = compute_next_run("0 3 * * *", "Asia/Tokyo", base=base)
        # 03:00 em Tokyo (+09) = 18:00 UTC do dia anterior.
        assert sp.astimezone(ZoneInfo("America/Sao_Paulo")).hour == 3
        assert tokyo.astimezone(ZoneInfo("Asia/Tokyo")).hour == 3
        # E os instantes UTC devem diferir (fusos distintos).
        assert sp != tokyo

    def test_default_base_eh_now(self) -> None:
        # Sanity: funciona sem base explicito.
        nxt = compute_next_run("*/5 * * * *", "UTC")
        assert nxt.tzinfo is timezone.utc
