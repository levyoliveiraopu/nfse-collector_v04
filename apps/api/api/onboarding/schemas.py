"""Schemas do endpoint `/onboarding/*` (APP-11).

Mantemos o payload minimo (`already_recorded` + `notification_id`) para
o wizard tomar decisao idempotente: a UI chama em todo load do passo 3
ao detectar primeira execucao ok, e o backend garante que apenas a
primeira chamada por (tenant, user) insere em `notifications`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FirstCollectionDoneOut(BaseModel):
    """Resposta de `POST /onboarding/first-collection-done`.

    - `already_recorded=True` quando ja havia `notifications` com o
      mesmo (tenant_id, user_id, type) — o endpoint e idempotente.
    - `notification_id` e o id da linha recem criada (ou da existente
      quando `already_recorded`).
    """

    already_recorded: bool
    notification_id: Optional[UUID] = None
