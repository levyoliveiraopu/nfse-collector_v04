# worker-core

Motor Python reutilizavel de coleta NFS-e a partir do Sistema Nacional
(API ADN), extraido do coletor legado em `src/` pela tarefa CORE-01.

Este pacote e um **lift-and-shift** dos modulos originais, sem mudanca
de API. Refactor funcional (credenciais por argumento, callback de
progresso, NSU sem disco) acontece em CORE-02/03/04.

## Conteudo

- `auth` — autenticacao mTLS a partir de .pfx A1, extracao de CNPJ.
- `fetcher` — consulta paginada a API ADN, filtros por competencia e
  extracao estruturada dos XMLs de NFS-e.
- `nsu_tracker` — estado de NSU por CNPJ em JSON local.
- `excel_builder` — geracao do relatorio .xlsx com abas
  "Notas Emitidas" e "Resumo".
- `batch_processor` — orquestrador legado: le `config/clientes.csv`,
  processa cada cliente e grava via backend de storage.
- `storage_backend` — Protocol do contrato de persistencia.
- `local_uploader`, `gdrive_uploader`, `noop_uploader` — backends.

Ponto de atalho no nivel do pacote:

```python
from worker_core import fetch_nfse  # alias de fetcher.buscar_todos_dfe_novos
```

## Instalacao em modo editavel

A partir da raiz do repositorio:

```bash
pip install -e packages/worker-core
```

Opcionalmente com suporte a Google Drive:

```bash
pip install -e "packages/worker-core[gdrive]"
```

## Compatibilidade com `src/`

Os modulos em `src/` permanecem como shims finos que re-exportam de
`worker_core`, preservando `main.py` e os testes existentes em
`tests/`. Em proximos tickets os shims serao removidos.
