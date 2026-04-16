#!/usr/bin/env bash
# INFRA-08 — Backup diario do Postgres para S3 (Backblaze B2 primario).
#
# Uso manual:
#   set -a; source /srv/nfse/prod/config/.env; set +a
#   bash infra/scripts/backup-postgres.sh
#
# Automatico (production): via systemd timer nfse-backup-postgres@prod.timer
# (ver infra/systemd/ e infra/backup.md).
#
# Comportamento:
#   1. Executa `pg_dump -Fc -Z 9` dentro do container do Postgres (INFRA-05)
#      via `docker compose exec -T postgres`, evitando dependencia de
#      pg_dump no host (INFRA-02 nao instala postgresql-client).
#   2. Grava local em $BACKUP_LOCAL_DIR/<prefix>/YYYY-MM-DD.dump[.age].
#      No dia 1 do mes -> prefix `monthly/YYYY-MM.dump` (retencao 365d no S3).
#      Nos demais dias  -> prefix `daily/YYYY-MM-DD.dump`  (retencao 30d no S3).
#   3. Cifra com age (https://age-encryption.org) se BACKUP_ENCRYPT=1
#      (default em staging/prod). A chave publica vai em BACKUP_AGE_RECIPIENT,
#      a privada vive apenas no cofre do owner (1Password/Bitwarden).
#   4. Upload para s3://$S3_BUCKET/$BACKUP_S3_PREFIX<prefix>/<file> via aws-cli.
#   5. Remove dumps locais com mtime > BACKUP_RETENTION_LOCAL_DAYS dias.
#   6. Registra uma linha JSON estruturada em $BACKUP_LOG_FILE com
#      status/size_bytes/duration_ms/s3_key/sha256 para o Promtail (INFRA-07)
#      ingerir em Loki.
#
# Exit codes:
#   0  sucesso
#   2  configuracao invalida / dependencia ausente
#   3  falha no pg_dump
#   4  falha na cifra (age)
#   5  falha no upload S3
#   6  falha na limpeza local (nao fatal -> apenas warn e retorna 0)

set -euo pipefail

log() {
  printf '[backup-pg] %s\n' "$*" >&2
}

log_json() {
  # Linha unica em JSON compacto para ingestao no Loki.
  # Args: key=value (sem espacos dentro do value). Escapa aspas do value.
  local status="$1"; shift
  local ts duration_ms="${DURATION_MS:-0}" size="${DUMP_SIZE:-0}"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local fields="\"ts\":\"$ts\",\"component\":\"backup-postgres\",\"env\":\"${DEPLOY_ENV:-unknown}\",\"status\":\"$status\",\"duration_ms\":$duration_ms,\"size_bytes\":$size"
  for kv in "$@"; do
    local k="${kv%%=*}" v="${kv#*=}"
    # escapa aspas literais do value
    v="${v//\"/\\\"}"
    fields="$fields,\"$k\":\"$v\""
  done
  local line="{${fields}}"
  printf '%s\n' "$line"
  if [[ -n "${BACKUP_LOG_FILE:-}" ]]; then
    mkdir -p "$(dirname "$BACKUP_LOG_FILE")" 2>/dev/null || true
    printf '%s\n' "$line" >> "$BACKUP_LOG_FILE" 2>/dev/null || true
  fi
}

die() {
  local code="$1"; shift
  log "ERRO: $*"
  log_json "failed" "exit_code=$code" "reason=$*"
  exit "$code"
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    die 2 "variavel $name nao definida (carregue config/.env antes)"
  fi
}

# ---------------------------------------------------------------------------
# 0. Config e pre-flight
# ---------------------------------------------------------------------------

require_var S3_ENDPOINT
require_var S3_BUCKET
require_var S3_KEY_ID
require_var S3_APPLICATION_KEY
require_var POSTGRES_USER
require_var POSTGRES_PASSWORD
require_var POSTGRES_DB

: "${S3_REGION:=us-west-004}"
: "${BACKUP_S3_PREFIX:=backups/postgres/}"
: "${BACKUP_LOCAL_DIR:=/srv/nfse/${DEPLOY_ENV:-prod}/backups/postgres}"
: "${BACKUP_RETENTION_LOCAL_DAYS:=3}"
: "${BACKUP_ENCRYPT:=1}"
: "${BACKUP_LOG_FILE:=/srv/nfse/${DEPLOY_ENV:-prod}/logs/backup-postgres.log}"
: "${COMPOSE_DIR:=/srv/nfse/${DEPLOY_ENV:-prod}}"
: "${COMPOSE_SERVICE:=postgres}"
: "${PG_DUMP_ARGS:=-Fc -Z 9}"

# BACKUP_S3_PREFIX precisa terminar com `/` para concatenar com daily/monthly.
if [[ "${BACKUP_S3_PREFIX}" != */ ]]; then
  BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX}/"
fi

if ! command -v aws >/dev/null 2>&1; then
  die 2 "aws CLI nao encontrada (instale: pipx install awscli)"
fi

if ! command -v docker >/dev/null 2>&1; then
  die 2 "docker nao encontrado (ver infra/vps-docker.md)"
fi

if [[ "${BACKUP_ENCRYPT}" == "1" ]]; then
  if ! command -v age >/dev/null 2>&1; then
    die 2 "age nao encontrado (apt install age) e BACKUP_ENCRYPT=1"
  fi
  if [[ -z "${BACKUP_AGE_RECIPIENT:-}" ]]; then
    die 2 "BACKUP_ENCRYPT=1 exige BACKUP_AGE_RECIPIENT (pubkey age1...)"
  fi
