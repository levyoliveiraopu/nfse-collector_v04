# Runbook — Migration/Alembic falhou no deploy

Use quando o step `migrate` do deploy falhar, quando `alembic upgrade head`
interromper ou quando a API ficar sem subir por incompatibilidade de schema.

## Severidade

- **Critica**: producao indisponivel apos migration parcialmente aplicada.
- **Alta**: staging/prod bloqueado antes de subir nova versao.
- **Media**: falha local ou em branch sem impacto operacional.

## Diagnostico rapido

1. Nao rode deploy novamente no escuro. Capture logs do job `migrate`.
2. Conferir revisao atual:

   ```bash
   docker compose -f docker-compose.deploy.yml run --rm migrate alembic current
   docker compose -f docker-compose.deploy.yml run --rm migrate alembic heads
   ```

3. Verificar se existe mais de uma head ou migration de merge ausente.
4. Conferir se a migration que falhou e transacional. DDL nao transacional pode deixar objetos parcialmente criados.
5. Confirmar backup recente antes de qualquer reparo em producao.

## Contencao

- Se a API antiga ainda roda: manter versao anterior e bloquear novo deploy.
- Se a API ficou indisponivel: executar rollback de imagem conforme `infra/deploy/rollback.md`.
- Se houve schema parcial: corrigir manualmente apenas com plano revisado e backup confirmado.

## Recuperacao padrao

1. Criar dump antes de mexer:

   ```bash
   bash infra/scripts/backup-postgres.sh
   ```

2. Corrigir migration em branch nova.
3. Rodar em staging com copia recente.
4. Reexecutar `alembic upgrade head`.
5. Validar `/ready`, login e fluxo critico.

## Validacao final

```bash
alembic current
alembic heads
curl -fsS https://api.<DOMINIO>/ready
```

Resultado esperado: uma unica head, API pronta e sem erro de schema nos logs.
