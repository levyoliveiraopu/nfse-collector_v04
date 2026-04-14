# RoPA minima (Registro de Operacoes de Tratamento)

> Ultima atualizacao: 2026-04-13

## Escopo

Registro inicial das principais operacoes de tratamento de dados pessoais na
NFS-e SaaS, em linha com LGPD.

| Operacao | Categoria de dados | Titulares | Finalidade | Base legal LGPD | Compartilhamento | Retencao |
|---|---|---|---|---|---|---|
| Cadastro e autenticacao | Nome, e-mail, hash de senha, IP, logs de login | Usuarios do cliente | Criar conta, autenticar e controlar acesso | Art. 7, V e IX | Hostinger, Resend | Enquanto conta ativa + logs por 90 dias |
| Processamento de NFS-e | Dados fiscais e metadados operacionais | Clientes e contribuintes vinculados ao cliente contratante | Executar coleta/consulta e disponibilizar resultados | Art. 7, V e II | Hostinger, Backblaze B2 | 90 dias (padrao operacional) |
| Gestao de certificado A1 | Arquivo PFX, validade, CNPJ vinculado, metadados de uso | Cliente contratante | Autenticacao mTLS em prefeituras e execucao da coleta | Art. 7, V e VI | Hostinger (app), Backblaze B2 (artefatos) | Enquanto necessario para operacao contratada; descarte seguro ao encerrar |
| Suporte e atendimento | Nome, e-mail, historico de tickets e interacoes | Usuarios do cliente | Resolver incidentes, orientar uso e manter continuidade | Art. 7, V e IX | Resend | Tempo necessario para atendimento + 90 dias |

## Agentes de tratamento

- **Controlador:** NFS-e SaaS (operado por Levy Oliveira).
- **Operadores principais:** Hostinger, Backblaze B2, Resend.

## Medidas tecnicas/organizacionais

- Controle de acesso por tenant (RLS) e principio do menor privilegio.
- Criptografia de dados sensiveis (incluindo PFX com AES-256-GCM).
- Logs de auditoria, monitoramento e trilhas de acesso.
- Politicas de retencao e descarte automatico quando aplicavel.

## Canal para titulares e ANPD

- E-mail do encarregado (DPO): `privacidade@nfse-saas.local`.
