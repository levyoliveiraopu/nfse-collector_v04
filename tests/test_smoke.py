"""Testes do smoke test E2E (CORE-06).

Cobre apenas a logica do proprio script (parsing/validacao de args,
filtro de janela por data, callback de progresso). O fluxo de coleta +
upload real e responsabilidade dos testes de CORE-04
(`test_fetch_nfse.py`) e CORE-05 (`test_storage.py`); replica-los aqui
seria duplicacao.
"""

from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


def _load_smoke_module():
    """Carrega `packages/worker-core/scripts/smoke.py` por path absoluto.

    O diretorio `scripts/` nao esta no PYTHONPATH por design — o smoke
    e rodado via `python -m scripts.smoke` a partir do worker-core.
    """
    smoke_path = (
        Path(__file__).resolve().parent.parent
        / "packages"
        / "worker-core"
        / "scripts"
        / "smoke.py"
    )
    import sys

    spec = importlib.util.spec_from_file_location("worker_core_smoke", smoke_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["worker_core_smoke"] = module  # dataclasses precisa ver o modulo
    spec.loader.exec_module(module)
    return module


smoke = _load_smoke_module()


# ---------------------------------------------------------------------------
# _within_window
# ---------------------------------------------------------------------------


def test_within_window_aceita_data_dentro_da_janela():
    cutoff = date(2026, 4, 9)  # 7 dias antes de 2026-04-16
    assert smoke._within_window("16/04/2026", cutoff) is True
    assert smoke._within_window("09/04/2026", cutoff) is True


def test_within_window_descarta_data_anterior_ao_cutoff():
    cutoff = date(2026, 4, 9)
    assert smoke._within_window("08/04/2026", cutoff) is False
    assert smoke._within_window("01/01/2020", cutoff) is False


def test_within_window_mantem_quando_data_invalida_ou_ausente():
    """Conservador: prefere subir XML legitimo a descartar silenciosamente."""
    cutoff = date(2026, 4, 9)
    assert smoke._within_window(None, cutoff) is True
    assert smoke._within_window("", cutoff) is True
    assert smoke._within_window("nao-e-data", cutoff) is True
    assert smoke._within_window("2026-04-16", cutoff) is True  # ISO != DD/MM/AAAA


# ---------------------------------------------------------------------------
# _parse_args / _validate_args
# ---------------------------------------------------------------------------


def test_parse_args_minimo(tmp_path: Path):
    pfx = tmp_path / "fake.pfx"
    pfx.write_bytes(b"x")
    args = smoke._parse_args([
        "--pfx", str(pfx),
        "--cnpj", "12345678000199",
    ])
    assert args.pfx == pfx
    assert args.cnpj == "12345678000199"
    assert args.dias == 7
    assert args.ambiente == "PRODUCAO"
    assert args.dry_run is False
    assert args.max_documentos is None
    assert args.rate_limit == 0


def test_validate_args_rejeita_cnpj_invalido(tmp_path: Path):
    pfx = tmp_path / "fake.pfx"
    pfx.write_bytes(b"x")
    args = smoke._parse_args(["--pfx", str(pfx), "--cnpj", "abc"])
    with pytest.raises(SystemExit, match="14 digitos"):
        smoke._validate_args(args)


def test_validate_args_rejeita_pfx_inexistente(tmp_path: Path):
    args = smoke._parse_args([
        "--pfx", str(tmp_path / "nao-existe.pfx"),
        "--cnpj", "12345678000199",
    ])
    with pytest.raises(SystemExit, match="PFX nao encontrado"):
        smoke._validate_args(args)


def test_validate_args_rejeita_dias_zero_ou_negativo(tmp_path: Path):
    pfx = tmp_path / "fake.pfx"
    pfx.write_bytes(b"x")
    args = smoke._parse_args([
        "--pfx", str(pfx),
        "--cnpj", "12345678000199",
        "--dias", "0",
    ])
    with pytest.raises(SystemExit, match="--dias"):
        smoke._validate_args(args)


def test_validate_args_rejeita_uuid_invalido(tmp_path: Path):
    pfx = tmp_path / "fake.pfx"
    pfx.write_bytes(b"x")
    args = smoke._parse_args([
        "--pfx", str(pfx),
        "--cnpj", "12345678000199",
        "--tenant-id", "nao-uuid",
    ])
    with pytest.raises(SystemExit, match="--tenant-id"):
        smoke._validate_args(args)


# ---------------------------------------------------------------------------
# main: erros de configuracao
# ---------------------------------------------------------------------------


def test_main_falha_sem_password_env(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("NFSE_PFX_PASSWORD", raising=False)
    pfx = tmp_path / "fake.pfx"
    pfx.write_bytes(b"x")
    rc = smoke.main([
        "--pfx", str(pfx),
        "--cnpj", "12345678000199",
        "--dry-run",
    ])
    assert rc == smoke.EXIT_USAGE
    err = capsys.readouterr().err
    assert "NFSE_PFX_PASSWORD" in err


# ---------------------------------------------------------------------------
# Callback: nao loga payload sensivel (smoke check)
# ---------------------------------------------------------------------------


def test_emit_log_nao_inclui_pfx_password_nem_pfx_bytes(capsys):
    smoke._emit_log(
        "x",
        {"nsu": 1, "pfx_password": "segredo", "pfx_bytes": b"\x00\x01"},
    )
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    assert payload == {"event": "x", "nsu": 1}


def test_progress_callback_filtra_por_data_e_nao_chama_storage():
    storage = MagicMock()
    counters = smoke._UploadCounters()
    cutoff = date(2026, 4, 9)
    on_progress = smoke._make_progress_callback(
        storage=storage,
        tenant_id=uuid4(),
        execution_id=uuid4(),
        cutoff=cutoff,
        counters=counters,
    )

    item_velho = smoke.NfseItem(
        nsu=1,
        chave_nfse="K1",
        cnpj_emitente="12345678000199",
        data_emissao="01/01/2020",
        valor=100.0,
        xml_bytes=b"<NFSe/>",
        status="ok",
        error_code=None,
        error_message=None,
    )
    on_progress(item_velho)

    assert counters.filtered_by_date == 1
    assert counters.uploads_ok == 0
    storage.upload_xml.assert_not_called()


def test_progress_callback_dry_run_nao_chama_storage(capsys):
    counters = smoke._UploadCounters()
    cutoff = date(2026, 4, 9)
    on_progress = smoke._make_progress_callback(
        storage=None,  # dry-run
        tenant_id=uuid4(),
        execution_id=uuid4(),
        cutoff=cutoff,
        counters=counters,
    )
    item_novo = smoke.NfseItem(
        nsu=42,
        chave_nfse="K42",
        cnpj_emitente="12345678000199",
        data_emissao=date.today().strftime("%d/%m/%Y"),
        valor=200.0,
        xml_bytes=b"<NFSe>x</NFSe>",
        status="ok",
        error_code=None,
        error_message=None,
    )
    on_progress(item_novo)
    assert counters.uploads_ok == 1
    assert counters.bytes_total == len(item_novo.xml_bytes)
    out_lines = capsys.readouterr().out.strip().splitlines()
    payload = json.loads(out_lines[-1])
    assert payload["event"] == "smoke.dry_run.would_upload"
    assert payload["nsu"] == 42


def test_progress_callback_pula_parse_error():
    counters = smoke._UploadCounters()
    on_progress = smoke._make_progress_callback(
        storage=MagicMock(),
        tenant_id=uuid4(),
        execution_id=uuid4(),
        cutoff=date.today(),
        counters=counters,
    )
    item = smoke.NfseItem(
        nsu=7,
        chave_nfse=None,
        cnpj_emitente=None,
        data_emissao=None,
        valor=None,
        xml_bytes=None,
        status="parse_error",
        error_code="XML_NOT_FOUND",
        error_message="x",
    )
    on_progress(item)
    assert counters.parse_errors_skipped == 1
    assert counters.uploads_ok == 0
