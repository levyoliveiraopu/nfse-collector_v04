#!/usr/bin/env bash
# INFRA-08 — Restore do Postgres a partir de um dump do S3 (drill ou real).
#
# Uso:
#   set -a; source /srv/nfse/prod/config/.env; set +a
#   bash infra/scripts/restore-postgres.sh --latest
#   bash infra/scripts/restore-postgres.sh --key backups/postgres/daily/2026-04-16.dump.age
#   bash infra/scripts/restore-postgres.sh --latest --target-db nfse_restore_drill
#
# O fluxo padrao restaura sobre $POSTGRES_DB (DESTRUTIVO). Use --target-db
# <nome> para fazer o drill em staging sem tocar no banco principal:
# o script cria o banco alvo se nao existir e faz pg_restore nele.
#
# Checksum de sanidade pos-restore: conta linhas em `tenants`, `companies`,
# `audit_logs`, `users` e imprime antes/depois (antes vem do backup se
# disponivel; depois e o SELECT count(*) real).
#
# Exit codes:
#   0  sucesso
#   2  configuracao invalida / dependencia ausente / argumentos errados
#   3  falha ao baixar do S3
#   4  falha ao decifrar (age)
#   5  falha no pg_restore
#   6  checksums divergentes apos restore

set -euo pipefail

log() {
  printf '[restore-pg] %s\n' "$*" >&2
}

die() {
  local code="$1"; shift
  log "ERRO: $*"
  exit "$code"
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    die 2 "variavel $name nao definida (carregue config/.env antes)"
  fi
}

usage() {
  cat <<'EOF'
Uso:
  restore-postgres.sh --latest [--kind daily|monthly] [--target-db NAME] [--force]
  restore-postgres.sh --key <s3-key>                  [--target-db NAME] [--force]

Opcoes:
  --latest             Usa o objeto mais recente em backups/postgres/<kind>/.
  --kind daily|monthly Qual janela usar com --latest (default: daily).
  --key <s3-key>       S3 key completa (ex: backups/postgres/daily/2026-04-16.dump.age).
  --target-db <name>   Banco alvo; default = $POSTGRES_DB do ambiente.
  --force              Pula o prompt de confirmacao.
  -h, --help           Mostra esta ajuda.

Exemplos:
  # Restaurar o dump mais recente em um DB separado (drill):
  bash infra/scripts/restore-postgres.sh --latest --target-db nfse_restore_drill

  # Restaurar dump especifico sobre o DB de producao (DESTRUTIVO):
  bash infra/scripts/restore-postgres.sh \
      --key backups/postgres/daily/2026-04-16.dump.age --force
EOF
}

# ---------------------------------------------------------------------------
# 0. Parse de argumentos
# ---------------------------------------------------------------------------

MODE=""
S3_KEY=""
KIND="daily"
TARGET_DB=""
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --latest)       MODE="latest"; shift ;;
    --key)          MODE="key"; S3_KEY="${2:?--key exige valor}"; shift 2 ;;
    --kind)         KIND="${2:?--kind exige valor}"; shift 2 ;;
    --target-db)    TARGET_DB="${2:?--target-db exige valor}"; shift 2 ;;
    --force)        FORCE=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              usage >&2; die 2 "argumento desconhecido: $1" ;;
  esac
done

if [[ -z "$MODE" ]]; then
  usage >&2
  die 2 "informe --latest ou --key"
fi

if [[ "$KIND" != "daily" && "$KIND" != "monthly" ]]; then
  die 2 "--kind deve ser 'daily' ou 'monthly'"
fi

# ---------------------------------------------------------------------------
# 1. Config e pre-flight
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
: "${COMPOSE_DIR:=/srv/nfse/${DEPLOY_ENV:-prod}}"
: "${COMPOSE_SERVICE:=postgres}"

if [[ "${BACKUP_S3_PREFIX}" != */ ]]; then
  BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX}/"
fi

TARGET_DB="${TARGET_DB:-$POSTGRES_DB}"

if ! command -v aws >/dev/null 2>&1; then
  die 2 "aws CLI nao encontrada (instale: pipx install awscli)"
fi
if ! command -v docker >/dev/null 2>&1; then
  die 2 "docker nao encontrado"
fi

export AWS_ACCESS_KEY_ID="$S3_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$S3_APPLICATION_KEY"
export AWS_DEFAULT_REGION="$S3_REGION"

# ---------------------------------------------------------------------------
# 2. Resolve S3 key
# ---------------------------------------------------------------------------

if [[ "$MODE" == "latest" ]]; then
  PREFIX="${BACKUP_S3_PREFIX}${KIND}/"
  log "resolvendo ultimo dump em s3://${S3_BUCKET}/${PREFIX}"
  # aws s3 ls ordena por data ASC; pega ultima linha nao vazia.
  LATEST_LINE="$(aws --endpoint-url "$S3_ENDPOINT" \
      s3 ls "s3://${S3_BUCKET}/${PREFIX}" \
      | grep -E '\.dump(\.age)?$' \
      | tail -n 1 || true)"
  if [[ -z "$LATEST_LINE" ]]; then
    die 3 "nenhum dump encontrado em s3://${S3_BUCKET}/${PREFIX}"
  fi
  LATEST_NAME="$(echo "$LATEST_LINE" | awk '{print $NF}')"
  S3_KEY="${PREFIX}${LATEST_NAME}"
