# Guia de Resolução de Problemas — coletor legado (single-tenant)

> ⚠️ **Este documento cobre apenas o coletor legado** (CLI Python em
> `main.py`). Para a **plataforma SaaS multi-tenant**, os runbooks
> operacionais vivem em `docs/runbooks/`:
>
> - `credencial-invalida.md` — PFX recusado, senha errada, CN != CNPJ
> - `portal-indisponivel.md` — PORTAL_5XX / PORTAL_TIMEOUT / RATE_LIMIT
> - `parse-error.md` — XML invalido / sem campos obrigatorios
> - `storage-error.md` — falha ao subir XML/export para o S3
> - `reprocessamento.md` — como reprocessar items que falharam
> - `erro-desconhecido.md` — UNKNOWN sem categorizacao automatica
> - `disco-cheio.md` — VPS sem espaco (Docker, Postgres WAL, Loki)
> - `fila-travada.md` — RQ travado em `started_registry` ou `failed`
> - `ssl-expirando.md` — Let's Encrypt nao renovou via certbot
> - `backup-falhou.md` — exit code do `backup-postgres.sh` por camada
>
> Cada runbook segue o template "escopo / sintomas / como detectar /
> diagnostico / mitigacao / prevencao" e e linkado em
> `docs/architecture/occurrence-codes.md` e nos dashboards Grafana
> (`infra/compose/grafana/dashboards/api-worker-logs.json`).

Este documento cobre os cenários de erro mais comuns do **coletor legado**.
Para cada cenário, você encontrará como identificar o problema, a causa
raiz e os passos para resolver.

---

## Cenário 1 — Senha do certificado errada no clientes.csv

### Como identificar

O log da execução apresenta uma mensagem similar a:

```
[ERRO] CNPJ 12345678000199 — Falha ao abrir certificado: mac verify failure
```

ou

```
[ERRO] CNPJ 12345678000199 — Invalid password for PKCS12 file
```

### Causa

A coluna `cert_password` no `config/clientes.csv` contém uma senha incorreta para o arquivo `.pfx` desse CNPJ.

### Como resolver

**1.** Teste a senha diretamente no terminal para confirmar o diagnóstico:

```bash
openssl pkcs12 -info -in config/certificados/12345678000199.pfx -noout -passin pass:SUA_SENHA
```

Se a senha estiver errada, você verá: `Mac verify error: invalid password?`

**2.** Corrija a senha no `clientes.csv`:

```bash
nano config/clientes.csv
```

Localize a linha do CNPJ em questão e corrija o valor na coluna `cert_password`.

**3.** Execute novamente apenas para esse CNPJ para confirmar:

```bash
python main.py --cnpj 12345678000199
```

---

## Cenário 2 — Certificado .pfx vencido

### Como identificar

O log apresenta:

```
[ERRO] CNPJ 12345678000199 — Certificado expirado em DD/MM/AAAA
```

ou a autenticação mTLS é recusada pela API ADN com código `401` ou `403`.

### Causa

O certificado digital e-CNPJ A1 tem validade de 1 a 3 anos. Após a data de validade, ele não pode mais ser usado para autenticação.

### Como verificar a data de expiração

```bash
openssl pkcs12 -in config/certificados/12345678000199.pfx -nokeys -passin pass:SENHA \
  | openssl x509 -noout -dates
```

A saída mostra:
```
notBefore=Jan  1 00:00:00 2023 GMT
notAfter=Jan  1 00:00:00 2025 GMT   ← data de expiração
```

### Como resolver

1. Solicite ao cliente a renovação do certificado digital junto à autoridade certificadora (ex: Certisign, Serasa, Receita Federal)
2. Substitua o arquivo `.pfx` na pasta `config/certificados/` mantendo o mesmo nome:
   ```bash
   cp certificado_renovado.pfx config/certificados/12345678000199.pfx
   chmod 600 config/certificados/12345678000199.pfx
   ```
