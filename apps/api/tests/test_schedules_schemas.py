"""Testes unitarios dos schemas Pydantic de `/schedules` (API-12)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schedules.presets import PRESETS
from api.schedules.schemas import (
    ScheduleIn,
    SchedulePresetOut,
    ScheduleUpdate,
)


class TestScheduleIn:
    def test_defaults(self) -> None:
        s = ScheduleIn(cron_expr="0 3 * * *")
        assert s.timezone == "America/Sao_Paulo"
        assert s.enabled is True
        assert s.company_id is None

    def test_aceita_company_e_enabled_falso(self) -> None:
        cid = uuid4()
        s = ScheduleIn(
            cron_expr="0 3 * * *",
            timezone="UTC",
            company_id=cid,
            enabled=False,
        )
        assert s.company_id == cid
        assert s.enabled is False

    def test_rejeita_cron_invalido(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ScheduleIn(cron_expr="bogus")
        assert "cron_expr" in str(exc.value)

    def test_rejeita_tz_invalida(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ScheduleIn(cron_expr="0 3 * * *", timezone="Nao/Existe")
        assert "timezone" in str(exc.value)

    def test_extra_forbid(self) -> None:
        # Cliente nao pode setar `last_run_at` / `next_run_at` / `tenant_id`.
        with pytest.raises(ValidationError):
            ScheduleIn(cron_expr="0 3 * * *", last_run_at="2026-01-01T00:00:00Z")


class TestScheduleUpdate:
    def test_aceita_parciais(self) -> None:
        s = ScheduleUpdate(enabled=False)
        assert s.enabled is False
        assert s.cron_expr is None
        assert s.timezone is None

    def test_valida_cron_quando_presente(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleUpdate(cron_expr="bogus")

    def test_valida_tz_quando_presente(self) -> None:
        with pytest.raises(ValidationError):
            ScheduleUpdate(timezone="Nao/Existe")

    def test_extra_forbid_bloqueia_readonly(self) -> None:
        # Tentativa de alterar last_run_at / next_run_at via API -> 422.
        for field in ("last_run_at", "next_run_at", "tenant_id", "id", "created_by_user_id"):
            with pytest.raises(ValidationError):
                ScheduleUpdate(**{field: "x"})


class TestPresets:
    def test_presets_tem_tres_entradas_e_crons_validos(self) -> None:
        assert len(PRESETS) == 3
        ids = {p["id"] for p in PRESETS}
        assert ids == {"daily_03", "weekly_mon_06", "monthly_day1_05"}
        # Cada preset deve passar pelo schema publico.
        for p in PRESETS:
            out = SchedulePresetOut(**p)
            assert out.cron_expr
            assert out.label
            assert out.description
