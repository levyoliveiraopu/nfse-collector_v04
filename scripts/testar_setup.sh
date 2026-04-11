#!/bin/bash

cd "$(dirname "$0")/.."
ERROS=0
STORAGE_BACKEND="local"
BACKEND_NOME_EXIBICAO="local"

obter_valor_env() {
    local chave="$1"
    local linha
    linha=$(grep "^${chave}=" config/.env 2>/dev/null | tail -n 1)
    if [ -z "$linha" ]; then
        return 1
    fi

    local valor="${linha#*=}"
    valor="${valor%\"}"
    valor="${valor#\"}"
    echo "$valor"
}

echo "=== Testando configuração do nfse-collector ==="
echo ""

# 1. Python
if python3.11 --version &>/dev/null; then
    echo "✅ Python 3.11 instalado"
else
    echo "❌ Python 3.11 não encontrado — execute: sudo apt install python3.11"
    ERROS=$((ERROS+1))
fi

# 2. Virtualenv
if [ -d "venv" ]; then
    echo "✅ Virtualenv encontrado"
else
    echo "❌ Virtualenv não encontrado — execute: bash scripts/instalar.sh"
    ERROS=$((ERROS+1))
fi

# 3. Ambiente Python (interpretador + imports críticos)
if [ -x "venv/bin/python" ]; then
    echo "✅ venv/bin/python encontrado"

    if venv/bin/python -c "import requests, dotenv, openpyxl, cryptography, tenacity, googleapiclient, tqdm" &>/dev/null; then
        echo "✅ Dependências críticas Python importadas com sucesso"
    else
        echo "❌ Falha ao importar dependências críticas — execute: venv/bin/pip install -r requirements.txt"
        ERROS=$((ERROS+1))
    fi
else
    echo "❌ venv/bin/python não encontrado — execute: bash scripts/instalar.sh"
    ERROS=$((ERROS+1))
fi

# 4. Arquivo .env
if [ -f "config/.env" ]; then
    echo "✅ Arquivo config/.env encontrado"

    STORAGE_BACKEND_RAW=$(obter_valor_env "STORAGE_BACKEND")
    STORAGE_BACKEND_NORMALIZADO=$(echo "$STORAGE_BACKEND_RAW" | tr '[:upper:]' '[:lower:]')
    case "$STORAGE_BACKEND_NORMALIZADO" in
        ""|"local")
            STORAGE_BACKEND="local"
            BACKEND_NOME_EXIBICAO="local"
            ;;
        "noop")
            STORAGE_BACKEND="local"
            BACKEND_NOME_EXIBICAO="local (compat noop)"
            ;;
        "gdrive")
            STORAGE_BACKEND="gdrive"
            BACKEND_NOME_EXIBICAO="gdrive"
            ;;
        *)
            echo "❌ STORAGE_BACKEND inválido no config/.env: '$STORAGE_BACKEND_RAW' (use local, gdrive ou noop)"
            ERROS=$((ERROS+1))
            STORAGE_BACKEND="local"
            BACKEND_NOME_EXIBICAO="local"
            ;;
    esac

    echo "✅ STORAGE_BACKEND detectado: $BACKEND_NOME_EXIBICAO"
else
    echo "❌ config/.env não encontrado — execute: cp config/.env.example config/.env"
    ERROS=$((ERROS+1))
fi

# Extrai GOOGLE_CREDENTIALS_JSON do .env
GOOGLE_CREDENTIALS_JSON=""
if [ -f "config/.env" ]; then
    GOOGLE_CREDENTIALS_JSON=$(obter_valor_env "GOOGLE_CREDENTIALS_JSON")
fi

# 5. Backend local/gdrive
LOCAL_OUTPUT_DIR=""
NSU_ESTADO_PATH=""
if [ -f "config/.env" ]; then
    LOCAL_OUTPUT_DIR=$(obter_valor_env "LOCAL_OUTPUT_DIR")
    NSU_ESTADO_PATH=$(obter_valor_env "NSU_ESTADO_PATH")
fi

if [ -z "$LOCAL_OUTPUT_DIR" ]; then
    echo "❌ Variável LOCAL_OUTPUT_DIR está vazia ou ausente no config/.env"
    ERROS=$((ERROS+1))
else
    echo "✅ Variável LOCAL_OUTPUT_DIR configurada"
    if [ -d "$LOCAL_OUTPUT_DIR" ]; then
        echo "✅ Diretório LOCAL_OUTPUT_DIR existe: $LOCAL_OUTPUT_DIR"
    else
        echo "⚠️  Diretório LOCAL_OUTPUT_DIR não existe: $LOCAL_OUTPUT_DIR (será criado na execução)"
    fi
fi

if [ -z "$NSU_ESTADO_PATH" ]; then
    echo "❌ Variável NSU_ESTADO_PATH está vazia ou ausente no config/.env"
    ERROS=$((ERROS+1))
else
    echo "✅ Variável NSU_ESTADO_PATH configurada"
    DIRETORIO_PAI_NSU=$(dirname "$NSU_ESTADO_PATH")
    if [ ! -d "$DIRETORIO_PAI_NSU" ]; then
        echo "⚠️  Diretório pai de NSU_ESTADO_PATH não existe: $DIRETORIO_PAI_NSU"
        echo "   Crie com: mkdir -p \"$DIRETORIO_PAI_NSU\""
    fi
fi

