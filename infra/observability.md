# Observabilidade (INFRA-07)

Runbook para subir a stack de observabilidade minima do NFS-e SaaS:
**Loki + Promtail + Grafana + Uptime Kuma**, expostos sob `ops.<DOMINIO>`
atras do Nginx host com basic auth + IP allowlist.

> **Execucao:** este runbook roda na VPS pelo `deploy` (SSH). Os arquivos
> de stack vivem sob `/srv/nfse/prod/config/obs/` (espelho do diretorio
> `infra/compose/` deste repo).

## 0. Pre-requisitos

- INFRA-01 feito: VPS endurecida, usuario `deploy` com sudo.
- INFRA-02 feito: Docker Engine + Compose v2 instalados, arvore
  `/srv/nfse/prod/...` criada.
- INFRA-03 feito: DNS A `ops.<DOMINIO>` aponta pro IP da VPS,
  **DNS-only** (sem proxy Cloudflare — preservar TLS end-to-end, mesmo
  padrao que `api`).
- Nginx host instalado (INFRA-04) e `certbot --nginx` disponivel.
- `apache2-utils` instalado (`sudo apt-get install -y apache2-utils`)
  para gerar o arquivo `.htpasswd`.

## 1. Estrutura de diretorios na VPS

Criar os diretorios de dados persistentes e espelhar os configs:

```bash
# Dados persistentes (bind mounts do docker-compose.obs.yml).
sudo install -d -o 10001 -g 10001 -m 0750 /srv/nfse/prod/data/loki
sudo install -d -o 10001 -g 10001 -m 0750 /srv/nfse/prod/data/promtail
sudo install -d -o 472 -g 472 -m 0750 /srv/nfse/prod/data/grafana
sudo install -d -o deploy -g deploy -m 0750 /srv/nfse/prod/data/uptime-kuma

# Stack files (rsync do repo ou checkout de `main`).
sudo install -d -o deploy -g deploy -m 0750 /srv/nfse/prod/config/obs
rsync -av --delete \
  infra/compose/ deploy@${VPS_IP}:/srv/nfse/prod/config/obs/
```

> **UIDs**: Loki roda como `10001:10001` e Grafana como `472:472` nas
> imagens oficiais. Os `install -d` acima ja criam os diretorios com os
> owners corretos — sem isso os containers falham ao escrever.

## 2. Variaveis de ambiente

Criar `/srv/nfse/prod/config/.env` (modo `0600`, owner `deploy:deploy`)
com os valores reais, baseando-se nos placeholders do `config/.env.example`
(secao `# Observabilidade (INFRA-07)`):

```bash
# Dominio de ops (ex.: ops.saas.example.com).
OBS_DOMAIN=ops.<DOMINIO>

# Credenciais do admin do Grafana (trocar no primeiro login).
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<gerar-com-openssl-rand-base64-32>

# IP allowlist do Nginx — lista CSV de CIDRs que podem acessar ops.
# Exemplo: "203.0.113.10/32,198.51.100.0/24"
OPS_ALLOWED_IPS=<preencher>

# Telegram (para alertas do Uptime Kuma — ver secao 7).
TELEGRAM_BOT_TOKEN=<token-do-BotFather>
TELEGRAM_CHAT_ID=<chat-id-do-grupo-ou-DM>
```

> **Segredo**: `.env` fica **fora do repo**; so o `.env.example` e
> commitado. O cofre de senhas do owner guarda os valores reais.

## 3. Subir a stack de observabilidade

```bash
cd /srv/nfse/prod/config/obs
docker compose -f docker-compose.obs.yml --env-file ../.env up -d

# Acompanhar logs ate os 4 containers virarem "healthy":
docker compose -f docker-compose.obs.yml logs -f --tail=50
# Ctrl-C quando nao houver mais erros de boot.

docker compose -f docker-compose.obs.yml ps
# Esperado: loki / promtail / grafana / uptime-kuma em "Up".
```

Smoke test interno (via rede obs_net):

```bash
# Loki responde em /ready? (dentro da rede).
docker compose -f docker-compose.obs.yml exec promtail \
  wget -qO- http://loki:3100/ready

# Grafana servindo na porta 3001 do host.
curl -sI http://127.0.0.1:3001/api/health

# Uptime Kuma servindo na porta 3002 do host.
curl -sI http://127.0.0.1:3002/
```

## 4. Basic auth (.htpasswd) + IP allowlist

### 4.1 Gerar arquivo `.htpasswd-ops`

```bash
# Primeiro usuario (cria o arquivo). Use bcrypt (-B) em vez de MD5.
sudo htpasswd -B -c /etc/nginx/.htpasswd-ops levy

# Usuarios adicionais (sem -c para nao sobrescrever):
# sudo htpasswd -B /etc/nginx/.htpasswd-ops outro-op

# Permissoes: leitura pro usuario do Nginx.
sudo chown root:www-data /etc/nginx/.htpasswd-ops
sudo chmod 0640 /etc/nginx/.htpasswd-ops
```

