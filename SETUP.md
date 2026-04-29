# Guia de Instalação e Configuração — coletor legado (single-tenant)
**Ambiente:** VPS Ubuntu 22.04 LTS

> ⚠️ **Este documento cobre apenas o coletor legado** — o CLI Python
> single-tenant em `main.py` + `src/` (atualmente reaproveitado via
> `packages/worker-core/`). Continua util para uma operacao manual
> sem painel ou para a fase 1 de validacao do PFX/CNPJ.
>
> Para a **plataforma SaaS multi-tenant** (API FastAPI + Worker RQ +
> Painel Next.js + Postgres + Redis + S3), use:
>
> - `infra/deploy/README.md` — pipeline GitHub Actions -> VPS, runbook
>   de provisionamento, secrets, rollback.
> - `apps/api/README.md` — bootstrap da API local, migrations Alembic,
>   isolamento RLS, EXPLAINs esperados.
> - `infra/compose/README.md` — docker-compose base + override de deploy
>   + override de observabilidade.
> - `infra/vps-docker.md` + `infra/vps-hardening.md` — preparacao da VPS
>   antes do primeiro deploy.
> - `infra/nginx.md` + `infra/dns.md` — Nginx host + Cloudflare DNS-only.
> - `infra/backup.md` + `infra/observability.md` — backup diario e stack
>   de observabilidade.
>
> O `README.md` do repositorio tem a visao geral consolidada e link
> direto para tudo isso na secao "Status atual" e na arvore de docs.

---

## 1. PRÉ-REQUISITOS

Antes de iniciar, certifique-se de ter:

- VPS com Ubuntu 22.04 LTS (mínimo 2 GB de RAM e 20 GB de disco)
- Certificados digitais e-CNPJ A1, um arquivo `.pfx` por cliente listado em `config/clientes.csv`
- (Opcional) Conta Google com acesso ao Google Drive
- (Opcional) Acesso ao Google Cloud Console (console.cloud.google.com)

---

## 2. ORGANIZAÇÃO DOS CERTIFICADOS NA VPS

### 2.1. Criar a pasta de certificados

Acesse a VPS e execute:

```bash
mkdir -p config/certificados
```

### 2.2. Nomenclatura dos arquivos

Cada arquivo deve ser nomeado com os **14 dígitos do CNPJ** (sem pontos, barras ou traços), seguido da extensão `.pfx`:

```
12345678000199.pfx
```

### 2.3. Transferir os arquivos via SCP

Na sua máquina local, execute o comando abaixo substituindo `usuario`, `ip` e `/caminho` pelos valores corretos da sua VPS:

```bash
scp certificados/*.pfx usuario@ip:/caminho/nfse-collector/config/certificados/
```

### 2.4. Aplicar permissões de segurança

Após a transferência, restrinja o acesso aos arquivos:

```bash
chmod 600 config/certificados/*.pfx
chmod 700 config/certificados/
```

> **Por que isso importa:** O `chmod 600` garante que apenas o dono do arquivo possa ler e escrever. O `chmod 700` garante que apenas o dono possa acessar a pasta.

---

## 3. SEGURANÇA DAS SENHAS DOS CERTIFICADOS

As senhas dos certificados ficam armazenadas na coluna `cert_password` do arquivo `config/clientes.csv`.

### 3.1. Aplicar permissão restrita ao CSV

```bash
chmod 600 config/clientes.csv
```

### 3.2. Nunca versionar o clientes.csv

O arquivo `config/clientes.csv` já está incluído no `.gitignore` do projeto. Confirme isso antes de qualquer `git push`:

```bash
grep clientes.csv .gitignore
```

Se não aparecer na listagem, adicione manualmente:

```bash
echo "config/clientes.csv" >> .gitignore
```

> **Atenção:** Versionar senhas de certificados num repositório — mesmo privado — é uma falha grave de segurança. Nunca remova essa entrada do `.gitignore`.

---

