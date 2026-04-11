"""Testes para o módulo nsu_tracker."""

import json
import os

from src import nsu_tracker


class TestCarregarEstado:
    def test_arquivo_inexistente_retorna_vazio(self, tmp_path):
        resultado = nsu_tracker.carregar_estado(str(tmp_path / "nao_existe.json"))
        assert resultado == {}

    def test_arquivo_valido(self, tmp_path):
        estado_path = tmp_path / "estado.json"
        estado_path.write_text('{"12345678000199": 100, "98765432000111": 200}')
        resultado = nsu_tracker.carregar_estado(str(estado_path))
        assert resultado == {"12345678000199": 100, "98765432000111": 200}

    def test_arquivo_corrompido_retorna_vazio(self, tmp_path):
        estado_path = tmp_path / "estado.json"
        estado_path.write_text("{json invalido")
        resultado = nsu_tracker.carregar_estado(str(estado_path))
        assert resultado == {}
        # Deve ter criado backup
        assert (tmp_path / "estado.json.corrompido.bak").exists()

    def test_arquivo_nao_dict_retorna_vazio(self, tmp_path):
        estado_path = tmp_path / "estado.json"
        estado_path.write_text("[1, 2, 3]")
        resultado = nsu_tracker.carregar_estado(str(estado_path))
        assert resultado == {}


class TestSalvarEstado:
    def test_salvar_e_carregar(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        estado = {"12345678000199": 500}
        nsu_tracker.salvar_estado(estado, estado_path)

        carregado = nsu_tracker.carregar_estado(estado_path)
        assert carregado == {"12345678000199": 500}

    def test_escrita_atomica_nao_deixa_tmp(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        nsu_tracker.salvar_estado({"cnpj": 1}, estado_path)
        assert not os.path.exists(f"{estado_path}.tmp")

    def test_cria_diretorio_se_nao_existe(self, tmp_path):
        estado_path = str(tmp_path / "subdir" / "estado.json")
        nsu_tracker.salvar_estado({"cnpj": 1}, estado_path)
        assert os.path.isfile(estado_path)


class TestObterUltimoNsu:
    def test_cnpj_existente(self):
        estado = {"12345678000199": 100}
        assert nsu_tracker.obter_ultimo_nsu(estado, "12345678000199") == 100

    def test_cnpj_inexistente_retorna_zero(self):
        estado = {"12345678000199": 100}
        assert nsu_tracker.obter_ultimo_nsu(estado, "00000000000000") == 0

    def test_estado_vazio(self):
        assert nsu_tracker.obter_ultimo_nsu({}, "12345678000199") == 0


class TestAtualizarNsu:
    def test_atualiza_quando_maior(self):
        estado = {"12345678000199": 100}
        nsu_tracker.atualizar_nsu(estado, "12345678000199", 200)
        assert estado["12345678000199"] == 200

    def test_nao_regride(self):
        estado = {"12345678000199": 100}
        nsu_tracker.atualizar_nsu(estado, "12345678000199", 50)
        assert estado["12345678000199"] == 100

    def test_nao_atualiza_com_valor_igual(self):
        estado = {"12345678000199": 100}
        nsu_tracker.atualizar_nsu(estado, "12345678000199", 100)
        assert estado["12345678000199"] == 100

    def test_cnpj_novo(self):
        estado = {}
        nsu_tracker.atualizar_nsu(estado, "12345678000199", 50)
        assert estado["12345678000199"] == 50


class TestResetarCnpj:
    def test_reseta_cnpj_existente(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        nsu_tracker.salvar_estado({"12345678000199": 500, "outro": 100}, estado_path)

        nsu_tracker.resetar_cnpj(estado_path, "12345678000199")

        carregado = nsu_tracker.carregar_estado(estado_path)
        assert "12345678000199" not in carregado
        assert carregado["outro"] == 100

    def test_reseta_cnpj_inexistente_nao_quebra(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        nsu_tracker.salvar_estado({"outro": 100}, estado_path)

        nsu_tracker.resetar_cnpj(estado_path, "12345678000199")

        carregado = nsu_tracker.carregar_estado(estado_path)
        assert carregado == {"outro": 100}
