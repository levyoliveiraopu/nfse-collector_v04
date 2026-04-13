# CORE-05 — Cliente S3 para upload de XML + Excel

- **Trilha:** worker
- **Tamanho:** M
- **Status:** blocked (aguarda CORE-01 + INFRA-06)
- **Depende de:** CORE-01, INFRA-06

## Objetivo

Adicionar ao `worker_core` um cliente S3 para upload dos XML/Excel
gerados.

## Entregaveis

- `worker_core/storage.py` com:
  - `upload_xml(tenant_id, execution_id, nsu, xml_bytes) -> object_key`.
  - `upload_export(tenant_id, file_id, path_or_bytes, ext) -> object_key`.
- Uso de boto3 com endpoint customizavel (B2).
- Checksum SHA-256 calculado e retornado.
- Retry com backoff em falha transitoria.

## Definition of Done

- [ ] Upload real para bucket de teste.
- [ ] Object key segue convencao do ADR-003.
- [ ] Testes com S3 mock (moto).
