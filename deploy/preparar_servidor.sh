#!/usr/bin/env bash
# Prepara um VPS Ubuntu 22.04/24.04 novo para o bot (rodar UMA vez, como root):
#   bash preparar_servidor.sh
# O que faz:
#   1. cria o usuário "bot" e copia a sua chave SSH para ele
#   2. instala Docker, firewall (ufw), fail2ban e atualizações automáticas de segurança
#   3. firewall: libera só SSH (o bot não precisa de nenhuma porta aberta)
#   4. desliga login por senha e login direto como root (só por chave SSH)
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Rode como root: sudo bash $0"; exit 1; fi

# Trava de segurança: sem chave SSH instalada, desligar a senha trancaria você para fora.
if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo "ERRO: /root/.ssh/authorized_keys está vazio. Configure o acesso por chave SSH antes (veja docs/VPS.md)."
  exit 1
fi

echo "==> Atualizando o sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get upgrade -y
apt-get install -y ca-certificates curl git ufw fail2ban unattended-upgrades

echo "==> Atualizações automáticas de segurança"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Docker"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker

echo "==> Usuário 'bot'"
id bot >/dev/null 2>&1 || adduser --disabled-password --gecos "" bot
usermod -aG docker bot
install -d -m 700 -o bot -g bot /home/bot/.ssh
install -m 600 -o bot -g bot /root/.ssh/authorized_keys /home/bot/.ssh/authorized_keys

echo "==> Firewall: só SSH"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

echo "==> SSH: só chave, sem root"
cat > /etc/ssh/sshd_config.d/99-bot-seguranca.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF
systemctl restart ssh || systemctl restart sshd

echo "==> fail2ban (bloqueia quem erra login várias vezes)"
systemctl enable --now fail2ban

echo
echo "PRONTO. Agora entre como:  ssh bot@<IP_DO_SERVIDOR>"
echo "Antes de fechar esta sessão, TESTE o login acima em outra janela."
