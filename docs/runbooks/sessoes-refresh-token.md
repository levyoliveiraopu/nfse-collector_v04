# Runbook — Refresh token, replay e revogacao de sessoes

Use quando houver suspeita de roubo/replay de refresh token, login indevido,
sessao que nao deveria continuar ativa ou alerta de seguranca em autenticacao.

## Severidade

- **Critica**: replay confirmado, refresh token vazado ou acesso indevido em tenant real.
- **Alta**: multiplas tentativas suspeitas, usuario reporta sessao desconhecida.
- **Media**: limpeza preventiva de sessoes apos troca de senha/e-mail.

## Diagnostico rapido

1. Identificar `user_id`, `tenant_id`, IP aproximado e horario reportado.
2. Consultar refresh tokens ativos do usuario/tenant:

   ```sql
   SELECT id, user_id, tenant_id, revoked_at, replaced_by, created_at, expires_at
     FROM refresh_tokens
    WHERE user_id = '<USER_ID>'
    ORDER BY created_at DESC
    LIMIT 50;
   ```

3. Verificar se existe cadeia substituida (`replaced_by`) reutilizada apos rotacao.
4. Checar logs da API por `auth.login`, `refresh`, `revoked`, `replay` e status 401/429.

## Contencao

Revogar todas as sessoes do usuario afetado:

```sql
UPDATE refresh_tokens
   SET revoked_at = now()
 WHERE user_id = '<USER_ID>'
   AND revoked_at IS NULL;
```

Se o impacto for tenant inteiro:

```sql
UPDATE refresh_tokens
   SET revoked_at = now()
 WHERE tenant_id = '<TENANT_ID>'
   AND revoked_at IS NULL;
```

Depois disso, pedir novo login aos usuarios afetados.

## Validacao

- Novo refresh com token antigo deve retornar 401.
- Login novo deve gerar nova cadeia de refresh token.
- Nao deve haver tokens ativos antigos para o usuario/tenant revogado.

## Comunicacao

- Registrar horario, tenant, usuario e acao executada no incidente.
- Se houver evidencia de vazamento, abrir post-mortem e forcar troca de senha.
- Nunca colar refresh token real em issue, log, chat ou ticket.
