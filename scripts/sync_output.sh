#!/bin/bash

set -euo pipefail

# ============================================================
# Sincroniza a saída da coleta para um destino externo.
# Estrutura preparada para novos alvos (ex.: drive-api, s3).
#
# Uso:
#   scripts/sync_output.sh --target local-remote --dest usuario@host:/backup/nfse-collector
#   scripts/sync_output.sh --target local-remote --source output --dest /mnt/backup/nfse/output
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

TARGET="local-remote"
SOURCE_DIR="output"
DEST_PATH=""
RSYNC_OPTS="-avz --delete"

usage() {
    cat <<USAGE
Uso: $(basename "$0") [opções]

Opções:
  --target <alvo>      Alvo de sincronização (padrão: local-remote)
  --source <diretório> Diretório de origem relativo ao projeto (padrão: output)
  --dest <destino>     Destino da sincronização (obrigatório para local-remote)
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

mkdir -p logs
LOG_FILE="logs/sync_$(date +%Y-%m).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

SOURCE_PATH="$PROJECT_ROOT/$SOURCE_DIR"
if [[ ! -d "$SOURCE_PATH" ]]; then
    log "[ERRO] Diretório de origem não encontrado: $SOURCE_PATH"
    exit 1
fi

log "=== Início da sincronização (target=$TARGET) ==="
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
