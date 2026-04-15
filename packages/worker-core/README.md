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
- `nsu_tracker` — estado de NSU por CNPJ. Expoe o protocolo
  `NsuSource` (CORE-03) com duas implementacoes padrao:
  `InMemoryNsuSource` (testes, buffer em memoria) e `FileNsuSource`
  (compat com o JSON legado `config/estado/ultimo_nsu.json`). O
  backend DB-backed vem em API-13. As funcoes legadas
  `carregar_estado`/`salvar_estado`/`obter_ultimo_nsu`/`atualizar_nsu`/
  `resetar_cnpj` seguem disponiveis para `main.py --reset-nsu` e
  `src/diagnostico.py`.
- `excel_builder` — geracao do relatorio .xlsx com abas
  "Notas Emitidas" e "Resumo".
- `batch_processor` — orquestrador legado: le `config/clientes.csv`,
  processa cada cliente e grava via backend de storage.
- `storage_backend` — Protocol do contrato de persistencia.
- `local_uploader`, `gdrive_uploader`, `noop_uploader` — backends.

Ponto de atalho no nivel do pacote:

```python
from worker_core import fetch_nfse  # alias de fetcher.buscar_todos_dfe_novos
from worker_core import InMemoryNsuSource, FileNsuSource, NsuSource
```

`fetch_nfse(..., nsu_source=source)` delega a leitura/escrita do NSU
para a implementacao injetada: `source.get(cnpj)` define o ponto de
partida da paginacao e `source.set(cnpj, maior_nsu)` e chamado ao fim
quando o NSU progride. Sem `nsu_source`, o comportamento legado
(parametro `ultimo_nsu_salvo` + persistencia externa) e preservado.

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
