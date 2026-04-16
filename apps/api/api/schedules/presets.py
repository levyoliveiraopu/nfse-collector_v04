"""Presets sugeridos de agendamento para a UI (API-12).

Apenas sugestoes apresentadas em `GET /schedules/presets`. Nao sao
persistidos — sao o atalho para o usuario nao ter que decorar cron.
"""

from __future__ import annotations

from typing import TypedDict


class Preset(TypedDict):
    id: str
    label: str
    cron_expr: str
    description: str


PRESETS: tuple[Preset, ...] = (
    {
        "id": "daily_03",
        "label": "Diario as 03:00",
        "cron_expr": "0 3 * * *",
        "description": "Coleta todo dia as 03:00 do fuso informado.",
    },
    {
        "id": "weekly_mon_06",
        "label": "Semanal (segunda as 06:00)",
        "cron_expr": "0 6 * * 1",
        "description": "Coleta toda segunda-feira as 06:00 do fuso informado.",
    },
    {
        "id": "monthly_day1_05",
        "label": "Mensal (dia 1 as 05:00)",
        "cron_expr": "0 5 1 * *",
        "description": "Coleta todo dia 1 do mes as 05:00 do fuso informado.",
    },
)
