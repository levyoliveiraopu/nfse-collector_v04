# Gestao de usuarios, tenants e ciclo de vida

Este documento organiza o item 5.2 do checklist de producao e separa o que ja
existe do que ainda precisa de implementacao.

## Estado atual versionado

- UI de usuarios existe em `apps/web-app/app/usuarios/page.tsx` com listagem,
  convite, revogacao, troca de papel e remocao consumindo `/tenant/*`.
- Cliente frontend documenta que os endpoints `/tenant/members` e
  `/tenant/invitations` ainda dependem de API futura.
- Guardas RBAC de owner protegido existem em `apps/api/api/security/rbac.py` e
  no espelho de UI em `apps/web-app/lib/users/rbac.ts`.
- Login/API bloqueiam tenants `suspended` e `canceled` por `assert_tenant_active`.
- O `TenantSwitcher` ainda e placeholder visual e nao troca sessao/tenant.

## Contrato de producao esperado

### Convites

- `POST /tenant/invitations`: owner/admin cria convite com email, papel e expiracao.
- `POST /tenant/invitations/accept`: destinatario aceita token, cria ou vincula usuario e recebe sessao.
- `POST /tenant/invitations/{id}/revoke`: owner/admin revoga convite pendente.
- Convite expirado ou revogado nunca deve criar membership.
- Auditoria obrigatoria para convite, aceite e revogacao.

### Membros

- `GET /tenant/members`: lista membros do tenant atual.
- `PATCH /tenant/members/{user_id}`: altera papel respeitando `ensure_can_manage_member`.
- `DELETE /tenant/members/{user_id}`: remove membership respeitando owner protegido.
- Nao permitir que o ultimo owner ativo seja removido/rebaixado.

### Troca de tenant

- API deve expor memberships ativas do usuario.
- UI deve permitir selecionar tenant e reemitir sessao/JWT para o tenant escolhido.
- Tenants `suspended`/`canceled` aparecem bloqueados ou ocultos, nunca selecionaveis.

### Suspensao/cancelamento

- API protegida deve continuar bloqueando via `assert_tenant_active`.
- Scheduler nao deve criar novas execucoes para tenant suspenso/cancelado.
- Worker deve falhar/ignorar jobs pendentes de tenant bloqueado sem acessar PFX/portal.
- Cancelamento deve definir regra de retencao/purge de XMLs, exports, credenciais e dados cadastrais.

## Proximos tickets recomendados

1. API `/tenant/members` + `/tenant/invitations` com testes de owner protegido.
2. API de memberships/me para alimentar tenant switcher.
3. Tenant switcher funcional com refresh/relogin por tenant.
4. Admin endpoint de suspender/cancelar tenant e impacto em scheduler/worker.
