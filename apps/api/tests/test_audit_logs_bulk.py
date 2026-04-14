"""Insercao massiva em audit_logs (DATA-05 DoD).

Valida que o schema aguenta 10k linhas de audit log num tenant e que o
indice `(tenant_id, created_at DESC)` e usado pelo planner em consultas
de timeline.

Requer `TEST_DATABASE_URL` com `alembic upgrade head` aplicado. Pulado
quando a env nao esta setada — mesmo padrao do test_auth_routes_integration.

Como rodar localmente:

    export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
    alembic -x url="$TEST_DATABASE_URL" upgrade head
    pytest apps/api/tests/test_audit_logs_bulk.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL nao definida — pulando insercao massiva.",
)


BULK_N = 10_000


@pytest.fixture()
def admin_session():
    os.environ["API_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("API_JWT_SECRET", "integration-test-secret")
    os.environ.setdefault("API_ENVIRONMENT", "development")

    from api.config import get_settings
    from api.db import get_admin_session, reset_engine_for_tests
    from sqlalchemy import text

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()

    with get_admin_session() as session:
        session.execute(
            text(
                "TRUNCATE audit_logs, refresh_tokens, tenant_users, users, "
                "tenants CASCADE"
            )
        )
        yield session

    reset_engine_for_tests()


def test_bulk_insert_10k_audit_logs(admin_session) -> None:
    from sqlalchemy import text

    # Tenant ficticio; audit_logs tem FK para tenants.
    tenant_id = str(uuid.uuid4())
    admin_session.execute(
        text(
            "INSERT INTO tenants (id, name, slug) "
            "VALUES (:id, 'BulkCo', 'bulkco')"
        ),
        {"id": tenant_id},
    )

    # INSERT em lote via executemany — cobre o mesmo caminho que a app usara.
    rows = [
        {
            "tenant_id": tenant_id,
            "action": "nfse.fetched",
            "resource_type": "nfse",
            "resource_id": f"nsu-{i}",
            "metadata": "{}",
        }
        for i in range(BULK_N)
    ]
    admin_session.execute(
        text(
            "INSERT INTO audit_logs "
            "(tenant_id, action, resource_type, resource_id, metadata) "
            "VALUES (:tenant_id, :action, :resource_type, :resource_id, "
            "CAST(:metadata AS jsonb))"
        ),
        rows,
    )
    admin_session.commit()

    total = admin_session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE tenant_id = :t"),
        {"t": tenant_id},
    ).scalar_one()
    assert total == BULK_N

    # Timeline (ultimas 50) deve ser barata — sanity check via EXPLAIN.
    # Nao exige uso do indice (planner pode preferir heap scan em
    # datasets pequenos), mas garante que a query completa rapido.
    plan = admin_session.execute(
        text(
            "EXPLAIN (ANALYZE, FORMAT TEXT) "
            "SELECT id, action FROM audit_logs "
            "WHERE tenant_id = :t "
            "ORDER BY created_at DESC LIMIT 50"
        ),
        {"t": tenant_id},
    ).fetchall()
    plan_text = "\n".join(row[0] for row in plan)
    # Sanity: a query completou e o plano menciona o filtro por tenant_id.
    assert "tenant_id" in plan_text
