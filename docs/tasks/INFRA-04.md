# INFRA-04 — Nginx no host + Let's Encrypt

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready (apos INFRA-02 + INFRA-03)
- **Depende de:** INFRA-02, INFRA-03

## Objetivo

Servir HTTPS nos 4 subdominios com Let's Encrypt renovacao automatica.

## Entregaveis

- Nginx instalado no host (nao em container).
- Server blocks para `app`, `api`, `ops`, `www`, apex.
- Placeholder `em breve` em cada um ate as apps subirem.
- Certbot configurado (`certbot --nginx`) para todos.
- `systemd` timer de renovacao ativo.
- HSTS, TLS 1.2+, HTTP/2, gzip, security headers
  (X-Frame-Options, Referrer-Policy, X-Content-Type-Options).
- Rate limit basico em `/auth/*` (por IP).
- Configs versionadas em `infra/nginx/`.

## Definition of Done

- [ ] SSL Labs nota A nos 4 subdominios.
- [ ] `certbot renew --dry-run` ok.
- [ ] Configs commitadas.
