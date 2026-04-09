#!/bin/bash

cd "$(dirname "$0")/.."
DATA=$(date +%Y-%m-%d)
BACKUP_DIR="$HOME/backups/nfse-collector"
mkdir -p "$BACKUP_DIR"

echo "=== Backup nfse-collector — $DATA ==="

# Backup dos certificados
tar -czf "$BACKUP_DIR/certs_${DATA}.tar.gz" config/certificados/
echo "✅ Certificados: $BACKUP_DIR/certs_${DATA}.tar.gz"

# Backup do estado NSU + .env + clientes.csv
tar -czf "$BACKUP_DIR/estado_${DATA}.tar.gz" \
    config/estado/ \
    config/.env \
    config/clientes.csv \
    config/google_credentials.json 2>/dev/null
echo "✅ Estado/config: $BACKUP_DIR/estado_${DATA}.tar.gz"

echo ""
echo "Para restaurar os certificados:"
echo "  tar -xzf $BACKUP_DIR/certs_${DATA}.tar.gz -C /"
echo ""
echo "Recomendação: execute este script após cada processamento mensal."