### 4.2 Aplicar o server block do Nginx

1. Copiar `infra/nginx/ops.conf.example` para
   `/etc/nginx/sites-available/ops.conf`.
2. Substituir `<DOMINIO>` pelo dominio real.
3. Descomentar o bloco `allow ...; deny all;` e preencher com os CIDRs
   de `OPS_ALLOWED_IPS`. Deixar `satisfy all` (exige allowlist **E**
   basic auth — defesa em camadas).
4. Ativar e testar:

   ```bash
   sudo ln -sf /etc/nginx/sites-available/ops.conf /etc/nginx/sites-enabled/ops.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. Emitir o certificado TLS:

   ```bash
   sudo certbot --nginx -d ops.<DOMINIO> --non-interactive --agree-tos \
     -m ops@<DOMINIO> --redirect
   ```

   O certbot edita `ops.conf` inserindo as linhas `ssl_certificate*` no
   bloco 443 — aceite e rode `sudo nginx -t && sudo systemctl reload
   nginx` novamente.

## 5. Configurar Grafana

1. Abrir `https://ops.<DOMINIO>/grafana/` (vai pedir basic auth do
   Nginx primeiro, depois login Grafana com `GRAFANA_ADMIN_USER` /
   `GRAFANA_ADMIN_PASSWORD`).
2. Forcar troca de senha no primeiro login (Grafana obriga).
3. Validar datasource **Loki** em `Connections > Data sources`:
   - URL `http://loki:3100` (ja provisionada).
   - Clicar em **Test** — deve retornar "Data source connected and
     labels found".
4. Abrir o dashboard provisionado: `Dashboards > NFS-e > NFS-e — Logs
   API & Worker`. Deve mostrar logs, taxa de erro, fila RQ, ticks do
   scheduler, status final de execucoes, ocorrencias por codigo e status
   do backup Postgres. Paineis podem ficar vazios ate os services
   `nfse-api`/`nfse-worker` produzirem log — normal nesta fase.
5. Conferir os links de runbook no topo do dashboard. Devem apontar para
   fila travada, SSL expirando, backup falhou, refresh token/sessoes,
   migration falhou e restore completo.

> Para ajustar o dashboard sem perder o provisioning: editar o JSON em
> `infra/compose/grafana/dashboards/api-worker-logs.json` no repo,
> commitar, e rsync de volta pra VPS.

## 6. Configurar Uptime Kuma

1. Abrir `https://ops.<DOMINIO>/uptime/`. Primeiro acesso cria o
   admin local — use senha do cofre do owner.
2. Adicionar **4 monitores** (um para cada endpoint):

   | Nome | Tipo | URL / Host | Intervalo |
   |------|------|-----------|-----------|
   | site | HTTP(s) | `https://<DOMINIO>` | 60s |
   | app  | HTTP(s) | `https://app.<DOMINIO>` | 60s |
   | api  | HTTP(s) Keyword | `https://api.<DOMINIO>/health` keyword `"ok"` | 60s |
   | worker | HTTP(s) Keyword | `https://api.<DOMINIO>/healthz` keyword `"ok"` | 60s |

   > `worker` assume que o healthcheck do worker esta exposto via API
   > (CORE-04/INFRA-05). Se ainda nao existir, criar o monitor marcado
   > como **Paused** ate a rota ficar disponivel.

3. Em **Settings > Notifications > Setup Notification**:
   - Type: **Telegram**.
   - Bot Token: valor de `TELEGRAM_BOT_TOKEN`.
   - Chat ID: valor de `TELEGRAM_CHAT_ID`.
   - Marcar "Apply on all existing monitors".
4. Clicar em **Test** — uma mensagem deve chegar no chat do Telegram
   em segundos. Esse teste satisfaz o DoD "Alerta Telegram dispara em
   teste manual".

### 6.1 Como obter bot token e chat ID

1. Falar com `@BotFather` no Telegram, criar bot, copiar o token.
2. Criar o grupo/canal e adicionar o bot como admin.
3. Enviar uma mensagem no grupo e chamar
   `https://api.telegram.org/bot<TOKEN>/getUpdates` para ler o
   `chat.id` (negativo para grupos).

## 7. Verificacao final (Definition of Done)

Rodar no navegador / via CLI como `deploy`:

- [ ] **Grafana acessivel** em `https://ops.<DOMINIO>/grafana` com login
  funcional (basic auth Nginx + login Grafana).
- [ ] **Logs em tempo real**: abrir `Explore` no Grafana, selecionar
  datasource Loki, executar `{container_id=~".+"}` e ver linhas novas
  aparecendo em "Live" ou em "Last 5 minutes" conforme os containers
  produzem log.
- [ ] **Alerta Telegram**: botao "Test" da notificacao Uptime Kuma faz
  chegar mensagem no chat.

