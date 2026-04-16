"""Testes do handler `run_execution` (API-13).

Estrategia: monkey-patch em `worker_core.jobs` para substituir:

- `get_admin_session` / `get_tenant_session` por um fake que captura as
  queries SQL emitidas e devolve rows pre-configuradas.
- `fetch_nfse` por uma funcao controlada que emite `NfseItem` desejados.
- `decrypt` por identidade (plaintext == ciphertext).
- `S3StorageClient` por um stub que registra os uploads.

Cobre a DoD do ticket:

1. Caminho feliz: 2 itens ok -> status `succeeded`, items_ok=2.
2. Parcial: 1 ok + 1 parse_error -> status `partial` + occurrence
   `PARSE_ERROR`.
3. Credencial falhando na decifra -> status `failed` + occurrence
   `CRED_INVALID`.
4. Idempotencia: quando o INSERT retorna None (conflito em unique
   `(tenant_id, chave_nfse)`), o item nao conta como ok nem fail.
5. `fatal_rejected` do coletor -> status `failed` + occurrence
   `PORTAL_5XX`.
6. Execucao inexistente -> retorna `{"status": "not_found"}` sem
   levantar.
7. Status decision map (`_decide_final_status`) cobre os ramos.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from worker_core import jobs as jobs_module
from worker_core.collector import FetchSummary, NfseItem
from worker_core.crypto import CryptoError
from worker_core.jobs import JobError, _decide_final_status, run_execution
from worker_core.storage import StorageError, UploadResult


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, *, row=None, rowcount: int = 0):
        self._row = row
        self.rowcount = rowcount

    def one_or_none(self):
        return self._row

    def one(self):
        if self._row is None:
            raise RuntimeError("no row")
        return self._row


class _FakeRow:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        # Respostas pre-programadas por padrao de SQL lower-case.
        self._answers: dict[str, object] = {}
        # Default: INSERT execution_items com RETURNING retorna row (inserido).
        self.default_insert_row: _FakeRow | None = _FakeRow(id=uuid4())

    def set_answer(self, sql_contains: str, row) -> None:
        self._answers[sql_contains.lower()] = row

    def execute(self, clause, params=None):
        sql = str(clause).lower()
        self.calls.append((sql, params or {}))
        for key, row in self._answers.items():
            if key in sql:
                return _FakeResult(row=row, rowcount=1)
        if "insert into execution_items" in sql:
            return _FakeResult(row=self.default_insert_row, rowcount=1)
        return _FakeResult(row=None, rowcount=0)


class _FakeStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple] = []
        self.raise_error: bool = False

    def upload_xml(self, tenant_id, execution_id, nsu, xml_bytes) -> UploadResult:
        if self.raise_error:
            raise StorageError("b2 down")
        self.uploads.append((str(tenant_id), str(execution_id), nsu, len(xml_bytes)))
        return UploadResult(
            object_key=f"tenants/{tenant_id}/executions/{execution_id}/{nsu}.xml",
            sha256="a" * 64,
            size=len(xml_bytes),
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def credential_id() -> UUID:
    return uuid4()


@pytest.fixture
def execution_id() -> UUID:
    return uuid4()


@pytest.fixture
def patched_db(monkeypatch, tenant_id, company_id, credential_id, execution_id):
    """Substitui `get_admin_session` e `get_tenant_session` por `_FakeSession`.

    Cada sessao e compartilhada entre chamadas dentro do mesmo fixture —
    o `.calls` acumula todas as queries emitidas pelo handler.
    """
    session = _FakeSession()

    # Respostas das queries que o handler emite em `_load_execution_context`.
    session.set_answer(
        "select id, tenant_id, company_id\n                  from executions",
        _FakeRow(id=execution_id, tenant_id=tenant_id, company_id=company_id),
    )
    session.set_answer(
        "from companies where id",
        _FakeRow(cnpj="12345678000199"),
    )
    session.set_answer(
        "from company_credentials",
        _FakeRow(
            id=credential_id,
            pfx_object_key="tenants-credentials/x.pfx.enc",
            pfx_password_ciphertext=b"ENC_PWD",
        ),
    )

    @contextmanager
    def _cm(*args, **kwargs):
        yield session

    monkeypatch.setattr(jobs_module, "get_admin_session", _cm)
    monkeypatch.setattr(jobs_module, "get_tenant_session", lambda _tid: _cm())
    yield session


@pytest.fixture
def patched_decrypt(monkeypatch):
    """Substitui `decrypt` por identidade (ciphertext == plaintext)."""

    def _fake_decrypt(ct: bytes, _tenant_id):
        return bytes(ct)

    monkeypatch.setattr(jobs_module, "decrypt", _fake_decrypt)


@pytest.fixture
def fake_storage() -> _FakeStorage:
    return _FakeStorage()


@pytest.fixture
def fake_read_blob():
    return lambda _key: b"ENC_PFX"


def _item(nsu: int, *, status: str = "ok", chave: str | None = None) -> NfseItem:
    return NfseItem(
        nsu=nsu,
        chave_nfse=chave or f"CHAVE{nsu}",
        cnpj_emitente="12345678000199",
        data_emissao="10/04/2026",
        valor=100.0,
        xml_bytes=b"<xml/>" if status == "ok" else None,
        status=status,
        error_code=None if status == "ok" else "XML_PARSE",
        error_message=None if status == "ok" else "parse failed",
    )


def _summary(*, nsu_to: int = 10, fatal: bool = False, total_erro: int = 0) -> FetchSummary:
    return FetchSummary(
        cnpj="12345678000199",
        nsu_from=0,
        nsu_to=nsu_to,
        total_documentos=2,
        total_nfse=2,
        total_sucesso=2 - total_erro,
        total_cancelada=0,
        total_erro=total_erro,
        callback_errors=0,
        fatal_rejected=fatal,
    )


# ---------------------------------------------------------------------------
# Tests — caminho feliz
# ---------------------------------------------------------------------------


def test_run_execution_sucesso(
    monkeypatch, patched_db, patched_decrypt, fake_storage, fake_read_blob, execution_id
) -> None:
    items = [_item(1), _item(2)]

    def _fake_fetch(**kwargs):
        for it in items:
            kwargs["on_progress"](it)
        return _summary(nsu_to=2)

    monkeypatch.setattr(jobs_module, "fetch_nfse", _fake_fetch)

    result = run_execution(
        str(execution_id),
        storage_client=fake_storage,
        read_credential_blob=fake_read_blob,
    )

    assert result["status"] == "succeeded"
    assert result["items_ok"] == 2
    assert result["items_fail"] == 0
    assert len(fake_storage.uploads) == 2
    # Verifica que um UPDATE final marcou finished + contadores.
    finished_updates = [
        c for c in patched_db.calls
        if "update executions" in c[0] and ":st" in str(c[0])
    ]
    assert finished_updates


# ---------------------------------------------------------------------------
# Tests — parcial
# ---------------------------------------------------------------------------


def test_run_execution_partial_com_parse_error(
    monkeypatch, patched_db, patched_decrypt, fake_storage, fake_read_blob, execution_id
) -> None:
    items = [_item(1), _item(2, status="parse_error", chave=None)]

    def _fake_fetch(**kwargs):
        for it in items:
            kwargs["on_progress"](it)
        return _summary(nsu_to=2, total_erro=1)

    monkeypatch.setattr(jobs_module, "fetch_nfse", _fake_fetch)

    result = run_execution(
        str(execution_id),
        storage_client=fake_storage,
        read_credential_blob=fake_read_blob,
    )

    assert result["status"] == "partial"
    assert result["items_ok"] == 1
    assert result["items_fail"] == 1
    # Occurrence PARSE_ERROR inserida.
    occ_inserts = [c for c in patched_db.calls if "insert into occurrences" in c[0]]
    codes = [c[1].get("code") for c in occ_inserts]
    assert "PARSE_ERROR" in codes


# ---------------------------------------------------------------------------
# Tests — credencial falhando
# ---------------------------------------------------------------------------


def test_run_execution_credential_decrypt_failed(
    monkeypatch, patched_db, fake_storage, fake_read_blob, execution_id
) -> None:
    def _boom(_ct, _tid):
        raise CryptoError("tampered")

    monkeypatch.setattr(jobs_module, "decrypt", _boom)

    with pytest.raises(JobError, match="credential_decrypt_failed"):
        run_execution(
            str(execution_id),
            storage_client=fake_storage,
            read_credential_blob=fake_read_blob,
        )

    # Occurrence CRED_INVALID registrada + execution marcada como failed.
    occ = [c for c in patched_db.calls if "insert into occurrences" in c[0]]
    assert any(c[1].get("code") == "CRED_INVALID" for c in occ)
    failed = [c for c in patched_db.calls if "update executions" in c[0] and "'failed'" in c[0]]
    assert failed


# ---------------------------------------------------------------------------
# Tests — idempotencia
# ---------------------------------------------------------------------------


def test_run_execution_idempotente_quando_insert_nao_retorna_linha(
    monkeypatch, patched_db, patched_decrypt, fake_storage, fake_read_blob, execution_id
) -> None:
    # Forca o INSERT execution_items a devolver row=None (conflito DO NOTHING).
    patched_db.default_insert_row = None

    items = [_item(1), _item(2)]

    def _fake_fetch(**kwargs):
        for it in items:
            kwargs["on_progress"](it)
        return _summary(nsu_to=2)

    monkeypatch.setattr(jobs_module, "fetch_nfse", _fake_fetch)

    result = run_execution(
        str(execution_id),
        storage_client=fake_storage,
        read_credential_blob=fake_read_blob,
    )

    # Nenhum item contabilizado (duplicatas ignoradas silenciosamente).
    assert result["items_ok"] == 0
    assert result["items_fail"] == 0
    # Status final: "succeeded" (nada de novo coletado e sem falhas).
    assert result["status"] == "succeeded"


# ---------------------------------------------------------------------------
# Tests — portal rejeitou
# ---------------------------------------------------------------------------


def test_run_execution_fatal_rejected_vira_failed(
    monkeypatch, patched_db, patched_decrypt, fake_storage, fake_read_blob, execution_id
) -> None:
    def _fake_fetch(**kwargs):
        return _summary(nsu_to=0, fatal=True)

    monkeypatch.setattr(jobs_module, "fetch_nfse", _fake_fetch)

    result = run_execution(
        str(execution_id),
        storage_client=fake_storage,
        read_credential_blob=fake_read_blob,
    )

    assert result["status"] == "failed"
    occ = [c for c in patched_db.calls if "insert into occurrences" in c[0]]
    assert any(c[1].get("code") == "PORTAL_5XX" for c in occ)


# ---------------------------------------------------------------------------
# Tests — storage error upload
# ---------------------------------------------------------------------------


def test_run_execution_storage_error_cria_occurrence(
    monkeypatch, patched_db, patched_decrypt, fake_read_blob, execution_id
) -> None:
    storage = _FakeStorage()
    storage.raise_error = True

    items = [_item(1)]

    def _fake_fetch(**kwargs):
        for it in items:
            kwargs["on_progress"](it)
        return _summary(nsu_to=1)

    monkeypatch.setattr(jobs_module, "fetch_nfse", _fake_fetch)

    result = run_execution(
        str(execution_id),
        storage_client=storage,
        read_credential_blob=fake_read_blob,
    )

    assert result["storage_errors"] == 1
    occ = [c for c in patched_db.calls if "insert into occurrences" in c[0]]
    assert any(c[1].get("code") == "STORAGE_ERROR" for c in occ)


# ---------------------------------------------------------------------------
# Tests — execucao inexistente
# ---------------------------------------------------------------------------


def test_run_execution_inexistente_retorna_not_found(monkeypatch, execution_id) -> None:
    session = _FakeSession()
    # Nao programamos a row de executions -> execute devolve row=None.

    @contextmanager
    def _cm(*args, **kwargs):
        yield session

    monkeypatch.setattr(jobs_module, "get_admin_session", _cm)
    monkeypatch.setattr(jobs_module, "get_tenant_session", lambda _tid: _cm())

    result = run_execution(str(execution_id))
    assert result == {"status": "not_found", "execution_id": str(execution_id)}


# ---------------------------------------------------------------------------
# Tests — decisao de status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ok,fail,storage_err,fatal,expected",
    [
        (2, 0, 0, False, "succeeded"),
        (0, 0, 0, False, "succeeded"),
        (1, 1, 0, False, "partial"),
        (0, 2, 0, False, "failed"),
        (2, 0, 1, False, "partial"),
        (5, 0, 0, True, "failed"),
    ],
)
def test_decide_final_status(ok, fail, storage_err, fatal, expected) -> None:
    summary = FetchSummary(
        cnpj="12345678000199",
        nsu_from=0, nsu_to=1,
        total_documentos=ok + fail, total_nfse=ok + fail,
        total_sucesso=ok, total_cancelada=0, total_erro=fail,
        callback_errors=0, fatal_rejected=fatal,
    )
    assert _decide_final_status(summary, ok, fail, storage_err) == expected
