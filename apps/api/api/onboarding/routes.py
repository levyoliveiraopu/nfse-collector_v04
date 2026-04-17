"""Endpoint de registro de conclusao de onboarding (APP-11).

A UI do wizard (apps/web-app `components/onboarding/`) chama
`POST /onboarding/first-collection-done` quando detecta a primeira
execucao em estado `succeeded` ou `partial`. O handler grava uma linha
em `notifications` (channel=`email`, type=`first_collection_done`)
apontando para o usuario que completou — outbox que sera consumida pelo
worker SMTP quando ele existir (futuro). Chamadas subsequentes sao
no-op idempotente: retornam `already_recorded=True` com o id da linha
ja existente para o par (tenant_id, user_id).

RBAC: qualquer papel autenticado do tenant pode registrar a conclusao
(owner|admin|operator|viewer) — o wizard e acessivel por qualquer
membro novo.

Isolamento multi-tenant: o handler usa `get_tenant_db` (API-03), que
aplica `SET LOCAL app.current_tenant`, e a policy RLS de
`notifications` bloqueia leitura/escrita cross-tenant.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_tenant_db
from ..security.jwt import AccessClaims
from ..security.rbac import require_role
from .schemas import FirstCollectionDoneOut

logger = logging.getLogger("api.onboarding")

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_AnyMember = require_role("owner", "admin", "operator", "viewer")

_NOTIFICATION_TYPE = "first_collection_done"
_NOTIFICATION_CHANNEL = "email"


@router.post(
    "/first-collection-done",
    response_model=FirstCollectionDoneOut,
    status_code=status.HTTP_200_OK,
    summary="Registra na outbox a conclusao da 1a coleta do onboarding.",
)
def record_first_collection_done(
    db: Session = Depends(get_tenant_db),
    claims: AccessClaims = Depends(_AnyMember),
) -> FirstCollectionDoneOut:
    existing = db.execute(
        text(
            """
            SELECT id
              FROM notifications
             WHERE user_id = :uid
               AND type = :ntype
               AND channel = :chan
             LIMIT 1
            """
        ),
        {
            "uid": str(claims.sub),
            "ntype": _NOTIFICATION_TYPE,
            "chan": _NOTIFICATION_CHANNEL,
        },
    ).one_or_none()

    if existing is not None:
        logger.info(
            "onboarding.first_collection_done.idempotent",
            extra={
                "tenant_id": str(claims.tid),
                "user_id": str(claims.sub),
                "notification_id": str(existing.id),
            },
        )
        return FirstCollectionDoneOut(
            already_recorded=True,
            notification_id=existing.id,
        )

    row = db.execute(
        text(
            """
            INSERT INTO notifications (
                tenant_id, user_id, channel, type, payload, status
            ) VALUES (
                NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                :uid, :chan, :ntype, CAST(:payload AS jsonb), 'pending'
            )
            RETURNING id
            """
        ),
        {
            "uid": str(claims.sub),
            "chan": _NOTIFICATION_CHANNEL,
            "ntype": _NOTIFICATION_TYPE,
            "payload": "{}",
        },
    ).one()

    logger.info(
        "onboarding.first_collection_done.recorded",
        extra={
            "tenant_id": str(claims.tid),
            "user_id": str(claims.sub),
            "notification_id": str(row.id),
        },
    )
    return FirstCollectionDoneOut(
        already_recorded=False,
        notification_id=row.id,
    )
