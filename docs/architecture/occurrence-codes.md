# Catalogo de codigos de ocorrencia

Ticket de origem: **API-09** (`docs/tasks/API-09.md`).
Schema da tabela: `apps/api/alembic/versions/0006_occurrences.py` (DATA-04).
Endpoints: `apps/api/api/occurrences/` (router montado em `/occurrences`).

Este catalogo lista os codigos canonicos que a API e o worker
escrevem em `occurrences.code`. O campo e `TEXT` livre no banco — esta
documentacao e o contrato com o frontend (APP-06) e com os runbooks de
operacao. Adicione um codigo novo aqui antes de comecar a emiti-lo.

## Convencoes

- `code` em `SCREAMING_SNAKE_CASE` ASCII curto (`<= 32 chars`).
- Um codigo descreve um **tipo de problema** estavel — detalhes variaveis
  (ex.: HTTP status real, mensagem do portal) vao em `detail` (TEXT
  livre, pode carregar JSON serializado).
- `severity_default` e o ponto de partida; o emissor pode promover a
  severity por contexto (ex.: 5xx persistente -> `critical`).
- Codigos cuja resposta exige acao de cliente apontam para um runbook
  em `docs/runbooks/`.

## Codigos

| Codigo               | Severity default | Descricao                                                                 | Runbook |
|----------------------|------------------|---------------------------------------------------------------------------|---------|
| `CERT_EXPIRED`       | `error`          | Certificado A1 com `notAfter` no passado. Coleta nao autentica no portal. | `docs/runbooks/credencial-invalida.md` |
| `CERT_EXPIRING`      | `warning`        | Certificado A1 vence em <= 30 dias. Aviso preventivo.                     | `docs/runbooks/credencial-invalida.md` |
| `CERT_REVOKED`       | `error`          | Certificado revogado pela AC (CRL/OCSP).                                  | `docs/runbooks/credencial-invalida.md` |
| `CRED_INVALID`       | `error`          | Senha do PFX nao confere, ou CN nao bate com CNPJ da company.             | `docs/runbooks/credencial-invalida.md` |
| `PORTAL_5XX`         | `error`          | Portal da prefeitura devolveu 5xx persistente apos retries.               | `docs/runbooks/portal-indisponivel.md` |
| `PORTAL_TIMEOUT`     | `warning`        | Timeout de conexao/leitura no portal (sem 5xx explicito).                 | `docs/runbooks/portal-indisponivel.md` |
| `PORTAL_RATE_LIMIT`  | `warning`        | Portal limitou a taxa (HTTP 429 ou throttling).                           | `docs/runbooks/portal-indisponivel.md` |
| `PORTAL_HTTP_ERROR`  | `error`          | Erro HTTP nao-5xx persistente ou falha de conexao com o portal.           | `docs/runbooks/portal-indisponivel.md` |
| `RATE_LIMIT`         | `warning`        | Codigo legado para rate limit; emissores novos devem usar `PORTAL_RATE_LIMIT`. | `docs/runbooks/portal-indisponivel.md` |
| `REPROCESS_NEEDED`   | `info`           | Item reprocessavel detectado — operador pode disparar reprocess.          | `docs/runbooks/reprocessamento.md` |
| `PARSE_ERROR`        | `error`          | Resposta do portal nao casa com o XSD/contrato esperado.                  | `docs/runbooks/parse-error.md` |
| `STORAGE_ERROR`      | `critical`       | Falha ao gravar XML/anexo no storage S3 apos tentativas.                  | `docs/runbooks/storage-error.md` |
| `UNKNOWN`            | `error`          | Erro nao classificado. So usar como ultimo recurso; abrir issue.          | `docs/runbooks/erro-desconhecido.md` |
| `REPROCESS_NEEDED`   | `info`           | Item reprocessavel detectado — operador pode disparar reprocess.          | (em redacao) |
| `PARSE_ERROR`        | `error`          | Resposta do portal nao casa com o XSD/contrato esperado.                  | (em redacao) |
| `STORAGE_ERROR`      | `critical`       | Falha ao gravar XML/anexo no storage S3 apos tentativas.                  | (em redacao) |
| `UNKNOWN`            | `error`          | Erro nao classificado. So usar como ultimo recurso; abrir issue.          | (em redacao) |
| `SCHEDULE_OVERLAP`   | `warning`        | Disparo agendado pulado porque a execucao anterior da mesma company ainda esta em curso. | (em redacao) |

## Transicoes de status

A API expoe quatro transicoes em `POST /occurrences/{id}/...`:

- `acknowledge` — `open` -> `ack` (idempotente: re-acknowledge em ja
  `ack` retorna 200 sem mudar nada). 409 se a ocorrencia ja esta
  `resolved` ou `ignored`.
- `resolve` — `open|ack|snoozed` -> `resolved`. Grava `resolved_at = now()`
  e exige `note` no body (registrada em `audit_logs.metadata.note`).
- `assign` — define `assignee_user_id`; o user precisa ser membro do
  tenant corrente (consultado em `tenant_users`). 404 se nao for.

`snoozed` e `ignored` existem no schema mas nao tem endpoints proprios
nesta entrega — ficam para tickets futuros (snooze por scheduler,
ignore via UI de bulk).

## Como o frontend usa

`apps/web-app` (APP-06) renderiza badge de severity + label do codigo
+ link "Como resolver" apontando para o runbook desta tabela. Codigos
nao listados aqui caem no rotulo generico "Outro".
