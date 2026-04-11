"""
Ferramenta de diagnóstico para o nfse-collector.

Verifica autenticação mTLS, conectividade com a API ADN e estrutura da
resposta para um CNPJ específico, sem alterar nenhum estado.

Uso via CLI:
    python main.py --diagnostico 12345678000199
"""

import csv
import os

from src import auth, nfse_fetcher, nsu_tracker


def executar_diagnostico(cnpj: str, csv_path: str, nsu_estado_path: str) -> None:
    """Executa diagnóstico completo para o CNPJ informado.

    Testa autenticação mTLS, busca um lote raw da API (NSU=0) e exibe a
    estrutura da resposta para identificar problemas de configuração.

    Não modifica nenhum estado (NSU, arquivos, Drive).

    Args:
        cnpj:           CNPJ de 14 dígitos do contribuinte a diagnosticar.
        csv_path:       Caminho para config/clientes.csv.
        nsu_estado_path: Caminho para o arquivo JSON de estado NSU.
    """
    sep = "=" * 56
    print(f"\n{sep}")
    print(f" DIAGNÓSTICO — CNPJ {cnpj}")
    print(sep)

    # 1. Localizar cliente no CSV
    cliente = _encontrar_cliente(cnpj, csv_path)
    if cliente is None:
        print(f"[ERRO]  CNPJ {cnpj} não encontrado em '{csv_path}' ou certificado ausente.")
        return

    cert_path = cliente["cert_path"]
    cert_password = cliente["cert_password"]
    razao_social = cliente["razao_social"]
    print(f"[INFO]  Razão social  : {razao_social}")
    print(f"[INFO]  Certificado   : {cert_path}")

    cert_tmp: str | None = None
    key_tmp: str | None = None

    try:
        # 2. Criar session mTLS
        print("\n--- Autenticação ---")
        try:
            session, cert_tmp, key_tmp, certificate = auth.criar_session_cliente(
                cert_path, cert_password
            )
            print("[OK]    Certificado carregado com sucesso.")
        except Exception as exc:
            print(f"[ERRO]  Falha ao carregar certificado: {exc}")
            return

        # 3. Testar autenticação
        resultado = auth.testar_autenticacao(session)
        status_icon = "[OK]   " if resultado["ok"] else "[ERRO] "
        print(f"{status_icon} {resultado['mensagem']}")

        if not resultado["ok"]:
            print("\n[!] Autenticação falhou — verifique o certificado e a conectividade.")
            return

        # 4. NSU atual salvo
        print("\n--- Estado NSU ---")
        try:
            estado = nsu_tracker.carregar_estado(nsu_estado_path)
            nsu_salvo = nsu_tracker.obter_ultimo_nsu(estado, cnpj)
            print(f"[INFO]  NSU salvo para {cnpj}: {nsu_salvo}")
            if nsu_salvo > 0:
                print(
                    "[!]    NSU > 0: documentos anteriores ao NSU salvo não serão buscados."
                )
                print(
                    "       Para reprocessar tudo: python main.py --reset-nsu " + cnpj
                )
        except Exception as exc:
            print(f"[AVISO] Não foi possível ler estado NSU: {exc}")
            nsu_salvo = 0

        # 5. Buscar lote raw a partir de NSU=0
        print("\n--- Consulta à API ADN (NSU=0) ---")
        try:
            lote = nfse_fetcher.buscar_lote_dfe(session, 0, cnpj)
        except Exception as exc:
            print(f"[ERRO]  Falha na consulta à API: {exc}")
            return

        chaves_resposta = list(lote.keys())
        max_nsu = lote.get("maxNSU", "?")
        print(f"[OK]    Resposta recebida.")
        print(f"[INFO]  Chaves top-level: {chaves_resposta}")
        print(f"[INFO]  maxNSU da API   : {max_nsu}")

        # 6. Inspecionar documentos
        documentos = lote.get("loteNfse", [])
        if "loteNfse" not in lote:
            print(
                "[AVISO] Chave 'loteNfse' ausente na resposta. "
                "A resposta pode usar um campo diferente."
            )
            # Tentar encontrar campo que contenha lista
            for chave, valor in lote.items():
                if isinstance(valor, list) and chave != "loteNfse":
                    print(f"[INFO]  Lista encontrada na chave '{chave}' ({len(valor)} itens).")
                    documentos = valor
                    break

        print(f"[INFO]  Documentos no lote: {len(documentos)}")

        if not documentos:
            print(
                "\n[!]    Nenhum documento retornado para NSU=0.\n"
                "       Possíveis causas:\n"
                "         1. O CNPJ não tem NFS-e emitidas/tomadas no ADN.\n"
                "         2. O parâmetro cnpjConsulta não está sendo aceito.\n"
                "         3. A chave da resposta não é 'loteNfse' (verifique acima)."
            )
            return

        # 7. Inspecionar primeiro documento
        print("\n--- Primeiro documento ---")
        primeiro = documentos[0]
        chaves_doc = list(primeiro.keys())
        nsu_doc = primeiro.get("nsu", "?")
        print(f"[INFO]  NSU do documento: {nsu_doc}")
        print(f"[INFO]  Campos presentes: {chaves_doc}")

        # 8. Extrair XML
        print("\n--- Extração de XML ---")
        xml_content = None

        doc_zip = primeiro.get("docZip")
        if isinstance(doc_zip, str) and doc_zip.strip():
            import base64
            import gzip
            try:
                xml_content = gzip.decompress(base64.b64decode(doc_zip)).decode("utf-8")
                print("[OK]    XML decodificado via 'docZip' (base64+gzip).")
            except Exception as exc:
                print(f"[ERRO]  Falha ao decodificar 'docZip': {exc}")
        else:
            for campo in ("xmlNfse", "xml", "xmlNFSe", "nfseXml", "documento"):
                valor = primeiro.get(campo)
                if isinstance(valor, str) and valor.strip():
                    xml_content = valor
                    print(f"[OK]    XML encontrado em campo de texto '{campo}'.")
                    break

        if xml_content is None:
            print("[ERRO]  XML não encontrado em nenhum campo conhecido.")
            print(f"        Campos disponíveis no documento: {chaves_doc}")
            print(
                "        Campos tentados: docZip, xmlNfse, xml, xmlNFSe, nfseXml, documento"
            )
        else:
            print(f"[OK]    Tamanho do XML: {len(xml_content)} caracteres")
            data = nfse_fetcher.extrair_data_emissao(xml_content)
            if data:
                print(f"[OK]    Data de emissão: {data.strftime('%d/%m/%Y')}")
            else:
                print("[AVISO] Data de emissão não identificada no XML.")

        # 9. Resumo
        print(f"\n{sep}")
        print(" RESUMO DO DIAGNÓSTICO")
        print(sep)
        if xml_content:
            print("[✓] API acessível e XML extraído com sucesso.")
            if nsu_salvo > 0:
                print(f"[!] NSU salvo ({nsu_salvo}) pode estar avançado — considere --reset-nsu.")
            else:
                print("[✓] NSU em 0 — próxima execução buscará a partir do início.")
            print(
                "\nPróximo passo:"
                f"\n  python main.py --cnpj {cnpj} --dry-run"
            )
        else:
            print("[✗] Não foi possível extrair o XML. Veja detalhes acima.")
        print(sep + "\n")

    finally:
        if cert_tmp or key_tmp:
            auth.limpar_temporarios(cert_tmp or "", key_tmp or "")


def _encontrar_cliente(cnpj: str, csv_path: str) -> dict | None:
    """Lê o CSV e retorna o cliente correspondente ao CNPJ, ou None."""
    if not os.path.isfile(csv_path):
        return None

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for linha in reader:
            cnpj_csv = linha.get("cnpj", "").strip()
            if cnpj_csv != cnpj:
                continue
            cert_path = linha.get("cert_path", "").strip()
            if not os.path.isfile(cert_path):
                return None
            return {
                "cnpj": cnpj_csv,
                "razao_social": linha.get("razao_social", "").strip(),
                "cert_path": cert_path,
                "cert_password": linha.get("cert_password", "").strip(),
            }

    return None
