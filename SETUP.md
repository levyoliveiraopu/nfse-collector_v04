# Guia de Instalação e Configuração — nfse-collector
**Ambiente:** VPS Ubuntu 22.04 LTS

---

## 1. PRÉ-REQUISITOS

Antes de iniciar, certifique-se de ter:

- VPS com Ubuntu 22.04 LTS (mínimo 2 GB de RAM e 20 GB de disco)
- 300 certificados digitais e-CNPJ A1, um arquivo `.pfx` por cliente
- Conta Google com acesso ao Google Drive
- Acesso ao Google Cloud Console (console.cloud.google.com)

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

### 2.3. Transferir os 300 arquivos via SCP

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

## 4. CONFIGURAR O GOOGLE DRIVE (SERVICE ACCOUNT)

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

### 5.6. Configurar o arquivo .env

```bash
cp config/.env.example config/.env
nano config/.env
```

Preencha cada variável conforme as instruções nos comentários do próprio arquivo. As principais são:

| Variável | Descrição |
|---|---|
| `GOOGLE_CREDENTIALS_JSON` | Caminho para o JSON da Service Account |
| `GOOGLE_DRIVE_FOLDER_ROOT_ID` | ID da pasta raiz no Google Drive (passo 4.7) |
| `RATE_LIMIT_DELAY` | Segundos entre chamadas à API (padrão: 3) |
| `LOG_LEVEL` | Nível de log: DEBUG, INFO, WARNING, ERROR (padrão: INFO) |
| `LOG_TO_CONSOLE` | Exibe logs no terminal (`true`/`false`, padrão: `true`) |
| `HTTP_TIMEOUT_SECONDS` | Timeout HTTP por requisição à API ADN em segundos (padrão: 30) |
| `NSU_ESTADO_PATH` | Caminho para o arquivo `ultimo_nsu.json` |

Salve o arquivo com `Ctrl+O`, `Enter`, `Ctrl+X`.

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

### 9.1. Testar com um único cliente

```bash
python main.py --cnpj 12345678000199
```

Verifique nos logs se a autenticação foi bem-sucedida e se os arquivos foram enviados ao Drive.

### 9.2. Simular a execução completa (sem enviar ao Drive)

```bash
python main.py --dry-run
```

O `--dry-run` processa tudo normalmente mas não faz upload para o Google Drive. Útil para validar o ambiente antes da execução real.

### 9.3. Execução real com todos os clientes

```bash
python main.py
```

### 9.4. Verificar os resultados

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

### 10.2. Adicionar o agendamento

Cole a linha de agendamento presente no arquivo `scripts/executar_mensal.sh`. O agendamento padrão é todo dia 5 do mês às 08h:

```
0 8 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh >> /caminho/nfse-collector/logs/cron_$(date +\%Y-\%m).log 2>&1
```

Salve com `Ctrl+O`, `Enter`, `Ctrl+X`.

### 10.3. Verificar o agendamento

```bash
crontab -l
```

### 10.4. Acompanhar os logs após a execução

```bash
cat logs/cron_$(date +%Y-%m).log
```

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
  +-- Lê clientes.csv (300 CNPJs + caminhos dos certificados)
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
  |     +-- Envia XMLs + Excel para pasta do cliente no Google Drive
  |     +-- Salva o maior NSU encontrado no ultimo_nsu.json
  |
  +-- Gera Excel CONSOLIDADO com todos os clientes
  +-- Salva Excel consolidado na pasta raiz do Google Drive
  +-- Grava log completo da execução
```
