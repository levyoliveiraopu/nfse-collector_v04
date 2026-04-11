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

# 5. Google credentials
if [ -f "config/google_credentials.json" ]; then
    echo "✅ Google credentials encontrado"
else
    echo "❌ config/google_credentials.json não encontrado — ver SETUP.md seção 4"
    ERROS=$((ERROS+1))
fi

# 6. Pasta de certificados
QTD_PFX=$(find config/certificados -name "*.pfx" 2>/dev/null | wc -l)
if [ "$QTD_PFX" -gt 0 ]; then
    echo "✅ $QTD_PFX certificado(s) .pfx encontrado(s)"
else
    echo "❌ Nenhum .pfx em config/certificados/ — copie os certificados dos clientes"
    ERROS=$((ERROS+1))
fi

# 7. clientes.csv
LINHAS=$(tail -n +2 config/clientes.csv 2>/dev/null | wc -l)
if [ "$LINHAS" -gt 0 ]; then
    echo "✅ clientes.csv com $LINHAS cliente(s)"
else
    echo "❌ clientes.csv vazio ou não encontrado"
    ERROS=$((ERROS+1))
fi

# 8. Variáveis obrigatórias no .env
for VAR in GOOGLE_CREDENTIALS_JSON GOOGLE_DRIVE_FOLDER_ROOT_ID; do
    if grep -q "^${VAR}=" config/.env 2>/dev/null; then
        VALOR=$(grep "^${VAR}=" config/.env | cut -d= -f2)
        if [ -n "$VALOR" ] && [ "$VALOR" != "cole_aqui_o_id_da_pasta_raiz" ]; then
            echo "✅ Variável $VAR configurada"
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
