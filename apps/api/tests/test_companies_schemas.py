"""Testes unitarios dos schemas Pydantic de `/companies` (API-05)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.companies.schemas import CompanyIn, CompanyUpdate


def _valid_payload(**overrides) -> dict:
    base = {
        "cnpj": "11.222.333/0001-81",
        "razao_social": "Acme Servicos Contabeis LTDA",
        "nome_fantasia": "Acme",
        "municipio_ibge": "3550308",
        "uf": "sp",
        "status": "active",
        "portal_provider": "betha",
        "notes": None,
    }
    base.update(overrides)
    return base


class TestCompanyIn:
    def test_normaliza_cnpj_e_uf(self) -> None:
        payload = CompanyIn(**_valid_payload())
        assert payload.cnpj == "11222333000181"
        assert payload.uf == "SP"

    def test_rejeita_cnpj_com_dv_invalido(self) -> None:
        with pytest.raises(ValidationError) as exc:
            CompanyIn(**_valid_payload(cnpj="11222333000180"))
        assert "CNPJ invalido" in str(exc.value)

    def test_rejeita_cnpj_com_comprimento_errado(self) -> None:
        with pytest.raises(ValidationError) as exc:
            CompanyIn(**_valid_payload(cnpj="123"))
        assert "14 digitos" in str(exc.value)

    def test_rejeita_uf_desconhecida(self) -> None:
        with pytest.raises(ValidationError):
            CompanyIn(**_valid_payload(uf="XX"))

    def test_rejeita_status_fora_do_dominio(self) -> None:
        with pytest.raises(ValidationError):
            CompanyIn(**_valid_payload(status="deleted"))

    def test_status_default_active(self) -> None:
        payload = _valid_payload()
        payload.pop("status")
        assert CompanyIn(**payload).status == "active"

    def test_nome_fantasia_opcional(self) -> None:
        payload = _valid_payload(nome_fantasia=None)
        model = CompanyIn(**payload)
        assert model.nome_fantasia is None


class TestCompanyUpdate:
    def test_aceita_payload_vazio(self) -> None:
        # Pydantic aceita; o handler e que rejeita updates vazios.
        model = CompanyUpdate()
        assert model.model_dump(exclude_unset=True) == {}

    def test_nao_possui_campo_cnpj(self) -> None:
        # CNPJ e imutavel — schema nao deve expor esse campo.
        with pytest.raises(ValidationError):
            CompanyUpdate(cnpj="11222333000181")  # type: ignore[call-arg]

    def test_uf_normalizada(self) -> None:
        model = CompanyUpdate(uf="rj")
        assert model.uf == "RJ"

    def test_uf_none_permanece_none(self) -> None:
        model = CompanyUpdate()
        assert model.uf is None

    def test_rejeita_uf_invalida(self) -> None:
        with pytest.raises(ValidationError):
            CompanyUpdate(uf="YY")

    def test_exclude_unset_so_retorna_campos_informados(self) -> None:
        model = CompanyUpdate(razao_social="Novo Nome")
        data = model.model_dump(exclude_unset=True)
        assert data == {"razao_social": "Novo Nome"}
