#!/bin/bash

# ============================================================
# Para agendar no cron, execute: crontab -e
# Cole a linha abaixo (ajuste o caminho):
# 0 8 5 * * /caminho/absoluto/nfse-collector/scripts/executar_mensal.sh
# ============================================================

# Ir para o diretório do projeto
cd "$(dirname "$0")/.."

# Garantir que a pasta de logs exista
mkdir -p logs

# Calcular mês anterior automaticamente
ANO=$(date -d "$(date +%Y-%m-01) -1 month" +%Y)
MES=$(date -d "$(date +%Y-%m-01) -1 month" +%m)

# Arquivo de log
LOG_FILE="logs/cron_${ANO}-${MES}.log"

echo "=== Iniciando execução mensal: ${ANO}-${MES} ===" >> "$LOG_FILE" 2>&1
echo "Data/hora: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE" 2>&1

# Executar
venv/bin/python main.py --ano "$ANO" --mes "$MES" >> "$LOG_FILE" 2>&1

echo "=== Execução finalizada: $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE" 2>&1
