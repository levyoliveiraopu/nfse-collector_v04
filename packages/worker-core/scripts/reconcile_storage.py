#!/usr/bin/env python3
"""Reconciliador dry-run entre DB e S3 para resultados de execucao.

Detecta dois cenarios operacionais do PROD-READY 3.2:
- linhas `execution_items.status='ok'` sem `xml_object_key`;
- linhas com `xml_object_key` apontando para objeto inexistente no bucket.

Por padrao nao altera nada. Saida JSON para permitir uso em cron/alerta futuro.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Iterable

import boto3
import psycopg
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class Finding:
    kind: str
    execution_item_id: str
    tenant_id: str
    execution_id: str
    object_key: str | None


def _db_url() -> str:
    url = os.environ.get("WORKER_DATABASE_URL") or os.environ.get("API_DATABASE_URL")
    if not url:
        raise SystemExit("WORKER_DATABASE_URL ou API_DATABASE_URL obrigatoria")
    return url.replace("postgresql+psycopg://", "postgresql://")


def _s3_client():
    kwargs = {"service_name": "s3", "region_name": os.environ.get("S3_REGION") or "us-east-1"}
    endpoint = os.environ.get("S3_ENDPOINT")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    key = os.environ.get("S3_KEY_ID")
    secret = os.environ.get("S3_APPLICATION_KEY")
    if key and secret:
        kwargs["aws_access_key_id"] = key
        kwargs["aws_secret_access_key"] = secret
    return boto3.client(**kwargs)


def _iter_ok_items(conn, *, limit: int) -> Iterable[tuple[str, str, str, str | None]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, tenant_id::text, execution_id::text, xml_object_key
              FROM execution_items
             WHERE status = 'ok'
             ORDER BY created_at DESC
             LIMIT %s
            """,
            (limit,),
        )
        yield from cur.fetchall()


def _object_exists(client, *, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404:
            return False
        raise


def reconcile(*, limit: int) -> list[Finding]:
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise SystemExit("S3_BUCKET obrigatoria")

    findings: list[Finding] = []
    s3 = _s3_client()
    with psycopg.connect(_db_url()) as conn:
        for item_id, tenant_id, execution_id, object_key in _iter_ok_items(conn, limit=limit):
            if not object_key:
                findings.append(Finding("db_ok_without_object_key", item_id, tenant_id, execution_id, None))
                continue
            if not _object_exists(s3, bucket=bucket, key=object_key):
                findings.append(Finding("db_object_missing_in_s3", item_id, tenant_id, execution_id, object_key))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    findings = reconcile(limit=args.limit)
    print(json.dumps({"findings": [asdict(f) for f in findings]}, ensure_ascii=False))
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
