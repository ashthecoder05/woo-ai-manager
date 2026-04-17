#!/bin/bash
# HeySarva — VPS Setup Script
# Run this as root on a fresh Ubuntu 22.04 server
# Usage: bash setup-server.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  HeySarva Server Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System update ──────────────────────────────────────────
echo "[1/7] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install essentials ─────────────────────────────────────
echo "[2/7] Installing essentials..."
apt-get install -y -qq \
    curl git ufw nginx certbot \
    python3-certbot-nginx \
    ca-certificates gnupg lsb-release

# ── 3. Install Docker ─────────────────────────────────────────
echo "[3/7] Installing Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"

# ── 4. Firewall ───────────────────────────────────────────────
echo "[4/7] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Firewall status:"
ufw status

# ── 5. Create app user ────────────────────────────────────────
echo "[5/7] Creating app user..."
if ! id "sarva" &>/dev/null; then
    useradd -m -s /bin/bash sarva
    usermod -aG docker sarva
    echo "User 'sarva' created and added to docker group"
else
    echo "User 'sarva' already exists"
fi

# ── 6. Create app directory ───────────────────────────────────
echo "[6/7] Creating app directory..."
mkdir -p /app
chown sarva:sarva /app

# Create SSL cert directory
mkdir -p /etc/ssl/heysarva
chown sarva:sarva /etc/ssl/heysarva

# ── 7. Nginx placeholder ──────────────────────────────────────
echo "[7/7] Setting up Nginx..."
rm -f /etc/nginx/sites-enabled/default
systemctl enable nginx
systemctl restart nginx

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Upload your code to /app"
echo "  2. Place your .env file in /app"
echo "  3. Place nginx.conf in /etc/nginx/sites-available/heysarva"
echo "  4. Run: docker compose up -d --build"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