3. Se a senha do novo certificado for diferente, atualize o `clientes.csv`
4. Teste a autenticação:
   ```bash
   python main.py --cnpj 12345678000199
   ```

---

## Cenário 3 — Arquivo .pfx corrompido ou incompleto

### Como identificar

O log apresenta:

```
[ERRO] CNPJ 12345678000199 — Erro ao carregar certificado: Could not deserialize key data
```

ou

```
[ERRO] CNPJ 12345678000199 — ASN1_get_object: too long
```

### Causa

O arquivo `.pfx` foi corrompido durante a transferência (upload incompleto, interrupção de rede) ou o arquivo original já estava danificado.

### Como verificar

```bash
# Verifica a integridade básica do arquivo
openssl pkcs12 -info -in config/certificados/12345678000199.pfx -noout -passin pass:SENHA
```

Se o arquivo estiver corrompido, o OpenSSL retorna erros de parsing em vez da estrutura do certificado.

Verifique também o tamanho do arquivo. Um `.pfx` válido tipicamente tem entre 2 KB e 10 KB:

```bash
ls -lh config/certificados/12345678000199.pfx
```

Um arquivo com 0 bytes ou poucos bytes indica transferência incompleta.

### Como resolver

1. Solicite o arquivo `.pfx` original novamente ao cliente ou à fonte de onde foi obtido
2. Transfira novamente para a VPS:
   ```bash
   scp certificado_correto.pfx usuario@ip:/caminho/nfse-collector/config/certificados/12345678000199.pfx
   ```
3. Aplique as permissões:
   ```bash
   chmod 600 config/certificados/12345678000199.pfx
   ```
4. Valide o arquivo antes de executar:
   ```bash
   openssl pkcs12 -info -in config/certificados/12345678000199.pfx -noout -passin pass:SENHA
   ```

---

## Cenário 4 — CNPJ no clientes.csv diferente do CNPJ contido no certificado

### Como identificar

O log apresenta:

```
[ERRO] CNPJ 12345678000199 — CNPJ Raiz não confere: certificado pertence ao CNPJ 98765432000111
```

### Causa

O arquivo `.pfx` foi nomeado com um CNPJ mas contém o certificado de outro CNPJ. Isso geralmente ocorre quando os arquivos são renomeados manualmente de forma errada.

### Como verificar o CNPJ real do certificado

```bash
openssl pkcs12 -in config/certificados/12345678000199.pfx -nokeys -passin pass:SENHA \
  | openssl x509 -noout -subject
```

A saída exibe o subject do certificado, que contém o CNPJ real no campo `CN` ou `serialNumber`.

### Como resolver

1. Identifique a qual CNPJ o certificado pertence (pelo comando acima)
2. Se o arquivo estiver nomeado errado, renomeie-o corretamente:
   ```bash
   mv config/certificados/12345678000199.pfx config/certificados/98765432000111.pfx
   ```
3. Corrija o `clientes.csv` para apontar o `cert_path` correto para cada linha
4. Caso o certificado correto para o CNPJ `12345678000199` não exista, solicite-o ao cliente

---

## Cenário 5 — Cliente sem notas no padrão nacional ADN (NSU não avança)

### Como identificar

O log apresenta:

```
[INFO] CNPJ 12345678000199 — Nenhum documento encontrado a partir do NSU 0
```

O arquivo `ultimo_nsu.json` permanece com o valor `0` para esse CNPJ após a execução.

### Causa

**Isso não é um erro.** O cliente simplesmente não possui notas fiscais de serviço emitidas no padrão nacional ADN. Pode ocorrer porque:

- O município do cliente ainda não migrou para o padrão nacional NFS-e
- O cliente não emitiu notas no período consultado
- O CNPJ é de uma empresa que não emite NFS-e (ex: comércio, indústria)

### O que fazer