## 4. TRILHA OPCIONAL — CONFIGURAR GOOGLE DRIVE (SERVICE ACCOUNT)

> Esta trilha só é necessária se você for usar `STORAGE_BACKEND=gdrive`.  
> Se for usar apenas `STORAGE_BACKEND=local`, pode pular para a seção 5.

Siga os passos abaixo no Google Cloud Console.

### 4.1. Criar o projeto

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Clique em **Selecionar projeto** > **Novo projeto**
3. Nomeie o projeto como `nfse-collector` e clique em **Criar**

### 4.2. Ativar a API do Google Drive

1. No menu lateral, acesse **APIs & Services > Library**
2. Pesquise por **Google Drive API**
3. Clique em **Enable**

### 4.3. Criar a Service Account

1. Acesse **IAM & Admin > Service Accounts**
2. Clique em **Create Service Account**
3. Preencha o nome como `nfse-collector-sa`
4. Clique em **Done** (não é necessário atribuir papéis adicionais aqui)

### 4.4. Gerar a chave JSON

1. Na lista de Service Accounts, clique na que você acabou de criar
2. Acesse a aba **Keys**
3. Clique em **Add Key > Create new key**
4. Selecione o formato **JSON** e clique em **Create**
5. O arquivo será baixado automaticamente para o seu computador

### 4.5. Enviar a chave para a VPS

```bash
scp google_credentials.json usuario@ip:/caminho/nfse-collector/config/google_credentials.json
```

Aplique permissão restrita:

```bash
chmod 600 config/google_credentials.json
```

### 4.6. Compartilhar a pasta do Google Drive com a Service Account

1. Copie o e-mail da Service Account. Ele está no formato:
   ```
   nfse-collector-sa@nfse-collector.iam.gserviceaccount.com
   ```
2. No Google Drive, crie uma pasta chamada **NFS-e Clientes**
3. Clique com o botão direito na pasta > **Compartilhar**
4. Cole o e-mail da Service Account no campo de destinatário
5. Defina a permissão como **Editor**
6. Clique em **Compartilhar**

### 4.7. Copiar o ID da pasta

Abra a pasta **NFS-e Clientes** no Google Drive. O ID está na URL:

```
https://drive.google.com/drive/folders/ESTE_E_O_ID
```

Copie esse ID — ele será usado no próximo passo.

### 4.8. Configurar o .env

Cole o ID da pasta como valor da variável `GOOGLE_DRIVE_FOLDER_ROOT_ID` no arquivo `config/.env` (conforme a seção 5 deste guia).

---

## 5. INSTALAR O PROJETO NA VPS

### 5.1. Conectar à VPS

```bash
ssh usuario@ip
```

### 5.2. Atualizar o sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 5.3. Instalar dependências do sistema

