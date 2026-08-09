"""Validacao dos schemas de autenticacao."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.auth.schemas import LoginIn
from api.config import get_settings


def test_local_demo_email_requires_explicit_development_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_ENVIRONMENT", "development")
    monkeypatch.setenv("API_ALLOW_LOCAL_DEMO_LOGIN", "false")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        LoginIn(email="admin@demo.local", password="demo12345")

    monkeypatch.setenv("API_ALLOW_LOCAL_DEMO_LOGIN", "true")
    get_settings.cache_clear()
    payload = LoginIn(email="ADMIN@DEMO.LOCAL", password="demo12345")

    assert payload.email == "admin@demo.local"
    assert LoginIn.model_json_schema()["properties"]["email"]["format"] == "email"
    get_settings.cache_clear()
