#!/bin/bash
# Badger ICCID Pipeline — Ubuntu Server Setup
# Run once: bash deploy.sh

set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="badger"
APP_PORT=8001

echo "=== Badger ICCID Pipeline — Deploy ==="
echo "App directory: $APP_DIR"

# ── 1. System packages ─────────────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv curl

# ── 2. Node.js + SF CLI ────────────────────────────────────────────────────────
echo ""
echo "[2/6] Installing Node.js and Salesforce CLI..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

if ! command -v sf &>/dev/null; then
    sudo npm install -g @salesforce/cli
fi

echo "Node: $(node -v)  |  SF CLI: $(sf --version | head -1)"

# ── 3. Python virtual environment ──────────────────────────────────────────────
echo ""
echo "[3/6] Setting up Python virtual environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements2.txt -q
echo "Python: $(python --version)"

# ── 4. Runtime directories ─────────────────────────────────────────────────────
echo ""
echo "[4/6] Creating runtime directories..."
mkdir -p "$APP_DIR/log"
mkdir -p "$APP_DIR/data"

# ── 5. Systemd service ─────────────────────────────────────────────────────────
echo ""
echo "[5/6] Installing systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Badger ICCID Pipeline
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn web_app:app --host 0.0.0.0 --port $APP_PORT
Restart=on-failure
RestartSec=5
EnvironmentFile=$APP_DIR/.env.local
StandardOutput=append:$APP_DIR/log/service.log
StandardError=append:$APP_DIR/log/service.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

# ── 6. SF CLI login ────────────────────────────────────────────────────────────
echo ""
echo "[6/6] Salesforce CLI authentication..."
echo ""
echo "  The app uses SF CLI for Salesforce authentication."
echo "  To connect, open the app in a browser and go to:"
echo "  Admin → Import & Connect → paste your sfdxAuthUrl"
echo ""
echo "  To get the sfdxAuthUrl on your LOCAL machine (where you have a browser):"
echo "    sf org login web --alias sf-prod --instance-url https://cwc.my.salesforce.com"
echo "    sf org display --target-org sf-prod --verbose --json"
echo "  Copy the sfdxAuthUrl value and paste it in the Admin page."

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo " Badger is running at http://$(hostname -I | awk '{print $1}'):$APP_PORT"
echo " Service: sudo systemctl status $SERVICE_NAME"
echo " Logs:    tail -f $APP_DIR/log/service.log"
echo "============================================"
