# Pendencias manuais (owner) — issues fechadas

> Este documento lista as acoes que **so o owner** (voce, @LevyOliveirabr)
> pode executar para cada issue fechada. Cada item traz um passo-a-passo
> em linguagem simples, pensado para quem nao e tecnico em infra/legal.
>
> As issues marcadas como "Nenhuma acao manual" foram totalmente entregues
> pelo agente no PR correspondente — nao ha nada a fazer ali.

## Resumo rapido

| Issue | Ticket | Acao manual? | Tempo estimado |
|-------|--------|--------------|----------------|
| #3    | INFRA-01 (Hardening VPS)       | **SIM — critico** | 60–90 min |
| #19   | CORE-01 (Refactor worker)      | Nenhuma          | — |
| #25   | API-01 (Bootstrap FastAPI)     | Nenhuma          | — |
| #40   | DS-01 (Bootstrap Next.js)      | Nenhuma          | — |
| #71   | DOCS-01 (Termos de Uso)        | **SIM — revisao juridica** | 1–2 semanas (advogado) |
| #72   | DOCS-02 (Privacidade / LGPD)   | **SIM — publicacao + aceite** | depende de APP-xx |
| #73   | DOCS-03 (Runbook credencial)   | Nenhuma agora (uso em incidente) | — |
| #74   | DOCS-04 (Runbook portal fora)  | Nenhuma agora (uso em incidente) | — |
| #77   | GOV-07 (PR Guardrail)          | **SIM — config GitHub**  | 5 min |

---

## 1. #77 — GOV-07: Proteger a branch `main` no GitHub (5 min)

### Por que precisa

O agente criou um "workflow" (um robo do GitHub) que checa se toda Pull
Request (PR) atualiza `STATE.md` e `CHANGELOG.md`. Mas o GitHub **nao
obriga** automaticamente que esse robo precise aprovar — voce tem que
ligar essa obrigatoriedade nas configuracoes do repositorio.

Sem esse passo, alguem pode dar merge em uma PR mesmo que o robo tenha
reprovado.

### Passo a passo

1. Abra o repositorio no GitHub no navegador:
   `https://github.com/LevyOliveirabr/nfse-collector_v04`
2. Clique em **Settings** (aba no topo, ultima a direita).
3. No menu esquerdo, clique em **Branches**.
4. Em "Branch protection rules", clique em **Add branch ruleset** (ou
   **Add rule** no layout antigo).
5. Em **Branch name pattern**, digite: `main`
6. Marque as seguintes caixas:
   - [x] **Require a pull request before merging**
     - Sub-opcao: **Require approvals** = 0 (voce esta sozinho; pode
       deixar em 0 por enquanto).
   - [x] **Require status checks to pass before merging**
     - Em "Status checks that are required", procure e selecione:
       **`Require STATE.md + CHANGELOG.md update`**
       (se nao aparecer, rode qualquer PR uma vez — o nome so aparece
       apos a primeira execucao do workflow).
   - [x] **Do not allow bypassing the above settings** (opcional, mais
     seguro).
7. Clique em **Create** (ou **Save changes**).

### Como testar se funcionou

- Abra qualquer PR de teste sem tocar em `STATE.md`. O merge deve ficar
  **bloqueado** com a mensagem do workflow `pr-guardrail`.
- Se precisar pular em algum caso urgente, adicione a label
  `skip-guardrail` na PR.

---

## 2. #3 — INFRA-01: Endurecer a VPS Hostinger (60–90 min)

### Por que precisa

Uma VPS "crua" recem-contratada vem com login de root aberto e varios
riscos. Antes de colocar o produto no ar, voce precisa "fechar as portas"
(firewall, bloqueio de root, anti-brute-force). O agente **nao pode**
executar isso porque nao tem acesso SSH a sua VPS.

O runbook completo esta em `infra/vps-hardening.md`. Abaixo esta o
resumo em linguagem simples — **leia o runbook na hora de executar**,
pois ele tem os comandos exatos para copiar e colar.

### Pre-requisitos

- **VPS ja contratada** na Hostinger (voce disse que sim).
- Senha de root da VPS (veio no e-mail/painel da Hostinger).
- Um computador com terminal (Mac, Linux, ou Windows com WSL/Git Bash).

