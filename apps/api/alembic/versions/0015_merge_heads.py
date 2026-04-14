"""merge de heads: 0008_notifications + 0014_plans_subscriptions

Revision ID: 0015_merge_heads
Revises: 0008_notifications, 0014_plans_subscriptions
Create Date: 2026-04-14

Correcao incidental descoberta pelo DATA-06: `alembic heads` apontava
duas pontas abertas em `main`:

- `0008_notifications` — ponta da cadeia DATA-04
  (`0003 → 0004 → 0005 → 0006 → 0007 → 0008`).
- `0014_plans_subscriptions` — ponta da cadeia DATA-05
  (`0011_files` mergeou `0003_company_credentials` com
  `0010_auth_refresh_tokens`, mas ignorou a cadeia DATA-04).

Sem este merge, `alembic upgrade head` falha com "Multiple head
revisions are present", o que impede o job `test-rls` de DATA-06 (e
qualquer operador rodando migrations em um banco novo).

Esta revisao nao cria nem altera objetos — apenas fecha o fork
declarando os dois pais em `down_revision`. Tanto `upgrade` quanto
`downgrade` sao no-op.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0015_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0008_notifications",
    "0014_plans_subscriptions",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration — sem DDL."""
    pass


def downgrade() -> None:
    """Merge migration — sem DDL."""
    pass
