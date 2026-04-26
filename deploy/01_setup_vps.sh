#!/bin/bash
# ============================================================================
#  Hardening initial du VPS Hetzner (Ubuntu 24.04 ou Debian 12)
#  À exécuter EN ROOT sur un VPS fraîchement installé.
#  Usage :  ssh root@TON_IP 'bash -s' < 01_setup_vps.sh
# ============================================================================
set -euo pipefail

BOT_USER="${BOT_USER:-bot}"
BOT_SSH_KEY="${BOT_SSH_KEY:-}"  # ta clé publique SSH (ssh-ed25519 ...)

if [[ -z "$BOT_SSH_KEY" ]]; then
    echo "❌ BOT_SSH_KEY non défini. Exporte ta clé publique :"
    echo '   export BOT_SSH_KEY="ssh-ed25519 AAAA... ton@ordi"'
    exit 1
fi

echo "=== 1. Mise à jour système ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    build-essential git curl rsync \
    ufw fail2ban unattended-upgrades \
    logrotate htop tmux tzdata

echo "=== 2. Fuseau horaire Europe/Paris ==="
timedatectl set-timezone Europe/Paris

echo "=== 3. Création de l'utilisateur '$BOT_USER' ==="
if ! id "$BOT_USER" &>/dev/null; then
    useradd -m -s /bin/bash -G sudo "$BOT_USER"
    echo "$BOT_USER ALL=(ALL) NOPASSWD:/usr/bin/systemctl restart assistant-personnel, /usr/bin/systemctl status assistant-personnel, /usr/bin/systemctl stop assistant-personnel, /usr/bin/systemctl start assistant-personnel" > /etc/sudoers.d/bot-systemctl
    chmod 440 /etc/sudoers.d/bot-systemctl
fi

mkdir -p /home/$BOT_USER/.ssh
echo "$BOT_SSH_KEY" > /home/$BOT_USER/.ssh/authorized_keys
chown -R $BOT_USER:$BOT_USER /home/$BOT_USER/.ssh
chmod 700 /home/$BOT_USER/.ssh
chmod 600 /home/$BOT_USER/.ssh/authorized_keys

echo "=== 4. Hardening SSH ==="
cat > /etc/ssh/sshd_config.d/hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
LoginGraceTime 30
EOF
systemctl reload ssh || systemctl reload sshd

echo "=== 5. Firewall UFW ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

echo "=== 6. fail2ban ==="
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
port    = 22
maxretry = 3
findtime = 10m
bantime  = 1h
EOF
systemctl enable --now fail2ban

echo "=== 7. Mises à jour automatiques ==="
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
dpkg-reconfigure -plow unattended-upgrades

echo "=== 8. Swap de 2GB (si pas déjà présent) ==="
if ! swapon --show | grep -q '/swapfile'; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo ""
echo "✅ VPS durci. Prochaines étapes :"
echo "   1. Reconnecte-toi en tant que '$BOT_USER' (plus en root)"
echo "      ssh $BOT_USER@$(curl -s -4 ifconfig.me)"
echo "   2. Transfère le projet (voir 02_install_bot.sh)"
echo ""
