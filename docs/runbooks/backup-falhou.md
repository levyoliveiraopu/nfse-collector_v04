# Runbook — backup do Postgres falhou

> Alvo: rotina diaria do INFRA-08. Script
> `infra/scripts/backup-postgres.sh` disparado por
> `nfse-backup-postgres@prod.timer` as 03:00 America/Sao_Paulo.
> Layout S3: `backups/postgres/daily/YYYY-MM-DD.dump[.age]` (30d) +
> `backups/postgres/monthly/YYYY-MM.dump[.age]` (365d).

## Escopo

Use este runbook quando:

- O `status` da linha JSON em `/srv/nfse/<env>/logs/backup-postgres.log`
  nao e `ok`.
- Nao aparece objeto novo em `s3://$S3_BUCKET/backups/postgres/daily/`
  para a data de hoje.
- `systemctl status nfse-backup-postgres@prod.service` mostra
  `failed`/`exit-code != 0`.
- Drill de restore em staging nao consegue decifrar ou carregar o dump.

## 1. Como detectar

### 1.1 Fontes de alerta

- **Loki / Grafana** (futuro): quando o `scrape_config` do Promtail for
  adicionado para ler
  `/srv/nfse/<env>/logs/backup-postgres.log`
  (follow-up mencionado em `infra/backup.md` secao "Visao geral"), um
  alert rule buscando `status!="ok"` nas ultimas 24h cai neste runbook.
  Enquanto o follow-up nao esta aplicado, o sinal vem do timer + log em
  disco.
- **Systemd**: `systemctl --failed` em review diaria pega units
  quebradas.
- **Alerta futuro**: ausencia de objeto em S3 para o dia corrente (cron
  no host + webhook) -> anexar `runbook_url` para este arquivo.

### 1.2 Checagem manual

```bash
# Ultimas execucoes do timer.
systemctl list-timers nfse-backup-postgres@prod.timer
systemctl status nfse-backup-postgres@prod.service --no-pager

# Log estruturado do script (JSON por linha).
sudo tail -n 20 /srv/nfse/prod/logs/backup-postgres.log \
  | jq -r 'select(.component=="backup-postgres")
           | [.ts, .status, .duration_ms, .size_bytes, .s3_key] | @tsv'

# Journald (stdout + stderr do service).
sudo journalctl -u nfse-backup-postgres@prod.service --since "2 days ago" --no-pager

# Dump mais recente no S3.
aws s3 ls s3://$S3_BUCKET/backups/postgres/daily/ --recursive | tail -5
```

> Gatilho: agir quando o ultimo `status="ok"` e de mais de 26h atras (margem
> pro timer + `RandomizedDelaySec`).

## 2. Diagnostico

Mapa exit code -> causa (ver `infra/backup.md` secao "Exit codes"):

| exit | causa                          | acao tipica                              |
|------|--------------------------------|------------------------------------------|
| 0    | sucesso                        | —                                        |
| 2    | config/dependencia ausente     | rever `.env`, `aws`, `age`               |
| 3    | `pg_dump` falhou               | Postgres down, credencial errada         |
| 4    | cifra `age` falhou             | `BACKUP_AGE_RECIPIENT` invalido/vazio    |
| 5    | upload S3 negado/timeout       | Application Key B2, rede, bucket cheio   |
| 6    | warning na limpeza local       | permissao em `$BACKUP_LOCAL_DIR`         |

### 2.1 Postgres (`exit=3`)

```bash
cd /srv/nfse/prod/config
docker compose ps postgres

# Healthcheck interno.
docker compose exec -T postgres pg_isready -U "$POSTGRES_USER"

# Ultimos erros do Postgres.
docker compose logs --tail=200 postgres | grep -Ei "error|fatal|panic"
```

Se Postgres esta up, checar credenciais do `.env` e re-rodar manual:

```bash
sudo -u deploy BACKUP_ENCRYPT=0 \
    /srv/nfse/prod/scripts/backup-postgres.sh 2>&1 | tail -50
```

### 2.2 Cifra (`exit=4`)

```bash
# Recipient configurado?
grep '^BACKUP_AGE_RECIPIENT' /srv/nfse/prod/config/.env

# age instalado?
age --version

# Cifra um arquivo pequeno para validar o recipient:
echo test | age -r "$BACKUP_AGE_RECIPIENT" -o /tmp/age-test.age && \
  ls -la /tmp/age-test.age && rm -f /tmp/age-test.age
```

Recipient errado / vazio sai do `age` como `error: no recipients
specified`.

### 2.3 Upload S3 (`exit=5`)

```bash
# Credenciais + bucket carregados?
grep -E '^(S3_|BACKUP_)' /srv/nfse/prod/config/.env

# Teste idempotente.
aws s3 ls s3://$S3_BUCKET/backups/postgres/daily/ --summarize | tail -5

# Teste de write mesmo prefixo.
echo ok > /tmp/s3test.txt
aws s3 cp /tmp/s3test.txt s3://$S3_BUCKET/backups/postgres/daily/.healthcheck
aws s3 rm s3://$S3_BUCKET/backups/postgres/daily/.healthcheck
rm /tmp/s3test.txt
```

