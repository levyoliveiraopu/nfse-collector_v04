# CORE-04 — Refactor: callback de progresso por item

- **Trilha:** worker
- **Tamanho:** M
- **Status:** blocked (aguarda CORE-02 + CORE-03)
- **Depende de:** CORE-02, CORE-03

## Objetivo

`fetch_nfse(...)` emite callback para cada nota processada, permitindo
que o worker persista `execution_items` em tempo real.

## Entregaveis

- Assinatura:
  ```
  fetch_nfse(
      pfx_bytes, pfx_password, cnpj, nsu_source,
      on_progress: Callable[[NfseItem], None],
      on_log: Callable[[str, dict], None] = None,
  )
  ```
- `NfseItem` dataclass com campos: `nsu`, `chave_nfse`, `cnpj_emitente`,
  `data_emissao`, `valor`, `xml_bytes`, `status`, `error_code`,
  `error_message`.
- Retorno: resumo da execucao (contadores + nsu_from/to).

## Definition of Done

- [ ] Teste contra fixture ADN mockada: callback chamado N vezes.
- [ ] Erro em um item nao aborta o lote (exceto erros fatais).
