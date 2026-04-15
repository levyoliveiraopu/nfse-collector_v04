"""Validacao de cron + timezone e calculo de `next_run_at` (API-12).

Decisoes:

- **Cron 5-campos** (`minuto hora dia mes dia-da-semana`) — padrao Unix.
  `croniter` aceita 6/7 campos, mas o segundo/ms nao faz sentido num
  scheduler que varre em cadencia de minutos, e a UI de presets expoe
  apenas 5 campos. Rejeitamos 6+ explicitamente para fechar o contrato.
- **Timezone via `zoneinfo`** (stdlib >= 3.11). Alias IANA (ex.:
  `America/Sao_Paulo`). Nomes desconhecidos levantam `CronValidationError`
  que o handler traduz para 400.
- **`next_run_at` em UTC**. O calculo acontece na TZ do usuario (para
  que "todo dia as 03:00" signifique 03:00 **local**, respeitando DST),
  mas persistimos em UTC porque a coluna e `TIMESTAMPTZ` e o scheduler
  compara com `now()` do banco.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter


class CronValidationError(ValueError):
    """Cron ou timezone invalidos para o contrato da API.

    O handler do endpoint traduz para HTTP 400 com o mesmo `detail`.
    """


def validate_cron(expr: str) -> str:
    """Valida uma expressao cron de 5 campos e devolve a forma normalizada.

    Rejeita:
    - strings com != 5 campos (6/7 nao sao suportados);
    - sintaxe invalida (qualquer erro do `croniter`);
    - string vazia / so espacos.

    A normalizacao colapsa espacos repetidos para 1 espaco e tira whitespace
    nas pontas — mantem o `cron_expr` do banco em forma canonica.
    """
    if not isinstance(expr, str):
        raise CronValidationError("cron_expr deve ser string")
    normalized = " ".join(expr.split())
    if not normalized:
        raise CronValidationError("cron_expr vazia")
    parts = normalized.split(" ")
    if len(parts) != 5:
        raise CronValidationError(
            f"cron_expr deve ter 5 campos (minuto hora dia mes dow); "
            f"recebido {len(parts)} campo(s)"
        )
    try:
        # `is_valid` tolera 6/7 campos; por isso validamos o count antes
        # e usamos o construtor para pegar erros de sintaxe fina.
        croniter(normalized)
    except (CroniterBadCronError, ValueError) as exc:
        raise CronValidationError(f"cron_expr invalida: {exc}") from exc
    return normalized


def validate_timezone(tz: str) -> str:
    """Valida um nome IANA e devolve-o inalterado em caso de sucesso."""
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
    """Calcula o proximo disparo de `cron_expr` na TZ informada.

    Retorna um `datetime` tz-aware **em UTC** (pronto para persistir em
    coluna `TIMESTAMPTZ`). O calculo e feito na TZ local para preservar
    a semantica "as 03:00 de Sao Paulo" mesmo em transicoes de DST.

    Parametros:
        cron_expr: expressao cron de 5 campos ja validada.
        timezone_name: nome IANA ja validado.
        base: instante de referencia; default = agora em UTC.
    """
    tz = ZoneInfo(timezone_name)
    if base is None:
        base = datetime.now(tz=timezone.utc)
    # `croniter` trabalha com datetimes tz-aware: convertemos o `base`
    # para a TZ do usuario antes de pedir o proximo disparo.
    local_base = base.astimezone(tz)
    it = croniter(cron_expr, local_base)
    nxt_local = it.get_next(datetime)
    # croniter retorna naive ou tz-aware dependendo do base; forcamos TZ
    # local e devolvemos em UTC para o banco.
    if nxt_local.tzinfo is None:
        nxt_local = nxt_local.replace(tzinfo=tz)
    return nxt_local.astimezone(timezone.utc)
