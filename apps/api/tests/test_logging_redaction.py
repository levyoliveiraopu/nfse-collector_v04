from __future__ import annotations

import logging

from api.logging import SensitiveDataFilter, redact_text, redact_value


def test_redact_text_remove_tokens_e_presigned_url() -> None:
    text = (
        "Authorization: Bearer abc.def.ghi refresh_token=rt-secret "
        "url=https://bucket.example/file.xml?X-Amz-Signature=abc&X-Amz-Credential=def"
    )

    redacted = redact_text(text)

    assert "abc.def.ghi" not in redacted
    assert "rt-secret" not in redacted
    assert "X-Amz-Signature" not in redacted
    assert "Bearer [REDACTED]" in redacted
    assert "refresh_token=[REDACTED]" in redacted
    assert "[REDACTED_URL]" in redacted


def test_redact_value_remove_campos_sensiveis_aninhados() -> None:
    payload = {
        "tenant_id": "tenant-ok",
        "refresh_token": "rt-secret",
        "nested": {"pfx_password": "senha", "count": 1},
        "items": [{"ciphertext": "abc"}],
    }

    redacted = redact_value(payload)

    assert redacted["tenant_id"] == "tenant-ok"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["pfx_password"] == "[REDACTED]"
    assert redacted["items"][0]["ciphertext"] == "[REDACTED]"


def test_sensitive_filter_redige_msg_e_extra() -> None:
    record = logging.LogRecord(
        name="api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="login refresh_token=%s",
        args=("rt-secret",),
        exc_info=None,
    )
    record.presigned_url = "https://bucket/file.xml?X-Amz-Signature=abc"
    record.safe = "ok"

    assert SensitiveDataFilter().filter(record) is True

    assert "rt-secret" not in record.msg
    assert record.presigned_url == "[REDACTED_URL]"
    assert record.safe == "ok"