if [ "$STORAGE_BACKEND" = "gdrive" ]; then
    if [ -z "$GOOGLE_CREDENTIALS_JSON" ]; then
        echo "❌ Variável GOOGLE_CREDENTIALS_JSON está vazia no config/.env"
        ERROS=$((ERROS+1))
    elif [ -f "$GOOGLE_CREDENTIALS_JSON" ]; then
        echo "✅ Google credentials encontrado em: $GOOGLE_CREDENTIALS_JSON"
    else
        echo "❌ Arquivo Google credentials não encontrado no caminho informado em GOOGLE_CREDENTIALS_JSON: $GOOGLE_CREDENTIALS_JSON — ver SETUP.md seção 4"
        ERROS=$((ERROS+1))
    fi

    GOOGLE_DRIVE_FOLDER_ROOT_ID=$(obter_valor_env "GOOGLE_DRIVE_FOLDER_ROOT_ID")
    if [ -n "$GOOGLE_DRIVE_FOLDER_ROOT_ID" ] && [ "$GOOGLE_DRIVE_FOLDER_ROOT_ID" != "cole_aqui_o_id_da_pasta_raiz" ]; then
        echo "✅ Variável GOOGLE_DRIVE_FOLDER_ROOT_ID configurada"
    else
        echo "❌ Variável GOOGLE_DRIVE_FOLDER_ROOT_ID está vazia ou com valor padrão no .env"
        ERROS=$((ERROS+1))
    fi
else
    echo "ℹ️  Backend local: validações de Google Drive ignoradas"
fi

# 6. Pasta de certificados (informativo)
QTD_PFX=$(find config/certificados -name "*.pfx" 2>/dev/null | wc -l)
if [ "$QTD_PFX" -gt 0 ]; then
    echo "ℹ️  $QTD_PFX certificado(s) .pfx encontrado(s) em config/certificados/"
else
    echo "ℹ️  Nenhum .pfx em config/certificados/ (checagem apenas informativa)"
fi

# 7. clientes.csv
if [ -f "config/clientes.csv" ]; then
    HEADER=$(head -n 1 config/clientes.csv)
    CAMPOS_OBRIGATORIOS=("cnpj" "razao_social" "cert_path" "cert_password")
    HEADER_OK=1

    for CAMPO in "${CAMPOS_OBRIGATORIOS[@]}"; do
        if [[ ",$HEADER," != *",$CAMPO,"* ]]; then
            HEADER_OK=0
            break
        fi
    done

    if [ "$HEADER_OK" -eq 1 ]; then
        echo "✅ Cabeçalho de clientes.csv contém os campos obrigatórios"
    else
        echo "❌ Cabeçalho inválido em clientes.csv. Esperado conter: cnpj,razao_social,cert_path,cert_password"
        ERROS=$((ERROS+1))
    fi

    LINHAS=$(tail -n +2 config/clientes.csv | wc -l)
    if [ "$LINHAS" -gt 0 ]; then
        echo "✅ clientes.csv com $LINHAS cliente(s)"
    else
        echo "❌ clientes.csv sem linhas de cliente"
        ERROS=$((ERROS+1))
    fi

    CNPJ_INVALIDOS=$(awk -F',' '
        NR == 1 { next }
        {
            cnpj = $1
            gsub(/^ +| +$/, "", cnpj)
            if (cnpj == "" || cnpj !~ /^[0-9]{14}$/) {
                print NR
            }
        }
    ' config/clientes.csv)

    if [ -n "$CNPJ_INVALIDOS" ]; then
        echo "❌ Linhas inválidas em clientes.csv (cnpj vazio ou fora do padrão de 14 dígitos):"
        while IFS= read -r LINHA; do
            echo "   - linha $LINHA"
            ERROS=$((ERROS+1))
        done <<< "$CNPJ_INVALIDOS"
    else
        echo "✅ Todos os CNPJs de clientes.csv estão preenchidos e com 14 dígitos"
    fi
else
    echo "❌ clientes.csv não encontrado"
    ERROS=$((ERROS+1))
fi

# 8. Arquivo de estado
if [ -f "config/estado/ultimo_nsu.json" ]; then
    echo "✅ Arquivo de estado NSU encontrado"
else
    echo "⚠️  config/estado/ultimo_nsu.json não existe — será criado na primeira execução"
fi

# 9. Scripts operacionais (coleta + sincronização)
if [ -x "scripts/executar_mensal.sh" ]; then
    echo "✅ Script de coleta mensal encontrado: scripts/executar_mensal.sh"
else
    echo "❌ Script de coleta mensal ausente ou sem permissão de execução: scripts/executar_mensal.sh"
    ERROS=$((ERROS+1))
fi

if [ -x "scripts/sync_output.sh" ]; then
    echo "✅ Script de sincronização encontrado: scripts/sync_output.sh"
else
    echo "❌ Script de sincronização ausente ou sem permissão de execução: scripts/sync_output.sh"
    ERROS=$((ERROS+1))
fi

# 10. Dependência do target local-remote (rsync)
if command -v rsync >/dev/null 2>&1; then
    echo "✅ rsync disponível para sincronização local-remote"
else
    echo "⚠️  rsync não encontrado. A coleta funciona, mas o target local-remote do sync falhará."
    echo "   Instale com: sudo apt install rsync"
fi

# Resultado final
echo ""
if [ "$ERROS" -eq 0 ]; then
    if [ "$STORAGE_BACKEND" = "gdrive" ]; then
        echo "✅ setup ok para backend gdrive — pronto para executar: python main.py --dry-run"
    else
        echo "✅ setup ok para backend local — pronto para executar: python main.py --dry-run"
    fi
else
    echo "❌ $ERROS problema(s) encontrado(s). Corrija antes de executar."
fi
