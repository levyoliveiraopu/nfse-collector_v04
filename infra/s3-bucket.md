# INFRA-06 — Bucket S3 (Backblaze B2) — Setup

> Storage S3-compativel para XMLs de NFS-e, exports e PFX cifrados.
> Provider primario: **Backblaze B2** (ADR-003).
> Retencao: XML 90d, exports 30d, sem arquivamento.

## Visao Geral

A tarefa INFRA-06 tem duas frentes:

1. **Automatizado / versionado no repo** (feito nesta PR).
   - Template de lifecycle rules em `infra/s3-lifecycle.json`.
   - Variaveis de ambiente em `config/.env.example`.
   - Script de smoke test em `infra/scripts/s3-smoke-test.sh`.
   - Esta documentacao.
2. **Manual (owner — @LevyOliveirabr)**.
   - Criar conta Backblaze, bucket, Application Key.
   - Aplicar lifecycle rules no console.
   - Gravar credenciais no cofre local.
   - Esses passos nao podem ser automatizados pelo agente
     (requerem cartao/CPF/MFA, nao sao seguros via API sem conta).

## 1. Passos automatizados (nesta PR)

| Item | Arquivo |
|------|---------|
| Template lifecycle rules (XML 90d, exports 30d) | `infra/s3-lifecycle.json` |
| Variaveis `S3_*` documentadas | `config/.env.example` |
| Smoke test (ls, put, get, delete) | `infra/scripts/s3-smoke-test.sh` |
| Runbook / passo-a-passo manual | este arquivo |

Nenhuma credencial e commitada. Nenhum bucket real e criado pelo agente.

## 2. Passos manuais do owner

### 2.1 Criar conta Backblaze B2

1. Acesse <https://www.backblaze.com/sign-up/cloud-storage>.
2. Use o e-mail institucional do projeto (nao pessoal).
3. Ative **2FA** (TOTP, nao SMS). Guarde os recovery codes no cofre.
4. Confirme o e-mail.

### 2.2 Criar o bucket

1. Menu esquerdo -> **Buckets** -> **Create a Bucket**.
2. Preencha:
   - **Bucket Unique Name:** `nfse-saas-prod`
     (se colidir, tente `nfse-saas-prod-br` ou `nfse-saas-<sufixo>`;
     atualize `S3_BUCKET` no `.env`).
   - **Files in Bucket are:** `Private`.
   - **Default Encryption:** `Enable` (SSE-B2, AES-256).
   - **Object Lock:** `Disable` (nao queremos retencao compulsoria —
     ADR-003 pede delete por lifecycle).
3. **Create a Bucket**.
4. Apos criar, clique no bucket -> aba **Bucket Settings** ->
   **File Lifecycle** -> **Use custom lifecycle rules**.
5. **Versioning:** na aba **Bucket Settings**, ative
   **Keep prior versions -> Enable** (ADR-003 pede versioning on).
   Combinar com lifecycle para expirar versoes nao-atuais apos 7 dias
   (ja contemplado em `infra/s3-lifecycle.json`).

### 2.3 Aplicar lifecycle rules

> **Limitacao do B2 que muda o layout de chaves:** o B2 so aceita
> *prefix literal* em lifecycle rules, sem glob. Nao da pra expressar
> `tenants/*/exports/` (a regra pegaria todo `tenants/`). Para manter
> as duas janelas distintas (XML 90d, exports 30d) **sem mudar o ADR**,
> o bucket hospeda exports em um prefix irmao `tenants-exports/`, nao
> em `tenants/{tid}/exports/`.
>
> Layout efetivo de chaves no bucket:
> - `tenants/{tid}/executions/{eid}/{nsu}.xml`    -> 90d  (lifecycle 1)
> - `tenants-exports/{tid}/{file_id}.{ext}`       -> 30d  (lifecycle 2)
> - `tenants-credentials/{tid}/{cid}.pfx.enc`     -> **sem TTL** (API-06)
> - `backups/postgres/daily/YYYY-MM-DD.dump[.age]` -> 30d  (lifecycle 3, INFRA-08)
> - `backups/postgres/monthly/YYYY-MM.dump[.age]`  -> 365d (lifecycle 4, INFRA-08)
>
> Quando os tickets de worker/API implementarem upload (CORE-05,
> API-06, API-11), eles devem usar as variaveis `S3_EXECUTIONS_PREFIX`,
> `S3_EXPORTS_PREFIX` e `S3_CREDENTIALS_PREFIX` (ver secao 3) em vez de
> montar paths fixos.
>
> **API-06 — `tenants-credentials/`:** este prefix hospeda os PFX
> cifrados das companies. **Nao deve ter regra de lifecycle**, porque
> credenciais sao vivas enquanto a company existir; apaga-las por TTL
> quebraria o coletor sem aviso. O passo 2.3 abaixo deixa este prefix
> intencionalmente fora das duas rules do JSON versionado.

