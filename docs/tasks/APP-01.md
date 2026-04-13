# APP-01 — Paginas de auth (login, signup, recuperar, aceitar convite)

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda DS-03 + API-02)
- **Depende de:** DS-03, API-02

## Objetivo

Fluxo completo de autenticacao no painel.

## Entregaveis

- `/login` (email + senha + "esqueci senha" + "criar conta").
- `/signup` (nome + email + senha + aceita termos).
- `/recuperar-senha` (envia email) + `/redefinir-senha/:token`.
- `/aceitar-convite/:token` (confirma e define senha).
- Contexto `AuthProvider` guarda user + tokens (memoria + refresh cookie httponly).
- Logout limpa tudo.

## Definition of Done

- [ ] Fluxo E2E (Playwright): signup -> dashboard.
- [ ] Refresh automatico funciona.
