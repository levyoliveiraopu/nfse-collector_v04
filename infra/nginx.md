# Nginx no host + Let's Encrypt (INFRA-04)

Runbook manual para instalar **Nginx no host** da VPS Hostinger (nao em
container), publicar os 4 subdominios (+apex) com HTTPS via Let's Encrypt
e renovacao automatica (ADR-005).

> **Execucao:** este runbook e executado pelo owner via SSH na VPS real
> (usuario `deploy`). Os comandos **nao** rodam em CI. O DoD so e marcado
> apos os checks da secao 9 passarem.

## 0. Pre-requisitos

- INFRA-01 concluido (VPS Ubuntu 24.04, `deploy` + SSH chave-only + UFW).
- INFRA-02 concluido (Docker + Compose + diretorios em `/srv/nfse/`).
- INFRA-03 concluido (DNS Cloudflare propagado com `api` e `ops` em
  **DNS-only** — requisito de mTLS para as prefeituras, ADR-003).
- Confirmacao da distro:

  ```bash
  . /etc/os-release && echo "$ID $VERSION_CODENAME"   # esperado: ubuntu noble
  ```

- Placeholders usados abaixo (nao commitar valores reais):
  - `${DOMAIN}` — dominio temporario em uso (zona Cloudflare).
  - `${OWNER_EMAIL}` — e-mail do owner para registro Let's Encrypt.
  - `${VPS_IP}` — IP publico da VPS (conferir com `curl -4 ifconfig.me`).

## 1. Abrir portas 80/443 no UFW

```bash
sudo ufw status numbered                    # conferir estado
sudo ufw allow 80/tcp  comment 'HTTP acme + redirect'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw reload
sudo ufw status verbose                     # DoD: 80/tcp e 443/tcp ALLOW
```

## 2. Instalar Nginx + Certbot (pacotes oficiais Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

nginx -v           # esperado: nginx/1.24.x (Ubuntu 24.04)
certbot --version  # esperado: certbot 2.x
```

Confirmar que o servico subiu:

```bash
sudo systemctl enable --now nginx
sudo systemctl status nginx --no-pager
curl -s http://127.0.0.1/ | head -n 5      # "Welcome to nginx" padrao
```

## 3. Preparar diretorio do webroot ACME e do placeholder

Certbot usa `http-01` no webroot `/var/www/letsencrypt/` para renovacoes
sem downtime. O placeholder "em breve" vive em `/var/www/em-breve/`.

```bash
sudo mkdir -p /var/www/letsencrypt /var/www/em-breve
sudo chown root:root /var/www/letsencrypt /var/www/em-breve
sudo chmod 0755 /var/www/letsencrypt /var/www/em-breve

# Copiar o HTML do repo (assumindo repo clonado em /srv/nfse/prod/repo)
sudo cp /srv/nfse/prod/repo/infra/nginx/placeholders/em-breve.html \
        /var/www/em-breve/em-breve.html
sudo chmod 0644 /var/www/em-breve/em-breve.html
```

## 4. Aplicar os arquivos de configuracao

Este repo versiona a config em `infra/nginx/`. Vamos copiar para
`/etc/nginx/` — **sem** symlink, para evitar que um `git pull`
acidental quebre o nginx em prod.

```bash
REPO=/srv/nfse/prod/repo          # ajuste se seu clone fica em outro path

# Backup do nginx.conf original (rollback)
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak.$(date +%F)

# nginx.conf principal (overrides globais)
sudo cp "$REPO/infra/nginx/nginx.conf" /etc/nginx/nginx.conf

# Snippets compartilhados
sudo mkdir -p /etc/nginx/snippets
sudo cp "$REPO/infra/nginx/snippets/"*.conf /etc/nginx/snippets/

# Sites
sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
sudo cp "$REPO/infra/nginx/sites-available/"*.conf /etc/nginx/sites-available/