```bash
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 5.4. Enviar o projeto para a VPS

Caso o projeto não esteja em repositório remoto, envie via SCP a partir da sua máquina local:

```bash
scp -r nfse-collector/ usuario@ip:/caminho/nfse-collector/
```

Ou, se estiver num repositório Git, clone diretamente na VPS:

```bash
git clone https://github.com/seu-usuario/nfse-collector.git
```

### 5.5. Acessar a pasta do projeto e instalar

```bash
cd nfse-collector
bash scripts/instalar.sh
```

O script cria o ambiente virtual Python, instala todas as dependências e cria as pastas necessárias.

### 5.6. Configurar o arquivo .env (duas trilhas)

```bash
cp config/.env.example config/.env
nano config/.env
```

Preencha cada variável conforme as instruções nos comentários do próprio arquivo.
As variáveis abaixo estão organizadas por trilha de setup:

#### Trilha 1 (mínima): `STORAGE_BACKEND=local`

| Variável | Descrição |
|---|---|
| `STORAGE_BACKEND` | Defina como `local` |
| `LOCAL_OUTPUT_DIR` | Diretório real onde Excel/XML serão gravados em disco |
| `RATE_LIMIT_DELAY` | Segundos entre chamadas à API (padrão: 3) |
| `MAX_DOCUMENTOS_POR_EXECUCAO` | Limite de documentos por cliente em cada execução (`0` = sem limite). Útil para testes em produção (ex: `100`). |
| `LOG_LEVEL` | Nível de log: DEBUG, INFO, WARNING, ERROR (padrão: INFO) |
| `LOG_TO_CONSOLE` | Exibe logs no terminal (`true`/`false`, padrão: `true`) |
| `HTTP_TIMEOUT_SECONDS` | Timeout HTTP por requisição à API ADN em segundos (padrão: 30) |
| `NSU_ESTADO_PATH` | Caminho para o arquivo `ultimo_nsu.json` |

#### Trilha 2 (adicional/opcional): `STORAGE_BACKEND=gdrive`

Além da trilha mínima, configure também:

| Variável | Descrição |
|---|---|
| `GOOGLE_CREDENTIALS_JSON` | Caminho para o JSON da Service Account |
| `GOOGLE_DELEGATED_USER_EMAIL` | E-mail do usuário para Domain-Wide Delegation (opcional; usar quando não houver Shared Drive) |
| `GOOGLE_DRIVE_FOLDER_ROOT_ID` | ID da pasta raiz no Google Drive (passo 4.7) |

Salve o arquivo com `Ctrl+O`, `Enter`, `Ctrl+X`.

### 5.7. Matriz de configuração por backend

| Backend | `STORAGE_BACKEND` | Variáveis obrigatórias | Comportamento |
|---|---|---|---|
| Local (disco) | `local` | `LOCAL_OUTPUT_DIR` | Salva Excel/XML em disco local. **Não** inicializa Google Drive. |
| Google Drive | `gdrive` | `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_DRIVE_FOLDER_ROOT_ID` | Inicializa integração com Drive e envia arquivos para a pasta raiz configurada. |

> Se `STORAGE_BACKEND` tiver valor diferente de `local` ou `gdrive`, a execução é encerrada com erro explícito no log.
> Compatibilidade: `noop` ainda é aceito, mas será tratado como `local`.
> Atenção: use a variável `STORAGE_BACKEND` (com **D** no final).

---

## 6. PREPARAR O clientes.csv

### 6.1. Formato obrigatório

O arquivo deve ter as seguintes colunas, nesta ordem:

```
cnpj,razao_social,cert_path,cert_password
```

### 6.2. Regras de preenchimento

| Coluna | Regra |
|---|---|
| `cnpj` | Apenas os 14 dígitos numéricos, sem formatação |
| `razao_social` | Nome da empresa (pode conter espaços e acentos) |
| `cert_path` | Caminho relativo ao projeto, ex: `config/certificados/12345678000199.pfx` |
| `cert_password` | Senha do certificado .pfx |

### 6.3. Exemplo de linha

```
12345678000199,Empresa ABC Ltda,config/certificados/12345678000199.pfx,minhasenha
```

### 6.4. Editar no terminal

```bash
nano config/clientes.csv
```

---

## 7. ENTENDENDO O CONTROLE DE NSU

### O que é NSU?

NSU (Número Sequencial Único) é um contador atribuído pelo sistema ADN a cada documento fiscal. Funciona como um índice global — cada nova nota gerada no sistema recebe um NSU maior que o anterior.

### Por que o sistema usa NSU em vez de filtro por data?

A API NFS-e ADN **não possui filtro por data**. Os documentos são consultados a partir de um NSU informado, e a API retorna até 50 documentos por chamada a partir desse ponto.

O filtro de mês/ano é aplicado pelo próprio código após o download, lendo a data contida dentro de cada XML retornado.

### Como o estado é armazenado?

O arquivo `config/estado/ultimo_nsu.json` guarda o último NSU processado por CNPJ:

```json
{
  "12345678000199": 1050,
  "98765432000111": 340
}
```

### Comportamento por execução

- **1ª execução:** NSU inicial = `0`. O sistema busca todos os documentos disponíveis para o CNPJ.
- **Execuções seguintes:** O sistema busca a partir do último NSU salvo, trazendo apenas documentos novos.

> **Nunca apague o arquivo `ultimo_nsu.json`.** Ele é o ponto de retomada do sistema. Apagá-lo faz com que o sistema reprocesse todos os documentos desde o início na próxima execução.

---

## 8. TESTAR O SETUP

Execute o script de verificação do ambiente:

```bash
bash scripts/testar_setup.sh
```

### Erros comuns e o que fazer

| Mensagem de erro | Causa provável | Solução |
|---|---|---|
| `Certificado inválido` | Senha errada no `clientes.csv` | Corrija a coluna `cert_password` para esse CNPJ |
| `Certificado vencido` | Certificado expirado | Verifique com o comando abaixo e providencie a renovação |
| `CNPJ Raiz não confere` | O certificado não pertence ao CNPJ informado no CSV | Verifique se o arquivo `.pfx` corresponde ao CNPJ correto |
| `Google Drive: permissão negada` | Service Account não foi compartilhada na pasta do Drive | Repita o passo 4.6 |
| `NSU vazio` | Cliente sem notas no padrão nacional ADN | Não é erro — o cliente simplesmente não emitiu notas nesse padrão |

Para verificar a validade de um certificado manualmente:

```bash
openssl pkcs12 -info -in config/certificados/12345678000199.pfx -noout
```

---

## 9. PRIMEIRA EXECUÇÃO

### 9.1. Testar com um único cliente (funciona em `local` e `gdrive`)

```bash
python main.py --cnpj 12345678000199
```

Verifique nos logs se a autenticação foi bem-sucedida.
- Em `STORAGE_BACKEND=local`, confirme os arquivos no `LOCAL_OUTPUT_DIR`.
- Em `STORAGE_BACKEND=gdrive`, confirme também o envio ao Drive.

### 9.2. Simular a execução completa (`--dry-run`)

```bash
python main.py --dry-run
```

O `--dry-run` processa tudo normalmente, sem persistir uploads externos. Útil para validar o ambiente antes da execução real.

### 9.3. Exemplo funcional no modo local (sem Google)

Para validar pipeline em CI/local dev sem dependências externas, force o backend local:

```bash
STORAGE_BACKEND=local python main.py --ano 2026 --mes 3
```

Nesse modo, o sistema grava os arquivos apenas em disco local (`LOCAL_OUTPUT_DIR`) e não envia nada ao Google Drive.
No `config/.env.example`, o valor padrão é `/var/lib/nfse-collector/output`.

### 9.4. Execução real para toda a base de clientes

```bash
python main.py
```

### 9.5. Verificar os resultados (modo local e modo gdrive)

```bash
# Confirmar que o NSU foi salvo
cat config/estado/ultimo_nsu.json

