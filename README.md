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

## Backend de armazenamento
- Padrão: `STORAGE_BACKEND=local` (salva os arquivos em disco).
- Valores aceitos: `local` e `gdrive`.
- Compatibilidade: `noop` é tratado como `local`.
- Atenção: a variável correta é `STORAGE_BACKEND` (com **D** no final).

## Execução
python main.py                          # processa todos os clientes (mês anterior)
python main.py --cnpj 12345678000199    # processa 1 cliente em todas as competências (sem --ano/--mes)
python main.py --ano 2026 --mes 03      # processa mês específico
python main.py --cnpj 12345678000199 --ano 2026 --mes 03  # filtra competência
python main.py --dry-run                # simula sem fazer uploads
python main.py --reset-nsu 12345678000199  # reseta NSU de um cliente
scripts/sync_output.sh --target local-remote --dest usuario@host:/backup/nfse/output  # sincroniza saída após coleta

## Operação recomendada (robustez)
1. Execute a coleta mensal (`scripts/executar_mensal.sh`).
2. Em um segundo passo (cron separado), execute a sincronização (`scripts/sync_output.sh`).
3. Consulte os logs:
   - Coleta: `logs/cron_YYYY-MM.log`
   - Sincronização: `logs/sync_YYYY-MM.log`

## Documentação
Ver SETUP.md para instalação detalhada.
Ver TROUBLESHOOTING.md para solução de erros.
