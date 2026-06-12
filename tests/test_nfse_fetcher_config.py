from __future__ import annotations

import pytest

from worker_core import fetcher


class _Response:
    status_code = 200

    def json(self):
        return {"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []}

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return _Response()


def test_buscar_lote_dfe_usa_timeout_parametrizado(monkeypatch) -> None:
    monkeypatch.setenv("NFSE_ADN_CONNECT_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("NFSE_ADN_READ_TIMEOUT_SECONDS", "12.25")
    session = _Session()

    out = fetcher.buscar_lote_dfe(session, 10, "12345678000199")

    assert out["StatusProcessamento"] == "NENHUM_DOCUMENTO_LOCALIZADO"
    assert session.calls[0]["timeout"] == (3.5, 12.25)


def test_buscar_lote_dfe_classifica_5xx(monkeypatch) -> None:
    monkeypatch.setenv("NFSE_ADN_RETRY_ATTEMPTS", "1")

    class Response5xx:
        status_code = 503

        def json(self):
            return {}

        def raise_for_status(self):
            raise AssertionError("nao deve chegar aqui")

    class Session5xx:
        def get(self, *args, **kwargs):
            return Response5xx()

    with pytest.raises(fetcher.PortalRequestError) as excinfo:
        fetcher.buscar_lote_dfe(Session5xx(), 10, "12345678000199")

    assert excinfo.value.code == "ADN_HTTP_5XX"
    assert excinfo.value.status_code == 503
