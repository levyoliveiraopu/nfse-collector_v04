# Contribuindo

Este projeto e operado por solo founder com auxilio de agentes de IA em
sessoes paralelas. As regras abaixo existem para manter consistencia entre
sessoes que nao compartilham memoria.

## Fluxo padrao

1. Escolher uma tarefa em `docs/tasks/<TASK-ID>.md` (status `ready` em STATE.md).
2. Criar branch a partir de `main`:
   ```
   task/<TASK-ID>-<slug-curto>
   # ex: task/INFRA-01-hardening-vps
   ```
3. Executar conforme o ticket; cumprir todos os itens do DoD.
4. Atualizar `STATE.md` (mover de "Em Andamento" para concluido, destravar proximas).
5. Adicionar linha em `CHANGELOG.md`.
6. Abrir PR com titulo:
   ```
   <tipo>(<escopo>): <resumo curto>
   # ex: feat(infra): hardening inicial da VPS (INFRA-01)
   ```
7. Corpo do PR referencia a issue: `Closes #<numero>`.
8. Merge apos aprovacao (squash merge recomendado).

## Conventional Commits

Tipos aceitos:

- `feat` — nova funcionalidade
- `fix` — bug fix
- `chore` — tarefa operacional sem impacto de comportamento
- `docs` — somente documentacao
- `refactor` — refatoracao sem mudanca de comportamento
- `test` — testes
- `infra` — infraestrutura / deploy / ops
- `style` — formatacao

Escopos sugeridos: `api`, `worker`, `web-app`, `web-site`, `worker-core`,
`infra`, `db`, `docs`, `ci`.

## Branch protection (main)

- Proibido push direto.
- Exigir PR com 1 aprovacao.
- Exigir checks de CI verdes (lint + test).
- Permitir squash merge; proibir force-push.

## Limite de WIP

Maximo **4 tarefas** em andamento simultaneamente. Se passar disso, parar
e fechar o que esta em revisao antes de pegar mais.

> Em 29/04/2026 nao ha tarefa em andamento — ver `STATE.md` -> "Em
> Andamento". O backlog priorizado esta em "Proximas Destravadas".

## Quando uma tarefa esta maior do que o ticket previa

1. Pare a execucao.
2. Comente na issue com `blocked` e motivo.
3. Proponha divisao em sub-tickets.
4. Aguarde aprovacao antes de continuar.

## Seguranca

- Nunca commitar `.env`, `.pfx`, `.pem`, `.key`, credenciais de API, chaves
  mestras ou senhas.
- Revisar PR com `git diff` focado em secrets antes de publicar.
- Se um segredo vazar, **rotacionar imediatamente** e registrar no
  `docs/security/incidents.md`.
