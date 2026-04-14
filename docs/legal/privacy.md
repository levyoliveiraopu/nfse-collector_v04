# Politica de Privacidade

> Ultima atualizacao: 2026-04-13

Esta Politica de Privacidade descreve como a NFS-e SaaS ("Plataforma")
coleta, utiliza, compartilha, armazena e elimina dados pessoais, em
conformidade com a Lei Geral de Protecao de Dados Pessoais (LGPD - Lei
13.709/2018).

## 1. Controlador e contato

- **Controlador:** NFS-e SaaS (operado por Levy Oliveira).
- **Contato de privacidade / DPO (encarregado):**
  `privacidade@nfse-saas.local`.

## 2. Dados coletados

A Plataforma pode coletar os seguintes grupos de dados:

1. **Dados de cadastro e conta**
   - Nome, e-mail, senha (hash), telefone (opcional), empresa/razao social,
     CNPJ, perfil de acesso.
2. **Dados de uso da plataforma**
   - Acoes no painel, configuracoes, historico de execucoes,
     metadados de documentos e eventos operacionais.
3. **Dados tecnicos e de logs**
   - IP, user-agent, identificadores tecnicos, timestamps, logs de
     autenticacao e auditoria.
4. **Dados fiscais processados em nome do cliente**
   - Informacoes de NFS-e necessarias para consulta, conciliacao e
     disponibilizacao de arquivos.
5. **Certificado digital A1 (PFX)**
   - Arquivo PFX e metadados relacionados (apelido, validade, CNPJ vinculado),
     protegidos com criptografia AES-256-GCM.

## 3. Finalidades e bases legais (art. 7 da LGPD)

Tratamos dados pessoais para as finalidades abaixo:

- **Execucao de contrato e procedimentos preliminares** (art. 7, V):
  cadastro, autenticacao, prestacao do servico, suporte tecnico e cobranca.
- **Cumprimento de obrigacao legal/regulatoria** (art. 7, II):
  registros minimos, trilhas de auditoria e atendimento a requisicoes legitimas.
- **Legitimo interesse** (art. 7, IX):
  seguranca da plataforma, prevencao a fraude, melhoria de desempenho e
  estabilidade, com avaliacao de proporcionalidade.
- **Exercicio regular de direitos** (art. 7, VI):
  preservacao de evidencias para defesa em processos administrativos/judiciais.
- **Consentimento, quando aplicavel** (art. 7, I):
  comunicacoes opcionais e cenarios que exijam base especifica.

## 4. Compartilhamento de dados

Podemos compartilhar dados estritamente necessarios com operadores e
fornecedores de infraestrutura:

- **Hostinger**: hospedagem de servicos e banco de dados.
- **Backblaze B2 (S3 compativel)**: armazenamento de arquivos e exportacoes.
- **Resend**: envio transacional de e-mails (ex.: autenticacao, avisos).

Nao vendemos dados pessoais. Compartilhamentos adicionais ocorrerao apenas
quando houver base legal adequada.

## 5. Retencao e descarte

- Regra padrao da Plataforma: retencao operacional de **90 dias** para dados
  e artefatos vinculados a execucoes fiscais, conforme politica interna.
- Exportacoes podem possuir regra de retencao dedicada (ex.: 30 dias),
  conforme configuracao de storage.
- Apos os prazos de retencao, os dados sao eliminados ou anonimizados de forma
  segura, salvo obrigacao legal de guarda por prazo superior.

## 6. Direitos do titular (art. 18 da LGPD)

O titular pode solicitar, quando aplicavel:

- Confirmacao da existencia de tratamento;
- Acesso aos dados;
- Correcao de dados incompletos, inexatos ou desatualizados;
- Anonimizacao, bloqueio ou eliminacao de dados desnecessarios/excessivos;
- Portabilidade dos dados, observados segredos comercial e industrial;
- Eliminacao dos dados tratados com consentimento;
- Informacao sobre compartilhamentos;
- Revogacao do consentimento e oposicao ao tratamento, quando cabivel.

Solicitacoes devem ser enviadas para `privacidade@nfse-saas.local`.

## 7. Seguranca da informacao

Adotamos medidas tecnicas e organizacionais para proteger os dados, incluindo:

- Controle de acesso por tenant e perfil;
- Criptografia de dados sensiveis em repouso e em transito;
- Segregacao logica multi-tenant com RLS no banco de dados;
- Monitoramento, logs de auditoria e revisao periodica de seguranca.

## 8. Cookies e trackers

- Utilizamos cookies estritamente necessarios para autenticacao e sessao.
- Caso sejam adotados cookies analiticos/marketing no futuro, esta politica
  sera atualizada para refletir finalidade, prazo e mecanismo de opt-in/opt-out.

## 9. Transferencias internacionais

Quando houver uso de infraestrutura com processamento fora do Brasil,
adotaremos mecanismos contratuais e controles compativeis com a LGPD.

## 10. Atualizacoes desta politica

Esta Politica pode ser atualizada periodicamente. Mudancas relevantes serao
comunicadas em canais oficiais da Plataforma.
