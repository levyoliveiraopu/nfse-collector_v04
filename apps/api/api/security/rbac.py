"""RBAC por papel de membership (API-04).

Modela os quatro papeis seedados em `tenant_users` (DATA-01):

- `owner`    — dono do tenant (unico papel que pode remover/demover outro owner).
- `admin`    — administracao plena, exceto sobre owners.
- `operator` — operacao diaria (dispara coletas, gerencia companies).
- `viewer`   — somente leitura.

A matriz completa esta documentada em
`docs/architecture/rbac-matrix.md`. Este modulo oferece:

- `require_role(*allowed, min_role=None)` — fabrica de dependency FastAPI
  que encadeia `assert_tenant_active` (API-03) e, em seguida, valida o
  papel vindo do JWT. Retorna 403 claro quando falta permissao.
- `ensure_can_manage_member(actor_role, target_role, operation)` — guarda
  pura para transicoes sobre `tenant_users`. O owner e protegido: um
  admin nao pode remove-lo nem rebaixar seu papel. Projetada para ser
  chamada pelos endpoints de gestao de membros (API futura), ja com
  testes nesta entrega.
"""

from __future__ import annotations

from typing import Callable, Iterable, Literal

from fastapi import Depends, HTTPException, status

from ..deps import assert_tenant_active
from .jwt import AccessClaims

# Dominio completo, alinhado com o CHECK `ck_tenant_users_role` em
# `0001_initial_identity.py`.
ROLES: tuple[str, ...] = ("owner", "admin", "operator", "viewer")

# Ranking usado para `min_role=`: owner > admin > operator > viewer.
_ROLE_RANK: dict[str, int] = {"viewer": 1, "operator": 2, "admin": 3, "owner": 4}


def role_rank(role: str) -> int:
    """Retorna o rank do papel. Papel desconhecido -> 0 (menor que viewer)."""
    return _ROLE_RANK.get(role, 0)


def _normalize_allowed(
    allowed: Iterable[str], min_role: str | None
) -> frozenset[str]:
    """Resolve o conjunto efetivo de papeis autorizados."""
    effective: set[str] = set(allowed)
    if min_role is not None:
        if min_role not in _ROLE_RANK:
            raise ValueError(f"min_role desconhecido: {min_role!r}")
        threshold = _ROLE_RANK[min_role]
        effective.update(r for r, rank in _ROLE_RANK.items() if rank >= threshold)
    if not effective:
        raise ValueError("require_role requer pelo menos um papel permitido")
    for r in effective:
        if r not in _ROLE_RANK:
            raise ValueError(f"papel desconhecido: {r!r}")
    return frozenset(effective)


def require_role(
    *allowed: str, min_role: str | None = None
) -> Callable[[AccessClaims], AccessClaims]:
    """Fabrica uma dependency FastAPI que exige `claims.role in allowed`.

    Uso:

        @router.post("/companies",
                     dependencies=[Depends(require_role("owner", "admin"))])
        def create_company(...): ...

        @router.delete("/tenants/{id}",
                       dependencies=[Depends(require_role(min_role="owner"))])
        def delete_tenant(...): ...

    Ordem de validacao:
    1. `assert_tenant_active` (API-03) garante 401 se falta token e 403 se
       o tenant esta suspenso/cancelado.
    2. Esta funcao compara o papel do JWT com `allowed`. 403 se nao bate.

    Por que 403 (e nao 401): o usuario esta autenticado; o que falta e
    permissao. 401 induziria o cliente a re-autenticar em vao.
    """
    effective = _normalize_allowed(allowed, min_role)

    def _dep(
        claims: AccessClaims = Depends(assert_tenant_active),
    ) -> AccessClaims:
        if claims.role not in effective:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "permissao insuficiente: papel "
                    f"'{claims.role}' nao autorizado"
                ),
            )
        return claims

    return _dep


# ---------------------------------------------------------------------------
# Guardas sobre `tenant_users` (owner protegido)
# ---------------------------------------------------------------------------

MemberOperation = Literal["remove", "change_role"]


def ensure_can_manage_member(
    *,
    actor_role: str,
    target_role: str,
    operation: MemberOperation,
    new_role: str | None = None,
) -> None:
    """Valida se `actor_role` pode executar `operation` sobre `target_role`.

    Regras (veja `docs/architecture/rbac-matrix.md`):

    - Apenas `owner` e `admin` gerenciam membros; demais -> 403.
    - `owner` e protegido: somente outro `owner` pode remove-lo ou
      rebaixar seu papel. Admin que tente recebe 403.
    - Mudanca de papel nao pode promover acima do proprio papel do ator
      (admin nao pode criar outro admin; apenas owner promove a admin).

    Levanta `HTTPException(403)` com mensagem curta e acionavel.
    Nao tem efeito colateral (puramente funcional) — o endpoint deve
    chamar esta funcao antes do UPDATE/DELETE em `tenant_users`.
    """
    if actor_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="apenas owner ou admin podem gerenciar membros",
        )

    if target_role not in _ROLE_RANK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"papel alvo desconhecido: {target_role!r}",
        )

    # Owner so pode ser tocado por outro owner.
    if target_role == "owner" and actor_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="apenas um owner pode gerenciar outro owner",
        )

    if operation == "change_role":
        if new_role is None or new_role not in _ROLE_RANK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"novo papel invalido: {new_role!r}",
            )
        # Nao e possivel promover alguem acima do proprio papel do ator.
        if role_rank(new_role) > role_rank(actor_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"ator com papel '{actor_role}' nao pode promover a "
                    f"'{new_role}'"
                ),
            )
    elif operation != "remove":
        # Defesa contra uso incorreto; nao e caminho de usuario.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"operacao desconhecida: {operation!r}",
        )
