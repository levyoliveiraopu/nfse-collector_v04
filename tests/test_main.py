"""Testes para o módulo main (CLI e funções auxiliares)."""

from main import _mes_anterior, _construir_parser


class TestMesAnterior:
    def test_retorna_tupla_ano_mes(self):
        ano, mes = _mes_anterior()
        assert isinstance(ano, int)
        assert 1 <= mes <= 12

    def test_mes_anterior_nao_e_futuro(self):
        from datetime import date
        hoje = date.today()
        ano, mes = _mes_anterior()
        # O mês anterior nunca deve ser o mês atual
        if hoje.month > 1:
            assert mes == hoje.month - 1
            assert ano == hoje.year
        else:
            assert mes == 12
            assert ano == hoje.year - 1


class TestConstruirParser:
    def test_parser_aceita_cnpj(self):
        parser = _construir_parser()
        args = parser.parse_args(["--cnpj", "12345678000199"])
        assert args.cnpj == "12345678000199"

    def test_parser_aceita_ano_mes(self):
        parser = _construir_parser()
        args = parser.parse_args(["--ano", "2025", "--mes", "3"])
        assert args.ano == 2025
        assert args.mes == 3

    def test_parser_aceita_dry_run(self):
        parser = _construir_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_parser_aceita_reset_nsu(self):
        parser = _construir_parser()
        args = parser.parse_args(["--reset-nsu", "12345678000199"])
        assert args.reset_nsu == "12345678000199"

    def test_parser_aceita_lote_e_total(self):
        parser = _construir_parser()
        args = parser.parse_args(["--lote", "2", "--total-lotes", "6"])
        assert args.lote == 2
        assert args.total_lotes == 6

    def test_parser_sem_argumentos(self):
        parser = _construir_parser()
        args = parser.parse_args([])
        assert args.cnpj is None
        assert args.ano is None
        assert args.mes is None
        assert args.dry_run is False
        assert args.lote is None
        assert args.total_lotes is None
