# Checklist — simulacao de incidentes e validacao de runbooks

Objetivo: validar os runbooks existentes antes do go-live sem depender de um
incidente real. Cada simulacao deve gerar evidencia no ticket de operacao
(data, ambiente, executor, resultado e links de logs/prints sem segredo).

## Simulacoes obrigatorias

| Incidente | Como simular em staging | Runbook | Evidencia esperada |
|---|---|---|---|
| Fila travada | parar worker por 5 min e enfileirar execution dry-run | `fila-travada.md` | alerta recebido + fila drenada apos retorno |
| Portal indisponivel | forcar mock/URL invalida do ADN em staging controlado | `portal-indisponivel.md` | occurrence `PORTAL_*` e job sem ficar preso |
| Credencial invalida | usar PFX/senha de teste invalida | `credencial-invalida.md` + checklist de suporte | occurrence `CRED_INVALID`/`CERT_EXPIRED` |
| Migration falhou | criar migration falsa em staging descartavel | `migration-falhou.md` | deploy bloqueado e rollback documentado |
| Backup falhou | executar backup com bucket invalido em staging | `backup-falhou.md` | alerta/log `status=failed` |
| Restore completo | restaurar ultimo backup em DB temporario | `restore-completo.md` | contagens e `/ready` pos-restore |
| SSL expirando | validar monitor de certificado no Uptime Kuma | `ssl-expirando.md` | notificacao de teste enviada |
| Disco cheio | simular limite em volume temporario, nunca no `/` real | `disco-cheio.md` | mitigacao documentada |

## Criterios de conclusao

- Todos os runbooks acima foram abertos e seguidos por alguem que nao escreveu o codigo.
- Cada alerta chegou ao canal operacional esperado.
- Nenhum passo exigiu segredo colado em chat/ticket.
- Lacunas encontradas viraram issue antes do go-live.