Nenhuma ação corretiva é necessária. O sistema registra `0` documentos para esse cliente e avança para o próximo.

Se quiser confirmar manualmente que é um caso esperado, verifique com o cliente se o município dele já aderiu ao padrão ABRASF/ADN consultando o portal da Receita Federal ou a prefeitura local.

---

## Cenário 6 — API retornando erro 429 (muitas requisições)

### Como identificar

O log apresenta:

```
[AVISO] CNPJ 12345678000199 — HTTP 429 Too Many Requests. Aguardando X segundos...
```

### Causa

A API ADN aplica limite de requisições por período (rate limiting). Com 300 CNPJs sendo processados em sequência, o sistema pode ultrapassar esse limite temporariamente.

### Como resolver

O sistema já possui lógica de retry automático com backoff exponencial. Se o erro persistir após as tentativas automáticas:

**1.** Aguarde ao menos 30 minutos antes de tentar novamente:

```bash
python main.py --cnpj 12345678000199
```

**2.** Divida os clientes em lotes menores para reduzir a pressão de requisições:

```bash
# Divide os 300 clientes em 6 lotes de ~50
python main.py --lote 1 --total-lotes 6
sleep 600 && python main.py --lote 2 --total-lotes 6
```

**3.** Aumente o `RATE_LIMIT_DELAY` no `config/.env` (ex: de 3 para 10 segundos).

**4.** Ajuste o agendamento do cron para distribuir a carga em horários de menor uso (ex: madrugada):

```bash
crontab -e
# Altere o horário para 02:00 ao invés de 08:00
```

---

## Cenário 7 — Google Drive sem espaço disponível

### Como identificar

O log apresenta:

```
[ERRO] Falha ao enviar arquivo para o Drive: storageQuotaExceeded
```

ou

```
[ERRO] Upload falhou: The user's Drive storage quota has been exceeded
```

### Causa

A conta Google associada à Service Account atingiu o limite de armazenamento do Google Drive (15 GB na conta gratuita).

### Como resolver

**Opção 1 — Liberar espaço na conta Google:**

1. Acesse drive.google.com com a conta Google do projeto
2. Verifique o uso de armazenamento em **Armazenamento** (rodapé esquerdo)
3. Mova arquivos antigos para a lixeira e esvazie-a

**Opção 2 — Contrato Google Workspace:**

Para uso em produção com 300 clientes gerando XMLs e Excels mensalmente, recomenda-se contratar um plano Google One ou Google Workspace com espaço adequado.

**Verificar o espaço disponível:**

