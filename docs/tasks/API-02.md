# API-02 — Auth: signup + login + JWT refresh rotativo

- **Trilha:** api
- **Tamanho:** L
- **Status:** blocked (aguarda DATA-01)
- **Depende de:** DATA-01

## Objetivo

Autenticacao completa com argon2id, JWT de acesso curto (15min) e
refresh token rotativo (7 dias).

## Entregaveis

- Endpoints:
  - `POST /auth/signup` cria tenant + user owner.
  - `POST /auth/login` -> access + refresh.
  - `POST /auth/refresh` rotaciona refresh.
  - `POST /auth/logout` revoga refresh.
- Hash de senha: **argon2id**.
- Refresh token armazenado como hash no banco
  (tabela `refresh_tokens` ou coluna em `users`).
- Rate limit no login (ex: 5 tentativas/min por IP).
- Tests de auth (pytest).

## Definition of Done

- [ ] E2E com curl: signup -> login -> refresh -> logout.
- [ ] Senha nunca aparece em logs.
- [ ] Revoke invalida refresh.
