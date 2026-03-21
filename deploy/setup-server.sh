#!/bin/bash
# =============================================================================
# V-Rēķini Production Server Setup
# Run this on your server (204.168.150.114) as root
# Usage: sudo bash setup-server.sh
# =============================================================================

set -euo pipefail

APP_DIR="/opt/vrekini"
DOMAIN="v-rekini.lv"
REPO_URL="https://github.com/jaanisb133/invoicing-app.git"

echo "=== V-Rēķini Server Setup ==="
echo ""

# ---- 1. System packages ----
echo "[1/7] Installing system packages..."
apt update -y
apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git ufw

# ---- 2. Firewall ----
echo "[2/7] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# ---- 3. Deploy application ----
echo "[3/7] Deploying application..."
if [ -d "$APP_DIR" ]; then
    echo "  App directory exists, pulling latest..."
    cd "$APP_DIR"
    git pull
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Create data directory
mkdir -p "$APP_DIR/data"

# ---- 4. Environment file ----
echo "[4/7] Setting up environment..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << 'ENVEOF'
SMTP_HOST=server50.areait.lv
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=rekini@v-rekini.lv
SMTP_PASS=CHANGE_ME
SMTP_FROM=V-Rēķini <rekini@v-rekini.lv>
ENVEOF
    echo "  >>> IMPORTANT: Edit $APP_DIR/.env and set your SMTP_PASS <<<"
else
    echo "  .env already exists, skipping..."
fi

# Set permissions
chown -R www-data:www-data "$APP_DIR"

# ---- 5. Systemd service ----
echo "[5/7] Setting up systemd service..."
cp "$APP_DIR/deploy/vrekini.service" /etc/systemd/system/vrekini.service
systemctl daemon-reload
systemctl enable vrekini
systemctl restart vrekini
echo "  App service started."

# ---- 6. Nginx ----
echo "[6/7] Configuring nginx..."

# First set up a temporary HTTP-only config for certbot
cat > /etc/nginx/sites-available/vrekini << 'TMPEOF'
server {
    listen 80;
    server_name v-rekini.lv www.v-rekini.lv;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
TMPEOF

ln -sf /etc/nginx/sites-available/vrekini /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ---- 7. SSL Certificate ----
echo "[7/7] Obtaining SSL certificate..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email "rekini@v-rekini.lv" --redirect

# Now replace with the full production nginx config
cp "$APP_DIR/deploy/vrekini.nginx.conf" /etc/nginx/sites-available/vrekini
nginx -t && systemctl reload nginx

# ---- 8. Business registry cron job ----
echo "[8] Setting up daily business registry update..."
chmod +x "$APP_DIR/deploy/update-registry.sh"
# Add cron job if not already present
CRON_LINE="0 4 * * * $APP_DIR/deploy/update-registry.sh >> /var/log/vrekini-registry.log 2>&1"
(crontab -l 2>/dev/null | grep -qF "update-registry.sh") || \
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
echo "  Cron job added (runs daily at 04:00)"

# Run initial registry import
echo "  Running initial registry import (this may take a few minutes)..."
"$APP_DIR/deploy/update-registry.sh" || echo "  WARNING: Initial registry import failed — can be retried manually."

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  App running at: https://$DOMAIN"
echo "  Service status:  systemctl status vrekini"
echo "  App logs:        journalctl -u vrekini -f"
echo "  Nginx logs:      /var/log/nginx/"
echo ""
echo "  REMEMBER: Edit /opt/vrekini/.env with your actual SMTP password!"
echo ""
