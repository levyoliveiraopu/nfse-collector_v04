---
name: Task
about: Tarefa atomica do backlog
title: "[TASK-ID] Titulo"
labels: ready
---

## Referencia

Ticket: `docs/tasks/<TASK-ID>.md`

## Objetivo

<o que esta tarefa entrega>

## Depende de

- [ ] <IDs>

## Entregaveis

- [ ] <arquivos/commits>

## Definition of Done

- [ ] <criterio objetivo 1>
- [ ] <criterio objetivo 2>
- [ ] STATE.md atualizado
- [ ] CHANGELOG.md atualizado

## Prompt sugerido

```
Leia STATE.md e docs/tasks/<TASK-ID>.md. Execute a tarefa,
abra branch task/<TASK-ID>-<slug>, commite, atualize STATE.md
e CHANGELOG.md, e abra PR com "Closes #<numero-desta-issue>".
```
