"""Smoke test E2E do worker-core (CORE-06).

Executa o fluxo completo `mtls_session` -> `fetch_nfse` -> `S3StorageClient`
contra o ADN real, usando 1 CNPJ de teste com PFX A1 valido. Serve para
provar que CORE-02..05 funcionam fim-a-fim antes do worker SaaS (API-13)
consumir o pacote.

Uso tipico (dry run, sem subir nada):

    export NFSE_PFX_PASSWORD='senha-do-pfx'
    python -m scripts.smoke \
        --pfx /caminho/cliente.pfx \
        --cnpj 12345678000199 \
        --dias 7 \
        --max-documentos 50 \
        --dry-run

Uso real (sobe XMLs no bucket S3-compat configurado em S3_*):

    export NFSE_PFX_PASSWORD='senha-do-pfx'
    export S3_BUCKET=...
    export S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com
    export S3_REGION=us-west-004
    export S3_KEY_ID=...
    export S3_APPLICATION_KEY=...
    python -m scripts.smoke --pfx /caminho/cliente.pfx --cnpj 12345678000199

Garantias de seguranca (DoD CORE-06 — "sem dados sensiveis em logs"):

- Senha do PFX vem **apenas** via env `NFSE_PFX_PASSWORD`. Nunca como
  flag de CLI (apareceria em `ps`/history) e nunca logada.
- Credenciais S3 (`S3_KEY_ID`/`S3_APPLICATION_KEY`) sao lidas via
  `S3Settings.from_env` e nunca aparecem em log/print.
- Bytes do PFX e bytes do XML jamais sao impressos. Logs estruturados
  carregam apenas `nsu`/`chave_nfse`/`error_code`/`stage`/contadores.
- Em erro fatal (`ValueError` do `mtls_session`) o stack trace nao
  contem path/senha/bytes do PFX (`mtls_session` ja trata isso em
  CORE-02). O smoke nao re-faz raise com payload extra.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from worker_core import (
    FetchSummary,
    InMemoryNsuSource,
    NfseItem,
    S3Settings,
    S3StorageClient,
    StorageError,
    fetch_nfse,
)

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FATAL = 2
EXIT_NETWORK = 3

_PFX_PASSWORD_ENV = "NFSE_PFX_PASSWORD"


@dataclass
class _UploadCounters:
    """Contadores agregados pelos callbacks do smoke."""

    uploads_ok: int = 0
    uploads_failed: int = 0
    filtered_by_date: int = 0
    parse_errors_skipped: int = 0
    bytes_total: int = 0
    object_keys: list[str] = field(default_factory=list)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="worker-core-smoke",
        description=(
            "Smoke test E2E do worker-core: PFX -> ADN -> S3. "
            "Senha do PFX deve vir via env NFSE_PFX_PASSWORD."
        ),
    )
    parser.add_argument(
        "--pfx",
        required=True,
        type=Path,
        help="Caminho do arquivo .pfx A1 (lido em bytes).",
    )
    parser.add_argument(
        "--cnpj",
        required=True,
        help="CNPJ do contribuinte (14 digitos, sem mascara).",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=7,
        help="Janela de filtro client-side por data_emissao (default: 7).",
    )
    parser.add_argument(
        "--max-documentos",
        type=int,
        default=None,
        help="Teto de documentos a paginar na ADN (default: sem limite).",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=0,
        help="Segundos entre chamadas de paginacao (default: 0).",
    )
    parser.add_argument(
        "--ambiente",
        choices=("PRODUCAO", "HOMOLOGACAO"),
        default="PRODUCAO",
        help="Ambiente ADN (seta NFSE_AMBIENTE; default: PRODUCAO).",
    )
    parser.add_argument(
        "--nsu-inicial",
        type=int,
        default=0,
        help="NSU inicial da paginacao (default: 0 — desde o comeco).",
    )
    parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="UUID do tenant para compor object_key (default: aleatorio).",
    )
    parser.add_argument(
        "--execution-id",
        type=str,
        default=None,
        help="UUID da execucao para compor object_key (default: aleatorio).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao sobe pro S3, apenas conta o que subiria.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Habilita logging.INFO no worker_core.",
    )
    return parser.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> None:
    if not args.cnpj.isdigit() or len(args.cnpj) != 14:
        raise SystemExit("--cnpj precisa ter 14 digitos numericos sem mascara")
    if args.dias <= 0:
        raise SystemExit("--dias deve ser positivo")
    if args.rate_limit < 0:
        raise SystemExit("--rate-limit deve ser >= 0")
    if args.max_documentos is not None and args.max_documentos <= 0:
        raise SystemExit("--max-documentos deve ser positivo")
    if args.nsu_inicial < 0:
        raise SystemExit("--nsu-inicial deve ser >= 0")
    if not args.pfx.is_file():
        raise SystemExit(f"PFX nao encontrado: {args.pfx}")
    for label, value in (("--tenant-id", args.tenant_id), ("--execution-id", args.execution_id)):
        if value is not None:
            try:
                UUID(value)
            except ValueError as exc:
                raise SystemExit(f"{label} invalido: {exc}") from exc


def _within_window(data_emissao: Optional[str], cutoff: date) -> bool:
    """True quando `data_emissao` (DD/MM/AAAA) e >= cutoff.

    Itens sem data parseavel sao **mantidos** (conservador — preferimos
    subir que descartar silenciosamente um XML legitimo).
    """
    if not data_emissao:
        return True
    try:
        emissao = datetime.strptime(data_emissao, "%d/%m/%Y").date()
    except ValueError:
        return True
    return emissao >= cutoff


def _emit_log(evento: str, payload: dict) -> None:
    """Imprime evento estruturado em JSON. Garante zero segredos no payload.

    `worker_core.collector.fetch_nfse` ja sanitiza o que passa aqui (so
    contadores e identificadores publicos). Nao adicionamos nada do
    request body / response body.
    """
    safe = {k: v for k, v in payload.items() if k not in {"pfx_password", "pfx_bytes"}}
    print(json.dumps({"event": evento, **safe}, ensure_ascii=False, default=str))


def _make_progress_callback(
    storage: Optional[S3StorageClient],
    tenant_id: UUID,
    execution_id: UUID,
    cutoff: date,
    counters: _UploadCounters,
) -> "callable[[NfseItem], None]":
    def _on_progress(item: NfseItem) -> None:
        if item.status == "parse_error":
            counters.parse_errors_skipped += 1
            _emit_log(
                "smoke.skip_parse_error",
                {"nsu": item.nsu, "error_code": item.error_code},
            )
            return
        if not _within_window(item.data_emissao, cutoff):
            counters.filtered_by_date += 1
            return
        if item.xml_bytes is None:
            counters.parse_errors_skipped += 1
            _emit_log("smoke.skip_no_xml", {"nsu": item.nsu})
            return

        if storage is None:
            counters.uploads_ok += 1
            counters.bytes_total += len(item.xml_bytes)
            _emit_log(
                "smoke.dry_run.would_upload",
                {
                    "nsu": item.nsu,
                    "chave_nfse": item.chave_nfse,
                    "size": len(item.xml_bytes),
                },
            )
            return

        try:
            result = storage.upload_xml(
                tenant_id=tenant_id,
                execution_id=execution_id,
                nsu=item.nsu,
                xml_bytes=item.xml_bytes,
            )
        except StorageError as exc:
            counters.uploads_failed += 1
            _emit_log(
                "smoke.upload_failed",
                {"nsu": item.nsu, "error": str(exc)},
            )
            return

        counters.uploads_ok += 1
        counters.bytes_total += result.size
        counters.object_keys.append(result.object_key)
        _emit_log(
            "smoke.upload_ok",
            {
                "nsu": item.nsu,
                "object_key": result.object_key,
                "sha256": result.sha256,
                "size": result.size,
            },
        )

    return _on_progress


def _print_summary(
    summary: FetchSummary,
    counters: _UploadCounters,
    *,
    cutoff: date,
    dry_run: bool,
) -> None:
    print()
    print("=== Smoke summary ===")
    print(f"cnpj                       : {summary.cnpj}")
    print(f"cutoff (data_emissao >=)   : {cutoff.isoformat()}")
    print(f"nsu_from                   : {summary.nsu_from}")
    print(f"nsu_to                     : {summary.nsu_to}")
    print(f"total_documentos           : {summary.total_documentos}")
    print(f"total_nfse                 : {summary.total_nfse}")
    print(f"total_sucesso (collector)  : {summary.total_sucesso}")
    print(f"total_cancelada            : {summary.total_cancelada}")
    print(f"total_erro (parse)         : {summary.total_erro}")
    print(f"callback_errors            : {summary.callback_errors}")
    print(f"fatal_rejected             : {summary.fatal_rejected}")
    print("--- smoke counters ---")
    print(f"uploads_ok                 : {counters.uploads_ok}{' (dry-run)' if dry_run else ''}")
    print(f"uploads_failed             : {counters.uploads_failed}")
    print(f"filtered_by_date           : {counters.filtered_by_date}")
    print(f"parse_errors_skipped       : {counters.parse_errors_skipped}")
    print(f"bytes_total                : {counters.bytes_total}")
    if counters.object_keys:
        sample = counters.object_keys[:3]
        print(f"object_keys (amostra)      : {sample}")
        if len(counters.object_keys) > len(sample):
            print(f"  (+{len(counters.object_keys) - len(sample)} mais)")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    _validate_args(args)

    password = os.environ.get(_PFX_PASSWORD_ENV)
    if not password:
        print(
            f"erro: defina {_PFX_PASSWORD_ENV} com a senha do PFX "
            "(nunca passe a senha como argumento de CLI).",
            file=sys.stderr,
        )
        return EXIT_USAGE

    os.environ["NFSE_AMBIENTE"] = args.ambiente

    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    pfx_bytes = args.pfx.read_bytes()
    cutoff = date.today() - timedelta(days=args.dias)
    tenant_id = UUID(args.tenant_id) if args.tenant_id else uuid4()
    execution_id = UUID(args.execution_id) if args.execution_id else uuid4()

    storage: Optional[S3StorageClient]
    if args.dry_run:
        storage = None
        _emit_log(
            "smoke.start",
            {
                "cnpj": args.cnpj,
                "ambiente": args.ambiente,
                "tenant_id": str(tenant_id),
                "execution_id": str(execution_id),
                "cutoff": cutoff.isoformat(),
                "dry_run": True,
            },
        )
    else:
        try:
            settings = S3Settings.from_env()
        except StorageError as exc:
            print(f"erro: {exc}", file=sys.stderr)
            return EXIT_USAGE
        storage = S3StorageClient(settings=settings)
        _emit_log(
            "smoke.start",
            {
                "cnpj": args.cnpj,
                "ambiente": args.ambiente,
                "tenant_id": str(tenant_id),
                "execution_id": str(execution_id),
                "cutoff": cutoff.isoformat(),
                "bucket": settings.bucket,
                "executions_prefix": settings.executions_prefix,
            },
        )

    counters = _UploadCounters()
    nsu_source = InMemoryNsuSource()
    if args.nsu_inicial > 0:
        nsu_source.set(args.cnpj, args.nsu_inicial)

    on_progress = _make_progress_callback(
        storage=storage,
        tenant_id=tenant_id,
        execution_id=execution_id,
        cutoff=cutoff,
        counters=counters,
    )

    try:
        summary = fetch_nfse(
            pfx_bytes=pfx_bytes,
            pfx_password=password,
            cnpj=args.cnpj,
            nsu_source=nsu_source,
            on_progress=on_progress,
            on_log=_emit_log,
            max_documentos=args.max_documentos,
            rate_limit_delay=args.rate_limit,
        )
    except ValueError as exc:
        print(f"erro fatal (mTLS/PFX): {exc}", file=sys.stderr)
        return EXIT_FATAL
    except Exception as exc:  # noqa: BLE001 — boundary do CLI
        print(f"erro de rede ou execucao: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_NETWORK
    finally:
        # Best-effort: sobrescreve a referencia local. Nao garante zerar
        # paginas de memoria (Python nao expoe isso), mas evita reuso
        # acidental no escopo do main.
        pfx_bytes = b""
        password = ""

    _print_summary(summary, counters, cutoff=cutoff, dry_run=args.dry_run)

    if counters.uploads_failed > 0:
        return EXIT_NETWORK
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
