# Matriz de permissoes (RBAC)

Ticket de origem: **API-04** (`docs/tasks/API-04.md`).
Implementacao: `apps/api/api/security/rbac.py`.

## Papeis

Os quatro papeis sao seedados em `tenant_users` (DATA-01) e validados
pelo CHECK `ck_tenant_users_role`:

| Papel      | Rank | Descricao |
|------------|-----:|-----------|
| `owner`    |    4 | Dono do tenant. Papel unico protegido: apenas outro `owner` pode remover ou rebaixar um `owner`. |
| `admin`    |    3 | Administracao plena do tenant, exceto sobre `owner`. |
| `operator` |    2 | Operacao diaria: dispara coletas, gerencia companies/credenciais, resolve ocorrencias. |
| `viewer`   |    1 | Somente leitura. |

Rank e usado por `require_role(min_role="<papel>")` para expressar
"este papel ou superior".

## Como aplicar nos endpoints

```python
from fastapi import APIRouter, Depends
from api.security.rbac import require_role

router = APIRouter()

@router.post(
    "/companies",
    dependencies=[Depends(require_role("owner", "admin", "operator"))],
)
def create_company(...): ...

@router.delete(
    "/tenants/{tenant_id}",
    dependencies=[Depends(require_role(min_role="owner"))],
)
def delete_tenant(...): ...
```

`require_role` encadeia `assert_tenant_active` (API-03), portanto ja
cobre 401 (token ausente/invalido) e 403 (tenant suspenso/cancelado)
antes de checar o papel. Quando o papel nao e autorizado, a API
devolve **403** com mensagem explicita.

## Matriz por recurso

Legenda: `R` = leitura, `W` = criacao/edicao, `D` = remocao (hard/soft),
`—` = sem acesso. Tickets futuros devem referenciar esta matriz ao
aplicar `require_role`.

### Tenant / configuracoes

| Recurso                           | owner | admin | operator | viewer |
|-----------------------------------|:-----:|:-----:|:--------:|:------:|
| `GET /tenants/me`                 |   R   |   R   |    R     |   R    |
| `PATCH /tenants/me` (nome, slug)  |   W   |   W   |    —     |   —    |
| Alterar plano / billing           |   W   |   —   |    —     |   —    |
| Deletar tenant                    |   D   |   —   |    —     |   —    |

### Membros (`tenant_users`)

| Operacao                              | owner | admin | operator | viewer |
|---------------------------------------|:-----:|:-----:|:--------:|:------:|
| Listar membros                        |   R   |   R   |    R     |   R    |
| Convidar membro (role = viewer/operator) |   W   |   W   |    —     |   —    |
| Convidar / promover para `admin`      |   W   |   —   |    —     |   —    |
| Convidar / promover para `owner`      |   W   |   —   |    —     |   —    |
| Remover `viewer` / `operator`         |   D   |   D   |    —     |   —    |
| Remover `admin`                       |   D   |   D   |    —     |   —    |
| Remover `owner`                       |   D   |   —   |    —     |   —    |
| Rebaixar `owner`                      |   W   |   —   |    —     |   —    |

Regras escritas (aplicadas por `ensure_can_manage_member`):

1. **Owner protegido**: apenas outro `owner` pode remover ou rebaixar
   um `owner`. Admin que tente recebe 403.
2. **Promocao limitada pelo proprio papel**: o ator nao pode promover
   alguem a um papel superior ao seu (admin nao promove a admin/owner).
3. **Nao-gestores**: `operator` e `viewer` recebem 403 em qualquer
   operacao de gestao de membros.
4. **Ultimo owner**: a API deve recusar remover/rebaixar o unico
   `owner` restante do tenant. Regra checada pelo handler (consulta
   `COUNT(*) FROM tenant_users WHERE role = 'owner'`), nao por
   `ensure_can_manage_member`.

### Companies (CNPJs do tenant) — implementacao em API-05

| Endpoint                          | owner | admin | operator | viewer |
|-----------------------------------|:-----:|:-----:|:--------:|:------:|
| `GET /companies`                  |   R   |   R   |    R     |   R    |
| `GET /companies/{id}`             |   R   |   R   |    R     |   R    |
| `POST /companies`                 |   W   |   W   |    W     |   —    |
| `PATCH /companies/{id}`           |   W   |   W   |    W     |   —    |
| `DELETE /companies/{id}`          |   D   |   D   |    —     |   —    |
| Upload de PFX / credencial        |   W   |   W   |    W     |   —    |
| Rotacionar credencial             |   W   |   W   |    W     |   —    |

> DoD de API-04: "viewer recebe 403 ao tentar criar empresa" e coberta
> pelo contrato acima + testes em `apps/api/tests/test_rbac.py`.

### Executions (coletas)

| Endpoint                              | owner | admin | operator | viewer |
|---------------------------------------|:-----:|:-----:|:--------:|:------:|
| `GET /executions`                     |   R   |   R   |    R     |   R    |
| `GET /executions/{id}`                |   R   |   R   |    R     |   R    |
| `GET /executions/{id}/items`          |   R   |   R   |    R     |   R    |
| `POST /executions` (dispara manual)   |   W   |   W   |    W     |   —    |
| `POST /executions/{id}/cancel`        |   W   |   W   |    W     |   —    |
| `POST /executions/{id}/reprocess`     |   W   |   W   |    W     |   —    |
| Download de XLSX / artefatos          |   R   |   R   |    R     |   R    |

### Occurrences (inbox operacional) — implementacao em API-09

| Endpoint                                       | owner | admin | operator | viewer |
|------------------------------------------------|:-----:|:-----:|:--------:|:------:|
| `GET /occurrences`                             |   R   |   R   |    R     |   R    |
| `GET /occurrences/{id}`                        |   R   |   R   |    R     |   R    |
| `POST /occurrences/{id}/acknowledge`           |   W   |   W   |    W     |   —    |
| `POST /occurrences/{id}/resolve`               |   W   |   W   |    W     |   —    |
| `POST /occurrences/{id}/assign`                |   W   |   W   |    W     |   —    |

Catalogo de codigos (`code`) emitidos pelo worker e canonizados na UI
esta em `docs/architecture/occurrence-codes.md`. Cada acao mutadora
grava `audit_logs` com `action='occurrence.<verb>'`. A nota do
`resolve` e obrigatoria e fica em `audit_logs.metadata.note`.

### Auditoria e observabilidade

| Recurso                               | owner | admin | operator | viewer |
|---------------------------------------|:-----:|:-----:|:--------:|:------:|
| `GET /audit` (log de auditoria)       |   R   |   R   |    —     |   —    |
| `GET /metrics` / dashboards internos  |   R   |   R   |    R     |   R    |

## Respostas de erro

- `401 Unauthorized` — token ausente/invalido (emitido antes do RBAC,
  por `get_current_claims`).
- `403 Forbidden` com `detail: "tenant <status>"` — tenant suspenso ou
  cancelado (emitido por `assert_tenant_active`).
- `403 Forbidden` com `detail: "permissao insuficiente: papel '<x>' nao
  autorizado"` — papel nao pertence ao conjunto permitido.
- `403 Forbidden` com mensagem especifica — guardas de `tenant_users`
  (ex.: `"apenas um owner pode gerenciar outro owner"`).

Mensagens sao estaveis o suficiente para UX e logs, mas nao incluem
dados sensiveis (ex.: email alheio, id interno).
