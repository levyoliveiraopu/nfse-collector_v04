# Runbook — Restore completo do Postgres

Use em disaster recovery, drill trimestral ou recuperacao apos corrupcao/perda
de banco. O procedimento operacional detalhado tambem esta em `infra/backup.md`.

## Severidade

- **Critica**: perda/corrupcao em producao.
- **Alta**: drill obrigatorio antes de go-live ou antes de migration arriscada.

## Pre-requisitos

- Artefato de backup `.dump.age` disponivel localmente ou no S3/B2.
- Chave privada age do ambiente.
- Janela de manutencao aprovada.
- Deploy congelado ate validacao final.

## Passo a passo seguro

1. Parar API, worker e scheduler para evitar escrita concorrente.
2. Baixar o backup escolhido e validar checksum/tamanho.
3. Restaurar em banco temporario primeiro:

   ```bash
   bash infra/scripts/restore-postgres.sh /caminho/backup.dump.age nfse_restore_tmp
   ```

4. Rodar validacoes no banco temporario:

   ```sql
   SELECT count(*) FROM tenants;
   SELECT count(*) FROM companies;
   SELECT count(*) FROM executions;
   SELECT count(*) FROM execution_items;
   ```

5. Se a validacao passar, repetir restore no destino aprovado conforme janela.
6. Rodar migrations pendentes, se necessario.
7. Subir API/worker/scheduler.
8. Validar `/ready`, login, listagem de companies e uma coleta dry-run.

## Criterios de sucesso

- API `/ready` retorna `ok`.
- Tabelas principais possuem volumes esperados.
- RLS/tenant isolation continua funcionando.
- Nenhum worker processa jobs antigos indevidamente sem revisao.

## Rollback do restore

Se o restore novo falhar, manter servicos parados e restaurar o backup anterior
mais recente. Nao misturar dados entre dois restores sem decisao explicita.
