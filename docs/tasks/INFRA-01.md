# INFRA-01 — Hardening inicial da VPS Hostinger

- **Trilha:** infra
- **Tamanho:** M
- **Status:** ready
- **Depende de:** nada (VPS ja contratada)

## Objetivo

Deixar o servidor Linux seguro para receber o stack de producao.

## Pre-requisitos

- VPS Ubuntu 24.04 provisionada na Hostinger.
- Acesso root inicial via painel/SSH.
- Chave publica SSH (ed25519) do operador.

## Entregaveis

- Usuario `deploy` com sudo sem senha, login por chave.
- Root SSH desabilitado (`PermitRootLogin no`).
- Autenticacao por senha desabilitada.
- `ufw` ativo: permitir 22 (restrito ao IP do operador), 80, 443.
- `fail2ban` com jail SSH.
- `unattended-upgrades` habilitado para patches de seguranca.
- Timezone `America/Sao_Paulo`, NTP via `chrony` ou `systemd-timesyncd`.
- Checklist documentado em `infra/vps-hardening.md`.

## Definition of Done

- [ ] `ssh deploy@vps` funciona com chave.
- [ ] `ssh root@vps` recusado.
- [ ] `ufw status` mostra regras corretas.
- [ ] `fail2ban-client status sshd` ativo.
- [ ] `timedatectl` mostra TZ correta.
- [ ] Checklist commitado em `infra/vps-hardening.md`.

## Prompt sugerido

```
Leia STATE.md e docs/tasks/INFRA-01.md. Execute a tarefa conectando
via SSH como root, aplicando o hardening, criando o usuario deploy e
documentando passos em infra/vps-hardening.md. Abra branch
task/INFRA-01-hardening, commite, atualize STATE.md e CHANGELOG.md,
e abra PR com "Closes #<issue>".
```

## Notas

Nao commitar IP da VPS em claro. Usar placeholder `${VPS_IP}`.
