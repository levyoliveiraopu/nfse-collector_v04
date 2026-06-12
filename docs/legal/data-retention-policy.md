# Politica de retencao — XMLs, exports, logs e backups

## Objetivo

Definir a regra operacional minima de retencao para producao. Qualquer prazo
contratual diferente deve ser refletido em migration/configuracao antes do go-live.

## Regras propostas

| Classe | Local | Prazo/versionado | Acao ao expirar |
|---|---|---|---|
| XML de execucao | S3/B2 prefixo `tenants/` | lifecycle de execucoes documentado em `infra/s3-lifecycle.json` | remocao automatica pelo bucket |
| Export ZIP | S3/B2 prefixo `tenants-exports/` | 30 dias | remocao automatica pelo bucket e `files.expires_at` |
| Credencial PFX cifrada | S3/B2 prefixo `tenants-credentials/` | sem lifecycle automatico | remover ao revogar/substituir credencial |
| Logs Loki | Loki | 14 dias em `infra/compose/loki/loki-config.yml` | compactacao/remocao pelo Loki |
| Audit logs | Postgres | prazo juridico/contratual a definir | purge controlado por migration/job futuro |
| Backups Postgres | S3/B2 + copia local | conforme `infra/backup.md` e envs de backup | rotacao local/remota cifrada |

## Requisitos de seguranca

- Logs nao podem conter PFX, senha, ciphertext, refresh token ou presigned URL.
- Exports devem usar presigned URL temporaria e nao URL publica permanente.
- Credenciais A1 nao devem compartilhar lifecycle dos XMLs/exports.

## Pendencias antes do go-live

- Confirmar se a retencao de XML deve ser 90 dias, 5 anos ou custom por plano.
- Implementar job de purge de linhas expiradas se o banco precisar refletir remocao fisica do S3.
- Formalizar politica de eliminacao de tenant cancelado.
