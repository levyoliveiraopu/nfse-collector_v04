# nfse-collector

Automação de coleta mensal de NFS-e via API ADN do Sistema Nacional NFS-e.
Coleta XMLs e gera planilhas Excel, processando **N clientes** conforme o arquivo `config/clientes.csv`.

## Pré-requisitos

### Obrigatórios gerais
- Python 3.11+
- Certificados digitais e-CNPJ A1 (`.pfx`) dos clientes que serão processados
- Arquivo de clientes em `config/clientes.csv` (define o total de CNPJs processados)
- Arquivo `.env` configurado com as variáveis necessárias para execução

### Obrigatórios apenas para `STORAGE_BACKEND=gdrive`
- Google Drive com Service Account configurada

## Instalação
bash scripts/instalar.sh

## Backend de armazenamento
- Padrão: `STORAGE_BACKEND=local` (salva os arquivos em disco).
- Valores aceitos: `local` e `gdrive`.
- Compatibilidade: `noop` é tratado como `local`.
- Atenção: a variável correta é `STORAGE_BACKEND` (com **D** no final).

## Execução

### Exemplo com backend local
STORAGE_BACKEND=local python main.py                          # processa todos os CNPJs de config/clientes.csv (mês anterior)
python main.py --cnpj 12345678000199                          # processa 1 cliente em todas as competências (sem --ano/--mes)
python main.py --ano 2026 --mes 03                            # processa mês específico para todos os CNPJs do CSV
python main.py --cnpj 12345678000199 --ano 2026 --mes 03      # filtra competência
python main.py --dry-run                                      # simula sem fazer uploads
python main.py --reset-nsu 12345678000199                     # reseta NSU de um cliente
scripts/sync_output.sh --target local-remote --dest usuario@host:/backup/nfse/output  # sincroniza saída após coleta
scripts/sync_output.sh --target local-remote --source output --dest usuario@host:/backup/nfse/output  # override manual da origem

### Exemplo com backend Google Drive
STORAGE_BACKEND=gdrive python main.py                         # processa todos os CNPJs de config/clientes.csv enviando para o Drive

## Operação recomendada (robustez)
1. Execute a coleta mensal (`scripts/executar_mensal.sh`).
2. Em um segundo passo (cron separado), execute a sincronização (`scripts/sync_output.sh`).
   - Sem `--source`, o script usa `LOCAL_OUTPUT_DIR` do `config/.env` (ou `config/.env.example` como fallback).
3. Consulte os logs:
   - Coleta: `logs/cron_YYYY-MM.log`
   - Sincronização: `logs/sync_YYYY-MM.log`

## Documentação
Ver SETUP.md para instalação detalhada.
Ver TROUBLESHOOTING.md para solução de erros.
