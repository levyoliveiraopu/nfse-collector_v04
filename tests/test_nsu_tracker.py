"""Testes para o módulo nsu_tracker."""

import json
import os

from src import nsu_tracker
from worker_core.nsu_tracker import (
    FileNsuSource,
    InMemoryNsuSource,
    NsuSource,
)


class TestCarregarEstado:
    def test_arquivo_inexistente_retorna_vazio_e_cria_arquivo(self, tmp_path):
        estado_path = tmp_path / "nao_existe.json"
        resultado = nsu_tracker.carregar_estado(str(estado_path))
        assert resultado == {}
        assert estado_path.exists()
        assert json.loads(estado_path.read_text()) == {}

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


# ---------------------------------------------------------------------------
# Protocolo NsuSource (CORE-03)
# ---------------------------------------------------------------------------


class TestInMemoryNsuSource:
    def test_get_default_zero(self):
        source = InMemoryNsuSource()
        assert source.get("12345678000199") == 0

    def test_set_atualiza_valor(self):
        source = InMemoryNsuSource()
        source.set("12345678000199", 100)
        assert source.get("12345678000199") == 100

    def test_set_nao_regride(self):
        source = InMemoryNsuSource({"12345678000199": 200})
        source.set("12345678000199", 100)
        assert source.get("12345678000199") == 200

    def test_set_ignora_valor_igual(self):
        source = InMemoryNsuSource({"12345678000199": 200})
        source.set("12345678000199", 200)
        assert source.get("12345678000199") == 200

    def test_cnpjs_sao_isolados(self):
        source = InMemoryNsuSource()
        source.set("A", 10)
        source.set("B", 20)
        assert source.get("A") == 10
        assert source.get("B") == 20

    def test_initial_precarrega_estado(self):
        source = InMemoryNsuSource({"A": 5, "B": 7})
        assert source.get("A") == 5
        assert source.get("B") == 7
        assert source.snapshot() == {"A": 5, "B": 7}

    def test_snapshot_retorna_copia_independente(self):
        source = InMemoryNsuSource({"A": 1})
        snap = source.snapshot()
        snap["A"] = 999
        assert source.get("A") == 1

    def test_conforma_com_protocolo(self):
        assert isinstance(InMemoryNsuSource(), NsuSource)


class TestFileNsuSource:
    def test_get_default_zero_em_arquivo_novo(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        source = FileNsuSource(estado_path)
        assert source.get("12345678000199") == 0

    def test_set_persiste_em_disco(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        source = FileNsuSource(estado_path)
        source.set("12345678000199", 150)
        assert source.get("12345678000199") == 150
        # Outra instância apontando pro mesmo arquivo deve ler o valor.
        source2 = FileNsuSource(estado_path)
        assert source2.get("12345678000199") == 150

    def test_set_nao_regride(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        source = FileNsuSource(estado_path)
        source.set("12345678000199", 500)
        source.set("12345678000199", 100)
        assert source.get("12345678000199") == 500
        # Disco também permanece em 500.
        assert FileNsuSource(estado_path).get("12345678000199") == 500

    def test_carrega_arquivo_preexistente(self, tmp_path):
        estado_path = tmp_path / "estado.json"
        estado_path.write_text(json.dumps({"12345678000199": 42}))
        source = FileNsuSource(str(estado_path))
        assert source.get("12345678000199") == 42

    def test_set_nao_regride_nao_reescreve_arquivo(self, tmp_path):
        """Set com valor menor não altera o arquivo em disco."""
        estado_path = tmp_path / "estado.json"
        estado_path.write_text(json.dumps({"A": 500}))
        mtime_inicial = estado_path.stat().st_mtime_ns
        source = FileNsuSource(str(estado_path))
        source.set("A", 100)
        # Arquivo não foi regravado.
        assert estado_path.stat().st_mtime_ns == mtime_inicial
        assert json.loads(estado_path.read_text()) == {"A": 500}

    def test_cnpjs_sao_isolados_em_disco(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        source = FileNsuSource(estado_path)
        source.set("A", 10)
        source.set("B", 20)
        assert json.loads(open(estado_path).read()) == {"A": 10, "B": 20}

    def test_conforma_com_protocolo(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        assert isinstance(FileNsuSource(estado_path), NsuSource)

    def test_estado_path_acessivel(self, tmp_path):
        estado_path = str(tmp_path / "estado.json")
        source = FileNsuSource(estado_path)
        assert source.estado_path == estado_path