### Passo a passo (visao geral)

1. **Gere uma chave SSH no seu computador** (uma vez na vida):
   ```bash
   ssh-keygen -t ed25519 -C "deploy@nfse-saas"
   ```
   Aperte Enter em todas as perguntas. Isso cria dois arquivos em
   `~/.ssh/`: `id_ed25519` (privada — **nunca mostre a ninguem**) e
   `id_ed25519.pub` (publica — pode ser colada em servidores).

2. **Entre na VPS como root** (primeira vez):
   ```bash
   ssh root@SEU_IP_DA_VPS
   ```
   Ele pede a senha que veio no painel Hostinger. Digite (nao aparece na
   tela, normal).

3. **Siga as secoes 2 a 8 de `infra/vps-hardening.md`**, em ordem:
   - Secao 2: atualiza o sistema (`apt update` etc).
   - Secao 3: ajusta o fuso horario para Sao Paulo.
   - Secao 4: cria o usuario `deploy` e autoriza sua chave publica.
   - Secao 5: desliga login de root e login por senha no SSH.
   - Secao 6: liga o firewall (UFW) permitindo so SSH/HTTP/HTTPS.
   - Secao 7: liga o fail2ban (bane IPs que tentam chutar senha).
   - Secao 8: liga atualizacoes automaticas de seguranca.

4. **Rode os 6 testes da secao 9** do mesmo arquivo. Se os 6 passarem, a
   VPS esta pronta.

### Dicas para quem e leigo

- **Abra dois terminais** ao endurecer o SSH (secao 5). Em um, voce
  continua logado como root. No outro, voce testa se `ssh deploy@...`
  funciona. So feche o terminal de root quando o `deploy` estiver ok.
  Se voce fechar o root sem testar e algo der errado, pode se trancar
  fora da VPS.
- **Fallback:** no painel da Hostinger existe um "Console" web que
  funciona mesmo se o SSH estiver quebrado. Se travar, use esse console.
- **Nao commite** o IP da VPS nem a chave privada em nenhum arquivo do
  repositorio. Guarde tudo em um cofre (Bitwarden, 1Password).

### Como saber que acabou

Marque os 6 checkboxes da secao 9 do runbook. Quando os 6 estao verdes,
a tarefa esta concluida na pratica.

---

## 3. #71 — DOCS-01: Revisao juridica dos Termos de Uso

### Por que precisa

O agente escreveu um rascunho de Termos de Uso em `docs/legal/terms.md`.
Mas "rascunho escrito por IA" **nao substitui advogado**. Antes de abrir
cadastro para clientes pagantes, voce precisa:

1. Um advogado validar o texto.
2. O texto estar publicado em um link visivel.
3. O cliente aceitar no momento do cadastro.

### Passo a passo

1. **Leia** o arquivo `docs/legal/terms.md` e anote qualquer trecho que
   nao reflete o seu negocio (precos, politica de cancelamento, etc).
2. **Contrate um advogado** de direito digital / SaaS (pode ser freelance
   via Jusbrasil, LinkedIn, ou indicacao). Envie o `.md` e peca:
   - Validacao da clausula de **retencao de 90 dias** (ADR-003).
   - Adequacao ao **Marco Civil da Internet** e **Codigo de Defesa do
     Consumidor**.
   - Revisao do foro e legislacao aplicavel.
3. Quando o advogado devolver alteracoes, abra uma PR (ou peca ao agente
   para abrir) atualizando `docs/legal/terms.md`.
4. **Integrar com o produto** (isso e outro ticket, mas ja deixe no
   radar):
   - Pagina `/termos` no site publico.
   - Checkbox obrigatorio "Li e aceito os Termos de Uso" no cadastro.
   - Gravar no banco a data/IP do aceite (para prova juridica).

### Como saber que acabou

- [ ] `docs/legal/terms.md` revisado por advogado.
- [ ] Pagina `/termos` no site.
- [ ] Aceite obrigatorio no signup.

Os tres itens podem sair em PRs separadas.

---

## 4. #72 — DOCS-02: Publicar Privacidade e exigir aceite no signup

### Por que precisa