Quando os tres estiverem verdes, marcar o DoD do ticket.

## 8. Operacao

- **Retenção de logs no Loki**: 14 dias (`retention_period: 336h` em
  `loki-config.yml`). Suficiente para debug — logs de auditoria do SaaS
  ficam em `audit_logs` no Postgres (DATA-05), nao em Loki.
- **Backup**: o volume `/srv/nfse/prod/data/grafana` contem dashboards
  e usuarios — incluir no snapshot de `/srv/nfse/prod/data` do INFRA-08.
  Loki e Uptime Kuma ficam opcionais (reconstruiveis).
- **Atualizacao de imagem**: subir a versao no
  `docker-compose.obs.yml`, `docker compose pull && docker compose up -d`.
  Grafana respeita migrations automaticas de versao minor.
- **Rotacao de senha basic auth**: rodar `sudo htpasswd -B
  /etc/nginx/.htpasswd-ops <user>` e comunicar o time.
- **Revogar acesso**: `sudo htpasswd -D /etc/nginx/.htpasswd-ops <user>`
  + remover IP da allowlist no `ops.conf` + `nginx -t && reload`.
- **Exportar dashboard** (antes de editar muito na UI): `Share > Export
  > Save to file` e salvar sobre
  `infra/compose/grafana/dashboards/api-worker-logs.json` no repo.

## 9. Runbooks de infra e suporte (DOCS-05)

Os runbooks operacionais ficam em `docs/runbooks/`:

| Cenario | Runbook | Alerta correspondente |
|---------|---------|-----------------------|
| Disco cheio na VPS | `docs/runbooks/disco-cheio.md` | Uptime Kuma caindo em cascata + log `no space left` via Loki |
| Fila RQ travada / worker off | `docs/runbooks/fila-travada.md` | Monitor `worker` em `/healthz` (Uptime Kuma) |
| Cert TLS expirando | `docs/runbooks/ssl-expirando.md` | "Certificate Expiry Notification" dos monitores Uptime Kuma |
| Backup do Postgres falhou | `docs/runbooks/backup-falhou.md` | `systemctl --failed` + linha JSON `status="failed"` em `backup-postgres.log` |
| Refresh token/revogacao de sessoes | `docs/runbooks/sessoes-refresh-token.md` | suspeita de replay/acesso indevido |
| Migration/Alembic falhou | `docs/runbooks/migration-falhou.md` | deploy `migrate` falhou |
| Restore completo | `docs/runbooks/restore-completo.md` | DR drill ou desastre real |
| Credencial invalida/certificado vencido | `docs/runbooks/checklist-credencial-invalida.md` | occurrences `CRED_INVALID`, `CERT_EXPIRED`, `CERT_EXPIRING` |
| Simulacao de incidentes | `docs/runbooks/incident-simulation-checklist.md` | validacao pre go-live dos runbooks |

O contrato de alertas versionado fica em `infra/observability-alerts.md`.

### 9.1 Links no dashboard Grafana

O dashboard `NFS-e — Logs API & Worker` ja lista os 4 runbooks no topo
(menu de links do dashboard). Os links sao provisionados pelo arquivo
`infra/compose/grafana/dashboards/api-worker-logs.json` (`"links"` no
root do JSON) e apontam para a versao em `main` no GitHub. Ao editar
pela UI, reexportar e salvar sobre o arquivo para nao perder o link.

### 9.2 Runbook URL nos monitores Uptime Kuma

Para cada monitor (`site` / `app` / `api` / `worker`), preencher o campo
**Description** com a URL do runbook correspondente. O Uptime Kuma
inclui a descricao no payload do Telegram — o operador que recebe o
alerta chega direto no runbook.

Exemplo (monitor `worker`):

```
Runbook: https://github.com/levyoliveiraopu/nfse-collector_v04/blob/main/docs/runbooks/fila-travada.md
```

Ativar tambem a opcao **Certificate Expiry Notification** em cada um
dos monitores HTTPs — dispara Telegram a 14/7/3 dias do vencimento com
link para `ssl-expirando.md` (via campo Description).

### 9.3 Alert rules Grafana/Uptime Kuma

As regras obrigatorias e queries LogQL de referencia estao em
`infra/observability-alerts.md`. Ao criar uma rule em cima do Loki,
cada rule **deve** ter `runbook_url` em `annotations`:

```yaml
# Exemplo de alert rule Grafana (formato JSON/YAML provisionado):
annotations:
  summary: "Taxa de erros alta no worker"
  description: "count_over_time({container_id=\"nfse-worker\"} |~ \"(?i)error\" [5m]) > 20"
  runbook_url: "https://github.com/levyoliveiraopu/nfse-collector_v04/blob/main/docs/runbooks/fila-travada.md"
```

A UI do Grafana renderiza `runbook_url` como botao "Run book" na
pagina do alerta.
