"""Testes unitarios do RBAC (API-04).

Cobre:
- `require_role(...)` devolve 403 quando o papel nao bate com o
  conjunto permitido, e os mesmos claims quando bate.
- `require_role(min_role=...)` respeita a hierarquia.
- `require_role` via TestClient+FastAPI: token com papel `viewer` nao
  cria empresa (403), token com papel `admin` passa. Router efemero
  evita acoplamento com API-05, que ainda nao existe.
- `ensure_can_manage_member` protege o `owner`: admin nao remove nem
  rebaixa owner; owner pode; nao-gestores (operator/viewer) recebem 403.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.security.jwt import AccessClaims
from api.security.rbac import (
    ROLES,
    ensure_can_manage_member,
    require_role,
    role_rank,
)


def _claims(role: str) -> AccessClaims:
    now = datetime.now(tz=timezone.utc)
    return AccessClaims(
        sub=uuid4(),
        tid=uuid4(),
        role=role,
        jti="jti-test",
        iat=now,
        exp=now,
    )


# ---------------------------------------------------------------------------
# require_role: validacao direta da funcao retornada
# ---------------------------------------------------------------------------


def test_require_role_aceita_papel_permitido() -> None:
    dep = require_role("admin")
    claims = _claims("admin")
    assert dep(claims=claims) is claims


@pytest.mark.parametrize("role", ["owner", "operator", "viewer"])
def test_require_role_rejeita_papel_nao_permitido(role: str) -> None:
    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(claims=_claims(role))
    assert exc.value.status_code == 403
    assert role in exc.value.detail


def test_require_role_aceita_varios_papeis() -> None:
    dep = require_role("owner", "admin")
    for role in ("owner", "admin"):
        assert dep(claims=_claims(role)).role == role
    for role in ("operator", "viewer"):
        with pytest.raises(HTTPException) as exc:
            dep(claims=_claims(role))
        assert exc.value.status_code == 403


def test_require_role_min_role_respeita_hierarquia() -> None:
    dep = require_role(min_role="admin")
    # admin e owner passam
    assert dep(claims=_claims("owner")).role == "owner"
    assert dep(claims=_claims("admin")).role == "admin"
    # operator e viewer nao
    for role in ("operator", "viewer"):
        with pytest.raises(HTTPException) as exc:
            dep(claims=_claims(role))
        assert exc.value.status_code == 403


def test_require_role_min_role_combina_com_allowed() -> None:
    # admin+ OU operator — usado quando um papel inferior tem excecao
    dep = require_role("operator", min_role="admin")
    for role in ("owner", "admin", "operator"):
        assert dep(claims=_claims(role)).role == role
    with pytest.raises(HTTPException):
        dep(claims=_claims("viewer"))


def test_require_role_falha_fechado_em_papel_desconhecido() -> None:
    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(claims=_claims("superuser"))
    assert exc.value.status_code == 403


def test_require_role_rejeita_configuracao_invalida() -> None:
    with pytest.raises(ValueError):
        require_role()
    with pytest.raises(ValueError):
        require_role("ceo")  # papel fora do dominio
    with pytest.raises(ValueError):
        require_role(min_role="ceo")


def test_role_rank_conhece_os_quatro_papeis() -> None:
    # Ancoragem: rank cresce de viewer para owner.
    ranks = [role_rank(r) for r in ("viewer", "operator", "admin", "owner")]
    assert ranks == sorted(ranks)
    assert role_rank("desconhecido") == 0


def test_roles_batem_com_check_do_banco() -> None:
    # Domo do CHECK `ck_tenant_users_role` em 0001_initial_identity.py.
    assert set(ROLES) == {"owner", "admin", "operator", "viewer"}


# ---------------------------------------------------------------------------
# require_role sob TestClient — DoD: viewer -> 403 ao criar empresa.
# ---------------------------------------------------------------------------


@pytest.fixture()
def probe_client(monkeypatch: pytest.MonkeyPatch):
    """App FastAPI minimo com `POST /_probe/companies` protegido por
    `require_role("owner","admin","operator")` — reflete a linha de
    companies da matriz em `docs/architecture/rbac-matrix.md`.

    Mocka `get_current_claims` para extrair o papel do header custom
    `X-Test-Role` e `assert_tenant_active` para aceitar sempre — o
    objetivo aqui e provar o comportamento do RBAC, nao re-testar API-03.
    """
    from api.security import rbac as rbac_module
    from fastapi import Header

    # Substituimos a dependency encadeada `assert_tenant_active` do rbac
    # por uma que le o papel do header — isola o teste do ciclo JWT/DB.
    def fake_assert_tenant_active(
        x_test_role: str | None = Header(default=None, alias="X-Test-Role"),
    ):
        if not x_test_role:
            raise HTTPException(status_code=401, detail="sem papel de teste")
        return _claims(x_test_role)

    monkeypatch.setattr(
        rbac_module, "assert_tenant_active", fake_assert_tenant_active
    )

    app = FastAPI()

    @app.post("/_probe/companies", status_code=201)
    def create_company_probe(
        claims: AccessClaims = Depends(
            rbac_module.require_role("owner", "admin", "operator")
        ),
    ):
        return {"role": claims.role}

    @app.delete("/_probe/tenant")
    def delete_tenant_probe(
        claims: AccessClaims = Depends(rbac_module.require_role(min_role="owner")),
    ):
        return {"role": claims.role}

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("owner", 201),
        ("admin", 201),
        ("operator", 201),
        ("viewer", 403),
    ],
)
def test_probe_create_company_respeita_rbac(
    probe_client, role: str, expected_status: int
) -> None:
    resp = probe_client.post("/_probe/companies", headers={"X-Test-Role": role})
    assert resp.status_code == expected_status
    if expected_status == 403:
        assert "permissao insuficiente" in resp.json()["detail"]
        assert role in resp.json()["detail"]


def test_probe_delete_tenant_somente_owner(probe_client) -> None:
    for role in ("admin", "operator", "viewer"):
        resp = probe_client.delete("/_probe/tenant", headers={"X-Test-Role": role})
        assert resp.status_code == 403
    resp = probe_client.delete("/_probe/tenant", headers={"X-Test-Role": "owner"})
    assert resp.status_code == 200


def test_probe_sem_header_retorna_401(probe_client) -> None:
    # RBAC nao pode ser alcancado sem autenticacao — quem barra e o
    # `assert_tenant_active` (mock), equivalente ao 401 de API-03.
    resp = probe_client.post("/_probe/companies")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# ensure_can_manage_member — owner protegido.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", ["viewer", "operator", "admin"])
def test_admin_pode_remover_nao_owner(target: str) -> None:
    # Nao levanta.
    ensure_can_manage_member(
        actor_role="admin", target_role=target, operation="remove"
    )


def test_admin_nao_pode_remover_owner() -> None:
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role="admin", target_role="owner", operation="remove"
        )
    assert exc.value.status_code == 403
    assert "owner" in exc.value.detail


def test_admin_nao_pode_rebaixar_owner() -> None:
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role="admin",
            target_role="owner",
            operation="change_role",
            new_role="admin",
        )
    assert exc.value.status_code == 403


def test_owner_pode_remover_outro_owner() -> None:
    ensure_can_manage_member(
        actor_role="owner", target_role="owner", operation="remove"
    )


def test_owner_pode_rebaixar_outro_owner() -> None:
    ensure_can_manage_member(
        actor_role="owner",
        target_role="owner",
        operation="change_role",
        new_role="admin",
    )


@pytest.mark.parametrize("actor", ["operator", "viewer"])
def test_nao_gestor_nao_pode_gerenciar_membros(actor: str) -> None:
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role=actor, target_role="viewer", operation="remove"
        )
    assert exc.value.status_code == 403
    assert "gerenciar membros" in exc.value.detail


def test_admin_nao_pode_promover_a_admin() -> None:
    # admin promovendo viewer -> admin seria permitir criar pares;
    # regra: novo papel nao pode ser superior ao proprio papel.
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role="admin",
            target_role="viewer",
            operation="change_role",
            new_role="owner",
        )
    assert exc.value.status_code == 403
    assert "owner" in exc.value.detail


def test_admin_pode_promover_viewer_para_operator() -> None:
    ensure_can_manage_member(
        actor_role="admin",
        target_role="viewer",
        operation="change_role",
        new_role="operator",
    )


def test_owner_pode_promover_para_admin() -> None:
    ensure_can_manage_member(
        actor_role="owner",
        target_role="operator",
        operation="change_role",
        new_role="admin",
    )


def test_change_role_com_new_role_invalido_retorna_403() -> None:
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role="owner",
            target_role="admin",
            operation="change_role",
            new_role=None,
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException):
        ensure_can_manage_member(
            actor_role="owner",
            target_role="admin",
            operation="change_role",
            new_role="ceo",
        )


def test_target_role_desconhecido_retorna_403() -> None:
    with pytest.raises(HTTPException) as exc:
        ensure_can_manage_member(
            actor_role="owner", target_role="intern", operation="remove"
        )
    assert exc.value.status_code == 403
