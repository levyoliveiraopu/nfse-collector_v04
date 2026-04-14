# Docker Engine + Compose v2 na VPS Hostinger (INFRA-02)

Runbook manual para instalar Docker Engine + buildx + Compose v2 e preparar a
estrutura de diretorios que vai abrigar os stacks `prod` e `staging`
(Compose + Nginx host — ADR-005).

> **Execucao:** este runbook e executado pelo owner via SSH na VPS real.
> Os comandos **nao** rodam em CI. O ticket fica fechado quando todos os
> checks da secao 7 passarem.

## 0. Pre-requisitos

- INFRA-01 concluido: VPS Ubuntu 24.04 endurecida, usuario `deploy` com
  sudo sem senha, SSH chave-only (ver `infra/vps-hardening.md`).
- Login como `deploy` via SSH:

  ```bash
  ssh deploy@${VPS_IP}
  ```

- Confirmacao da distro (runbook assume Ubuntu 24.04 "noble"):

  ```bash
  . /etc/os-release && echo "$ID $VERSION_CODENAME"   # esperado: ubuntu noble
  ```

## 1. Remover pacotes Docker antigos (se houver)

Ubuntu 24.04 nao traz Docker por padrao, mas imagens da Hostinger as vezes
ja tem `docker.io`/`podman-docker` instalados. Remove-os para evitar
conflito com o repo oficial:

```bash
for pkg in docker.io docker-doc docker-compose docker-compose-v2 \
           podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done
```

## 2. Adicionar o repositorio oficial do Docker

Usamos o repo oficial (`download.docker.com`) — versoes mais recentes que
o `docker.io` dos repositorios do Ubuntu e compatibilidade garantida com
o Compose plugin v2.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update
```

## 3. Instalar Docker Engine + buildx + Compose plugin

```bash
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker.service containerd.service
```

Validar versoes:

```bash
docker --version                # Docker version 27.x (ou superior)
docker compose version          # Docker Compose version v2.29+ (>= 2.20)
docker buildx version           # github.com/docker/buildx v0.x
```

## 4. Adicionar `deploy` ao grupo `docker`

```bash
sudo usermod -aG docker deploy
```

O grupo so vale em novas sessoes. Saia e entre novamente via SSH:

```bash
exit
ssh deploy@${VPS_IP}
id -nG | tr ' ' '\n' | grep -x docker   # deve imprimir: docker
docker ps                                # nao deve pedir sudo
```

> Alternativa sem re-login (apenas para conferir na mesma sessao):
> `newgrp docker` abre um subshell com o grupo ja ativo.

## 5. Configurar log-driver com rotacao

Sem limites o `json-file` default pode lotar o disco da VPS. Fixa
rotacao em `/etc/docker/daemon.json`:

```bash
sudo install -d -m 0755 /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true
}
EOF

sudo systemctl restart docker
docker info --format '{{.LoggingDriver}}'   # json-file
```

> **Nao** habilitar API TCP do daemon (`-H tcp://...`). Acesso remoto
> fica via SSH; socket Unix (`/var/run/docker.sock`) continua o unico
> canal.

## 6. Estrutura de diretorios em `/srv/nfse/`

Arvore padrao que os Compose stacks (`prod` e `staging`) vao montar como
volumes (INFRA-05 em diante):

```
/srv/nfse/
  prod/
    data/        # volumes de dados (postgres, redis, minio-cache, ...)
    backups/     # dumps pg_dump / snapshots antes do retention
    logs/        # logs de aplicacao (fora do json-file do Docker)
    config/      # arquivos .env e configs montadas read-only nos services
  staging/
    data/
    backups/
    logs/
    config/
```

Criar com owner `deploy:deploy` e mode `0750` no topo e nas subpastas:

```bash
sudo install -d -o deploy -g deploy -m 0750 /srv/nfse
for env in prod staging; do
  sudo install -d -o deploy -g deploy -m 0750 /srv/nfse/${env}
  for sub in data backups logs config; do
    sudo install -d -o deploy -g deploy -m 0750 /srv/nfse/${env}/${sub}
  done
done
```

Conferir:

```bash
find /srv/nfse -maxdepth 2 -mindepth 1 \
  -printf '%m %u:%g %p\n'
```

Esperado: todas as linhas com `750 deploy:deploy`.

> **Nota:** alguns servicos (ex.: Postgres, que exige `0700` no PGDATA)
> vao sobrescrever permissoes **dentro** de `/srv/nfse/*/data/<service>/`
> quando subirem via Compose. Isso e esperado — nao precisa relaxar o
> `0750` do topo para acomoda-los; cada container gerencia seu proprio
> subdiretorio.

## 7. Verificacao final (Definition of Done)

Rode como `deploy` via SSH:

```bash
# [x] docker compose version >= 2.20
docker compose version

# [x] deploy roda docker ps sem sudo
docker ps

# [x] diretorios criados com owner deploy:deploy e mode 750
find /srv/nfse -maxdepth 2 -mindepth 1 -printf '%m %u:%g %p\n'
```

Quando os tres checks acima estiverem verdes, marcar o DoD do ticket.

## 8. Notas de operacao

- **Smoke test rapido** (opcional, apos DoD):

  ```bash
  docker run --rm hello-world
  docker compose version
  ```

- **Atualizacao do Docker** segue `apt-get upgrade` normal; o repo oficial
  entrega releases estaveis. Evitar `apt full-upgrade` as cegas se o stack
  estiver rodando — preferir janela de manutencao.
- **Backup do daemon.json** (`/etc/docker/daemon.json`) e do arquivo de
  repo (`/etc/apt/sources.list.d/docker.list`) deve entrar no cofre de
  runbooks do owner. Sao pequenos e deterministicos; nao precisam de
  versionamento aqui no repo.
- **Nunca** commitar conteudo real de `/srv/nfse/*/config/` (vai ter
  `.env`, chaves B2, segredos Postgres). Essa pasta e apenas montada
  read-only nos services, nao espelhada no git.
- Se `docker ps` ainda pedir sudo apos o re-login, checar `groups deploy`
  (deve listar `docker`) e reiniciar o servico SSH (`sudo systemctl
  restart ssh`) para garantir que sessoes novas herdem o grupo.
