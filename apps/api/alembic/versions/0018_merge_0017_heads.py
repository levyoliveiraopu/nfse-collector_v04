"""merge heads: 0017_executions_listing_index + 0017_exports

Revision ID: 0018_merge_0017_heads
Revises: 0017_executions_listing_index, 0017_exports
Create Date: 2026-04-17

Contexto:
- A arvore de migrations voltou a ter duas pontas em `main` apos a
  entrada simultanea de `0017_executions_listing_index` (API-08) e
  `0017_exports` (API-15), ambas apontando para `0016_merge_0015_heads`.
- Isso faz `alembic upgrade head` falhar com "Multiple head revisions",
  quebrando o job `test-rls` do CI (DATA-06).

Esta revisao fecha o fork sem DDL adicional — segue o mesmo padrao
do merge 0016 (ver cabecalho daquele arquivo). Nome curto mantem o
identifier dentro do limite padrao `VARCHAR(32)` de
`alembic_version.version_num`.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0018_merge_0017_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0017_executions_listing_index",
    "0017_exports",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration — sem DDL."""
    pass


def downgrade() -> None:
    """Merge migration — sem DDL."""
    pass
