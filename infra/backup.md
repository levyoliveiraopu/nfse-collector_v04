# INFRA-08 — Backup Postgres para S3

> Backup diario do Postgres com `pg_dump -Fc`, upload cifrado para o bucket
> B2 (INFRA-06) e drill de restore validado em staging.
>
> Script: `infra/scripts/backup-postgres.sh`
> Restore: `infra/scripts/restore-postgres.sh`
> Systemd: `infra/systemd/nfse-backup-postgres@.{service,timer}`

## Visao geral

- **Cadencia:** diaria as 03:00 (America/Sao_Paulo, UTC-3) via
  `systemd.timer`. `Persistent=true` recupera o slot se o host estava
  desligado.
- **Formato:** `pg_dump -Fc -Z 9` (custom format, compressao nivel 9).
  Rodado dentro do container do Postgres (INFRA-05) via
  `docker compose exec -T` — evita instalar `postgresql-client` no host.
- **Cifra em repouso:** `age` (https://age-encryption.org) com
  recipient publico em `BACKUP_AGE_RECIPIENT`. A chave privada (`age-secret-key`)
  vive **apenas** no cofre (1Password/Bitwarden) do owner. Default ON em
  staging/production; dev pode rodar com `BACKUP_ENCRYPT=0`.
- **Layout S3:**
  - `backups/postgres/daily/YYYY-MM-DD.dump[.age]`  — retencao 30d.
  - `backups/postgres/monthly/YYYY-MM.dump[.age]`   — retencao 365d
    (gravado automaticamente no dia 1 do mes).
- **Retencao local:** `$BACKUP_LOCAL_DIR` (default
  `/srv/nfse/<env>/backups/postgres`) mantem dumps das ultimas
  `BACKUP_RETENTION_LOCAL_DAYS` jornadas (default 3d).
- **Log estruturado:** cada execucao escreve uma linha JSON em
  `$BACKUP_LOG_FILE` (`/srv/nfse/<env>/logs/backup-postgres.log`). O
  Promtail (INFRA-07) ja coleta `/var/log` e `/var/lib/docker/containers`
  — para ingerir este arquivo, adicione um `scrape_config` em
  `infra/compose/promtail/promtail-config.yml` apontando para o log
  (follow-up; nao bloqueia o DoD desta tarefa).

## 1. Instalacao na VPS

### 1.1 Pre-requisitos

- Stack base INFRA-05 rodando (`docker compose ps` mostra `nfse-postgres`
  healthy).
- `/srv/nfse/<env>/` provisionado (INFRA-02 — mode 0750, owner
  `deploy:deploy`).
- `aws` CLI instalado para o usuario `deploy`:
  ```bash
  sudo apt install -y pipx
  sudo -u deploy pipx install awscli
  ```
- `age` instalado (cifra do dump):
  ```bash
  sudo apt install -y age
  ```

### 1.2 Gerar o par age (uma vez)

Na **workstation** do owner (nao na VPS), gere o par e **guarde a chave
privada no cofre**:

```bash
age-keygen -o nfse-backup-age.key
# Saida:
#   Public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   chave privada gravada em nfse-backup-age.key
```

- **Chave publica** (`age1...`) -> va para `BACKUP_AGE_RECIPIENT` no
  `/srv/nfse/<env>/config/.env`. Pode commitar? **Nao neste repo** —
  `.env` nao e versionado. A pubkey em si **nao e segredo** (so cifra),
  mas mantemos no `.env` para simplificar operacao.
- **Chave privada** (`AGE-SECRET-KEY-1...` dentro de `nfse-backup-age.key`)
  -> grave no cofre como item **"NFS-e SaaS / Backup age key (prod)"**
  e **delete o arquivo local**. Nunca suba para a VPS em operacao
  normal — so entra na VPS temporariamente durante um drill de restore
  (secao 4).

Perda da chave privada = backups inservíveis. Duplicar a entrada no cofre
com um owner adicional e essencial.

### 1.3 Popular `/srv/nfse/<env>/config/.env`

Adicione ao `.env` ja existente (do INFRA-05/INFRA-09):

```bash
# Backup Postgres (INFRA-08) — ver infra/backup.md
BACKUP_LOCAL_DIR=/srv/nfse/prod/backups/postgres
BACKUP_S3_PREFIX=backups/postgres/
BACKUP_RETENTION_LOCAL_DAYS=3
BACKUP_ENCRYPT=1
BACKUP_AGE_RECIPIENT=age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# BACKUP_AGE_IDENTITY so em drills de restore — ver secao 4.
```

As variaveis `S3_*`, `POSTGRES_*`, `COMPOSE_DIR` e `DEPLOY_ENV` sao
herdadas dos tickets anteriores (INFRA-05/06/09).

### 1.4 Criar symlinks do runtime

O systemd template espera o script em
`/srv/nfse/<env>/scripts/backup-postgres.sh`:

```bash
sudo -u deploy mkdir -p /srv/nfse/prod/scripts /srv/nfse/prod/logs
sudo -u deploy ln -sfn /srv/nfse/repo/infra/scripts/backup-postgres.sh \
    /srv/nfse/prod/scripts/backup-postgres.sh
sudo -u deploy ln -sfn /srv/nfse/repo/infra/scripts/restore-postgres.sh \
    /srv/nfse/prod/scripts/restore-postgres.sh
```

### 1.5 Instalar os units systemd

```bash
sudo install -m 0644 \
    /srv/nfse/repo/infra/systemd/nfse-backup-postgres@.service \
    /etc/systemd/system/nfse-backup-postgres@.service
sudo install -m 0644 \
    /srv/nfse/repo/infra/systemd/nfse-backup-postgres@.timer \
    /etc/systemd/system/nfse-backup-postgres@.timer

sudo systemctl daemon-reload
sudo systemctl enable --now nfse-backup-postgres@prod.timer
```

Valide que o timer esta ativo:

```bash
# Confirme o timezone do host primeiro — o OnCalendar usa o TZ local.
timedatectl status | grep -E 'Time zone|Local time'
# Esperado: "Time zone: America/Sao_Paulo (-03, -0300)" (setado em INFRA-01).

systemctl list-timers nfse-backup-postgres@prod.timer
# Deve mostrar NEXT=amanha 03:00:00 -03, LAST= ainda vazio.
```

### 1.6 Dry run imediato

Para nao esperar ate 03:00:

```bash
sudo systemctl start nfse-backup-postgres@prod.service
sudo journalctl -u nfse-backup-postgres@prod.service --no-pager -n 50
# Procure por "[backup-pg] PASS" e uma linha JSON com "status":"ok".
```

Confirme no S3:

```bash
set -a; source /srv/nfse/prod/config/.env; set +a
aws --endpoint-url "$S3_ENDPOINT" s3 ls \
    "s3://${S3_BUCKET}/backups/postgres/daily/" | tail -n 5
```

## 2. Uso manual (ad-hoc)

```bash
# Backup manual imediato (mesmo caminho que o cron):
set -a; source /srv/nfse/prod/config/.env; set +a
bash /srv/nfse/prod/scripts/backup-postgres.sh

# Restore do dump mais recente em um DB efemero (drill):
bash /srv/nfse/prod/scripts/restore-postgres.sh \
    --latest --target-db nfse_restore_drill \
    # BACKUP_AGE_IDENTITY apontando para a chave privada temporaria (ver §4)

# Restore de um dump especifico sobre prod (DESTRUTIVO):
bash /srv/nfse/prod/scripts/restore-postgres.sh \
    --key backups/postgres/daily/2026-04-16.dump.age \
    --force
```

## 3. Lifecycle do bucket

Duas regras novas em `infra/s3-lifecycle.json` (total 4 regras no B2 —
ver `infra/s3-bucket.md` secao 2.3):

| Prefix                      | `daysFromUploadingToHiding` | `daysFromHidingToDeleting` | Proposito                |
|-----------------------------|-----------------------------|----------------------------|--------------------------|
| `backups/postgres/daily/`   | 30                          | 1                          | Dailies (30d)            |
| `backups/postgres/monthly/` | 365                         | 1                          | Monthlies (12 meses)     |

> **Por que prefixos em vez de tags?** O ticket menciona "manual tag"
> para monthlies, mas o B2 Lifecycle nao suporta tagging — so prefix
> literal (mesma limitacao que forcou `tenants-exports/` em INFRA-06).
> Solucao: o script grava em `monthly/` quando `date +%d == 01`, em
> `daily/` nos demais dias. As duas rules sao independentes.

Aplique via B2 CLI (recomendado):

```bash
b2 account authorize <MASTER_KEY_ID> <MASTER_APPLICATION_KEY>
b2 bucket update \
  --lifecycle-rules "$(jq -c '.lifecycleRules' \
      /srv/nfse/repo/infra/s3-lifecycle.json)" \
  nfse-saas-prod allPrivate
```

Ou via console web: **Buckets -> nfse-saas-prod -> Lifecycle Settings**
e adicione as duas regras acima (alem das duas ja existentes de
`tenants/` e `tenants-exports/`).

## 4. Drill de restore em staging

Objetivo: provar que o dump cifrado do S3 recupera os dados intactos.
Faca **antes** de confiar no processo em producao e **pelo menos uma vez
por trimestre** daqui pra frente.

### 4.1 Preparar staging

- Staging precisa ter a stack base subida (`compose --project-directory
  /srv/nfse/staging ... up -d postgres`).
- Copie o `.env` de prod para `/srv/nfse/staging/config/.env` e **troque
  `POSTGRES_PASSWORD` e `S3_*`** para valores de staging. (Owner pode ter
  um bucket separado `nfse-saas-staging` — ou usar o de prod **somente
  para leitura** via Application Key read-only.)

### 4.2 Exportar a chave privada age temporariamente

```bash
# Na sua workstation, recupere a chave do cofre e envie para a VPS
# staging com SFTP/SCP. Mode 0600. **Remover ao final do drill.**
scp nfse-backup-age.key deploy@staging.<DOMINIO>:/tmp/nfse-backup-age.key
ssh deploy@staging.<DOMINIO> 'chmod 600 /tmp/nfse-backup-age.key'
```

### 4.3 Rodar o restore em um DB isolado

```bash
ssh deploy@staging.<DOMINIO>
set -a; source /srv/nfse/staging/config/.env; set +a
export BACKUP_AGE_IDENTITY=/tmp/nfse-backup-age.key

bash /srv/nfse/staging/scripts/restore-postgres.sh \
    --latest --target-db nfse_restore_drill --force
```

O script termina imprimindo checksum de sanidade:

```
[restore-pg] checksum de sanidade (count(*) por tabela):
[restore-pg]   tenants        = 1
[restore-pg]   users          = 1
[restore-pg]   tenant_users   = 1
[restore-pg]   companies      = 0
[restore-pg]   audit_logs     = 42
[restore-pg] PASS — restore em 'nfse_restore_drill' completo
```

### 4.4 Validar integridade

Compare com o banco ativo de staging (se aplicavel):

```bash
docker compose --project-directory /srv/nfse/staging \
    -f /srv/nfse/staging/docker-compose.base.yml \
    exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    'SELECT count(*) FROM tenants; SELECT count(*) FROM audit_logs;'
```

Spot check adicional — MD5 de linhas ordenadas em uma tabela estavel:

```sql
-- rode contra ambos os DBs (origem e restaurado) e compare:
SELECT md5(string_agg(t::text, ',' ORDER BY id)) FROM tenants t;
SELECT md5(string_agg(p::text, ',' ORDER BY code)) FROM plans p;
```

### 4.5 Limpar

```bash
docker compose --project-directory /srv/nfse/staging \
    -f /srv/nfse/staging/docker-compose.base.yml \
    exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
    psql -U "$POSTGRES_USER" -d postgres -c \
    'DROP DATABASE IF EXISTS nfse_restore_drill;'

# CRITICO: apaga a chave privada do staging.
ssh deploy@staging.<DOMINIO> 'shred -u /tmp/nfse-backup-age.key'
```

Registre no runbook interno: data, dump usado, tempo de restore,
checksum OK/FAIL.

## 5. Troubleshooting

| Sintoma                                             | Causa provavel                                               | Acao                                                                                 |
|-----------------------------------------------------|--------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `pg_dump falhou (rc=1)`                             | Container `postgres` nao up ou `POSTGRES_PASSWORD` errado    | `docker compose ps`, `journalctl -u nfse-backup-postgres@prod.service`               |
| `age nao encontrado`                                | `apt install age` nao feito                                  | Instalar; ou `BACKUP_ENCRYPT=0` (nao recomendado em prod)                            |
| `BACKUP_ENCRYPT=1 exige BACKUP_AGE_RECIPIENT`       | `.env` nao foi editado                                       | Preencher `BACKUP_AGE_RECIPIENT` com a pubkey `age1...`                              |
| `falha no upload S3`                                | Application Key sem permissao em `backups/postgres/`         | Verificar escopo da key em Backblaze; ou criar key dedicada sem prefix restrito      |
| `dump cifrado exige BACKUP_AGE_IDENTITY`            | Restore rodado sem expor a chave privada                     | Copiar chave do cofre para `/tmp/nfse-backup-age.key` (chmod 600) — secao 4.2        |
| `pg_restore rc=1` (warning, nao erro)               | `--no-owner` causa avisos de role inexistente                | Ignorar se rc <= 1; o script ja aceita isso                                          |
| Timer nao dispara                                   | `WantedBy=timers.target` nao habilitado                      | `sudo systemctl enable --now nfse-backup-postgres@prod.timer`                        |
| Dump crescendo muito rapido                         | Possivel explosao em `audit_logs`                            | Monitorar `size_bytes` no log JSON; considerar `--exclude-table-data=audit_logs`     |

## 6. Checklist do Definition of Done (INFRA-08)

Parte automatizada (versionada neste PR):

- [x] `infra/scripts/backup-postgres.sh` — `pg_dump -Fc`, dual-prefix
      (`daily/`+`monthly/`), cifra opcional com age, upload S3,
      retencao local.
- [x] `infra/scripts/restore-postgres.sh` — download, decifra,
      `pg_restore`, checksums de sanidade, suporte a `--target-db`
      para drill.
- [x] Systemd template `nfse-backup-postgres@.{service,timer}` com
      `OnCalendar=America/Sao_Paulo 03:00:00`.
- [x] Lifecycle rules em `infra/s3-lifecycle.json` (30d daily + 365d
      monthly).
- [x] Variaveis `BACKUP_*` em `config/.env.example`.
- [x] Runbook (este arquivo).

Parte manual (owner — fica aberto no issue #10 ate validacao):

- [ ] **(owner)** Par `age` gerado; chave privada no cofre; publica
      em `/srv/nfse/prod/config/.env` (`BACKUP_AGE_RECIPIENT`).
- [ ] **(owner)** Timer `nfse-backup-postgres@prod.timer` ativo na VPS.
- [ ] **(owner)** Lifecycle rules 3 e 4 aplicadas no bucket B2.
- [ ] **(owner)** Backup roda via cron por 2 dias seguidos (LAST do
      `systemctl list-timers` confirma + listagem S3 mostra 2
      dailies).
- [ ] **(owner)** Drill de restore em staging passa (secao 4);
      checksum bate com origem.

## 7. Referencias

- ADR-003 — Storage externo + retencao 90d sem arquivamento.
- ADR-005 — Deploy Docker Compose em VPS Hostinger.
- INFRA-05 — Compose base Postgres/Redis.
- INFRA-06 — Bucket B2 (4 lifecycle rules totais).
- INFRA-07 — Loki/Promtail para ingestao do JSON log (follow-up).
- INFRA-09 — Pipeline de deploy (convivencia com backup durante
  `docker compose pull && up`).
