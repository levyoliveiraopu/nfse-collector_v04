# INFRA-09 — Pipeline de deploy

Deploy automatizado dos ambientes `staging` e `prod` via GitHub Actions
+ SSH na VPS Hostinger (ADR-005).

- `staging`: disparado por **merge em `main`** (workflow
  `.github/workflows/deploy-staging.yml`).
- `prod`: disparado por **push de tag `v*`** (workflow
  `.github/workflows/deploy-prod.yml`). Aceita tambem disparo manual
  (`workflow_dispatch`) com `tag` de entrada.

Ambos rodam:

1. Build do `apps/api/Dockerfile` e push para **GHCR**
   (`ghcr.io/<owner>/nfse-api:<tag>` + `latest-{staging,prod}`).
2. SSH no VPS via `appleboy/ssh-action` executando
   `/srv/nfse/deploy.sh` com `DEPLOY_ENV` e `DEPLOY_TAG` exportados.
3. O script faz `docker compose pull && up -d --remove-orphans`, aguarda
   o health em `GET /health` da API (30 tentativas x 2s) e, em falha,
   **restaura a tag anterior** registrada em
   `/srv/nfse/<env>/config/.last_deploy_tag`.

---

## 1. Preparacao unica na VPS (owner, manual)

### 1.1 Arvore de diretorios

Criada por INFRA-02 (`/srv/nfse/{prod,staging}/{data,backups,logs,config}`).
Precisamos adicionar os compose files e o `deploy.sh`:

```bash
# como usuario `deploy` na VPS
cd /srv/nfse

# Clona o repo em uma pasta separada (fonte unica dos composes).
git clone https://github.com/levyoliveiraopu/nfse-collector_v04.git repo

# Linka os arquivos usados em runtime por cada ambiente.
for env in staging prod; do
  ln -sfn "/srv/nfse/repo/infra/compose/docker-compose.base.yml"   "/srv/nfse/${env}/docker-compose.base.yml"
  ln -sfn "/srv/nfse/repo/infra/compose/docker-compose.deploy.yml" "/srv/nfse/${env}/docker-compose.deploy.yml"
done

# Linka o script de deploy para um caminho fixo.
ln -sfn /srv/nfse/repo/infra/deploy/deploy.sh /srv/nfse/deploy.sh
chmod +x /srv/nfse/repo/infra/deploy/deploy.sh
```

> O script usa apenas `docker compose` + `curl` + bash builtins — nenhuma
> dependencia extra alem do que INFRA-02 ja instalou.

### 1.2 `config/.env` de cada ambiente

Copiar de `infra/compose/.env.example` e preencher com valores reais
(senhas, `DOMAIN`, etc.). **Nunca versionar.** Adicionar tambem as
variaveis esperadas pelo `docker-compose.deploy.yml`:

```bash
# /srv/nfse/staging/config/.env (owner preenche)
IMAGE_REGISTRY=ghcr.io/levyoliveiraopu
API_DATABASE_URL=postgresql+psycopg://...
API_REDIS_URL=redis://:...@redis:6379/0
# ... + todas as vars de POSTGRES_*/REDIS_*/API_* ja documentadas em
# infra/compose/.env.example e config/.env.example.
```

### 1.3 `docker login ghcr.io` na VPS

Necessario para `docker compose pull` baixar as imagens privadas.
Gerar um PAT no GitHub com scope `read:packages` (salvar como secret
`GHCR_TOKEN` se quiser rotacionar via workflow futuro):

