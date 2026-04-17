"""Testes do wrapper de cron+TZ do scheduler (API-14)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from worker.cron_utils import (
    CronValidationError,
    compute_next_run,
    validate_cron,
    validate_timezone,
)


def test_validate_cron_aceita_5_campos() -> None:
    assert validate_cron("* * * * *") == "* * * * *"
    assert validate_cron("0 3 * * *") == "0 3 * * *"


def test_validate_cron_normaliza_whitespace() -> None:
    assert validate_cron("  0   3  *  *  * ") == "0 3 * * *"


def test_validate_cron_rejeita_6_campos() -> None:
    with pytest.raises(CronValidationError, match="5 campos"):
        validate_cron("0 0 3 * * *")


def test_validate_cron_rejeita_vazio() -> None:
    with pytest.raises(CronValidationError, match="vazia"):
        validate_cron("   ")


def test_validate_cron_rejeita_sintaxe_invalida() -> None:
    with pytest.raises(CronValidationError, match="invalida"):
        validate_cron("xx yy zz ww vv")


def test_validate_timezone_aceita_iana() -> None:
    assert validate_timezone("America/Sao_Paulo") == "America/Sao_Paulo"
    assert validate_timezone("UTC") == "UTC"


def test_validate_timezone_rejeita_desconhecida() -> None:
    with pytest.raises(CronValidationError, match="timezone invalida"):
        validate_timezone("Mars/Phobos")


def test_validate_timezone_rejeita_vazia() -> None:
    with pytest.raises(CronValidationError, match="vazia"):
        validate_timezone("")


def test_compute_next_run_devolve_utc() -> None:
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("* * * * *", "UTC", base=base)
    assert nxt.tzinfo == timezone.utc
    assert nxt == datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)


def test_compute_next_run_respeita_tz_local() -> None:
    # 03:00 em America/Sao_Paulo (UTC-3 sem DST em 2026) == 06:00 UTC.
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("0 3 * * *", "America/Sao_Paulo", base=base)
    assert nxt.tzinfo == timezone.utc
    # Proximo 03:00 local apos 09:00 local (12 UTC) e 03:00 do dia seguinte.
    assert nxt == datetime(2026, 1, 2, 6, 0, tzinfo=timezone.utc)


def test_compute_next_run_semanal() -> None:
    # Segunda 06:00 America/Sao_Paulo = segunda 09:00 UTC (sem DST).
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)  # quinta
    nxt = compute_next_run("0 6 * * 1", "America/Sao_Paulo", base=base)
    assert nxt.weekday() == 0  # segunda em UTC (09:00 UTC ainda segunda)
    assert nxt.hour == 9