# Substituir DOMAIN.EXAMPLE pelo dominio real (SO dentro de sites-available)
sudo sed -i "s/DOMAIN\.EXAMPLE/${DOMAIN}/g" /etc/nginx/sites-available/*.conf

# Ativar cada site
for site in apex www app api ops; do
  sudo ln -sf /etc/nginx/sites-available/${site}.conf \
              /etc/nginx/sites-enabled/${site}.conf
done

# Remover default que o Ubuntu ativa
sudo rm -f /etc/nginx/sites-enabled/default

# Validar sintaxe
sudo nginx -t
```

Se `nginx -t` reclamar de `ssl_certificate` ausente, tudo bem — seguir
para a secao 6 (certbot cria os certs e o Nginx volta a validar).
Para destravar o `nginx -t` enquanto os certs nao existem, comentar
temporariamente os server blocks 443 via:

```bash
sudo sed -i 's/^    listen      443 /    # listen      443 /; s/^    listen      \[::\]:443 /    # listen      \[::\]:443 /' \
  /etc/nginx/sites-enabled/*.conf
sudo nginx -t && sudo systemctl reload nginx
```

Depois do certbot (secao 6), reverter o comentario ou deixar o proprio
certbot reescrever os `listen 443` com os paths de cert.

## 5. Gerar parametros Diffie-Hellman (2048 bits)

```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048
sudo chmod 0600 /etc/nginx/ssl/dhparam.pem
```

Descomentar a linha `ssl_dhparam` em `/etc/nginx/snippets/tls.conf`.

## 6. Emitir certificados com Certbot (`--nginx`)

Um unico cert cobrindo os cinco hostnames (SAN). Let's Encrypt rejeita
hostnames sem DNS propagado, entao confirme os `dig` de INFRA-03 antes.

```bash
# Test run primeiro (staging) — evita gastar quota em caso de erro.
sudo certbot --nginx \
  --staging \
  --non-interactive \
  --agree-tos \
  --email ${OWNER_EMAIL} \
  -d ${DOMAIN} \
  -d www.${DOMAIN} \
  -d app.${DOMAIN} \
  -d api.${DOMAIN} \
  -d ops.${DOMAIN}

# Apos validar que funcionou no staging, revogar e emitir em producao.
sudo certbot delete --cert-name ${DOMAIN}   # limpa certs de staging

sudo certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email ${OWNER_EMAIL} \
  --redirect \
  -d ${DOMAIN} \
  -d www.${DOMAIN} \
  -d app.${DOMAIN} \
  -d api.${DOMAIN} \
  -d ops.${DOMAIN}
```

Flags relevantes:

- `--nginx` — usa o plugin que **edita os server blocks** adicionando
  `ssl_certificate`/`ssl_certificate_key` e um redirect HTTP->HTTPS.
- `--redirect` — forca HTTP→HTTPS em todos os hostnames.
- `--non-interactive --agree-tos --email` — nao trava no prompt, util
  para reexecucoes automatizadas.

Conferir o cert emitido:

```bash
sudo certbot certificates
# Esperado: 1 certificado chamado ${DOMAIN}, com 5 SANs.
```

## 7. Ativar o timer de renovacao

O pacote `certbot` do Ubuntu instala automaticamente `certbot.timer`
(systemd) que roda `certbot renew` 2x/dia. Validar:

```bash
systemctl list-timers certbot.timer --no-pager
# Esperado: NEXT em <24h, UNIT=certbot.timer, ACTIVATES=certbot.service

sudo systemctl enable --now certbot.timer
sudo systemctl status certbot.timer --no-pager

# DoD: dry-run deve passar SEM modificar nada.
sudo certbot renew --dry-run
# Esperado: "Congratulations, all simulated renewals succeeded"
```

Reload do nginx pos-renovacao e automatico (plugin `--nginx` instala um
hook). Confirmar com:

```bash
ls /etc/letsencrypt/renewal-hooks/deploy/
# Se estiver vazio, criar:
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh >/dev/null <<'SH'
#!/bin/sh
systemctl reload nginx
SH
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

## 8. Ativar HSTS (pos-emissao)

Depois que todos os 5 hostnames responderem `HTTP/2 200` em HTTPS,
descomentar a linha `Strict-Transport-Security` em
`/etc/nginx/snippets/security-headers.conf` e recarregar:

```bash
sudo sed -i 's|^# add_header Strict-Transport-Security|add_header Strict-Transport-Security|' \
  /etc/nginx/snippets/security-headers.conf

sudo nginx -t && sudo systemctl reload nginx
```

**Nao** incluir `preload` enquanto o nome comercial definitivo (SITE-*)
nao sair — preload e irreversivel.

## 9. Checks de Definition of Done

```bash
# [x] nginx -t verde
sudo nginx -t

# [x] HTTP responde 301 (redirect para HTTPS) em todos os hostnames
for h in ${DOMAIN} www.${DOMAIN} app.${DOMAIN} api.${DOMAIN} ops.${DOMAIN}; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -I "http://${h}/")
  echo "${h}: HTTP ${code}"
  [ "${code}" = "301" ] || echo "  FALHA"
done

# [x] HTTPS responde 200 ou 503 placeholder em todos os hostnames
for h in ${DOMAIN} www.${DOMAIN} app.${DOMAIN} api.${DOMAIN} ops.${DOMAIN}; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -I "https://${h}/")
  echo "${h}: HTTPS ${code}"
done
# Esperado: app/www/ops/apex -> 200 (em breve). api -> 503 (em breve).

# [x] Headers de seguranca presentes
curl -sI "https://www.${DOMAIN}/" | grep -iE '^(strict-transport|x-frame-options|x-content-type|referrer-policy|permissions-policy):'

# [x] HTTP/2 negociado
curl -sI --http2 "https://app.${DOMAIN}/" | head -n 1
# Esperado: HTTP/2 200

# [x] Rate limit em /auth/* — 6a requisicao em <1s retorna 429
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  curl -sS -o /dev/null -w "req ${i}: %{http_code}\n" "https://api.${DOMAIN}/auth/login"
done | tail
# Esperado: alguns 429 apos o burst.

# [x] Renovacao automatica OK
sudo certbot renew --dry-run

# [x] SSL Labs — rodar manualmente (browser) em cada hostname:
#     https://www.ssllabs.com/ssltest/analyze.html?d=app.${DOMAIN}
#     Esperado: nota A (ou superior) nos 5 hostnames.
```

Quando tudo estiver verde, marcar DoD do INFRA-04.

## 10. Troubleshooting

- **`nginx -t` reclama `"ssl_certificate"` nao encontrado:** ainda nao
  rodou o certbot, ou certbot falhou. Conferir `/etc/letsencrypt/live/${DOMAIN}/`.
- **Certbot `Timeout during connect`:** DNS nao propagou (INFRA-03) ou
  UFW bloqueou a porta 80. `dig +short ${DOMAIN}` deve bater com `${VPS_IP}`.
- **429 aparecendo em lugar errado:** `limit_req` foi colocado no
  `location /` em vez de `location ^~ /auth/`. So o `^~ /auth/` deve
  ter `limit_req`.
- **Cloudflare em `api`/`ops` proxyado (laranja):** o TLS e terminado na
  Cloudflare e o mTLS das prefeituras quebra. Voltar esses dois para
  DNS-only (cinza) — INFRA-03 secao 3.
- **HSTS ativo antes do cert:** browsers ficam presos a HTTPS quebrado.
  Se aconteceu, desativar HSTS no nginx, esperar `max-age` expirar
  (default 1 ano...) — evite esse cenario.

## 11. Estrutura dos arquivos versionados

```
infra/nginx/
├── nginx.conf                         # overrides globais (http block)
├── snippets/
│   ├── connection-upgrade.conf        # map $http_upgrade $connection_upgrade
│   ├── tls.conf                       # TLS 1.2+, ciphers, stapling
│   ├── security-headers.conf          # HSTS (off), X-Frame, Referrer, etc
│   ├── rate-limit.conf                # limit_req_zone auth_ip 5r/s
│   └── proxy-common.conf              # headers + timeouts de reverse proxy
├── sites-available/
│   ├── apex.conf                      # ${DOMAIN} -> redirect www
│   ├── www.conf                       # www.${DOMAIN} -> placeholder
│   ├── app.conf                       # app.${DOMAIN} -> placeholder / proxy 3000
│   ├── api.conf                       # api.${DOMAIN} -> placeholder / proxy 8000 + rate limit
│   └── ops.conf                       # ops.${DOMAIN} -> placeholder
└── placeholders/
    └── em-breve.html                  # HTML estatico "Em breve"
```

Quando INFRA-05 subir o Compose, os `proxy_pass` comentados em
`app.conf` / `api.conf` sao descomentados e os `try_files` do
placeholder saem.
