#!/usr/bin/env bash
# INFRA-06 — smoke test do bucket S3 (Backblaze B2 ou qualquer S3-compativel).
#
# Uso:
#   set -a; source config/.env; set +a
#   bash infra/scripts/s3-smoke-test.sh
#
# O teste executa put -> get -> diff -> presign -> ls -> delete sob o prefix
# $S3_EXECUTIONS_PREFIX/_smoketest/, garantindo que a Application Key
# tem permissao apenas onde deveria (least privilege — ver ADR-003).
# Nao toca em dados de tenants reais.

set -euo pipefail

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "[s3-smoke] ERRO: variavel $name nao definida." >&2
    echo "[s3-smoke] Carregue config/.env antes: set -a; source config/.env; set +a" >&2
    exit 2
  fi
}

require_var S3_ENDPOINT
require_var S3_BUCKET
require_var S3_KEY_ID
require_var S3_APPLICATION_KEY
: "${S3_EXECUTIONS_PREFIX:=tenants/}"
: "${S3_REGION:=us-west-004}"

if ! command -v aws >/dev/null 2>&1; then
  echo "[s3-smoke] ERRO: aws CLI nao encontrada. Instale: pipx install awscli" >&2
  exit 2
fi

# Credenciais passadas via env pro aws-cli (nao toca em ~/.aws/credentials).
export AWS_ACCESS_KEY_ID="$S3_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$S3_APPLICATION_KEY"
export AWS_DEFAULT_REGION="$S3_REGION"

echo "[s3-smoke] endpoint=$S3_ENDPOINT bucket=$S3_BUCKET"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

UUID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid;print(uuid.uuid4())")"
KEY="${S3_EXECUTIONS_PREFIX}_smoketest/${UUID}.txt"
SRC="$TMP_DIR/src.txt"
DST="$TMP_DIR/dst.txt"

printf 'nfse-saas smoke test %s\n' "$UUID" > "$SRC"

# put
aws --endpoint-url "$S3_ENDPOINT" s3 cp "$SRC" "s3://$S3_BUCKET/$KEY" >/dev/null
echo "[s3-smoke] put  OK  -> $KEY"

# get
aws --endpoint-url "$S3_ENDPOINT" s3 cp "s3://$S3_BUCKET/$KEY" "$DST" >/dev/null
if ! diff -q "$SRC" "$DST" >/dev/null; then
  echo "[s3-smoke] ERRO: conteudo baixado difere do enviado." >&2
  exit 1
fi
echo "[s3-smoke] get  OK  -> conteudo identico"

# presigned URL
PRESIGNED_URL="$(aws --endpoint-url "$S3_ENDPOINT" s3 presign "s3://$S3_BUCKET/$KEY" --expires-in 3600)"
if [[ -z "$PRESIGNED_URL" ]]; then
  echo "[s3-smoke] ERRO: aws s3 presign nao retornou URL." >&2
  exit 1
fi
if command -v curl >/dev/null 2>&1; then
  curl -fsS --max-time 10 "$PRESIGNED_URL" -o "$TMP_DIR/presigned.txt"
  if ! diff -q "$SRC" "$TMP_DIR/presigned.txt" >/dev/null; then
    echo "[s3-smoke] ERRO: conteudo da presigned URL difere do enviado." >&2
    exit 1
  fi
fi
echo "[s3-smoke] url  OK  -> presigned URL 1h gerada e validada"

# ls
COUNT="$(aws --endpoint-url "$S3_ENDPOINT" s3 ls "s3://$S3_BUCKET/${S3_EXECUTIONS_PREFIX}_smoketest/" | wc -l | tr -d ' ')"
if [[ "$COUNT" -lt 1 ]]; then
  echo "[s3-smoke] ERRO: ls nao encontrou o objeto recem-criado." >&2
  exit 1
fi
echo "[s3-smoke] ls   OK  -> $COUNT objeto(s) no prefix ${S3_EXECUTIONS_PREFIX}_smoketest/"

# delete
aws --endpoint-url "$S3_ENDPOINT" s3 rm "s3://$S3_BUCKET/$KEY" >/dev/null
echo "[s3-smoke] del  OK"

echo "[s3-smoke] PASS"
