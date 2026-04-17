# Runbook — certificado TLS expirando ou renovacao quebrada

> Alvo: Nginx host (INFRA-04) servindo os 5 hostnames com certificado
> Let's Encrypt emitido via `certbot --nginx`. Renovacao automatica pelo
> `certbot.timer` (systemd).

## Escopo

Use este runbook quando:

- Um dos 5 hostnames esta a <=30 dias do vencimento e a renovacao
  automatica nao aconteceu.
- `certbot renew` manual falha.
- Uptime Kuma / navegador reporta `SSL_ERROR_EXPIRED` ou
  `NET::ERR_CERT_DATE_INVALID`.
- HSTS ativo + cert vencido deixa o dominio inacessivel (mitigar rapido).

Os 5 hostnames cobertos pelo cert SAN unico (ver `infra/nginx.md`):
`<DOMINIO>`, `www.<DOMINIO>`, `app.<DOMINIO>`, `api.<DOMINIO>`,
`ops.<DOMINIO>`.

## 1. Como detectar

### 1.1 Fontes de alerta

- **Uptime Kuma** (INFRA-07): monitores HTTPs tem opcao "Certificate
  Expiry Notification" — Uptime Kuma alerta por Telegram a 14 dias do
  vencimento. **Confirmar que a notificacao esta ligada em cada monitor
  (site/app/api/worker)**.
- **Browser / cliente**: usuarios relatam pagina recusada por cert
  invalido.
- **Alerta futuro** (Grafana): log query em Loki sobre stderr do Nginx
  filtrando "certificate has expired" pode virar alerta; anexar
  `runbook_url` apontando para este arquivo.

### 1.2 Checagem manual

```bash
# Por hostname — reporta notAfter.
for H in <DOMINIO> www.<DOMINIO> app.<DOMINIO> api.<DOMINIO> ops.<DOMINIO>; do
  echo "== $H =="
  echo | openssl s_client -servername "$H" -connect "$H:443" 2>/dev/null \
    | openssl x509 -noout -subject -issuer -dates
done

# Via certbot (consulta o estado local).
sudo certbot certificates
```

```bash
# Timer ativo e rodou recentemente?
systemctl list-timers certbot.timer
sudo journalctl -u certbot.timer --since "7 days ago" --no-pager | tail -50
sudo journalctl -u certbot.service --since "7 days ago" --no-pager | tail -100
```

> Gatilho: agir quando `notAfter` estiver a <=30 dias de hoje, ou quando
> `certbot renew --dry-run` falhar.

## 2. Diagnostico

### 2.1 Por que a renovacao nao aconteceu?

Causas comuns:

1. **DNS mudou** (A record nao aponta mais pra VPS) — desafio HTTP-01
   falha.
2. **Cloudflare com proxy ativado** (laranja em vez de cinza) nos
   hostnames `api`/`ops` — INFRA-03 exige DNS-only para preservar TLS
   end-to-end. Proxy ativo quebra ACME.
3. **Nginx parado ou com config invalida** — certbot nao consegue servir
   `/.well-known/acme-challenge/`.
4. **Rate limit do Let's Encrypt** — exagero em re-emissao (50 certs por
   domain/semana).
5. **Webroot com permissao errada** — `/var/www/letsencrypt/` precisa
   existir e ser legivel pelo `www-data`.
6. **`--redirect` cobrindo o path ACME** — raro, mas o plugin `nginx`
   normalmente exclui. Conferir em `nginx -T | grep -A5 letsencrypt`.

### 2.2 Simular a renovacao

```bash
# Dry-run — nao consome quota Let's Encrypt.
sudo certbot renew --dry-run

# Verbose quando nao der.
sudo certbot renew --dry-run --verbose 2>&1 | tee /tmp/certbot-dryrun.log
```

Erros tipicos:

- `DNS problem: NXDOMAIN looking up A for <dominio>` -> conferir
  registro DNS.
- `Cloudflare` no header -> proxy ativado; desligar.
- `Timeout during connect` -> porta 80 fechada no firewall/UFW, ou
  Nginx sem bloco `80 default_server`.
- `too many failed authorizations` -> rate limit; aguardar.

### 2.3 Cert individual a ponto de expirar com renovacao saudavel?

Se `certbot renew --dry-run` passa mas o certificado em produção esta
antigo, provavelmente o Nginx nao foi recarregado apos a renovacao:

```bash
# Ver o arquivo de cert servido (data de modificacao recente =
# renovacao ok; Nginx precisa reload para carregar).
sudo ls -la /etc/letsencrypt/live/<DOMINIO>/fullchain.pem

# Timestamp do ultimo reload do Nginx.
systemctl show nginx -p ActiveEnterTimestamp
```

## 3. Mitigacao

### 3.1 Renovar manualmente (caminho feliz)

```bash
sudo certbot renew --force-renewal
sudo nginx -t && sudo systemctl reload nginx
```

Validar:

```bash
echo | openssl s_client -servername api.<DOMINIO> -connect api.<DOMINIO>:443 2>/dev/null \
  | openssl x509 -noout -dates
```

### 3.2 Cloudflare com proxy ligado

1. Painel Cloudflare -> DNS -> clicar na nuvem laranja dos hostnames
   afetados para virar cinza (DNS-only).
2. Aguardar ~60s.
3. `sudo certbot renew --force-renewal`.
4. `sudo systemctl reload nginx`.

### 3.3 Nginx sem responder no webroot

```bash
# Testar se o challenge path serve um arquivo qualquer.
sudo install -d /var/www/letsencrypt/.well-known/acme-challenge
echo ok | sudo tee /var/www/letsencrypt/.well-known/acme-challenge/test
curl -I http://api.<DOMINIO>/.well-known/acme-challenge/test
# Esperado 200. Se 404 -> falta bloco de location no server 80.
sudo rm /var/www/letsencrypt/.well-known/acme-challenge/test
```

Se 404, conferir `infra/nginx/` (INFRA-04) — deve existir um `location
/.well-known/acme-challenge/` apontando para `/var/www/letsencrypt/`.

### 3.4 Reemitir do zero (quando o cert esta corrompido)

```bash
# Ler o nome do cert atual.
sudo certbot certificates | grep -A1 "Certificate Name"

# Revogar (opcional).
sudo certbot revoke --cert-name <nome>

# Emitir de novo cobrindo todos os 5 hostnames.
sudo certbot --nginx \
  -d <DOMINIO> -d www.<DOMINIO> -d app.<DOMINIO> -d api.<DOMINIO> -d ops.<DOMINIO> \
  --redirect --non-interactive --agree-tos -m ops@<DOMINIO>
```

### 3.5 Mitigacao de ultima hora (HSTS ativo + cert vencido)

Usuarios com HSTS preload no navegador nao conseguem mais acessar nem
por HTTP. Nao ha bypass remoto — so emitindo cert novo. Enquanto isso,
ignorar o domain afetado e usar um hostname alternativo (se existir) —
ou limpar HSTS localmente no navegador do cliente afetado
(chrome: `chrome://net-internals/#hsts`).

Motivo adicional para **manter HSTS desligado ate estar 100% confiante
no processo de renovacao** — recomendacao do runbook `infra/nginx.md`.

## 4. Prevencao

- [ ] **`certbot.timer` ativo**: `systemctl is-enabled certbot.timer`
  -> `enabled`.
- [ ] **Dry-run mensal**: `sudo certbot renew --dry-run` em rotina
  mensal como parte do health check de operacao.
- [ ] **Uptime Kuma com "Certificate Expiry Notification"**: habilitar
  em **cada** um dos 4 monitores HTTPs; default dispara 14/7/3 dias
  antes.
- [ ] **Cloudflare DNS-only** nos 5 hostnames — preservado desde
  INFRA-03. Conferir quando adicionar hostname novo.
- [ ] **HSTS desligado** enquanto o processo nao esta 100% testado
  (comentado em `infra/nginx/security-headers.conf` — so ligar depois
  de 2 renovacoes automaticas bem-sucedidas).
- [ ] **Quota Let's Encrypt**: nao re-emitir em loop. Em caso de bug,
  usar `--staging` para debugar (emite contra ACME de teste, sem
  consumir quota real).

## Referencias

- `infra/nginx.md` — setup do Nginx + certbot + HSTS.
- `infra/nginx/security-headers.conf` — bloco HSTS (comentado por
  padrao).
- `infra/dns.md` / ADR-005 — DNS-only Cloudflare.
- `docs/runbooks/disco-cheio.md` — eventualmente o certbot falha por
  disco cheio em `/etc/letsencrypt`; triangular com este runbook.