**Aplicar via B2 CLI (recomendado — usa o JSON versionado):**

```bash
# Instale a CLI oficial do B2 (uma vez):
pip install --user b2

# Autentique com a Application Key master (Account Info -> My Auth Tokens,
# ou crie uma key com Type=All temporariamente):
b2 account authorize <MASTER_KEY_ID> <MASTER_APPLICATION_KEY>

# Aplique o lifecycle do arquivo versionado no repo:
b2 bucket update \
  --lifecycle-rules "$(jq -c '.lifecycleRules' infra/s3-lifecycle.json)" \
  nfse-saas-prod allPrivate
```

**Alternativa — console web** (usar se nao quiser instalar a CLI):

1. Bucket -> **Lifecycle Settings** -> **Use custom lifecycle rules**.
2. Add rule 1:
   - File Name Prefix: `tenants/`
   - Hide files older than: **90** days
   - Delete hidden files after: **1** day
3. Add rule 2:
   - File Name Prefix: `tenants-exports/`
   - Hide files older than: **30** days
   - Delete hidden files after: **1** day
4. Add rule 3 (INFRA-08, dailies):
   - File Name Prefix: `backups/postgres/daily/`
   - Hide files older than: **30** days
   - Delete hidden files after: **1** day
5. Add rule 4 (INFRA-08, monthlies):
   - File Name Prefix: `backups/postgres/monthly/`
   - Hide files older than: **365** days
   - Delete hidden files after: **1** day
6. **Update Bucket**.

Confirme no console: **Buckets -> nfse-saas-prod -> Lifecycle Settings**
deve mostrar exatamente **quatro** regras com os prefixos e janelas acima
(duas de dados operacionais + duas de backup). Especificamente: **nao crie**
uma quinta regra cobrindo `tenants-credentials/` — esse prefix recebe os
PFX cifrados (API-06) e **precisa ficar sem TTL**.

### 2.4 Criar Application Key (least privilege)

1. Menu esquerdo -> **Application Keys** -> **Add a New Application Key**.
2. Preencha:
   - **Name of Key:** `nfse-saas-prod-worker`.
   - **Allow access to Bucket(s):** `nfse-saas-prod` (somente este).
   - **Type of Access:** `Read and Write`.
   - **Allow List All Bucket Names:** **desmarcado** (least privilege).
   - **File name prefix:** *(em branco)* — a key precisa enxergar
     `tenants/` (XML), `tenants-exports/` (exports) e
     `tenants-credentials/` (PFX cifrados — API-06). Para isolamento
     mais forte, gere **uma key por prefix** e mantenha o `prefix`
     restrito; nesse caso configure `S3_KEY_ID`/`S3_APPLICATION_KEY`
     da key que cobre `tenants-credentials/` na API e a do worker
     com o prefix `tenants/`.
   - **Duration:** em branco (sem expiracao) ou 365 dias
     (se optar por rotacao anual, crie lembrete no calendario).
3. **Create New Key**.
4. **IMPORTANTE:** a tela mostra `keyID` e `applicationKey` **uma unica
   vez**. Copie imediatamente para o cofre (1Password/Bitwarden):

```
Backblaze B2 — nfse-saas-prod
  keyID:          <cole aqui>
  applicationKey: <cole aqui>
  endpoint:       s3.<regiao>.backblazeb2.com   (ex.: s3.us-west-004.backblazeb2.com)
  bucket:         nfse-saas-prod
```

O endpoint correto aparece em **Buckets -> Endpoint** (ex.:
`s3.us-west-004.backblazeb2.com`).

### 2.5 Gravar no cofre local e no `.env`

- Cofre: crie item **"NFS-e SaaS / S3 prod"** com os 4 campos acima.
- No servidor (quando INFRA-02 estiver pronto), popule
  `.env` a partir de `config/.env.example` com os valores do cofre.
- Jamais commite o `.env` preenchido.

## 3. Variaveis de ambiente

Adicionadas em `config/.env.example`:

