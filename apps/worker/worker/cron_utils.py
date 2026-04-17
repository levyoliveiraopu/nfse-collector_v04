"""Utilitarios de cron + timezone para o scheduler (API-14).

Duplica a logica de `apps/api/api/schedules/cron.py` (API-12) aqui porque
o worker nao pode importar de `apps/api`. O contrato e o mesmo:

- Cron de 5 campos (`minuto hora dia mes dia-da-semana`). `croniter`
  aceita 6/7 campos, mas o scheduler dispara em cadencia de minutos e o
  CRUD rejeita 6+ explicitamente. Reforcamos aqui para defesa em
  profundidade caso um schedule corrompido chegue ao tick.
- Timezone IANA validado via `zoneinfo.ZoneInfo`.
- `compute_next_run` trabalha na TZ do usuario (preserva "as 03:00 de
  Sao Paulo" em transicoes de DST) e devolve em UTC para comparacao com
  a coluna `TIMESTAMPTZ`.

Fonte canonica: `apps/api/api/schedules/cron.py`. Qualquer mudanca aqui
deve ser replicada la (e vice-versa) ate que um pacote compartilhado
seja extraido.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter


class CronValidationError(ValueError):
    """Cron ou timezone invalidos."""


def validate_cron(expr: str) -> str:
    if not isinstance(expr, str):
        raise CronValidationError("cron_expr deve ser string")
    normalized = " ".join(expr.split())
    if not normalized:
        raise CronValidationError("cron_expr vazia")
    parts = normalized.split(" ")
    if len(parts) != 5:
        raise CronValidationError(
            f"cron_expr deve ter 5 campos; recebido {len(parts)}"
        )
    try:
        croniter(normalized)
    except (CroniterBadCronError, ValueError) as exc:
        raise CronValidationError(f"cron_expr invalida: {exc}") from exc
    return normalized


def validate_timezone(tz: str) -> str:
    if not isinstance(tz, str) or not tz.strip():
        raise CronValidationError("timezone vazia")
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise CronValidationError(f"timezone invalida: {tz!r}") from exc
    except (ValueError, KeyError) as exc:
        raise CronValidationError(f"timezone invalida: {tz!r}") from exc
    return tz


def compute_next_run(
    cron_expr: str,
    timezone_name: str,
    *,
    base: Optional[datetime] = None,
) -> datetime:
    """Calcula o proximo disparo em UTC, respeitando TZ local (DST).

    Parametros:
        cron_expr: expressao cron 5-campos (validada).
        timezone_name: nome IANA (validado).
        base: instante de referencia; default = agora em UTC.
    """
    tz = ZoneInfo(timezone_name)
    if base is None:
        base = datetime.now(tz=timezone.utc)
    local_base = base.astimezone(tz)
    it = croniter(cron_expr, local_base)
    nxt_local = it.get_next(datetime)
    if nxt_local.tzinfo is None:
        nxt_local = nxt_local.replace(tzinfo=tz)
    return nxt_local.astimezone(timezone.utc)