Parecido com o #71, mas para a **Politica de Privacidade / LGPD**. A
LGPD (Lei Geral de Protecao de Dados) exige que voce diga ao usuario:
que dados voce coleta, para que, com quem compartilha, e como ele pode
pedir exclusao. Sem isso, o projeto tem risco legal em producao.

O rascunho ja esta em `docs/legal/privacy.md` e o "RoPA" (registro de
operacoes, exigido pela LGPD) em `docs/legal/ropa.md`.

### Passo a passo

1. **Leia** `docs/legal/privacy.md`. Confira se os tres "fornecedores"
   citados fazem sentido para o seu caso:
   - **Backblaze** (armazenamento S3).
   - **Hostinger** (VPS).
   - **Resend** (envio de e-mail).

   Se voce trocar qualquer um deles (ex.: Wasabi em vez de Backblaze),
   atualize o texto.

2. **Defina o DPO (Encarregado de Dados).** Pode ser voce mesmo no
   inicio. Coloque um e-mail de contato do tipo `privacidade@seudominio`
   (crie no Google Workspace / Zoho / Resend).

3. **Revisao juridica** (mesmo advogado do #71 pode fazer os dois juntos —
   pratica de mercado).

4. **Integrar com o produto** (novamente, outro ticket do backlog, mas
   anote):
   - Pagina `/privacidade` no site publico.
   - Checkbox obrigatorio "Li e aceito a Politica de Privacidade" no
     cadastro (pode ser a mesma checkbox dos Termos, com dois links).
   - Gravar data/IP do aceite no banco.
   - Botao "Solicitar exclusao dos meus dados" no painel (direito do
     titular — art. 18 LGPD).

### Como saber que acabou

- [ ] Texto revisado por advogado.
- [ ] DPO definido e e-mail de contato ativo.
- [ ] Pagina `/privacidade` publicada.
- [ ] Aceite obrigatorio no signup.
- [ ] Fluxo de "excluir meus dados" no painel.

---

## 5. #73 e #74 — DOCS-03 / DOCS-04: Runbooks de incidente

### O que sao

Sao **manuais de socorro**. Voce nao faz nada "agora" com eles. Quando
o sistema em producao der um alerta, voce abre o arquivo e segue os
passos.

- `docs/runbooks/credencial-invalida.md` — quando o certificado digital
  A1 do cliente expirar ou for revogado.
- `docs/runbooks/portal-indisponivel.md` — quando a prefeitura estiver
  fora do ar ou devolvendo `rate-limit`.

### O que voce pode fazer hoje

1. **Ler os dois arquivos** — so para saber que existem.
2. **Deixar um atalho** no seu gerenciador de tarefas (Notion, Linear,
   Todoist) apontando para eles. Quando chegar um alerta no futuro, voce
   ja sabe onde procurar.
3. Quando um cliente real tiver o incidente, abra o runbook e siga as
   secoes "Acoes do cliente" / "Acoes do suporte".

Nao precisa de nenhuma configuracao no GitHub, VPS ou produto.

---

## 6. Issues sem acao manual

Essas entregas foram 100% codigo. O agente abriu PR, atualizou
`STATE.md` e `CHANGELOG.md`, e o trabalho esta fechado.

- **#19 CORE-01** — Refactor do motor legado para `packages/worker-core/`
  (PR #80).
- **#25 API-01** — Bootstrap do servico FastAPI em `apps/api/`.
- **#40 DS-01** — Bootstrap do painel Next.js em `apps/web-app/`.

Voce so "usa" esses artefatos quando subir o stack em producao, o que
acontece nos tickets **INFRA-02** (Docker Compose) e seguintes, ainda
no backlog.

---

## Ordem sugerida de execucao

Se for fazer tudo, uma boa sequencia e:

1. **GOV-07** (5 min, no GitHub, agora).
2. **INFRA-01** (na VPS, reserva uma noite sem pressa).
3. **DOCS-01 + DOCS-02 juntos** (um unico briefing com o advogado
   economiza tempo e dinheiro).
4. **DOCS-03 / DOCS-04** — so ler e arquivar o link.

Qualquer duvida em um passo especifico, abra uma issue com o rotulo
`question` ou me chame aqui no Claude Code com o numero do passo que
travou.