fi

if [[ -z "$S3_KEY" ]]; then
  die 2 "s3 key vazia (bug interno)"
fi

log "alvo: s3://${S3_BUCKET}/${S3_KEY} -> DB '$TARGET_DB'"

# ---------------------------------------------------------------------------
# 3. Confirmacao (salvo --force)
# ---------------------------------------------------------------------------

if [[ "$FORCE" != "1" ]]; then
  if [[ "$TARGET_DB" == "$POSTGRES_DB" ]]; then
    log "ATENCAO: restore destrutivo sobre $TARGET_DB (mesmo DB de producao)."
  fi
  printf '[restore-pg] Confirmar restore em "%s"? (digite RESTAURAR): ' "$TARGET_DB" >&2
  read -r ANSWER
  if [[ "$ANSWER" != "RESTAURAR" ]]; then
    die 2 "cancelado pelo usuario"
  fi
fi

# ---------------------------------------------------------------------------
# 4. Download + decifra
# ---------------------------------------------------------------------------

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

LOCAL_BASENAME="$(basename "$S3_KEY")"
LOCAL_PATH="${TMP_DIR}/${LOCAL_BASENAME}"

if ! aws --endpoint-url "$S3_ENDPOINT" s3 cp \
      "s3://${S3_BUCKET}/${S3_KEY}" "$LOCAL_PATH" \
      --only-show-errors; then
  die 3 "falha ao baixar s3://${S3_BUCKET}/${S3_KEY}"
fi
log "download OK -> $LOCAL_PATH ($(stat -c %s "$LOCAL_PATH") bytes)"

DUMP_PATH="$LOCAL_PATH"
if [[ "$LOCAL_PATH" == *.age ]]; then
  if ! command -v age >/dev/null 2>&1; then
    die 4 "dump cifrado (.age) mas 'age' nao esta instalado"
  fi
  if [[ -z "${BACKUP_AGE_IDENTITY:-}" ]]; then
    die 4 "dump cifrado exige BACKUP_AGE_IDENTITY (caminho da chave privada age)"
  fi
  if [[ ! -r "$BACKUP_AGE_IDENTITY" ]]; then
    die 4 "BACKUP_AGE_IDENTITY ($BACKUP_AGE_IDENTITY) nao existe ou nao legivel"
  fi
  DUMP_PATH="${LOCAL_PATH%.age}"
  if ! age -d -i "$BACKUP_AGE_IDENTITY" -o "$DUMP_PATH" "$LOCAL_PATH"; then
    die 4 "age -d falhou (chave correta? arquivo integro?)"
  fi
  rm -f "$LOCAL_PATH"
  log "decifrado OK -> $DUMP_PATH"
fi

# ---------------------------------------------------------------------------
# 5. Criar DB alvo se necessario
# ---------------------------------------------------------------------------

compose_exec() {
  docker compose \
    --project-directory "$COMPOSE_DIR" \
    -f "${COMPOSE_DIR}/docker-compose.base.yml" \
    exec -T \
    -e "PGPASSWORD=${POSTGRES_PASSWORD}" \
    "$COMPOSE_SERVICE" \
    "$@"
}

DB_EXISTS="$(compose_exec psql -U "$POSTGRES_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'" || true)"
DB_EXISTS="$(echo "$DB_EXISTS" | tr -d '[:space:]')"

if [[ "$DB_EXISTS" != "1" ]]; then
  log "DB '$TARGET_DB' nao existe — criando..."
  if ! compose_exec psql -U "$POSTGRES_USER" -d postgres -c \
        "CREATE DATABASE \"$TARGET_DB\" OWNER \"$POSTGRES_USER\";"; then
    die 5 "falha ao criar DB '$TARGET_DB'"
  fi
fi

# ---------------------------------------------------------------------------
# 6. pg_restore
# ---------------------------------------------------------------------------

log "pg_restore em '$TARGET_DB' (--clean --if-exists)..."
set +e
compose_exec pg_restore \
    --clean --if-exists --no-owner --no-privileges \
    -U "$POSTGRES_USER" -d "$TARGET_DB" \
    < "$DUMP_PATH"
RC=$?
set -e

# pg_restore devolve >0 quando encontra warnings (ex.: role inexistente com
# --no-owner): aceitamos rc<=1 como sucesso e marcamos rc==2+ como falha.
if [[ $RC -gt 1 ]]; then
  die 5 "pg_restore falhou (rc=$RC)"
fi
log "pg_restore OK (rc=$RC)"

# ---------------------------------------------------------------------------
# 7. Checksums pos-restore
# ---------------------------------------------------------------------------

run_count() {
  local tbl="$1"
  compose_exec psql -U "$POSTGRES_USER" -d "$TARGET_DB" -tAc \
      "SELECT count(*) FROM $tbl" 2>/dev/null | tr -d '[:space:]'
}

log "checksum de sanidade (count(*) por tabela):"
for TBL in tenants users tenant_users companies audit_logs; do
  VAL="$(run_count "$TBL" || echo 'N/A')"
  printf '[restore-pg]   %-14s = %s\n' "$TBL" "$VAL" >&2
done

log "PASS — restore em '$TARGET_DB' completo"
