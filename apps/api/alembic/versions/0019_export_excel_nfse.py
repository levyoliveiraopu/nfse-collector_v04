"""Permite export de NFS-e em Excel.

Revision ID: 0019_export_excel_nfse
Revises: 0018_merge_0017_heads
Create Date: 2026-08-08
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0019_export_excel_nfse"
down_revision: Union[str, None] = "0018_merge_0017_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_exports_kind", "exports", type_="check")
    op.create_check_constraint(
        "ck_exports_kind", "exports", "kind IN ('zip_xml','excel_nfse')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_exports_kind", "exports", type_="check")
    op.create_check_constraint("ck_exports_kind", "exports", "kind IN ('zip_xml')")
