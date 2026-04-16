"""merge heads: 0015_merge_heads + 0015_companies_deleted_at

Revision ID: 0016_merge_0015_heads
Revises: 0015_merge_heads, 0015_companies_deleted_at
Create Date: 2026-04-14

Contexto:
- A arvore de migrations voltou a ter duas pontas em `main` apos a
  entrada de `0015_companies_deleted_at`, porque ela revisa
  `0014_plans_subscriptions` em paralelo com `0015_merge_heads`.
- Isso faz `alembic upgrade head` falhar com "Multiple head revisions".

Esta revisao fecha o fork sem DDL adicional, preservando historico e
mantendo o encadeamento correto para ambientes novos e existentes.

Nota sobre o identifier:
- O revision ID foi encurtado para `0016_merge_0015_heads` (21 chars)
  porque o default do Alembic grava em `alembic_version.version_num`
  como `VARCHAR(32)`, e o nome original ("0016_merge_companies_
  deleted_at_and_merge_heads", 47 chars) estourava o limite durante
  `alembic upgrade head`, quebrando o job `test-rls` no CI. Como o
  UPDATE em `alembic_version` falhava antes de persistir, nenhum
  ambiente chegou a gravar o valor antigo — renomear e seguro.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0016_merge_0015_heads"
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
