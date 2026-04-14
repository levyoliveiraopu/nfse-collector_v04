# Termos de Uso — NFS-e SaaS

> **Importante:** este documento e um modelo operacional para o produto em fase inicial e **nao substitui revisao juridica profissional**. Recomenda-se validacao por advogado antes da entrada em producao comercial.

**Ultima atualizacao:** 2026-04-13

## 1. Partes e aceite

1.1. Estes Termos de Uso (“Termos”) regulam o acesso e uso da plataforma NFS-e SaaS (“Plataforma”) pelo cliente contratante (“Cliente”).

1.2. Ao criar conta, concluir cadastro, contratar plano ou continuar utilizando a Plataforma, o Cliente declara que leu, compreendeu e concorda com estes Termos e com a Politica de Privacidade aplicavel.

1.3. Se o aceite for realizado por representante, este declara possuir poderes para vincular a pessoa juridica ou fisica contratante.

## 2. Objeto e escopo do servico

2.1. A Plataforma tem por objeto disponibilizar infraestrutura de software para coleta, processamento, organizacao e disponibilizacao de dados e artefatos relacionados a NFS-e, conforme funcionalidades ativas no plano contratado.

2.2. O servico e prestado em modelo SaaS, com acesso remoto, sujeito a evolucoes tecnicas, manutencoes e limites operacionais razoaveis.

2.3. O Cliente reconhece que o correto funcionamento de parte das rotinas depende de fatores externos, incluindo disponibilidade de sistemas de terceiros (prefeituras, provedores de e-mail, provedores de armazenamento e conectividade).

## 3. Cadastro, credenciais e uso permitido

3.1. O Cliente deve fornecer dados verdadeiros, completos e atualizados no cadastro, mantendo-os corretos durante toda a vigencia da contratacao.

3.2. O Cliente e responsavel por manter sob sigilo credenciais de acesso, certificados, senhas e chaves sob sua guarda, bem como por toda atividade executada em sua conta.

3.3. E vedado utilizar a Plataforma para finalidade ilicita, para tentativa de acesso nao autorizado, para violacao de direitos de terceiros ou para sobrecarga intencional da infraestrutura.

## 4. Retencao de dados e responsabilidade fiscal do Cliente

4.1. Em conformidade com a politica tecnica do produto (ADR-003), arquivos operacionais e artefatos vinculados as rotinas sao mantidos por **ate 90 (noventa) dias**, contados da data de processamento/geracao, podendo ser removidos automaticamente apos esse prazo.

4.2. O Cliente declara ciencia de que a Plataforma **nao substitui** obrigacoes legais de guarda fiscal e contabil, sendo responsabilidade exclusiva do Cliente manter seus proprios mecanismos de arquivamento e conservacao pelo prazo legal aplicavel.

4.3. O Cliente deve realizar exportacao e armazenamento externo dos documentos de seu interesse dentro do periodo de retencao informado.

## 5. Planos, pagamento, renovacao e cancelamento

5.1. O uso comercial da Plataforma esta sujeito aos planos, limites, valores, periodicidade e condicoes comerciais divulgados no momento da contratacao.

5.2. Salvo previsao diversa na proposta/plano, a renovacao ocorre automaticamente ao fim de cada ciclo, mediante pagamento do valor vigente.

5.3. O nao pagamento podera implicar suspensao de acesso, restricao de funcionalidades ou cancelamento da conta, apos comunicacao razoavel pelos canais disponiveis.

5.4. O Cliente podera solicitar cancelamento a qualquer tempo, observadas as regras de aviso previo, encerramento de ciclo e eventuais obrigacoes financeiras ja constituídas.

5.5. Encerrada a contratacao, os dados permanecerao sujeitos aos prazos de retencao tecnicos e legais aplicaveis, com posterior descarte seguro quando cabivel.

## 6. Propriedade intelectual

6.1. O codigo-fonte, marcas, layout, documentacao e demais ativos da Plataforma pertencem ao titular do produto, permanecendo todos os direitos reservados.

6.2. Estes Termos nao transferem ao Cliente titularidade sobre propriedade intelectual da Plataforma, concedendo apenas licenca limitada, nao exclusiva, intransferivel e revogavel de uso durante a vigencia contratual.

## 7. Limitacao de responsabilidade

7.1. A Plataforma e fornecida com esforcos tecnicos razoaveis de disponibilidade e seguranca, sem garantia de funcionamento ininterrupto ou livre de erros em 100% do tempo.

7.2. Na extensao permitida pela lei, o fornecedor nao responde por lucros cessantes, danos indiretos, perda de oportunidade, danos reputacionais ou prejuizos decorrentes de falhas de terceiros, mau uso, configuracoes incorretas, compartilhamento indevido de credenciais ou descumprimento de orientacoes operacionais pelo Cliente.

7.3. Eventual responsabilidade direta comprovada fica limitada ao montante efetivamente pago pelo Cliente nos 3 (tres) meses anteriores ao evento danoso, salvo hipoteses de dolo ou disposicao legal imperativa em contrario.

## 8. Privacidade e protecao de dados

8.1. O tratamento de dados pessoais observara a legislacao aplicavel, incluindo a Lei Geral de Protecao de Dados (Lei no 13.709/2018), e as regras descritas na Politica de Privacidade.

8.2. O Cliente declara possuir base legal adequada para inserir e processar dados na Plataforma, quando atuar como controlador desses dados.

## 9. Alteracoes dos Termos

9.1. Estes Termos podem ser atualizados para refletir mudancas legais, regulatorias, tecnicas ou comerciais.

9.2. A versao vigente sera disponibilizada em area publica de “Legal/Termos”, com data de ultima atualizacao.

## 10. Legislacao e foro

10.1. Estes Termos sao regidos pelas leis da Republica Federativa do Brasil.

10.2. Fica eleito o foro da comarca do domicilio do fornecedor da Plataforma, com renuncia a qualquer outro, por mais privilegiado que seja, ressalvadas hipoteses de competencia absoluta e direitos do consumidor quando aplicaveis.

## 11. Contato

11.1. Dúvidas sobre estes Termos podem ser encaminhadas pelos canais oficiais de suporte indicados na Plataforma.

---

## Referencias de implementacao no produto

Para cumprimento de DoD do ticket DOCS-01, este documento deve ser referenciado:

- na tela de signup (checkbox de aceite com link para `docs/legal/terms.md` e pagina publica equivalente);
- na rota `/legal` do app/site, contendo link visivel para “Termos de Uso”.

> Neste repositorio, as aplicacoes `app` e `site` ainda nao foram inicializadas; por isso, a referencia operacional foi registrada neste documento e no `README.md` ate a entrega das trilhas APP/SITE.
