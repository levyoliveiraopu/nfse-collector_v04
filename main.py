"""
nfse-collector — ponto de entrada da linha de comando.

Uso:
  python main.py                              # mês anterior, todos os clientes
  python main.py --cnpj 12345678000199        # um CNPJ específico
  python main.py --ano 2026 --mes 03          # mês específico, todos
  python main.py --cnpj 12345678000199 --ano 2026 --mes 03
  python main.py --dry-run                    # simula sem uploads nem NSU
  python main.py --reset-nsu 12345678000199   # zera NSU e encerra
  python main.py --lote 1 --total-lotes 6     # processa lote 1 de 6
"""

import argparse
import os
import sys
from datetime import date

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Variáveis obrigatórias no .env
# ---------------------------------------------------------------------------

_VARS_OBRIGATORIAS = [
    "GOOGLE_CREDENTIALS_JSON",
    "GOOGLE_DRIVE_FOLDER_ROOT_ID",
    "NSU_ESTADO_PATH",
]


def _validar_env() -> None:
    """Encerra com mensagem de erro se alguma variável obrigatória estiver ausente."""
    ausentes = [v for v in _VARS_OBRIGATORIAS if not os.getenv(v)]
    if ausentes:
        print("Erro: variáveis obrigatórias ausentes no .env:")
        for v in ausentes:
            print(f"  {v}")
        print("Consulte config/.env.example para referência.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Cálculo de mês anterior
# ---------------------------------------------------------------------------

def _mes_anterior() -> tuple[int, int]:
    """Retorna (ano, mes) do mês anterior ao atual."""
    hoje = date.today()
    if hoje.month == 1:
        return hoje.year - 1, 12
    return hoje.year, hoje.month - 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfse-collector",
        description="Coleta NFS-e da API ADN Nacional e organiza no Google Drive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cnpj",
        metavar="CNPJ",
        help="Processa apenas o CNPJ informado (14 dígitos, sem formatação).",
    )
    parser.add_argument(
        "--ano",
        type=int,
        metavar="AAAA",
        help="Ano de competência (ex.: 2026). Padrão: mês anterior.",
    )
    parser.add_argument(
        "--mes",
        type=int,
        metavar="MM",
        choices=range(1, 13),
        help="Mês de competência (1–12). Padrão: mês anterior.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula o processamento sem fazer uploads nem salvar estado NSU.",
    )
    parser.add_argument(
        "--reset-nsu",
        metavar="CNPJ",
        help="Reseta o NSU do CNPJ informado para 0 e encerra.",
    )
    parser.add_argument(
        "--diagnostico",
        metavar="CNPJ",
        help=(
            "Testa autenticação mTLS e exibe estrutura da resposta da API ADN "
            "para o CNPJ informado. Não altera nenhum estado."
        ),
    )
    parser.add_argument(
        "--lote",
        type=int,
        metavar="N",
        help="Número do lote a processar (1-based). Requer --total-lotes.",
    )
    parser.add_argument(
        "--total-lotes",
        type=int,
        metavar="T",
        help="Total de lotes em que os clientes serão divididos.",
    )
    return parser


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    # Carregar .env antes de qualquer outra operação
    load_dotenv("config/.env")

    parser = _construir_parser()
    args = parser.parse_args()

    # --- Diagnóstico (ação isolada, encerra após executar) ---
    if args.diagnostico:
        nsu_estado_path = os.getenv("NSU_ESTADO_PATH", "config/estado/ultimo_nsu.json")
        from src.diagnostico import executar_diagnostico
        executar_diagnostico(args.diagnostico, "config/clientes.csv", nsu_estado_path)
        sys.exit(0)

    # --- Reset NSU (ação isolada, encerra após executar) ---
    if args.reset_nsu:
        _validar_env()
        nsu_estado_path = os.getenv("NSU_ESTADO_PATH", "config/estado/ultimo_nsu.json")
        from src import nsu_tracker
        nsu_tracker.resetar_cnpj(nsu_estado_path, args.reset_nsu)
        sys.exit(0)

    # --- Validar variáveis de ambiente ---
    _validar_env()

    # --- Validar parâmetros de lote ---
    if args.lote and not args.total_lotes:
        parser.error("--lote requer --total-lotes.")
    if args.total_lotes and not args.lote:
        parser.error("--total-lotes requer --lote.")
    if args.lote and args.total_lotes:
        if args.lote < 1 or args.lote > args.total_lotes:
            parser.error(
                f"--lote deve estar entre 1 e {args.total_lotes}."
            )
        if args.total_lotes < 2:
            parser.error("--total-lotes deve ser no mínimo 2.")

    # --- Determinar competência ---
    if args.ano and args.mes:
        ano, mes = args.ano, args.mes
    elif args.ano or args.mes:
        parser.error("Informe --ano e --mes juntos, ou nenhum dos dois.")
        return  # inalcançável; satisfaz o type checker
    else:
        ano, mes = _mes_anterior()

    # --- Carregar lista de clientes apenas para exibir o total ---
    csv_path = "config/clientes.csv"
    total_clientes = 0
    if os.path.isfile(csv_path):
        import csv as _csv
        with open(csv_path, newline="", encoding="utf-8") as f:
            linhas = [
                r for r in _csv.DictReader(f)
                if r.get("cnpj", "").strip()
                and (not args.cnpj or r.get("cnpj", "").strip() == args.cnpj)
            ]
        total_clientes = len(linhas)

    # --- Banner inicial ---
    modo = "DRY-RUN" if args.dry_run else "PRODUÇÃO"
    print("nfse-collector — iniciando")
    print(f"Competência   : {mes:02d}/{ano}")
    print(f"Clientes carregados: {total_clientes}")
    print(f"Modo          : {modo}")
    if args.lote:
        print(f"Lote          : {args.lote}/{args.total_lotes}")
    print()

    # --- Processar ---
    from src.batch_processor import processar_todos_clientes

    processar_todos_clientes(
        ano=ano,
        mes=mes,
        dry_run=args.dry_run,
        cnpj_filtro=args.cnpj,
        lote=args.lote,
        total_lotes=args.total_lotes,
    )


if __name__ == "__main__":
    main()
