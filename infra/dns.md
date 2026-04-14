# DNS no Cloudflare (INFRA-03)

Runbook manual para configurar os subdominios do stack NFS-e SaaS na
Cloudflare apontando para a VPS Hostinger (ADR-005).

> **Execucao:** este runbook e executado pelo owner no painel Cloudflare.
> Os comandos **nao** rodam em CI. O DoD do ticket so e marcado apos os
> checks `dig` da secao 6 passarem contra a zona real.

## 0. Placeholders

Substitua nos comandos abaixo — **nao commitar valores reais** neste repo:

- `${DOMAIN}` — dominio temporario atualmente em uso (sera migrado quando
  o nome comercial definitivo sair; ver secao 7).
- `${VPS_IP}` — IP publico IPv4 da VPS Hostinger (painel Hostinger).
- `${VPS_IP6}` — IP publico IPv6 da VPS, **se** habilitado (opcional).

## 1. Pre-requisitos

- Dominio temporario ja delegado a Cloudflare (nameservers `*.ns.cloudflare.com`
  configurados no registrar).
- Zona ativa na conta Cloudflare do owner.
- VPS Hostinger com IPv4 publico estavel (INFRA-01 concluido).
- Acesso ao painel Cloudflare **ou** token de API com escopo `Zone:DNS:Edit`
  na zona alvo.

## 2. Registros a criar

Criar cinco registros A (e opcionalmente cinco AAAA se IPv6 estiver ativo
na VPS). Todos apontam para o mesmo IP da VPS.

| Tipo | Nome            | Destino      | Proxy Cloudflare | TTL  | Observacao                    |
|------|-----------------|--------------|------------------|------|-------------------------------|
| A    | `@` (apex)      | `${VPS_IP}`  | Proxied (laranja)| Auto | site institucional futuro     |
| A    | `www`           | `${VPS_IP}`  | Proxied (laranja)| Auto | redireciona para apex         |
| A    | `app`           | `${VPS_IP}`  | Proxied (laranja)| Auto | painel Next.js (`apps/web-app`)|
| A    | `api`           | `${VPS_IP}`  | **DNS only (cinza)** | Auto | FastAPI + mTLS ADN — ver §3 |
| A    | `ops`           | `${VPS_IP}`  | **DNS only (cinza)** | Auto | observabilidade + mTLS — ver §3 |

## 3. Por que `api` e `ops` ficam em DNS-only (CRITICO)

O worker de coleta NFS-e autentica nas prefeituras (ADN) via **mTLS** com
certificado digital **A1 (PFX)** do tenant (ADR-003). Se o subdominio
passar pelo proxy Cloudflare (nuvem laranja), o TLS e terminado na
Cloudflare — a prefeitura veria o certificado da Cloudflare, nao o PFX do
tenant, e a handshake mTLS falha. O mesmo vale para qualquer rota
administrativa em `ops` que exponha endpoints com TLS cliente.

Portanto **`api` e `ops` precisam ser Proxy = DNS only (cinza)** — o
trafego vai direto para a VPS, onde o Nginx host termina TLS e repassa
para os containers (Compose) com o PFX do tenant sendo usado pelo worker
na saida.

`app`, `www` e apex podem (e devem) usar proxy laranja: cacheiam estaticos,
escondem IP de origem e aplicam WAF basico.

## 4. Aplicacao via UI (Cloudflare Dashboard)

1. Abrir `https://dash.cloudflare.com/` → selecionar a zona `${DOMAIN}`.
2. Menu **DNS → Records → Add record**.
3. Para cada linha da tabela da secao 2:
   - **Type:** `A`
   - **Name:** `@`, `www`, `app`, `api` ou `ops`
   - **IPv4 address:** `${VPS_IP}`
   - **Proxy status:** conforme tabela (laranja para apex/www/app,
     cinza para api/ops)
   - **TTL:** Auto
   - Save.
4. Repetir para IPv6 com tipo `AAAA` e `${VPS_IP6}` **se** a VPS tiver
   IPv6 publico. Caso contrario, nao criar AAAA — evita ter hosts
   anunciando endereco que nao responde.
5. Em **DNS → Settings**, confirmar:
   - **DNSSEC:** enabled (opcional mas recomendado — copiar o DS record
     para o registrar).
   - **CNAME Flattening:** padrao (so afeta se no futuro trocarmos apex
     por CNAME).

## 5. Aplicacao via API (referencia alternativa)

Util para automacao futura e para documentar o que a UI faz. Requer
`CF_API_TOKEN` com `Zone:DNS:Edit` e `CF_ZONE_ID` (aba **Overview** da
zona). **Nao commitar o token** — usar variavel de ambiente local:

```bash
# Listar registros atuais
curl -s -H "Authorization: Bearer ${CF_API_TOKEN}" \
  "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records?type=A" \
  | jq '.result[] | {name,content,proxied}'

# Helper: cria um registro A
create_a() {
  local name="$1" proxied="$2"
  curl -s -X POST -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records" \
    --data "{\"type\":\"A\",\"name\":\"${name}\",\"content\":\"${VPS_IP}\",\"ttl\":1,\"proxied\":${proxied}}"
}

create_a "${DOMAIN}"        true     # apex
create_a "www.${DOMAIN}"    true
create_a "app.${DOMAIN}"    true
create_a "api.${DOMAIN}"    false    # DNS only — mTLS
create_a "ops.${DOMAIN}"    false    # DNS only — mTLS
```

## 6. Verificacao (Definition of Done)

Rodar do host do operador (qualquer maquina fora da VPS):

```bash
# [x] Resolucao dos cinco nomes retorna o IP da VPS
dig +short app.${DOMAIN}
dig +short api.${DOMAIN}
dig +short ops.${DOMAIN}
dig +short www.${DOMAIN}
dig +short ${DOMAIN}
# Cada linha deve imprimir: ${VPS_IP}
# (Se proxied, vira IP da Cloudflare — verificar na secao abaixo.)

# [x] api e ops estao em DNS-only (resolvem direto para ${VPS_IP},
#     NAO para faixa Cloudflare 104.16.0.0/12 ou 172.64.0.0/13)
for host in api ops; do
  ip=$(dig +short ${host}.${DOMAIN} | tail -n1)
  echo "${host}.${DOMAIN} -> ${ip}"
  [ "${ip}" = "${VPS_IP}" ] && echo "  OK (DNS only)" \
    || echo "  FALHA — proxy esta ativo, desabilitar!"
done

# [x] apex / www / app podem estar atras do proxy (IPs Cloudflare)
for host in @ www app; do
  name="${host/@/${DOMAIN}}"
  [ "${host}" = "@" ] || name="${host}.${DOMAIN}"
  dig +short "${name}"
done
# Esperado: IPs Cloudflare (104.x / 172.x) — nao e obrigatorio, mas e o padrao recomendado.

# [x] Headers confirmam proxy-off em api/ops (apos a VPS subir Nginx)
curl -sI "https://api.${DOMAIN}/health" | grep -iE '^(server|cf-ray):'
# Esperado: Server: nginx (sem header cf-ray). Se aparecer 'cf-ray', o
# proxy esta ativo e precisa ser desligado.
```

Quando os tres blocos acima estiverem verdes, marcar o DoD do ticket
INFRA-03.

## 7. Migracao para o dominio definitivo

Quando o nome comercial sair (pendencia registrada em `STATE.md` → "Pendencias
de Decisao"), recriar esta mesma zona no dominio novo:

1. Adicionar o novo dominio na Cloudflare e apontar NS no registrar.
2. Recriar os cinco registros desta tabela apontando para `${VPS_IP}`.
3. Configurar os mesmos flags de proxy (DNS-only em api/ops).
4. Atualizar `NEXT_PUBLIC_APP_URL`, `API_CORS_ORIGINS` e variaveis de
   ambiente equivalentes nos apps e no Compose.
5. Manter a zona antiga por >= 7 dias com redirect 301 no apex/www para
   o novo dominio, enquanto caches TTL expiram.
6. Apos 30 dias sem trafego na zona antiga, remover a zona da Cloudflare
   e liberar o registro no registrar.

## 8. Notas de seguranca

- **Nao** commitar `${DOMAIN}` temporario, `${VPS_IP}` nem `CF_API_TOKEN`
  neste repo. Placeholders em documentos, valores reais em `.env` local
  e no cofre do owner.
- Habilitar **DNSSEC** na zona e inserir o DS record no registrar — uma
  das mitigacoes mais baratas contra hijack do dominio.
- Habilitar **Always Use HTTPS** e **Automatic HTTPS Rewrites** apenas
  nas subdomains em proxy laranja (apex/www/app). Em api/ops o TLS e
  servido pelo Nginx da VPS (Let's Encrypt via certbot — INFRA-04/05).
- Restringir acesso ao painel Cloudflare com 2FA obrigatorio e API
  tokens com escopo minimo (`Zone:DNS:Edit` na zona especifica, nunca
  tokens globais).
- Se o IP da VPS mudar (troca de plano Hostinger, failover), atualizar
  os cinco registros em um unico passo — considerar script automatizado
  com a API quando a operacao se repetir.