Erros esperados e o que fazem:

- `AccessDenied` -> Application Key B2 sem permissao ou com prefix
  restrito a `tenants/` (INFRA-06 documenta esse ponto). Gerar key com
  escopo para `backups/postgres/` ou sem prefix restrito.
- `RequestTimeTooSkewed` -> relogio da VPS fora de sincronia; conferir
  `timedatectl status` e `systemctl status systemd-timesyncd`.
- `Could not connect to the endpoint URL` -> rede caiu; retentar.

### 2.4 Restore drill quebrado

Quando o upload vai bem mas o dump nao abre:

```bash
# Baixar o mais recente (no staging) e validar.
aws s3 cp s3://$S3_BUCKET/backups/postgres/daily/$(date +%F).dump.age /tmp/today.dump.age

# Decifrar com a chave privada do cofre.
age -d -i /tmp/nfse-backup-age.key -o /tmp/today.dump /tmp/today.dump.age

# pg_restore em modo listagem (so inspeciona o toc).
docker compose exec -T postgres pg_restore --list /tmp/today.dump | head -30
```

Se falha ao decifrar: chave privada errada ou arquivo truncado no
upload -> re-executar backup e re-tentar o drill.

## 3. Mitigacao

### 3.1 Reexecutar o backup manualmente

```bash
sudo systemctl start nfse-backup-postgres@prod.service
sudo journalctl -u nfse-backup-postgres@prod.service -f
```

Alternativa direta:

```bash
sudo -u deploy /srv/nfse/prod/scripts/backup-postgres.sh
```

### 3.2 Backup emergencial (pula dependencias quebradas)

Quando `age` / `aws` estao indisponiveis e e preciso um dump urgente:

```bash
cd /srv/nfse/prod/config
ts=$(date +%F_%H%M)
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -Z 9 \
  > /srv/nfse/prod/backups/postgres/emergency-"$ts".dump

ls -la /srv/nfse/prod/backups/postgres/emergency-"$ts".dump
```

Subir pro S3 manualmente quando voltar:

```bash
aws s3 cp /srv/nfse/prod/backups/postgres/emergency-"$ts".dump \
  s3://$S3_BUCKET/backups/postgres/daily/emergency-"$ts".dump
```

> Esse dump **nao** esta cifrado — manter local no maximo 24h e
> remover assim que o fluxo normal voltar.

### 3.3 Timer nao disparando

```bash
# Habilitar + startar.
sudo systemctl enable --now nfse-backup-postgres@prod.timer

# TZ do host precisa estar America/Sao_Paulo (ver infra/vps-hardening.md).
timedatectl status
```

`Persistent=true` no timer garante slot perdido recuperado no proximo
boot — nao precisa forcar disparo retroativo.

### 3.4 Lifecycle rule quebrada

Se objetos antigos nao somem (e disco do bucket cresce):

```bash
b2 bucket get "$S3_BUCKET" | jq '.lifecycleRules'
```

Deve conter 4 rules (`tenants/`, `tenants-exports/`,
`backups/postgres/daily/`, `backups/postgres/monthly/`). Reaplicar
pelo JSON versionado:

```bash
b2 bucket update "$S3_BUCKET" \
  --lifecycle-rules "$(jq -c '.lifecycleRules' /srv/nfse/repo/infra/s3-lifecycle.json)"
```

## 4. Prevencao

- [ ] `BACKUP_ENCRYPT=1` em staging/prod (default do script) — nunca
  subir dump em claro pro B2.
- [ ] **Chave privada age** duplicada no cofre (1Password/Bitwarden)
  com owner adicional. Perda da chave = backups inservíveis.
- [ ] **Drill de restore trimestral** em staging — ver secao 4 de
  `infra/backup.md`. Resultado anotado em post-mortem curto.
- [ ] Lifecycle B2 aplicada (ver secao 3.4). Conferir na revisao
  trimestral do infra.
- [ ] Promtail configurado para ler `backup-postgres.log` quando o
  follow-up for aplicado — ativa alerta por logs em vez de inspecao
  manual.
- [ ] VPS com NTP ativo (`timedatectl status` -> "System clock
  synchronized: yes") — evita `RequestTimeTooSkewed` no S3.
- [ ] Application Key B2 com escopo cobrindo `backups/postgres/`
  (key dedicada ou sem prefix restrito). Documentado em
  `infra/s3-bucket.md`.

## Referencias

- `infra/backup.md` — runbook completo do INFRA-08 (pre-requisitos,
  instalacao, drill de restore detalhado).
- `infra/scripts/backup-postgres.sh` — fonte do fluxo + exit codes.
- `infra/scripts/restore-postgres.sh` — procedimento de restore.
- `infra/systemd/nfse-backup-postgres@.{service,timer}`.
- `docs/runbooks/disco-cheio.md` — limpeza local quando dumps antigos
  lotam o disco da VPS.
