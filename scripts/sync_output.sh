#!/bin/bash

set -euo pipefail

# ============================================================
# Sincroniza a saída da coleta para um destino externo.
# Estrutura preparada para novos alvos (ex.: drive-api, s3).
#
# Uso:
#   scripts/sync_output.sh --target local-remote --dest usuario@host:/backup/nfse-collector
#   scripts/sync_output.sh --target local-remote --dest /mnt/backup/nfse/output
#   scripts/sync_output.sh --target local-remote --source output --dest /mnt/backup/nfse/output
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

TARGET="local-remote"
SOURCE_DIR="${LOCAL_OUTPUT_DIR:-}"
DEST_PATH=""
RSYNC_OPTS="-avz --delete"
ENV_FILE=""

usage() {
    cat <<USAGE
Uso: $(basename "$0") [opções]

Opções:
  --target <alvo>      Alvo de sincronização (padrão: local-remote)
  --source <diretório> Diretório de origem (sobrescreve LOCAL_OUTPUT_DIR do .env)
  --dest <destino>     Destino da sincronização (obrigatório para local-remote)
  --env-file <arquivo> Arquivo .env para ler LOCAL_OUTPUT_DIR (padrão: config/.env)
  --rsync-opts "..."   Opções extras do rsync (padrão: -avz --delete)
  -h, --help           Exibe esta ajuda
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --source)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --dest)
            DEST_PATH="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --rsync-opts)
            RSYNC_OPTS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERRO] Parâmetro inválido: $1"
            usage
            exit 1
            ;;
    esac
done

resolve_default_source_dir() {
    local env_file_path="$1"

    if [[ -n "$SOURCE_DIR" ]]; then
        return 0
    fi

    if [[ -f "$env_file_path" ]]; then
        local env_value
        env_value="$(sed -nE 's/^[[:space:]]*LOCAL_OUTPUT_DIR[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$/\1/p' "$env_file_path" | tail -n1)"
        env_value="${env_value%\"}"
        env_value="${env_value#\"}"
        env_value="${env_value%\'}"
        env_value="${env_value#\'}"

        if [[ -n "$env_value" ]]; then
            SOURCE_DIR="$env_value"
            return 0
        fi
    fi

    SOURCE_DIR="/var/lib/nfse-collector/output"
}

if [[ -z "$ENV_FILE" ]]; then
    if [[ -f "$PROJECT_ROOT/config/.env" ]]; then
        ENV_FILE="$PROJECT_ROOT/config/.env"
    else
        ENV_FILE="$PROJECT_ROOT/config/.env.example"
    fi
elif [[ "$ENV_FILE" != /* ]]; then
    ENV_FILE="$PROJECT_ROOT/$ENV_FILE"
fi

resolve_default_source_dir "$ENV_FILE"

mkdir -p logs
LOG_FILE="logs/sync_$(date +%Y-%m).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if [[ "$SOURCE_DIR" = /* ]]; then
    SOURCE_PATH="$SOURCE_DIR"
else
    SOURCE_PATH="$PROJECT_ROOT/$SOURCE_DIR"
fi
if [[ ! -d "$SOURCE_PATH" ]]; then
    log "[ERRO] Diretório de origem não encontrado: $SOURCE_PATH"
    exit 1
fi

log "=== Início da sincronização (target=$TARGET) ==="
log "Env carregado para defaults: $ENV_FILE"
log "Origem: $SOURCE_PATH"

case "$TARGET" in
    local-remote)
        if [[ -z "$DEST_PATH" ]]; then
            log "[ERRO] Informe --dest para o target local-remote"
            exit 1
        fi

        log "Destino: $DEST_PATH"
        log "Comando: rsync $RSYNC_OPTS $SOURCE_PATH/ $DEST_PATH/"
        # shellcheck disable=SC2086
        rsync $RSYNC_OPTS "$SOURCE_PATH/" "$DEST_PATH/" >> "$LOG_FILE" 2>&1
        ;;

    drive-api|s3)
        log "[ERRO] Target '$TARGET' ainda não implementado."
        log "        Use local-remote por enquanto."
        exit 2
        ;;

    *)
        log "[ERRO] Target desconhecido: $TARGET"
        log "        Targets suportados: local-remote (ativo), drive-api, s3 (futuro)."
        exit 1
        ;;
esac

log "=== Sincronização concluída com sucesso ==="
