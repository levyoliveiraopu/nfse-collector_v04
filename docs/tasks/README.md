# Backlog de Tarefas

Cada arquivo `<TASK-ID>.md` e um ticket atomico, com DoD objetivo e
prompt pronto para copiar.

## Trilhas

| Codigo | Trilha | Foco |
|--------|--------|------|
| GOV-* | Governanca | ADRs, templates, processos |
| INFRA-* | Infra & DevOps | VPS, Nginx, Docker, SSL, observabilidade |
| DATA-* | Data | Schema, migrations, RLS, seeds |
| CORE-* | Worker-core | Refactor do motor ADN existente |
| API-* | API | FastAPI, auth, RBAC, endpoints |
| DS-* | Design System | Tokens, layout, componentes shadcn |
| APP-* | App (painel) | Paginas do painel logado |
| SITE-* | Site (landing) | Paginas publicas (bloqueado ate nome) |
| DOCS-* | Docs & Legal | Termos, privacidade, runbooks |

## Status

Consultar `STATE.md` para ver quais tarefas estao destravadas agora.

## Como executar uma tarefa

```
Leia STATE.md e docs/tasks/<TASK-ID>.md.
Execute a tarefa, abra branch task/<TASK-ID>-<slug>, commite,
atualize STATE.md e CHANGELOG.md, e abra PR com
"Closes #<numero-da-issue>".
```

## Regras

- Uma tarefa = uma branch = um PR = uma issue fechada.
- Maximo 4 tarefas em andamento simultaneamente.
- Se estourar o tamanho (S/M/L) em 2x, parar e refatiar.
- Toda PR atualiza `STATE.md` e `CHANGELOG.md`.

## Indice rapido

Governanca: GOV-01..GOV-06
Infra: INFRA-01..INFRA-09
Data: DATA-01..DATA-07
Worker: CORE-01..CORE-06
API: API-01..API-15
DS: DS-01..DS-09
App: APP-01..APP-11
Site: SITE-01..SITE-10 (bloqueadas ate definir nome)
Docs: DOCS-01..DOCS-06