fi

mkdir -p "$BACKUP_LOCAL_DIR/daily" "$BACKUP_LOCAL_DIR/monthly"

# ---------------------------------------------------------------------------
# 1. Classificacao daily x monthly
# ---------------------------------------------------------------------------

DOM="$(date +%d)"
if [[ "$DOM" == "01" ]]; then
  KIND="monthly"
  STAMP="$(date +%Y-%m)"
else
  KIND="daily"
  STAMP="$(date +%Y-%m-%d)"
fi

DUMP_BASENAME="${STAMP}.dump"
DUMP_PATH="${BACKUP_LOCAL_DIR}/${KIND}/${DUMP_BASENAME}"
UPLOAD_PATH="$DUMP_PATH"
S3_BASENAME="$DUMP_BASENAME"

log "inicio env=${DEPLOY_ENV:-unknown} kind=$KIND stamp=$STAMP"

# ---------------------------------------------------------------------------
# 2. pg_dump via docker compose exec
# ---------------------------------------------------------------------------

START_NS="$(date +%s%N)"

# Nota: usamos `docker compose -f ... exec -T` para herdar o ambiente do stack
# INFRA-05. `-T` desabilita alocacao de TTY (necessario em cron). O comando
# interno lê PGPASSWORD exportado no env do container via PGPASSWORD=... .
set +e
docker compose \
  --project-directory "$COMPOSE_DIR" \
  -f "${COMPOSE_DIR}/docker-compose.base.yml" \
  exec -T \
  -e "PGPASSWORD=${POSTGRES_PASSWORD}" \
  "$COMPOSE_SERVICE" \
  pg_dump ${PG_DUMP_ARGS} -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  > "$DUMP_PATH"
PG_RC=$?
set -e

if [[ $PG_RC -ne 0 ]]; then
  rm -f "$DUMP_PATH"
  die 3 "pg_dump falhou (rc=$PG_RC)"
fi

if [[ ! -s "$DUMP_PATH" ]]; then
  rm -f "$DUMP_PATH"
  die 3 "pg_dump gerou arquivo vazio"
fi

log "pg_dump OK -> $DUMP_PATH ($(stat -c %s "$DUMP_PATH") bytes)"

# ---------------------------------------------------------------------------
# 3. Cifra com age (opcional)
# ---------------------------------------------------------------------------

if [[ "${BACKUP_ENCRYPT}" == "1" ]]; then
  ENC_PATH="${DUMP_PATH}.age"
  if ! age -r "$BACKUP_AGE_RECIPIENT" -o "$ENC_PATH" "$DUMP_PATH"; then
    rm -f "$ENC_PATH"
    die 4 "age falhou ao cifrar o dump"
  fi
  # Depois de cifrado, nao precisamos mais do plaintext local.
  rm -f "$DUMP_PATH"
  UPLOAD_PATH="$ENC_PATH"
  S3_BASENAME="${DUMP_BASENAME}.age"
  log "age OK -> $UPLOAD_PATH"
else
  log "WARN: BACKUP_ENCRYPT=0 — dump em claro (use apenas em dev)"
fi

# ---------------------------------------------------------------------------
# 4. Upload para S3
# ---------------------------------------------------------------------------

DUMP_SIZE="$(stat -c %s "$UPLOAD_PATH")"

# SHA-256 para auditoria (vai pro log JSON, nao pro metadata S3 — B2 nao
# suporta metadata arbitrario de forma confiavel via signature V4).
if command -v sha256sum >/dev/null 2>&1; then
  DUMP_SHA256="$(sha256sum "$UPLOAD_PATH" | awk '{print $1}')"
else
  DUMP_SHA256="unavailable"
fi

export AWS_ACCESS_KEY_ID="$S3_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$S3_APPLICATION_KEY"
export AWS_DEFAULT_REGION="$S3_REGION"

S3_KEY="${BACKUP_S3_PREFIX}${KIND}/${S3_BASENAME}"

if ! aws --endpoint-url "$S3_ENDPOINT" s3 cp \
      "$UPLOAD_PATH" "s3://${S3_BUCKET}/${S3_KEY}" \
      --only-show-errors; then
  die 5 "falha no upload S3 s3://${S3_BUCKET}/${S3_KEY}"
fi

log "upload OK -> s3://${S3_BUCKET}/${S3_KEY}"

# ---------------------------------------------------------------------------
# 5. Retencao local
# ---------------------------------------------------------------------------

if ! find "$BACKUP_LOCAL_DIR" -type f \
      \( -name '*.dump' -o -name '*.dump.age' \) \
      -mtime "+${BACKUP_RETENTION_LOCAL_DAYS}" -print -delete > /tmp/backup-pg-cleanup.$$ 2>&1; then
  log "WARN: limpeza local reportou erros (veja /tmp/backup-pg-cleanup.$$)"
else
  rm -f /tmp/backup-pg-cleanup.$$ || true
fi

# ---------------------------------------------------------------------------
# 6. Log final
# ---------------------------------------------------------------------------

END_NS="$(date +%s%N)"
DURATION_MS=$(( (END_NS - START_NS) / 1000000 ))

log_json "ok" \
  "kind=$KIND" \
  "s3_key=$S3_KEY" \
  "sha256=$DUMP_SHA256" \
  "encrypted=${BACKUP_ENCRYPT}"

log "PASS duration_ms=$DURATION_MS size_bytes=$DUMP_SIZE"