# Verificar o log da execução
cat logs/execucao_$(date +%Y-%m).log
```

Acesse também o Google Drive e confirme que as pastas dos clientes foram criadas com os XMLs e o Excel.

---

## 10. EXECUÇÃO AUTOMÁTICA MENSAL (CRON)

### 10.1. Abrir o crontab

```bash
crontab -e
```

Se for a primeira vez, escolha o editor `nano` quando solicitado.

### 10.2. Adicionar agendamentos separados (coleta -> sincronização)

Para aumentar a robustez operacional, mantenha a coleta e a sincronização em jobs independentes:

- **Coleta primeiro** (gera arquivos localmente e registra em `logs/cron_YYYY-MM.log`)
- **Sincronização depois** (envia os artefatos e registra em `logs/sync_YYYY-MM.log`)

Exemplo (dia 5 de cada mês, funcionando no modo local):

```cron
# 08:00 - coleta
0 8 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh

# 08:20 - sincronização (alvo rsync/local-remote)
20 8 5 * * /caminho/nfse-collector/scripts/sync_output.sh --target local-remote --dest usuario@host:/backup/nfse/output
```

> Ajuste o intervalo entre os jobs conforme o tempo médio de coleta do seu ambiente.
> Sem `--source`, o script usa `LOCAL_OUTPUT_DIR` do `config/.env` (ou `config/.env.example` como fallback). Use `--source` apenas para sobrescrever esse caminho.

Salve com `Ctrl+O`, `Enter`, `Ctrl+X`.

### 10.3. Verificar o agendamento

```bash
crontab -l
```

### 10.4. Acompanhar os logs após a execução

```bash
cat logs/cron_$(date +%Y-%m).log
cat logs/sync_$(date +%Y-%m).log
```

### 10.5. Targets de sincronização

O script `scripts/sync_output.sh` usa `--target` para escolher o backend de sincronização.

- `local-remote` (implementado): sincroniza com `rsync`.
- `drive-api` (reservado para implementação futura).
- `s3` (reservado para implementação futura).

---

## 11. MANUTENÇÃO

### Adicionar um novo cliente

1. Copie o arquivo `.pfx` para `config/certificados/`:
   ```bash
   cp novo_cliente.pfx config/certificados/12345678000199.pfx
   chmod 600 config/certificados/12345678000199.pfx
   ```
2. Adicione uma nova linha no `config/clientes.csv`:
   ```bash
   nano config/clientes.csv
   ```

### Remover um cliente

Exclua a linha correspondente ao CNPJ do `config/clientes.csv`. O arquivo `.pfx` pode ser mantido ou removido da pasta `config/certificados/`.

### Renovar um certificado vencido

Substitua o arquivo `.pfx` antigo pelo novo, mantendo o mesmo nome:

```bash
cp novo_certificado.pfx config/certificados/12345678000199.pfx
chmod 600 config/certificados/12345678000199.pfx
```

Se a senha do certificado mudou, atualize também a coluna `cert_password` no `clientes.csv`.

### Backup mensal obrigatório

Faça backup dos seguintes arquivos e pastas todo mês:

```
config/certificados/
config/clientes.csv
config/estado/ultimo_nsu.json
config/.env
config/google_credentials.json
```

Exemplo de comando para backup compactado:

```bash
tar -czf backup_nfse_$(date +%Y-%m).tar.gz \
  config/certificados/ \
  config/clientes.csv \
  config/estado/ultimo_nsu.json \
  config/.env \
  config/google_credentials.json
