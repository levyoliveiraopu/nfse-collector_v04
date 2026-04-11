#!/bin/bash

cd "$(dirname "$0")/.."
ERROS=0

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

# 3. Dependências
if venv/bin/pip show requests &>/dev/null; then
    echo "✅ Dependências Python instaladas"
else
    echo "❌ Dependências não instaladas — execute: venv/bin/pip install -r requirements.txt"
    ERROS=$((ERROS+1))
fi

# 4. Arquivo .env
if [ -f "config/.env" ]; then
    echo "✅ Arquivo config/.env encontrado"
else
    echo "❌ config/.env não encontrado — execute: cp config/.env.example config/.env"
    ERROS=$((ERROS+1))
fi

# Extrai GOOGLE_CREDENTIALS_JSON do .env
GOOGLE_CREDENTIALS_JSON=""
if [ -f "config/.env" ]; then
    LINHA_CREDENTIALS=$(grep "^GOOGLE_CREDENTIALS_JSON=" config/.env 2>/dev/null | tail -n 1)
    if [ -n "$LINHA_CREDENTIALS" ]; then
        GOOGLE_CREDENTIALS_JSON="${LINHA_CREDENTIALS#GOOGLE_CREDENTIALS_JSON=}"
        GOOGLE_CREDENTIALS_JSON="${GOOGLE_CREDENTIALS_JSON%\"}"
        GOOGLE_CREDENTIALS_JSON="${GOOGLE_CREDENTIALS_JSON#\"}"
    fi
fi

# 5. Google credentials
if [ -z "$GOOGLE_CREDENTIALS_JSON" ]; then
    echo "❌ Variável GOOGLE_CREDENTIALS_JSON está vazia no config/.env"
    ERROS=$((ERROS+1))
elif [ -f "$GOOGLE_CREDENTIALS_JSON" ]; then
    echo "✅ Google credentials encontrado em: $GOOGLE_CREDENTIALS_JSON"
else
    echo "❌ Arquivo Google credentials não encontrado no caminho informado em GOOGLE_CREDENTIALS_JSON: $GOOGLE_CREDENTIALS_JSON — ver SETUP.md seção 4"
    ERROS=$((ERROS+1))
fi

# 6. Pasta de certificados (informativo)
QTD_PFX=$(find config/certificados -name "*.pfx" 2>/dev/null | wc -l)
if [ "$QTD_PFX" -gt 0 ]; then
    echo "ℹ️  $QTD_PFX certificado(s) .pfx encontrado(s) em config/certificados/"
else
    echo "ℹ️  Nenhum .pfx em config/certificados/ (checagem apenas informativa)"
fi

# 7. clientes.csv e caminhos de certificado
if [ -f "config/clientes.csv" ]; then
    TOTAL_CLIENTES=0
    CERT_VALIDOS=0
    INVALIDOS=()

    while IFS=, read -r CNPJ RAZAO CERT_PATH CERT_PASSWORD; do
        # Ignora linhas vazias
        if [ -z "$CNPJ" ] && [ -z "$CERT_PATH" ]; then
            continue
        fi

        TOTAL_CLIENTES=$((TOTAL_CLIENTES+1))
        CNPJ_CLEAN=$(echo "$CNPJ" | tr -d '\r')
        CERT_PATH_CLEAN=$(echo "$CERT_PATH" | tr -d '\r')

        if [ -n "$CERT_PATH_CLEAN" ] && [ -f "$CERT_PATH_CLEAN" ]; then
            CERT_VALIDOS=$((CERT_VALIDOS+1))
        else
            INVALIDOS+=("$CNPJ_CLEAN")
        fi
    done < <(tail -n +2 config/clientes.csv)

    if [ "$TOTAL_CLIENTES" -gt 0 ]; then
        echo "✅ clientes.csv com $TOTAL_CLIENTES cliente(s)"
        echo "✅ Certificados válidos: $CERT_VALIDOS/$TOTAL_CLIENTES"

        if [ "${#INVALIDOS[@]}" -gt 0 ]; then
            echo "❌ CNPJ(s) com cert_path inválido:"
            for CNPJ_INVALIDO in "${INVALIDOS[@]}"; do
                echo "   - $CNPJ_INVALIDO"
            done
            ERROS=$((ERROS+1))
        fi
    else
        echo "❌ clientes.csv vazio (sem linhas de cliente)"
        ERROS=$((ERROS+1))
    fi
else
    echo "❌ config/clientes.csv não encontrado"
    ERROS=$((ERROS+1))
fi

# 8. Variáveis obrigatórias no .env
for VAR in GOOGLE_DRIVE_FOLDER_ROOT_ID; do
    if grep -q "^${VAR}=" config/.env 2>/dev/null; then
        VALOR=$(grep "^${VAR}=" config/.env | cut -d= -f2)
        if [ -n "$VALOR" ] && [ "$VALOR" != "cole_aqui_o_id_da_pasta_raiz" ]; then
            echo "✅ Variável $VAR configurada"

            if [ "$VAR" = "NSU_ESTADO_PATH" ]; then
                DIRETORIO_PAI=$(dirname "$VALOR")
                if [ ! -d "$DIRETORIO_PAI" ]; then
                    echo "⚠️  Diretório pai de NSU_ESTADO_PATH não existe: $DIRETORIO_PAI"
                    echo "   Crie com: mkdir -p \"$DIRETORIO_PAI\""
                fi
            fi
        else
            echo "❌ Variável $VAR está vazia ou com valor padrão no .env"
            ERROS=$((ERROS+1))
        fi
    else
        echo "❌ Variável $VAR não encontrada no .env"
        ERROS=$((ERROS+1))
    fi
done

# 9. Arquivo de estado
if [ -f "config/estado/ultimo_nsu.json" ]; then
    echo "✅ Arquivo de estado NSU encontrado"
else
    echo "⚠️  config/estado/ultimo_nsu.json não existe — será criado na primeira execução"
fi

# Resultado final
echo ""
if [ "$ERROS" -eq 0 ]; then
    echo "✅ SETUP OK — pronto para executar: python main.py --dry-run"
else
    echo "❌ $ERROS problema(s) encontrado(s). Corrija antes de executar."
fi
