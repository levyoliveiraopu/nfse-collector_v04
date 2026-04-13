# APP-11 — Wizard de onboarding (3 passos)

- **Trilha:** app
- **Tamanho:** M
- **Status:** blocked (aguarda APP-03 + APP-04 + APP-05)
- **Depende de:** APP-03, APP-04, APP-05

## Objetivo

Acompanhar o primeiro usuario do tenant ate completar a 1a coleta.

## Entregaveis

- Ao logar pela 1a vez: wizard em modal persistente ate concluir.
- Passo 1: Cadastrar 1a empresa.
- Passo 2: Subir PFX.
- Passo 3: Rodar 1a execucao.
- Progresso salvo (se fechar retoma).
- Evento `first_collection_done` dispara email de parabens.

## Definition of Done

- [ ] Usuario novo chega ate "1a coleta ok" em < 10 min.
- [ ] Skip visivel mas destacado como nao recomendado.