```bash
# como usuario deploy
echo "$GHCR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

O `docker login` persiste credenciais em `~/.docker/config.json` do
usuario `deploy` — sobrevive a reboots.

### 1.4 Bootstrap inicial (primeira subida de staging)

`deploy.sh` exige que exista uma imagem ja publicada no GHCR — entao o
primeiro deploy vem **do proprio merge em `main`** que puxa este PR.
Fluxo recomendado:

1. Mergear este PR em `main`.
2. O workflow `deploy-staging` dispara, builda e publica
   `nfse-api:sha-<sha>` + `latest-staging` no GHCR.
3. O SSH tenta rodar `deploy.sh`. Na primeira vez nao havera tag
   anterior em `config/.last_deploy_tag`, entao:
   - deploy sobe e grava a tag nova;
   - se health falhar, script aborta sem rollback cego (espera owner
     ver logs com `docker compose logs -f api`).

---

## 2. Secrets do repo (Settings > Secrets and variables > Actions)

| Secret       | Onde | Conteudo                                              |
|--------------|------|-------------------------------------------------------|
| `SSH_HOST`   | repo | IP/host do VPS (ex: `123.45.67.89` ou `vps.dom.br`).  |
| `SSH_USER`   | repo | Usuario `deploy` (INFRA-01).                          |
| `SSH_KEY`    | repo | Chave privada SSH **sem passphrase** do `deploy`.     |
| `GHCR_TOKEN` | opc. | PAT `read:packages` usado no `docker login` da VPS.   |

O push para o GHCR **nao** usa `GHCR_TOKEN`: o workflow usa o
`GITHUB_TOKEN` nativo (`permissions: packages: write`), que ja tem
permissao de publicar no GHCR do proprio repo.

### 2.1 Gerar a chave SSH do deploy

```bash
# localmente (ou no VPS, movendo a privada depois)
ssh-keygen -t ed25519 -N "" -f nfse_deploy_ci -C "gha-deploy@nfse"
cat nfse_deploy_ci.pub  # -> append em ~deploy/.ssh/authorized_keys no VPS
cat nfse_deploy_ci      # -> conteudo do secret SSH_KEY
```

Opcional (recomendado): restringir o `authorized_keys` para so rodar
`deploy.sh`:

```
# ~deploy/.ssh/authorized_keys
command="/srv/nfse/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...
```

(O `appleboy/ssh-action` usa pty por padrao — se restringir com
`no-pty`, passar `use_insecure_cipher: false` e `request_pty: false`
no step do workflow. Para o MVP, deixo sem `command=` e reforco com
fail2ban + UFW ja configurados em INFRA-01.)

---

## 3. DoD e como validar

Do ticket (`docs/tasks/INFRA-09.md`):

- [ ] **PR de teste em main dispara deploy staging com sucesso.**
  Verificar em Actions > `deploy-staging` que `build-push` + `deploy`
  ficam verdes e que `curl -fsS https://api.staging.<DOMINIO>/health`
  retorna 200 (ou `ssh deploy@vps 'curl -fsS http://127.0.0.1:8000/health'`).

- [ ] **Push de tag `v0.0.1` dispara deploy prod.**
  `git tag v0.0.1 && git push origin v0.0.1`. Confirmar approval no
  environment `prod` se configurado. Validar health igual a staging.

- [ ] **Rollback testado manualmente.**
  Simular falha de health: alterar `HEALTH_URL` para um path inexistente
  e disparar o workflow via `workflow_dispatch`. O `deploy.sh` deve
  reverter para a tag anterior (`config/.last_deploy_tag`), re-subir e
  sair com `exit 20` (marcando o workflow como falho mesmo apos rollback
  bem-sucedido).

> Execucao real fica a cargo do owner — os workflows e scripts ficam
> versionados e revisaveis, seguindo o mesmo padrao de INFRA-01/02/04/07.

---

## 4. Operacao

**Disparar manualmente staging:** `Actions > deploy-staging > Run workflow`.

**Promover staging -> prod:**

```bash
git tag v0.0.1
git push origin v0.0.1
```

**Ver tag atualmente em producao:**

```bash
ssh deploy@vps 'cat /srv/nfse/prod/config/.last_deploy_tag'
```

**Rollback manual (sem falha de health):**

```bash
ssh deploy@vps \
  'cd /srv/nfse && DEPLOY_ENV=prod DEPLOY_TAG=v0.0.0 bash deploy.sh'
```

**Logs em tempo real:**

```bash
ssh deploy@vps 'docker compose \
  --env-file /srv/nfse/prod/config/.env \
  -f /srv/nfse/prod/docker-compose.base.yml \
  -f /srv/nfse/prod/docker-compose.deploy.yml \
  logs -f api'
```

---

## 5. Pendencias conhecidas

- **Worker (`nfse-worker`)**: aguarda CORE-05 publicar Dockerfile e
  imagem. O `docker-compose.deploy.yml` ja contem o bloco comentado;
  quando a imagem existir, descomentar + adicionar `build-push` de
  `nfse-worker` nos dois workflows.
- **Pinning de versao de actions**: `appleboy/ssh-action@v1.2.0`,
  `docker/build-push-action@v6` — revisar a cada 6 meses.
- **Branch protection**: CI (`lint-python`/`test-python`/`lint-ts`) ja
  protege `main` (GOV-06). O gate efetivo de deploy sao os workflows
  disparados *apos* o merge.
