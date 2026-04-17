# Runbook — erro de parse do retorno do portal

## Escopo

Use este runbook para ocorrencias com o codigo:

- `PARSE_ERROR`

## Sintomas

- Worker baixou resposta do portal mas falhou ao interpretar o XML/JSON.
- `chave_nfse` gravada, mas item marcado com `status='parse_error'`.
- Log mostra excecao em `worker_core.collector` ou `worker_core.parser`.
- Detalhe da ocorrencia inclui trecho do payload que quebrou o contrato.

## Causas comuns

1. **Mudanca de schema do portal**: prefeitura atualizou o XSD/WSDL sem
   aviso previo.
2. **Resposta parcialmente corrompida** (bytes truncados, BOM, encoding
   misturado).
3. **Payload HTML no lugar de XML** (ex.: portal caiu e serviu pagina de
   erro em HTML como corpo 200).
4. **Namespace novo** ou `xsi:type` inesperado que nosso parser ignora.

## Diagnostico

1. Abrir a ocorrencia e copiar o `detail` (fragmento da resposta).
2. Salvar o XML bruto em `/tmp/raw.xml` e validar com `xmllint` quando
   possivel:
   ```bash
   xmllint --noout --schema docs/schemas/<portal>.xsd /tmp/raw.xml
   ```
3. Conferir se outras empresas da mesma prefeitura tambem apresentam
   `PARSE_ERROR` no mesmo intervalo — indicativo de mudanca de contrato.
4. Comparar com o ultimo payload valido arquivado em S3
   (`tenants/<tid>/executions/<eid>/<nsu>.xml`).

## Mitigacao

### Problema pontual (uma empresa / um NSU)

1. Registrar a ocorrencia como `ack` e acompanhar reprocessamento.
2. Se reprocesso voltar com sucesso -> `resolved` com nota
   "retorno inconsistente momentaneo".

### Problema sistemico (prefeitura inteira)

1. Abrir issue de engenharia apontando:
   - CNPJ da prefeitura / portal;
   - diff entre XML anterior e atual;
   - amostra de `execution_id` afetados.
2. Travar agendamentos da prefeitura afetada temporariamente
   (`POST /schedules/:id { enabled: false }`) para nao gerar alarme em
   loop.
3. Patch do parser segue via PR regular. Retomar agendamentos apos
   validacao em staging.

## Quando escalar

- Mais de 3 prefeituras com `PARSE_ERROR` na mesma janela de 24h: abrir
  incidente — pode indicar bug no nosso deploy, nao nos portais.
- `PARSE_ERROR` com taxa > 5% dos itens coletados: escalar para
  engenharia imediatamente.

## Prevencao

- Contratos de schema versionados em `docs/schemas/` (quando disponiveis).
- Testes de regressao com fixtures de retorno real por prefeitura.
- Alerta de Grafana (INFRA-07) quando taxa de `PARSE_ERROR` cruza
  threshold.
