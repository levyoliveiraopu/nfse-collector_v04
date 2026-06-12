# Rollback e migrations — deploy Docker Compose

Este procedimento complementa `infra/deploy/deploy.sh` e existe porque o
rollback de imagem nao desfaz automaticamente DDL ja aplicado por Alembic.

## Modelo adotado

1. O deploy publica tres imagens com a mesma tag: `nfse-api`, `nfse-worker` e
   `nfse-web-app`.
2. O Compose executa o servico one-shot `migrate` antes de liberar API,
   worker, scheduler e web-app.
3. O health de deploy valida `GET /ready` da API. Esse endpoint checa DB,
   Redis e configuracao S3 minima.
4. Se `/ready` falhar, `deploy.sh` volta `DEPLOY_TAG` para a tag anterior e
   sobe as imagens anteriores.

## Regra para migrations

Toda migration enviada para producao deve ser **forward-compatible** com a
versao anterior da aplicacao enquanto o deploy ainda pode sofrer rollback.
Na pratica:

- adicionar colunas/tabelas antes de tornar uso obrigatorio;
- nao remover/renomear coluna usada pela versao anterior no mesmo release;
- fazer backfill em job separado quando houver volume relevante;
- so remover estruturas antigas em release posterior, depois de uma janela de
  observacao.

## Falha antes da migration

Se o pull/build falhar, nada muda no servidor. Corrija a imagem/tag e rode o
deploy novamente.

## Falha durante `alembic upgrade head`

O Compose nao libera os servicos dependentes. A API antiga continua rodando se
os containers antigos ainda estavam ativos antes do `up`. Acoes:

1. consultar logs: `docker logs nfse-migrate`;
2. corrigir a migration ou dado inconsistente;
3. rodar `DEPLOY_TAG=<tag-corrigida> bash /srv/nfse/deploy.sh` novamente.

Nao rode `alembic downgrade` em producao sem plano especifico aprovado.

## Falha depois da migration, antes de `/ready`

`deploy.sh` faz rollback automatico das imagens. O schema permanece no head
novo; por isso a regra de forward-compatibility acima e obrigatoria.
Se a versao anterior nao for compativel, pare o rollback automatico e aplique o
plano manual da migration/release.

## Rollback manual de emergencia

```bash
set -a; source /srv/nfse/prod/config/.env; set +a
export DEPLOY_ENV=prod
export DEPLOY_TAG="$(cat /srv/nfse/prod/config/.last_deploy_tag)"
bash /srv/nfse/deploy.sh
```

Se houver suspeita de corrupcao de dados, execute primeiro um backup manual e
siga `infra/backup.md` para restore/drill.