Acesse [drive.google.com](https://drive.google.com) com a conta associada e verifique o uso de armazenamento no rodapé esquerdo da página.

---

## Cenário 8 — Service Account sem permissão na pasta raiz do Drive

### Como identificar

O log apresenta:

```
[ERRO] Falha ao acessar pasta do Drive (ID: XXXXX): File not found
```

ou

```
[ERRO] Google Drive: permissão negada para a pasta raiz
```

### Causa

A Service Account não foi adicionada como colaboradora na pasta **NFS-e Clientes** do Google Drive, ou o `GOOGLE_DRIVE_FOLDER_ROOT_ID` no `.env` está incorreto.

### Como resolver

**1.** Confirme o ID da pasta no `.env`:

```bash
grep GOOGLE_DRIVE_FOLDER_ROOT_ID config/.env
```

**2.** Acesse o Google Drive, abra a pasta **NFS-e Clientes** e verifique se o ID na URL bate com o valor do `.env`.

**3.** Compartilhe a pasta com a Service Account (se ainda não fez ou se o compartilhamento foi removido):

- Clique com o botão direito na pasta > **Compartilhar**
- Cole o e-mail da Service Account (formato: `nome@projeto.iam.gserviceaccount.com`)
- Defina como **Editor**
- Clique em **Compartilhar**

**4.** Aguarde 1-2 minutos (o Google Drive pode levar alguns instantes para propagar a permissão) e execute novamente:

```bash
python main.py --cnpj 12345678000199
```

---

## Cenário 9 — ultimo_nsu.json corrompido

### Como identificar

O log apresenta:

```
[ERRO] Falha ao ler config/estado/ultimo_nsu.json: JSONDecodeError
```

ou o sistema apresenta comportamento inesperado, reprocessando documentos já baixados.

### Como verificar o estado do arquivo

```bash
cat config/estado/ultimo_nsu.json
```

Um arquivo saudável tem o formato:
```json
{
  "12345678000199": 1050,
  "98765432000111": 340
}
```

Se o conteúdo estiver truncado, com caracteres estranhos ou vazio, o arquivo está corrompido.

### Como resetar um CNPJ específico

**Sem apagar os dados dos outros CNPJs**, edite o arquivo e corrija apenas o valor do CNPJ afetado:

```bash
nano config/estado/ultimo_nsu.json
```

- Para reprocessar esse CNPJ desde o início: defina o valor como `0`
- Para retomar a partir de um NSU conhecido: defina o NSU correto

Exemplo após edição:
```json
{
  "12345678000199": 0,
  "98765432000111": 340
}
```

### Se o arquivo inteiro estiver corrompido

Se não for possível recuperar nenhum valor:

**1.** Faça backup do arquivo corrompido para referência:
```bash
cp config/estado/ultimo_nsu.json config/estado/ultimo_nsu.json.corrompido
```

**2.** Recrie o arquivo com um JSON vazio e resete cada CNPJ conforme necessário:
```bash
echo '{}' > config/estado/ultimo_nsu.json
```

**3.** Execute o sistema novamente. Todos os CNPJs serão reprocessados desde o NSU 0, o que pode demorar mais que o normal.

> **Prevenção:** Inclua `config/estado/ultimo_nsu.json` no backup mensal obrigatório descrito no SETUP.md.

---

## Cenário 10 — VPS sem memória suficiente para processar 300 certificados

### Como identificar

O log apresenta:

```
[ERRO] MemoryError ao carregar certificado
```

ou o processo é encerrado abruptamente com:

```
Killed
```

Verifique o uso de memória durante a execução:

```bash
# Em outro terminal, monitore em tempo real
watch -n 2 free -h
```

### Causa

Cada certificado `.pfx` carregado em memória, combinado com o parsing dos XMLs retornados, pode consumir entre 20 MB e 50 MB por cliente. Processar todos os 300 clientes em sequência sem liberar memória pode ultrapassar o limite disponível na VPS.

### Como resolver

**Solução principal — Processar em lotes menores:**

Use os parâmetros `--lote` e `--total-lotes` para dividir os clientes em grupos:

```bash
# Divide os 300 clientes em 6 lotes de ~50
python main.py --lote 1 --total-lotes 6   # clientes 1-50
python main.py --lote 2 --total-lotes 6   # clientes 51-100
python main.py --lote 3 --total-lotes 6   # clientes 101-150
```

**Automatizar no cron com intervalo entre lotes:**

```bash
# Exemplo de crontab com 6 lotes, um por hora a partir das 02h
0 2 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 1 --total-lotes 6
0 3 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 2 --total-lotes 6
0 4 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 3 --total-lotes 6
0 5 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 4 --total-lotes 6
0 6 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 5 --total-lotes 6
0 7 5 * * /caminho/nfse-collector/scripts/executar_mensal.sh --lote 6 --total-lotes 6
```

**Verificar uso de memória disponível:**

```bash
free -h
```

Para 300 clientes em sequência, recomenda-se no mínimo 4 GB de RAM. Com 2 GB, processe em lotes de no máximo 50 clientes por vez.

**Alternativa — Adicionar swap temporariamente:**

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

> Swap não substitui RAM — é significativamente mais lento. Use apenas como medida de emergência enquanto providencia um upgrade da VPS.
