#!/bin/bash
set -e

echo "=== Instalando nfse-collector ==="

# Verificar Ubuntu
if ! lsb_release -a 2>/dev/null | grep -q "Ubuntu"; then
    echo "⚠️  Este script foi testado no Ubuntu 22.04"
fi

# Instalar dependências do sistema
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip

# Criar virtualenv
python3.11 -m venv venv
echo "✅ Virtualenv criado"

# Instalar dependências Python
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
echo "✅ Dependências Python instaladas"

# Criar pastas necessárias
mkdir -p logs config/estado config/certificados
if [ ! -f config/estado/ultimo_nsu.json ]; then
    echo '{}' > config/estado/ultimo_nsu.json
fi
echo "✅ Pastas criadas"

# Permissões de segurança
chmod 700 config/certificados
echo "✅ Permissões aplicadas"

echo ""
echo "=== Instalação concluída ==="
echo "Próximo passo: cp config/.env.example config/.env && nano config/.env"
