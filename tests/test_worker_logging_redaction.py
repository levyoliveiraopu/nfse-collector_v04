from __future__ import annotations

import logging

from worker_core.logging import SensitiveDataFilter, redact_text, redact_value


def test_worker_redaction_texto_livre() -> None:
    redacted = redact_text('senha=abc token=secret "ciphertext":"deadbeef"')

    assert "abc" not in redacted
    assert "secret" not in redacted
    assert "deadbeef" not in redacted
    assert "senha=[REDACTED]" in redacted


def test_worker_redaction_extra_record() -> None:
    record = logging.LogRecord("worker", logging.INFO, __file__, 1, "Bearer abc.def", (), None)
    record.pfx_password = "senha-real"
    record.object_key = "tenants/x.xml"

    SensitiveDataFilter().filter(record)

    assert record.msg == "Bearer [REDACTED]"
    assert record.pfx_password == "[REDACTED]"
    assert record.object_key == "tenants/x.xml"


def test_worker_redaction_mapping() -> None:
    assert redact_value({"authorization": "Bearer abc", "ok": "value"}) == {
        "authorization": "[REDACTED]",
        "ok": "value",
    }