```

---

## FLUXO RESUMIDO

```
VPS (cron todo dia 5 às 08h)
  |
  +-- Lê clientes.csv (quantidade de CNPJs conforme `config/clientes.csv` + caminhos dos certificados)
  |
  +-- Para cada cliente:
  |     |
  |     +-- Carrega certificado .pfx do cliente
  |     +-- Autentica na API ADN via mTLS com certificado do cliente
  |     +-- Lê último NSU salvo para esse CNPJ (ultimo_nsu.json)
  |     +-- Chama GET /DFe/{UltimoNSU} repetidamente (50 docs por vez)
  |     |
  |     +-- Para cada documento retornado:
  |     |     +-- Extrai data do XML
  |     |     +-- Filtra apenas os documentos do mês anterior
  |     |     +-- Gera arquivo XML individual por nota
  |     |
  |     +-- Gera Excel resumo do cliente com os dados extraídos
  |     +-- Se `STORAGE_BACKEND=gdrive`: envia XMLs + Excel para pasta do cliente no Google Drive
  |     +-- Se `STORAGE_BACKEND=local`: grava XMLs + Excel em `LOCAL_OUTPUT_DIR`
  |     +-- Salva o maior NSU encontrado no ultimo_nsu.json
  |
  +-- Gera Excel CONSOLIDADO com todos os clientes processados
  +-- Se `gdrive`: salva consolidado na pasta raiz do Google Drive
  +-- Se `local`: salva consolidado em `LOCAL_OUTPUT_DIR`
  +-- Grava log completo da execução
```
