# ADR-003 — Storage S3 externo, cifra PFX AES-GCM, retencao 90d sem arquivamento

- **Status:** Aceito
- **Data:** 2026-04-13

## Contexto

- XMLs de NFS-e podem totalizar grande volume (centenas/milhares por
  CNPJ/mes).
- Banco relacional nao deve armazenar blobs.
- Guarda fiscal (5 anos) **nao e responsabilidade nossa** — cliente pode
  baixar e armazenar onde quiser.
- Certificados PFX exigem protecao forte (criptografia em repouso).

## Decisao

### Storage
- Uso de bucket **S3-compativel** externo (Backblaze B2 como primeira
  escolha; Wasabi/AWS/Storj como fallback).
- Estrutura de chaves:
  `tenants/{tenant_id}/executions/{execution_id}/{nsu}.xml`
  `tenants/{tenant_id}/exports/{file_id}.{ext}`
  `tenants/{tenant_id}/credentials/{credential_id}.pfx.enc`
- Banco guarda somente metadados + `object_key` + `expires_at`.

### Retencao
- XML: **90 dias** no bucket, depois **apagado** por lifecycle rule
  (sem archive/glacier).
- Excel/ZIP gerados: **30 dias**.
- Cliente deve baixar o que quer manter dentro do prazo.
- Termos de Uso e onboarding deixam isso explicito.
- Banner permanente em `/arquivos` reforca a mensagem.
- Metadados no Postgres permanecem enquanto o tenant estiver ativo.

### Criptografia do PFX
- Algoritmo: **AES-256-GCM**.
- KEK (Key Encryption Key) mestra em variavel de ambiente do worker
  (origem: arquivo offline protegido).
- DEK por tenant derivada via HKDF(KEK, tenant_id).
- PFX cifrado enviado ao S3; senha cifrada em coluna separada do banco.
- Descriptografia somente no worker, em memoria; PEM gerado em `tmpfs`
  (`/dev/shm`), permissao 600, apagado ao fim via context manager.
- Logs **nunca** contem senha, PEM ou bytes do PFX.

## Consequencias

**Positivas**
- Custo de storage baixo e previsivel.
- Sem complexidade de arquivamento frio.
- Seguranca de PFX atende a praticas OWASP ASVS L2 relevantes.

**Negativas**
- Cliente que esquecer de baixar perde o XML — mitigado por avisos e
  e-mails mensais.
- Gerenciamento da chave mestra exige disciplina (backup offline).

## Reavaliacao

- Se 20%+ dos clientes pedirem retencao estendida: criar add-on pago com
  retencao de 12 meses.
- Se surgir obrigacao regulatoria para nosso papel: revisar ADR.
