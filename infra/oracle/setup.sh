#!/usr/bin/env bash
# =============================================================================
# setup.sh — instalacao 1-comando do NFS-e SaaS numa VM unica (self-host).
#
# Pensado para uma VM Ubuntu 22.04/24.04 (ex: Oracle Cloud Always Free ARM),
# mas serve para qualquer VPS. Sobe TODA a stack com HTTPS automatico e
# storage S3 local (MinIO) — sem nenhum servico externo pago.
#
# Uso:
#   ./setup.sh <dominio> <email>
#   ./setup.sh nfse-teste.duckdns.org voce@gmail.com
#
# Tambem aceita via variaveis de ambiente:
#   DOMAIN=... ACME_EMAIL=... ./setup.sh
#
# Idempotente: se ja existir um .env, os segredos sao preservados. Rode de
# novo a vontade para aplicar mudancas de codigo (rebuild + up).
# =============================================================================
set -euo pipefail

# --- localizacao ------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/infra/compose"
ENV_PATH="$COMPOSE_DIR/.env"
EXAMPLE_PATH="$COMPOSE_DIR/.env.selfhost.example"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

# --- argumentos -------------------------------------------------------------
DOMAIN="${1:-${DOMAIN:-}}"
ACME_EMAIL="${2:-${ACME_EMAIL:-}}"

if [ -z "$DOMAIN" ]; then
  read -rp "Dominio publico (ex: nfse-teste.duckdns.org): " DOMAIN
fi
if [ -z "$ACME_EMAIL" ]; then
  read -rp "E-mail para o Let's Encrypt: " ACME_EMAIL
fi
[ -n "$DOMAIN" ] || die "dominio obrigatorio."
[ -n "$ACME_EMAIL" ] || die "e-mail obrigatorio."

# --- docker -----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Docker nao encontrado; instalando via get.docker.com ..."
  curl -fsSL https://get.docker.com | sh
  sudo systemctl enable --now docker || true
  if [ -n "${SUDO_USER:-}" ]; then sudo usermod -aG docker "$SUDO_USER" || true; fi
fi

# usa sudo no docker se o usuario atual nao tiver acesso ao daemon
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
  else
    die "docker instalado mas o daemon nao responde. Rode: sudo systemctl start docker"
  fi
fi
$DOCKER compose version >/dev/null 2>&1 || die "plugin 'docker compose' ausente. Reinstale o Docker (get.docker.com)."

# --- firewall do SO (Oracle Ubuntu bloqueia tudo menos 22 por padrao) -------
open_port() {
  local p="$1"
  if command -v iptables >/dev/null 2>&1; then
    if ! sudo iptables -C INPUT -p tcp --dport "$p" -j ACCEPT >/dev/null 2>&1; then
      sudo iptables -I INPUT -p tcp --dport "$p" -j ACCEPT || warn "nao consegui abrir a porta $p no iptables"
    fi
  fi
}
log "Abrindo portas 80, 443 e 8443 no firewall do SO ..."
open_port 80; open_port 443; open_port 8443
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save >/dev/null 2>&1 || true
else
  # tenta persistir sem o pacote extra
  sudo bash -c 'iptables-save > /etc/iptables/rules.v4' 2>/dev/null || true
fi
warn "Lembre-se: abra tambem 80, 443 e 8443 na Security List da VCN no console da Oracle (ingress 0.0.0.0/0)."

# --- .env (gera segredos so na primeira vez) --------------------------------
rand_hex()   { openssl rand -hex "${1:-24}"; }
rand_b64()   { openssl rand -base64 "${1:-48}" | tr -d '\n'; }
rand_b64url(){ openssl rand -base64 "${1:-32}" | tr '+/' '-_' | tr -d '\n'; }

if [ ! -f "$ENV_PATH" ]; then
  log "Gerando $ENV_PATH com senhas/segredos aleatorios ..."
  command -v openssl >/dev/null 2>&1 || die "openssl nao encontrado (instale: sudo apt-get install -y openssl)."
  cp "$EXAMPLE_PATH" "$ENV_PATH"

  PGPASS="$(rand_hex 24)"
  REDISPASS="$(rand_hex 24)"
  JWT="$(rand_b64 48)"
  KEK="$(rand_b64url 32)"
  S3KEY="nfse$(rand_hex 6)"
  S3SECRET="$(rand_hex 24)"

  # delimitador '|' no sed: base64/hex nunca contem '|'
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|"                 "$ENV_PATH"
  sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDISPASS}|"                    "$ENV_PATH"
  sed -i "s|^API_JWT_SECRET=.*|API_JWT_SECRET=${JWT}|"                          "$ENV_PATH"
  sed -i "s|^API_CREDENTIAL_KEK_B64=.*|API_CREDENTIAL_KEK_B64=${KEK}|"          "$ENV_PATH"
  sed -i "s|^S3_KEY_ID=.*|S3_KEY_ID=${S3KEY}|"                                  "$ENV_PATH"
  sed -i "s|^S3_APPLICATION_KEY=.*|S3_APPLICATION_KEY=${S3SECRET}|"             "$ENV_PATH"
  sed -i "s|^API_DATABASE_URL=.*|API_DATABASE_URL=postgresql+psycopg://nfse:${PGPASS}@postgres:5432/nfse|"           "$ENV_PATH"
  sed -i "s|^API_MIGRATION_DATABASE_URL=.*|API_MIGRATION_DATABASE_URL=postgresql+psycopg://nfse:${PGPASS}@postgres:5432/nfse|" "$ENV_PATH"
  sed -i "s|^API_REDIS_URL=.*|API_REDIS_URL=redis://:${REDISPASS}@redis:6379/0|" "$ENV_PATH"
  sed -i "s|SEU_DOMINIO|${DOMAIN}|g"                                            "$ENV_PATH"
  sed -i "s|SEU_EMAIL|${ACME_EMAIL}|g"                                          "$ENV_PATH"
  chmod 600 "$ENV_PATH"
else
  log ".env ja existe — preservando segredos. Atualizando apenas DOMAIN/ACME_EMAIL ..."
  sed -i "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|"          "$ENV_PATH"
  sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=${ACME_EMAIL}|" "$ENV_PATH"
fi

# --- build + migrate + up ---------------------------------------------------
cd "$COMPOSE_DIR"
export ENV_FILE=.env
COMPOSE="$DOCKER compose --env-file .env -f docker-compose.base.yml -f docker-compose.selfhost.yml"

log "Construindo as imagens (pode levar alguns minutos na primeira vez) ..."
$COMPOSE build

log "Subindo Postgres, Redis e MinIO ..."
$COMPOSE up -d postgres redis minio
$COMPOSE up minio-init

log "Rodando migrations do banco ..."
$COMPOSE run --rm migrate

log "Subindo API, worker, scheduler, painel e Caddy ..."
$COMPOSE up -d

echo
log "Status dos servicos:"
$COMPOSE ps
echo
log "Pronto! Em ~1 minuto o certificado HTTPS e emitido automaticamente."
cat <<EOF

  Painel:  https://${DOMAIN}
  API:     https://${DOMAIN}/backend/health
  S3:      https://${DOMAIN}:${S3_PUBLIC_PORT:-8443}

  Ver logs:        cd ${COMPOSE_DIR} && ${DOCKER} compose --env-file .env -f docker-compose.base.yml -f docker-compose.selfhost.yml logs -f
  Parar tudo:      ${DOCKER} compose --env-file .env -f docker-compose.base.yml -f docker-compose.selfhost.yml down
  Segredos:        ${ENV_PATH}  (guarde em local seguro; nao versione)

EOF
