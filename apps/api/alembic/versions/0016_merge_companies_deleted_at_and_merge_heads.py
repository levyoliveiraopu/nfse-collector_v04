"""merge heads: 0015_merge_heads + 0015_companies_deleted_at

Revision ID: 0016_merge_companies_deleted_at_and_merge_heads
Revises: 0015_merge_heads, 0015_companies_deleted_at
Create Date: 2026-04-14

Contexto:
- A arvore de migrations voltou a ter duas pontas em `main` apos a
  entrada de `0015_companies_deleted_at`, porque ela revisa
  `0014_plans_subscriptions` em paralelo com `0015_merge_heads`.
- Isso faz `alembic upgrade head` falhar com "Multiple head revisions".

Esta revisao fecha o fork sem DDL adicional, preservando historico e
mantendo o encadeamento correto para ambientes novos e existentes.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0016_merge_companies_deleted_at_and_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0015_merge_heads",
    "0015_companies_deleted_at",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration — sem DDL."""
    pass


def downgrade() -> None:
    """Merge migration — sem DDL."""
    pass
