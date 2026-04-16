# worker-core

Motor Python reutilizavel de coleta NFS-e a partir do Sistema Nacional
(API ADN), extraido do coletor legado em `src/` pela tarefa CORE-01.

Extraido como `lift-and-shift` em CORE-01, o pacote passou pelos refactors
previstos: CORE-02 (PFX em memoria via `mtls_session`), CORE-03 (NSU via
`NsuSource`) e CORE-04 (callback de progresso por item via `fetch_nfse`).

## Conteudo

- `auth` — autenticacao mTLS a partir de .pfx A1 (`mtls_session` consome
  bytes em memoria; `criar_session_cliente` segue como wrapper de compat),
  extracao de CNPJ.
- `fetcher` — consulta paginada a API ADN, filtros por competencia e
  extracao estruturada dos XMLs de NFS-e.
- `collector` — `fetch_nfse(...)` de alto nivel: abre `mtls_session`,
  pagina via `fetcher`, emite `NfseItem` por nota via `on_progress` e
  devolve `FetchSummary`. API alvo do worker SaaS (API-13).
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
- `storage` (CORE-05) — cliente S3-compat para upload de XMLs e
  exports (`S3StorageClient`, `upload_xml`, `upload_export`). Le as
  vars `S3_*` via `S3Settings.from_env()`; devolve `UploadResult` com
  `object_key`, `sha256` (hex) e `size`. Retry com backoff
  exponencial em falhas transientes (`SlowDown`,
  `ServiceUnavailable`, `InternalError`, `EndpointConnectionError`).
  Integracao com `batch_processor` fica para API-11 / CORE-04.

Ponto de atalho no nivel do pacote:

```python
from worker_core import fetch_nfse, NfseItem, FetchSummary
from worker_core import InMemoryNsuSource, FileNsuSource, NsuSource
from worker_core import S3StorageClient  # CORE-05
```

Exemplo de upload S3 (CORE-05):

```python
from worker_core import S3StorageClient

client = S3StorageClient()  # le S3_* do ambiente
xml_res = client.upload_xml(tenant_id, execution_id, nsu=42, xml_bytes=b"<NFSe/>")
exp_res = client.upload_export(tenant_id, file_id, path_or_bytes=excel_bytes, ext="xlsx")
print(xml_res.object_key, xml_res.sha256, xml_res.size)
```

### `fetch_nfse` (CORE-04)

API de alto nivel consumida pelo worker SaaS. Exemplo:

```python
def on_progress(item: NfseItem) -> None:
    # persiste execution_item, upload XML -> S3, etc.
    ...

summary = fetch_nfse(
    pfx_bytes=pfx_bytes,          # PFX ja decifrado (ADR-003)
    pfx_password=senha,
    cnpj="12345678000199",
    nsu_source=source,            # NsuSource injetado (CORE-03)
    on_progress=on_progress,      # chamado 1x por nota
    on_log=lambda e, p: ...,      # opcional, eventos estruturados
)
print(summary.total_sucesso, summary.nsu_to)
```

Garantias:

- Abre `mtls_session` internamente — o chamador nunca mexe em disco.
- Erro de **um item** (XML corrompido, excecao dentro de `on_progress`)
  nao aborta o lote: e registrado via `on_log` e a coleta segue.
- Erros **fatais** (PFX invalido, senha errada, cert vencido) propagam
  `ValueError` antes de qualquer callback.
- `NsuSource.get`/`set` delega a persistencia do NSU (`source.get(cnpj)`
  define o ponto inicial; `source.set(cnpj, maior_nsu)` ao fim quando
  progride).

### `buscar_todos_dfe_novos` (baixo nivel)

Continua exportado em `worker_core.fetcher` para cenarios em que o
chamador ja tem uma `requests.Session` mTLS pronta (ex.: o coletor
historico `main.py`). Aceita `nsu_source` opcional — quando omitido,
o comportamento legado (`ultimo_nsu_salvo` + persistencia externa) e
preservado.

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
