# nfse-collector

Automação de coleta mensal de NFS-e via API ADN do Sistema Nacional NFS-e.
Coleta XMLs e gera planilhas Excel para 300 clientes, organizando tudo no Google Drive.

## Pré-requisitos
- Python 3.11+
- 300 certificados digitais e-CNPJ A1 (.pfx)
- Google Drive com Service Account configurada
- VPS Ubuntu 22.04

## Instalação
bash scripts/instalar.sh

## Execução
python main.py                          # processa todos os clientes (mês anterior)
python main.py --cnpj 12345678000199    # processa 1 cliente em todas as competências (sem --ano/--mes)
python main.py --ano 2026 --mes 03      # processa mês específico
python main.py --cnpj 12345678000199 --ano 2026 --mes 03  # filtra competência
python main.py --dry-run                # simula sem fazer uploads
python main.py --reset-nsu 12345678000199  # reseta NSU de um cliente

## Documentação
Ver SETUP.md para instalação detalhada.
Ver TROUBLESHOOTING.md para solução de erros.
