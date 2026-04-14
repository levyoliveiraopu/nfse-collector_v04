# Hardening da VPS Hostinger (INFRA-01)

Runbook manual para preparar a VPS Ubuntu 24.04 (Hostinger) antes de
receber o stack de producao (Docker Compose, Nginx, Postgres, RQ workers).

> **Execucao:** este runbook e executado pelo owner via SSH. Os comandos
> **nao** rodam em CI. O ticket fica fechado quando todos os checks da
> secao 8 passarem na VPS real.

## 0. Placeholders

Substitua nos comandos abaixo — **nao commitar valores reais**:

- `${VPS_IP}` — IP publico da VPS (painel Hostinger).
- `${VPS_HOST}` — alias opcional em `~/.ssh/config` do operador.
- `${OPERATOR_IP}` — IP publico atual do operador (`curl -s https://ifconfig.me`).
  Se o IP do operador e dinamico, veja variante na secao 5.
- `${DEPLOY_PUBKEY}` — conteudo do `~/.ssh/id_ed25519.pub` do operador.

## 1. Pre-requisitos

- VPS Ubuntu 24.04 LTS provisionada na Hostinger.
- Senha de root recebida pelo painel (uso unico).
- Chave SSH ed25519 gerada no host do operador:

  ```bash
  ssh-keygen -t ed25519 -C "deploy@nfse-saas" -f ~/.ssh/id_ed25519
  ```

- Primeiro login para aceitar a fingerprint:

  ```bash
  ssh root@${VPS_IP}
  ```

## 2. Atualizar o sistema

Como `root` na VPS:

```bash
apt update
apt -y full-upgrade
apt -y autoremove
```

Reiniciar se o kernel foi atualizado:

```bash
[ -f /var/run/reboot-required ] && reboot
```

## 3. Timezone e NTP

Usamos `systemd-timesyncd` (ja vem no Ubuntu 24.04, zero pacote extra):

```bash
timedatectl set-timezone America/Sao_Paulo
timedatectl set-ntp true
systemctl enable --now systemd-timesyncd
timedatectl status
```

Resultado esperado: `Time zone: America/Sao_Paulo`, `System clock synchronized: yes`,
`NTP service: active`.

## 4. Criar usuario `deploy`

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy

# sudo sem senha (apenas para este usuario)
install -m 0440 /dev/stdin /etc/sudoers.d/deploy <<'EOF'
deploy ALL=(ALL) NOPASSWD:ALL
EOF
visudo -cf /etc/sudoers.d/deploy

# Autorizar a chave publica do operador
install -d -m 0700 -o deploy -g deploy /home/deploy/.ssh
install -m 0600 -o deploy -g deploy /dev/stdin /home/deploy/.ssh/authorized_keys <<EOF
${DEPLOY_PUBKEY}
EOF
```

Testar em um **segundo terminal** (sem fechar o root ainda):

```bash
ssh deploy@${VPS_IP} sudo -n whoami   # deve imprimir: root
```

So avance para a proxima secao quando o login por chave estiver confirmado.

## 5. Endurecer o SSH

Editar `/etc/ssh/sshd_config.d/99-hardening.conf` (preferimos arquivo em
`sshd_config.d/` para nao colidir com o `sshd_config` padrao do Ubuntu):

```bash
cat >/etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
LoginGraceTime 30
AllowUsers deploy
EOF

sshd -t && systemctl reload ssh
```

Validacao (em outro terminal, **antes** de encerrar o root):

```bash
ssh root@${VPS_IP}     # deve ser recusado
ssh deploy@${VPS_IP}   # deve entrar
```

## 6. UFW (firewall)

Regras: SSH restrito ao IP do operador, HTTP/HTTPS abertos.

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing

# Variante A (recomendada) — SSH so do IP do operador:
ufw allow from ${OPERATOR_IP} to any port 22 proto tcp comment 'SSH operador'

# Variante B — operador com IP dinamico:
# ufw limit 22/tcp comment 'SSH rate-limited'

ufw allow 80/tcp  comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status verbose
```

> **Atencao:** se usar a variante A e o IP do operador mudar, o acesso SSH
> cai. Guarde acesso de console do painel Hostinger como fallback.

## 7. fail2ban

```bash
apt install -y fail2ban
cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = %(sshd_backend)s
maxretry = 5
findtime = 10m
bantime  = 1h
EOF

systemctl enable --now fail2ban
fail2ban-client status sshd
```

## 8. unattended-upgrades (patches automaticos)

```bash
apt install -y unattended-upgrades apt-listchanges
dpkg-reconfigure -f noninteractive unattended-upgrades

cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Apenas security updates por padrao (Ubuntu 24.04 ja vem assim)
grep -E 'Unattended-Upgrade::Allowed-Origins|security' \
  /etc/apt/apt.conf.d/50unattended-upgrades

unattended-upgrade --dry-run --debug | tail -n 20
```

## 9. Verificacao final (Definition of Done)

Rode como `deploy` via SSH:

```bash
# [x] ssh deploy@vps funciona com chave
whoami                              # deploy

# [x] ssh root@vps recusado
ssh -o BatchMode=yes root@${VPS_IP} true 2>&1 | grep -i 'permission denied'

# [x] ufw status mostra regras corretas
sudo ufw status verbose             # deny incoming, allow 22/80/443

# [x] fail2ban-client status sshd ativo
sudo fail2ban-client status sshd    # Jail: sshd  Status: ...

# [x] timedatectl mostra TZ correta
timedatectl | grep -E 'Time zone|NTP service|synchronized'

# [x] unattended-upgrades habilitado
systemctl is-enabled unattended-upgrades.service
systemctl is-active  unattended-upgrades.service
```

Quando os seis checks acima estiverem verdes, marcar o DoD do ticket.

## 10. Notas de seguranca

- **Nao** commitar `${VPS_IP}`, `${OPERATOR_IP}` ou `authorized_keys` reais
  neste repo. Usar sempre placeholders.
- Manter backup offline da chave privada ed25519 do operador. Sem ela o
  acesso a VPS so pode ser recuperado pelo console do painel Hostinger.
- Rotacionar a chave periodicamente (anual) ou imediatamente se o laptop
  do operador for comprometido. Rotacao: gerar novo par, adicionar em
  `~deploy/.ssh/authorized_keys`, testar, remover a antiga.
- Se adicionar novos operadores: cada um com sua chave, append em
  `authorized_keys`. Usuario `deploy` continua compartilhado; usuarios
  humanos individuais so serao introduzidos se/quando a equipe crescer.
- Guardar saida de `ufw status numbered` e `fail2ban-client status sshd`
  no cofre de runbooks do owner (Notion / 1Password), nao no repo.
