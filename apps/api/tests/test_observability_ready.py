from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient


def test_ready_returns_ok_when_dependencies_are_available(monkeypatch) -> None:
    from api import main as main_module
    from api.config import get_settings

    monkeypatch.setenv("API_DATABASE_URL", "postgresql+psycopg://u:p@db/nfse")
    monkeypatch.setenv("API_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("S3_ENDPOINT", "https://s3.example.test")
    monkeypatch.setenv("S3_BUCKET", "bucket")
    monkeypatch.setenv("S3_KEY_ID", "key")
    monkeypatch.setenv("S3_APPLICATION_KEY", "secret")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    class _Session:
        def execute(self, _clause):
            return None

    @contextmanager
    def _admin_session():
        yield _Session()

    monkeypatch.setattr(main_module, "get_admin_session", _admin_session)
    monkeypatch.setattr(main_module, "ping_redis", lambda: None)

    app = main_module.create_app()
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {
        "database": True,
        "redis": True,
        "storage_config": True,
    }
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_ready_returns_503_with_dependency_details(monkeypatch) -> None:
    from api import main as main_module
    from api.config import get_settings
    from api.queue import QueueError

    monkeypatch.setenv("API_DATABASE_URL", "postgresql+psycopg://u:p@db/nfse")
    monkeypatch.setenv("API_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_KEY_ID", raising=False)
    monkeypatch.delenv("S3_APPLICATION_KEY", raising=False)
    get_settings.cache_clear()  # type: ignore[attr-defined]

    @contextmanager
    def _admin_session():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    def _ping_redis():
        raise QueueError("redis indisponivel")

    monkeypatch.setattr(main_module, "get_admin_session", _admin_session)
    monkeypatch.setattr(main_module, "ping_redis", _ping_redis)

    app = main_module.create_app()
    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"] == {
        "database": False,
        "redis": False,
        "storage_config": False,
    }
    assert body["details"]["database"] == "RuntimeError"
    assert body["details"]["redis"] == "redis indisponivel"
    assert "S3_BUCKET" in body["details"]["storage_config"]
    get_settings.cache_clear()  # type: ignore[attr-defined]
