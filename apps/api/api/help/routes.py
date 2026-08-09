"""Telemetria agregada e privada da ajuda contextual.

Os endpoints nunca recebem consultas de busca, URLs completas, IDs de usuario
ou dados fiscais. Cada chamada apenas incrementa um contador diario por tenant,
papel e dimensoes normalizadas.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .schemas import (
    HelpEventIn,
    HelpInsightRow,
    HelpInsightsOut,
    HelpInsightsTotals,
)

router = APIRouter(prefix="/help", tags=["help"])

_AnyMember = require_role("owner", "admin", "operator", "viewer")
_AdminOnly = require_role("owner", "admin")


@router.post(
    "/events",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Incrementa uma metrica diaria anonimizada da ajuda",
)
def record_help_event(
    payload: HelpEventIn,
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_AnyMember),
) -> Response:
    db.execute(
        text(
            """
            INSERT INTO help_metrics_daily (
                tenant_id, day, role, event_type,
                article_slug, route_key, tour_id, count
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                CURRENT_DATE, :role, :event_type,
                :article_slug, :route_key, :tour_id, 1
            )
            ON CONFLICT (
                tenant_id, day, role, event_type,
                article_slug, route_key, tour_id
            ) DO UPDATE SET
                count = help_metrics_daily.count + 1,
                updated_at = now()
            """
        ),
        {
            "role": claims.role,
            "event_type": payload.event_type,
            "article_slug": payload.article_slug or "",
            "route_key": payload.route_key or "",
            "tour_id": payload.tour_id or "",
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


_EVENT_KEYS = (
    "article_opened",
    "search_performed",
    "search_no_results",
    "tour_started",
    "tour_completed",
    "tour_skipped",
    "tour_failed",
    "feedback_yes",
    "feedback_no",
)


def _counts(rows) -> dict[str, int]:
    counts = {key: 0 for key in _EVENT_KEYS}
    for row in rows:
        counts[str(row.event_type)] = int(row.total)
    return counts


@router.get(
    "/insights",
    response_model=HelpInsightsOut,
    summary="Indicadores agregados da ajuda para administradores",
)
def get_help_insights(
    days: int = Query(default=30),
    db: Session = Depends(get_tenant_db),
    _claims: AccessClaims = Depends(_AdminOnly),
) -> HelpInsightsOut:
    # Literal no response e validacao explicita mantem a API restrita aos
    # tres presets exibidos na interface.
    if days not in (7, 30, 90):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="days deve ser 7, 30 ou 90")

    date_to = date.today()
    date_from = date_to - timedelta(days=days - 1)
    params = {"date_from": date_from}

    total_rows = db.execute(
        text(
            """
            SELECT event_type, SUM(count)::bigint AS total
              FROM help_metrics_daily
             WHERE day >= :date_from
             GROUP BY event_type
            """
        ),
        params,
    ).all()

    grouped = db.execute(
        text(
            """
            SELECT article_slug, route_key, event_type,
                   SUM(count)::bigint AS total
              FROM help_metrics_daily
             WHERE day >= :date_from
             GROUP BY article_slug, route_key, event_type
             ORDER BY article_slug, route_key, event_type
            """
        ),
        params,
    ).all()

    by_dimension: dict[tuple[str, str], list] = {}
    for row in grouped:
        key = (str(row.article_slug), str(row.route_key))
        by_dimension.setdefault(key, []).append(row)

    insight_rows = [
        HelpInsightRow(
            article_slug=article_slug,
            route_key=route_key,
            **_counts(rows),
        )
        for (article_slug, route_key), rows in by_dimension.items()
    ]

    return HelpInsightsOut(
        days=days,  # type: ignore[arg-type]
        date_from=date_from,
        date_to=date_to,
        totals=HelpInsightsTotals(**_counts(total_rows)),
        rows=insight_rows,
    )
