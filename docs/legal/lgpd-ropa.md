# ROPA e base legal — dados fiscais e certificados

Este documento organiza o item 5.1 do checklist de producao. Ele nao substitui
revisao juridica, mas fixa o inventario tecnico minimo para LGPD antes do go-live.

## Papeis LGPD

- **Cliente/tenant:** controlador dos dados fiscais de suas empresas, usuarios e certificados.
- **Plataforma:** operador, tratando dados para prestar coleta, organizacao, exportacao e suporte.
- **Suboperadores:** provedores de infraestrutura usados em producao, como VPS, S3/B2, email transacional e observabilidade.

## Atividades de tratamento

| Atividade | Dados | Finalidade | Base legal sugerida | Retencao |
|---|---|---|---|---|
| Cadastro de tenant/usuario | nome, email, tenant, papel | autenticar e autorizar acesso | execucao de contrato | enquanto conta ativa + prazo de auditoria |
| Cadastro de empresas | CNPJ, razao social, municipio, status | identificar contribuinte consultado | execucao de contrato/obrigacao legal do cliente | enquanto empresa ativa + prazo fiscal do cliente |
| Credencial A1 | PFX cifrado, senha cifrada, validade/cert metadata | autenticar no portal ADN | execucao de contrato | enquanto credencial ativa; revogada quando substituida/removida |
| Coleta NFS-e | XML, chave, NSU, valores, datas, prestador/tomador quando presentes | entregar documentos fiscais ao cliente | execucao de contrato/obrigacao legal do cliente | conforme `docs/legal/data-retention-policy.md` |
| Logs operacionais | eventos, ids tecnicos, status, codigos de erro | seguranca, suporte e auditoria tecnica | legitimo interesse/execucao de contrato | menor prazo util; sem segredos |
| Backups | dump cifrado do banco | recuperacao de desastre | execucao de contrato/seguranca | conforme politica de backup |

## Dados sensiveis/segredos operacionais

PFX, senha de PFX, refresh token, ciphertext e presigned URL sao segredos
operacionais. Devem ser criptografados/redigidos e nunca enviados por canal de
suporte. O filtro de logs `SensitiveDataFilter` e parte do controle tecnico.

## Pendencias juridicas antes de producao

- Revisao final dos Termos de Uso e Politica de Privacidade por responsavel legal.
- Lista formal de suboperadores reais do ambiente de producao.
- Confirmacao do prazo fiscal/contratual esperado pelo publico-alvo.
- Processo de atendimento a titulares: acesso, correcao, eliminacao e portabilidade quando aplicavel.