```
# Storage S3-compativel (Backblaze B2 primario — ADR-003)
S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com
S3_REGION=us-west-004
S3_BUCKET=nfse-saas-prod
S3_KEY_ID=
S3_APPLICATION_KEY=
S3_FORCE_PATH_STYLE=true
S3_EXECUTIONS_PREFIX=tenants/
S3_EXPORTS_PREFIX=tenants-exports/
S3_CREDENTIALS_PREFIX=tenants-credentials/
```

- `S3_ENDPOINT` — URL completa do endpoint regional do bucket.
- `S3_REGION` — regiao do endpoint (B2 usa o formato `us-west-004`).
- `S3_BUCKET` — nome do bucket (ajuste se colidiu no passo 2.2).
- `S3_KEY_ID` / `S3_APPLICATION_KEY` — credenciais geradas em 2.4.
  **Nunca** commitar valores reais.
- `S3_FORCE_PATH_STYLE=true` — necessario para B2 com boto3/aws-cli.
- `S3_EXECUTIONS_PREFIX` / `S3_EXPORTS_PREFIX` — prefixos onde o worker
  grava XMLs (90d) e exports (30d). Ver secao 2.3 para o motivo do
  layout com dois prefixos irmaos.

## 4. Teste local com credenciais

Depois de popular o `.env` (fora do git), rode o smoke test:

```bash
# Exporta as variaveis do .env para a shell atual:
set -a; source config/.env; set +a

# Roda o smoke test (put -> get -> diff -> ls -> delete):
bash infra/scripts/s3-smoke-test.sh
```

Saida esperada:

```
[s3-smoke] endpoint=https://s3.us-west-004.backblazeb2.com bucket=nfse-saas-prod
[s3-smoke] put  OK  -> tenants/_smoketest/<uuid>.txt
[s3-smoke] get  OK  -> conteudo identico
[s3-smoke] ls   OK  -> 1 objeto no prefix tenants/_smoketest/
[s3-smoke] del  OK
[s3-smoke] PASS
```

Alternativa manual com AWS CLI (mesmo bucket, mesma chave):

```bash
aws --endpoint-url "$S3_ENDPOINT" \
    s3 ls "s3://$S3_BUCKET/"
# deve listar (ou vir vazio) sem erro de acesso.

aws --endpoint-url "$S3_ENDPOINT" \
    s3 cp README.md "s3://$S3_BUCKET/tenants/_smoketest/readme.txt"

aws --endpoint-url "$S3_ENDPOINT" \
    s3 rm "s3://$S3_BUCKET/tenants/_smoketest/readme.txt"
```

Se `s3 ls` no bucket raiz falhar com `AccessDenied` mas
`s3 ls s3://$S3_BUCKET/tenants/` funcionar, **esta correto** — a
Application Key foi restrita ao prefix `tenants/` (least privilege).

## 5. Checklist de Definition of Done (INFRA-06)

> **Status em 2026-04-15:** parte automatizada entregue em PR #79;
> os 7 itens `(owner)` abaixo **seguem em aberto** e o issue #8
> permanece aberto ate a validacao manual do bucket B2. Consumidores
> da infra (CORE-05 / API-06 / API-11 / INFRA-08) ja podem usar o
> template de lifecycle, as variaveis `S3_*` e o smoke test versionados
> no repo — mas o upload real contra o bucket so funciona apos o setup
> manual descrito em §2.1–§2.5.

- [x] Template de lifecycle commitado (`infra/s3-lifecycle.json`).
- [x] Variaveis de ambiente documentadas (`config/.env.example`).
- [x] Runbook documentado (este arquivo).
- [x] Smoke test disponivel (`infra/scripts/s3-smoke-test.sh`).
- [ ] **(owner)** Conta Backblaze criada com 2FA.
- [ ] **(owner)** Bucket `nfse-saas-prod` criado, private, versioning on.
- [ ] **(owner)** Lifecycle rules aplicadas via B2 CLI (4 regras — 2 de
      dados operacionais + 2 de backup Postgres; ver tambem
      `infra/backup.md`).
- [ ] **(owner)** Application Key restrita ao bucket + prefix `tenants/`.
- [ ] **(owner)** Credenciais gravadas no cofre (1Password/Bitwarden).
- [ ] **(owner)** `aws s3 ls s3://nfse-saas-prod/tenants/` retorna
  sucesso com a key restrita.
- [ ] **(owner)** Lifecycle visivel no console Backblaze.

Os 7 itens manuais devem ser marcados pelo owner na issue #8 antes
de fechar a tarefa. A PR so entrega o que pode ser versionado sem
expor segredos.
