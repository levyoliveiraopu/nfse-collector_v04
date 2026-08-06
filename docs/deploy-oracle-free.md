# Deploy grátis para testes — VM única (Oracle Cloud Always Free)

Este guia coloca **todo o sistema NFS-e SaaS no ar, com HTTPS**, rodando em
uma única máquina virtual **gratuita** da Oracle Cloud (plano *Always Free*),
usando `docker compose`. Não precisa de nenhum serviço externo pago:

- **Postgres** e **Redis** → containers na própria VM.
- **Storage S3** → **MinIO** local (substitui o Backblaze B2).
- **HTTPS automático** → **Caddy** + Let's Encrypt (certificado grátis).
- **Domínio** → grátis via **DuckDNS** (ou o seu domínio próprio).

> Resultado final: `https://seu-nome.duckdns.org` com o painel, a API, o
> worker e o agendador rodando de verdade, prontos para você testar coleta,
> onboarding, agendamentos, ocorrências, etc.

Tudo o que roda na VM está definido em:

- `infra/compose/docker-compose.selfhost.yml` — os serviços.
- `infra/compose/caddy/Caddyfile` — o proxy/HTTPS.
- `infra/compose/.env.selfhost.example` — as variáveis.
- `infra/oracle/setup.sh` — o instalador de 1 comando.

---

## 0. Visão geral (5 passos)

1. Criar conta na Oracle Cloud (Always Free).
2. Criar a VM Ubuntu (shape ARM gratuito).
3. Abrir as portas 80, 443 e 8443 na rede da Oracle.
4. Criar um domínio grátis (DuckDNS) apontando para o IP da VM.
5. Entrar por SSH, clonar o repositório e rodar `setup.sh`.

Tempo estimado: ~30–40 min (a maior parte é esperar cadastro e build).

---

## 1. Conta Oracle Cloud (Always Free)

1. Acesse <https://www.oracle.com/br/cloud/free/> e clique em **Comece já**.
2. Preencha o cadastro. **É pedido um cartão de crédito apenas para
   verificação de identidade** — o plano *Always Free* **não cobra**; os
   recursos que vamos usar ficam dentro da cota gratuita permanente.
3. Escolha a região mais próxima (ex.: *Brazil East (São Paulo)* —
   `sa-saopaulo-1`). A região não muda depois.

> Dica: se aparecer erro de "Out of capacity" ao criar a VM ARM (passo 2),
> é falta temporária de máquinas gratuitas na região. Tente de novo mais
> tarde, ou use o script "always-free retry" (seção *Problemas comuns*).

---

## 2. Criar a máquina virtual (VM)

No console da Oracle: **Menu ☰ → Compute → Instances → Create instance**.

- **Name**: `nfse-teste` (o que quiser).
- **Image and shape** → **Edit**:
  - **Image**: `Canonical Ubuntu 22.04` (ou 24.04).
  - **Shape** → **Change shape** → **Ampere** (ARM) →
    **VM.Standard.A1.Flex**. Configure:
    - **OCPUs**: `2`
    - **Memory (GB)**: `12`
  - *(Isso cabe folgado na cota Always Free: até 4 OCPUs e 24 GB de ARM.
    Não use o shape "Micro" de 1 GB — não dá conta de buildar o painel.)*
- **Networking**: deixe criar uma nova VCN e sub-rede públicas (padrão).
  Garanta **Assign a public IPv4 address = Yes**.
- **Add SSH keys**:
  - Se você não tem uma chave, escolha **Generate a key pair for me** e
    **baixe a chave privada** (guarde bem — é o que dá acesso à VM).
  - Se já tem, cole a sua chave **pública**.
- Clique **Create**. Em ~1 min a VM fica *Running*. **Anote o
  "Public IP address"** — vamos usá-lo já já.

---

## 3. Abrir as portas 80, 443 e 8443 (rede da Oracle)

Por padrão a Oracle só libera a porta 22 (SSH). Precisamos liberar HTTP,
HTTPS e a porta do S3.

1. Na página da instância, em **Primary VNIC**, clique no nome da
   **Subnet**.
2. Clique na **Security List** padrão (ex.: *Default Security List for ...*).
3. **Add Ingress Rules** e crie **uma regra para cada porta** (ou uma com a
   lista):
   - **Source CIDR**: `0.0.0.0/0`
   - **IP Protocol**: `TCP`
   - **Destination Port Range**: `80`  → Add
   - Repita para `443` e para `8443`.

