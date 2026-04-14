#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# INFRA-09 — deploy.sh
#
# Atualiza um ambiente (`staging` ou `prod`) na VPS para a tag informada,
# executa health check pos-deploy e faz rollback automatico para a tag
# anterior caso o health falhe.
#
# Uso (executado remotamente pelo GitHub Actions via appleboy/ssh-action):
#   DEPLOY_ENV=staging DEPLOY_TAG=sha-abc1234 bash /srv/nfse/deploy.sh
#
# Pressupostos (atendidos por INFRA-02 e INFRA-05):
#   - usuario `deploy` no grupo `docker`;
#   - arvore `/srv/nfse/{prod,staging}/{data,backups,logs,config}`;
#   - `/srv/nfse/<env>/` contem `docker-compose.base.yml`,
#     `docker-compose.deploy.yml` e `config/.env` (fora do repo,
#     provisionados manualmente pelo owner — ver `infra/deploy/README.md`);
#   - `docker login ghcr.io` ja efetuado no host (via `GHCR_TOKEN` / PAT
#     read:packages, tambem documentado no README).
#
# Health check: bate em http://127.0.0.1:8000/health (API FastAPI,
# conforme API-01). Worker ainda nao expoe HTTP — quando CORE-05 chegar,
# incluir checagem adicional aqui.
#
# Rollback: antes de pull/up, grava a tag corrente em
# `config/.last_deploy_tag`. Em falha do health, restaura a tag anterior
# e re-sobe. Se nao houver tag anterior registrada, falha explicito sem
# rollback cego (melhor parar e o owner investigar).
# ------------------------------------------------------------------------------

set -euo pipefail

: "${DEPLOY_ENV:?DEPLOY_ENV obrigatorio (staging|prod)}"
: "${DEPLOY_TAG:?DEPLOY_TAG obrigatorio (ex: sha-abc1234 ou v0.0.1)}"

case "${DEPLOY_ENV}" in
  staging|prod) ;;
  *) echo "ERRO: DEPLOY_ENV invalido: ${DEPLOY_ENV}" >&2; exit 2 ;;
esac

readonly STACK_DIR="/srv/nfse/${DEPLOY_ENV}"
readonly CONFIG_DIR="${STACK_DIR}/config"
readonly ENV_FILE="${CONFIG_DIR}/.env"
readonly LAST_TAG_FILE="${CONFIG_DIR}/.last_deploy_tag"
readonly COMPOSE_FILES=(
  "-f" "${STACK_DIR}/docker-compose.base.yml"
  "-f" "${STACK_DIR}/docker-compose.deploy.yml"
)
readonly HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
readonly HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
readonly HEALTH_INTERVAL="${HEALTH_INTERVAL:-2}"

log() { printf '[deploy %s %s] %s\n' "${DEPLOY_ENV}" "$(date -u +%FT%TZ)" "$*"; }

if [[ ! -f "${ENV_FILE}" ]]; then
  log "ERRO: ${ENV_FILE} nao existe — owner deve provisionar o .env na VPS."
  exit 3
fi

compose() {
  docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" "$@"
}

health_check() {
  local attempt=1
  while (( attempt <= HEALTH_RETRIES )); do
    if curl -fsS --max-time 3 "${HEALTH_URL}" >/dev/null 2>&1; then
      log "health ok em ${HEALTH_URL} (tentativa ${attempt})"
      return 0
    fi
    log "health falhou (tentativa ${attempt}/${HEALTH_RETRIES}) — aguardando ${HEALTH_INTERVAL}s"
    sleep "${HEALTH_INTERVAL}"
    attempt=$(( attempt + 1 ))
  done
  return 1
}

previous_tag=""
if [[ -f "${LAST_TAG_FILE}" ]]; then
  previous_tag="$(cat "${LAST_TAG_FILE}")"
fi

log "deploy inicio — tag alvo=${DEPLOY_TAG} tag anterior=${previous_tag:-<nenhuma>}"

# Grava a nova tag no env (lido pelo docker-compose.deploy.yml via ${DEPLOY_TAG}).
export DEPLOY_TAG
# Persistimos a tag nova ANTES do pull/up para que a proxima execucao do script
# veja essa tag como "anterior" caso o novo deploy suba limpo.
echo "${DEPLOY_TAG}" > "${LAST_TAG_FILE}.new"

log "docker login ghcr.io (assume que ja foi feito — pulando)"
log "pull das imagens"
compose pull

log "up -d --remove-orphans"
compose up -d --remove-orphans

log "aguardando health em ${HEALTH_URL} (${HEALTH_RETRIES}x${HEALTH_INTERVAL}s)"
if health_check; then
  mv "${LAST_TAG_FILE}.new" "${LAST_TAG_FILE}"
  log "deploy ok — tag atual gravada em ${LAST_TAG_FILE}"
  exit 0
fi

# ---- rollback ---------------------------------------------------------------
log "HEALTH CHECK FALHOU — iniciando rollback"
rm -f "${LAST_TAG_FILE}.new"

if [[ -z "${previous_tag}" ]]; then
  log "ERRO: sem tag anterior registrada em ${LAST_TAG_FILE} — rollback abortado."
  log "containers podem estar em estado ruim; owner deve investigar manualmente."
  exit 10
fi

log "revertendo para tag=${previous_tag}"
export DEPLOY_TAG="${previous_tag}"
compose pull
compose up -d --remove-orphans

if health_check; then
  log "rollback ok — servico estabilizado na tag=${previous_tag}"
else
  log "ERRO: rollback nao recuperou o servico; owner deve investigar."
  exit 11
fi

# Sinaliza falha do deploy original mesmo com rollback bem-sucedido, para que
# o workflow do GitHub Actions marque a execucao como falha.
exit 20
