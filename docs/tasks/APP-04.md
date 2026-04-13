# APP-04 — /empresas/[id]/credencial (upload PFX)

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda DS-07 + API-06)
- **Depende de:** DS-07, API-06

## Objetivo

UI para upload e gestao de certificado A1.

## Entregaveis

- Aba "Credencial" com:
  - Status atual (badge) + fingerprint + validade.
  - Botao "Atualizar credencial" (abre dialog com FileDropzone + SecretField).
  - Botao "Testar agora".
  - Botao "Revogar" (ConfirmDialog com digite REVOGAR).
- Feedback de erro: senha incorreta, PFX invalido, CN nao casa.

## Definition of Done

- [ ] Upload cifra no servidor (API-06) e badge fica verde.
- [ ] Teste de auth real funciona.