> O `setup.sh` abre essas mesmas portas no firewall **de dentro** do Ubuntu
> (iptables) automaticamente. Este passo aqui é o firewall **da nuvem**, que
> só dá para mexer pelo console.

---

## 4. Domínio grátis com DuckDNS

O HTTPS precisa de um domínio (não funciona com IP puro). O DuckDNS dá um
subdomínio grátis:

1. Acesse <https://www.duckdns.org> e faça login (Google/GitHub).
2. Em **domains**, digite um nome, ex.: `nfse-teste`, e clique **add domain**.
   Isso cria `nfse-teste.duckdns.org`.
3. No campo **current ip** desse domínio, coloque o **Public IP** da sua VM
   (passo 2) e clique **update ip**.

> Prefere usar **seu próprio domínio**? Basta criar um registro **A**
> apontando para o IP público da VM (ex.: `nfse.suaempresa.com.br → IP`).
> Depois é só usar esse domínio no lugar do DuckDNS no passo 5.

---

## 5. Instalar o sistema — Opção A: automática (recomendada)

Com esta opção você **não digita nenhum comando**: a VM se instala sozinha no
primeiro boot. Use o arquivo `infra/oracle/cloud-init.yaml`.

1. Abra `infra/oracle/cloud-init.yaml`
   ([ver no GitHub](https://github.com/levyoliveiraopu/nfse-collector_v04/blob/claude/sistema-testes-internet-ap40rm/infra/oracle/cloud-init.yaml))
   e edite **as duas linhas** no topo do script:
   - `DOMAIN="SEU_DOMINIO"` → seu domínio (ex.: `nfse-teste.duckdns.org`)
   - `ACME_EMAIL="SEU_EMAIL"` → seu e-mail
2. **Este passo é feito na criação da VM (passo 2)**: em *Create instance* →
   **Show advanced options** → aba **Management** → **User data** →
   **Paste cloud-init script** → cole **todo** o conteúdo do arquivo (já com
   as duas linhas editadas).
3. Crie a VM normalmente. No primeiro boot ela instala tudo sozinha
   (Docker, segredos, build, migrations, HTTPS) — leva ~5–10 min.
4. Depois de a VM ter IP público, aponte seu domínio (DuckDNS, passo 4) para
   esse IP. O Caddy emite o certificado assim que o DNS resolver.

Para acompanhar a instalação (opcional), conecte por SSH e rode:

```bash
sudo tail -f /var/log/nfse-setup.log
```

Quando aparecer o bloco final com "Painel: https://...", está no ar. 🎉

> Já criou a VM sem o cloud-init? Sem problema — use a **Opção B** abaixo.

---

## 5-B. Instalar o sistema — Opção B: manual (SSH + 1 comando)

Conecte na VM por SSH (troque a chave e o IP pelos seus). O usuário padrão
da imagem Ubuntu da Oracle é `ubuntu`:

```bash
chmod 600 sua-chave-privada.key
ssh -i sua-chave-privada.key ubuntu@SEU_IP_PUBLICO
```

Já dentro da VM:

```bash
# ferramentas básicas
sudo apt-get update && sudo apt-get install -y git

# clonar o repositório
git clone https://github.com/levyoliveiraopu/nfse-collector_v04.git
cd nfse-collector_v04

# (enquanto este deploy não estiver na branch main, use a branch do PR:)
# git checkout claude/sistema-testes-internet-ap40rm

# rodar o instalador: ./setup.sh <dominio> <email>
./infra/oracle/setup.sh nfse-teste.duckdns.org voce@gmail.com
```

O `setup.sh` faz **tudo sozinho**:

- instala o Docker (se faltar);
- abre 80/443/8443 no firewall do Ubuntu;
- gera um `.env` com **senhas e segredos aleatórios** (Postgres, Redis, JWT,
  chave de cifra das credenciais, credenciais do MinIO);
- **builda** as imagens (API, worker, agendador, painel);
- cria o bucket no MinIO;
- roda as **migrations** do banco;
- sobe **todos** os serviços.

A primeira execução leva alguns minutos (build). No fim ele imprime:

```
  Painel:  https://nfse-teste.duckdns.org
  API:     https://nfse-teste.duckdns.org/backend/health
  S3:      https://nfse-teste.duckdns.org:8443
```

Aguarde ~1 minuto para o Caddy emitir o certificado HTTPS e abra o painel no
navegador. 🎉

---

## 6. Testar

1. Abra `https://SEU_DOMINIO` → deve carregar o painel (cadeado verde).
2. Faça o **cadastro** (signup): crie o tenant, o usuário owner e a senha.
3. Faça **login** e percorra o **onboarding**: cadastre uma empresa (CNPJ) e
   suba um **certificado A1 (.pfx)** de teste.
4. Crie um **agendamento** ou dispare uma **coleta** manual e acompanhe em
   *Execuções* e *Ocorrências*.

> Checagem rápida da API (do seu PC ou da VM):
> ```bash
> curl https://SEU_DOMINIO/backend/health     # {"status":"ok"}
> curl https://SEU_DOMINIO/backend/ready       # checa DB, Redis e storage
> ```

---

## 7. Operação do dia a dia

Todos os comandos rodam de dentro de `nfse-collector_v04/infra/compose`.
Para encurtar, defina um apelido:

```bash
cd ~/nfse-collector_v04/infra/compose
alias dc='docker compose --env-file .env -f docker-compose.base.yml -f docker-compose.selfhost.yml'
```

- **Ver status**: `dc ps`
- **Ver logs** (tudo): `dc logs -f`
- **Ver logs** de um serviço: `dc logs -f api` (ou `worker`, `web-app`, `caddy`…)
- **Reiniciar** um serviço: `dc restart api`
- **Parar tudo**: `dc down`
- **Subir de novo**: `dc up -d`
- **Atualizar o código** (novos commits):
  ```bash
  cd ~/nfse-collector_v04 && git pull
  ./infra/oracle/setup.sh SEU_DOMINIO SEU_EMAIL   # rebuilda e sobe (mantém o .env)
  ```
- **Backup do banco**:
  ```bash
  dc exec postgres pg_dump -U nfse nfse > backup_$(date +%F).sql
  ```
- **Console do MinIO** (admin do storage) — só via túnel SSH, por segurança:
  ```bash
  ssh -i sua-chave.key -L 9001:127.0.0.1:9001 ubuntu@SEU_IP
  # depois abra http://localhost:9001 no seu navegador
  ```

---

## 8. Problemas comuns

- **O painel não abre / sem cadeado.**
  - Confirme que o DNS aponta certo: `ping SEU_DOMINIO` deve mostrar o IP da VM.
  - Confirme que abriu 80/443/8443 na **Security List** da Oracle (passo 3).
  - Veja os logs do Caddy: `dc logs caddy` (mostra erros de emissão do
    certificado). O Let's Encrypt exige a porta **80** acessível da internet.

- **"Out of host capacity" ao criar a VM ARM.**
  - Falta temporária de máquinas gratuitas na região. Tente outra região,
    outro horário, ou repita o "Create" algumas vezes.

- **Login no painel falha / cai para a tela de login.**
  - O cookie de sessão é `Secure` → só funciona por **HTTPS**. Acesse sempre
    por `https://SEU_DOMINIO`, nunca pelo IP nem por `http://`.

- **Download de arquivo/export não abre.**
  - É servido pelo MinIO em `:8443`. Confirme que a porta **8443** está
    aberta na Security List da Oracle e no firewall do SO.

- **Build falha por falta de memória.**
  - Use o shape ARM com **2 OCPU / 12 GB** (passo 2). O shape Micro de 1 GB
    não builda o painel Next.js.

---

## 9. Segurança (importante)

Este setup é ótimo para **testes**. Antes de usar com dados reais, considere:

- O arquivo `infra/compose/.env` guarda **todos os segredos** — mantenha a VM
  restrita (só sua chave SSH) e **nunca** versione o `.env`.
- Postgres, Redis e o console do MinIO só escutam em `127.0.0.1` (não expostos
  à internet) — o acesso é via túnel SSH.
- Troque as senhas/segredos se o `.env` vazar (basta apagar o `.env` e rodar o
  `setup.sh` de novo — ele gera tudo novo; atenção: isso invalida sessões e
  exige re-cifrar credenciais).
- Mantenha o sistema operacional atualizado: `sudo apt-get update && sudo apt-get upgrade -y`.

---

## 10. E se eu quiser um caminho ainda mais simples (pago)?

Se a burocracia da Oracle incomodar, um **VPS pago barato** (Hostinger,
Contabo, DigitalOcean; ~R$25–35/mês) roda exatamente estes mesmos comandos —
é só criar o VPS Ubuntu, apontar o domínio e rodar o `setup.sh`. O sistema
foi projetado para isso.
