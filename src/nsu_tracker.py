"""
Gerenciamento do estado de NSU (Número Sequencial Único) por CNPJ.

O arquivo config/estado/ultimo_nsu.json registra até onde cada cliente foi
processado. Isso permite que execuções subsequentes busquem apenas documentos
novos, em vez de reprocessar todo o histórico.

Formato do arquivo:
    {
        "12345678000199": 1050,
        "98765432000111": 340,
        "11223344000155": 0
    }

Regra fundamental: o NSU nunca regride. Se o sistema for interrompido no meio
do processamento, na próxima execução ele retoma a partir do último NSU salvo
com sucesso.
"""

import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)


def carregar_estado(estado_path: str) -> dict:
    """Lê o arquivo JSON de estado e retorna o dict de NSUs por CNPJ.

    Args:
        estado_path: Caminho para o arquivo ultimo_nsu.json.

    Returns:
        Dict mapeando CNPJ (str) → último NSU processado (int).
        Retorna {} se o arquivo não existir ou estiver corrompido.
    """
    if not os.path.isfile(estado_path):
        logger.debug(
            "Arquivo de estado não encontrado em '%s'. Criando com estado vazio.",
            estado_path,
        )
        try:
            salvar_estado({}, estado_path)
        except OSError as exc:
            logger.warning(
                "Não foi possível criar arquivo de estado em '%s': %s",
                estado_path,
                exc,
            )
        return {}

    try:
        with open(estado_path, "r", encoding="utf-8") as f:
            estado = json.load(f)

        if not isinstance(estado, dict):
            raise ValueError("O conteúdo do arquivo não é um objeto JSON.")

        logger.debug(
            "Estado carregado de '%s': %d CNPJ(s) registrado(s).",
            estado_path,
            len(estado),
        )
        return estado

    except (json.JSONDecodeError, ValueError) as exc:
        caminho_backup = f"{estado_path}.corrompido.bak"
        try:
            shutil.copy2(estado_path, caminho_backup)
            logger.warning(
                "Arquivo de estado corrompido em '%s'. "
                "Backup salvo em '%s'. Erro: %s. "
                "Iniciando com estado vazio.",
                estado_path,
                caminho_backup,
                exc,
            )
        except OSError as backup_exc:
            logger.warning(
                "Arquivo de estado corrompido em '%s' e não foi possível "
                "criar backup: %s. Iniciando com estado vazio.",
                estado_path,
                backup_exc,
            )

        return {}


def salvar_estado(estado: dict, estado_path: str) -> None:
    """Persiste o dict de NSUs em disco usando escrita atômica.

    A escrita atômica (gravar em .tmp e renomear) garante que uma
    interrupção no meio do processo não deixe o arquivo em estado
    corrompido — ou o arquivo antigo permanece intacto, ou o novo
    arquivo completo é colocado no lugar.

    Args:
        estado:      Dict mapeando CNPJ (str) → NSU (int).
        estado_path: Caminho de destino para o arquivo ultimo_nsu.json.
    """
    diretorio = os.path.dirname(estado_path)
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)

    caminho_tmp = f"{estado_path}.tmp"

    try:
        with open(caminho_tmp, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(caminho_tmp, estado_path)

        logger.debug(
            "Estado salvo em '%s': %d CNPJ(s).", estado_path, len(estado)
        )

    except OSError as exc:
        # Remove o .tmp se a operação falhou, para não deixar lixo no disco
        if os.path.isfile(caminho_tmp):
            try:
                os.remove(caminho_tmp)
            except OSError:
                pass
        raise OSError(
            f"Falha ao salvar estado em '{estado_path}': {exc}"
        ) from exc


def obter_ultimo_nsu(estado: dict, cnpj: str) -> int:
    """Retorna o último NSU registrado para o CNPJ, ou 0 se não houver registro.

    NSU 0 instrui a API ADN a retornar a partir do primeiro documento
    disponível para o CNPJ, equivalente a um reprocessamento completo.

    Args:
        estado: Dict de estado carregado por `carregar_estado`.
        cnpj:   14 dígitos do CNPJ sem formatação.

    Returns:
        Último NSU processado (int ≥ 0).
    """
    return estado.get(cnpj, 0)


def atualizar_nsu(estado: dict, cnpj: str, novo_nsu: int) -> dict:
    """Atualiza o NSU de um CNPJ no dict em memória (não salva em disco).

    O NSU nunca regride: a atualização só ocorre se `novo_nsu` for
    estritamente maior que o valor atual. Isso protege contra cenários
    em que a API retorne documentos fora de ordem ou o chamador passe
    um valor inconsistente.

    Args:
        estado:   Dict de estado atual (será modificado in-place e retornado).
        cnpj:     14 dígitos do CNPJ sem formatação.
        novo_nsu: Novo valor de NSU a registrar.

    Returns:
        O mesmo dict `estado` com o valor atualizado (ou inalterado se
        novo_nsu não for maior que o atual).
    """
    nsu_atual = estado.get(cnpj, 0)

    if novo_nsu > nsu_atual:
        estado[cnpj] = novo_nsu
        logger.debug(
            "NSU atualizado para CNPJ %s: %d → %d.", cnpj, nsu_atual, novo_nsu
        )
    else:
        logger.debug(
            "NSU não atualizado para CNPJ %s: novo valor %d não é maior que o atual %d.",
            cnpj,
            novo_nsu,
            nsu_atual,
        )

    return estado


def resetar_cnpj(estado_path: str, cnpj: str) -> None:
    """Remove o registro de NSU de um CNPJ, forçando reprocessamento completo.

    Na próxima execução, `obter_ultimo_nsu` retornará 0 para esse CNPJ,
    e a API ADN enviará todos os documentos disponíveis desde o início.

    Args:
        estado_path: Caminho para o arquivo ultimo_nsu.json.
        cnpj:        14 dígitos do CNPJ a ser resetado.
    """
    estado = carregar_estado(estado_path)

    if cnpj in estado:
        nsu_anterior = estado.pop(cnpj)
        salvar_estado(estado, estado_path)
        logger.info(
            "NSU do CNPJ %s resetado (era %d). Próxima execução reprocessará desde o início.",
            cnpj,
            nsu_anterior,
        )
        print(f"NSU do CNPJ {cnpj} resetado para 0 (era {nsu_anterior}).")
    else:
        logger.info(
            "CNPJ %s não encontrado no estado — nenhuma alteração necessária.",
            cnpj,
        )
        print(f"CNPJ {cnpj} não encontrado no estado — já está em 0.")
