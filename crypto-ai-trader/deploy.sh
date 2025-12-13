#!/bin/bash
# deployment.sh - Deploy crypto trading bot to VPS

set -e

echo "🚀 Crypto AI Trading Bot Deployment"
echo "===================================="

# Configuration
DEPLOY_USER="crypto-trader"
DEPLOY_PATH="/home/crypto-trader/crypto-ai-trader"
VENV_PATH="$DEPLOY_PATH/venv"
SERVICE_NAME="crypto-trader"
REPO_URL="$1"

if [ -z "$REPO_URL" ]; then
    echo "Usage: ./deploy.sh <git-repo-url>"
    exit 1
fi

echo "📋 Step 1: System Setup"
echo "======================"
sudo apt-get update -y
sudo apt-get install -y python3.9 python3.9-venv python3-pip git curl

echo "👤 Step 2: Create Application User"
echo "===================================="
if ! id "$DEPLOY_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash "$DEPLOY_USER"
    echo "✅ User '$DEPLOY_USER' created"
else
    echo "✅ User '$DEPLOY_USER' already exists"
fi

echo "📦 Step 3: Clone Repository"
echo "============================"
sudo su - "$DEPLOY_USER" << EOF
    if [ -d "$DEPLOY_PATH" ]; then
        cd "$DEPLOY_PATH"
        git pull origin main
    else
        git clone "$REPO_URL" "$DEPLOY_PATH"
        cd "$DEPLOY_PATH"
    fi
EOF

echo "🐍 Step 4: Setup Python Environment"
echo "===================================="
sudo su - "$DEPLOY_USER" << EOF
    cd "$DEPLOY_PATH"
    python3.9 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Python dependencies installed"
EOF

echo "⚙️  Step 5: Configure Environment"
echo "=================================="
if [ ! -f "$DEPLOY_PATH/.env" ]; then
    echo "⚠️  .env file not found"
    echo "Please create .env file at $DEPLOY_PATH/.env"
    echo "Copy from .env.example and fill in your credentials"
    exit 1
else
    echo "✅ .env file found"
fi

echo "🔧 Step 6: Create Systemd Service"
echo "=================================="
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Crypto AI Trading Bot
After=network.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$DEPLOY_PATH
ExecStart=$VENV_PATH/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

echo "📝 Step 7: Enable and Start Service"
echo "==================================="
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "======================="
echo ""
echo "📊 Service Status:"
sudo systemctl status "$SERVICE_NAME"
echo ""
echo "📋 Monitor logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "⚙️  Manage service:"
echo "   sudo systemctl start/stop/restart $SERVICE_NAME"
echo ""
echo "🚀 Bot is now running and will auto-restart on failure!"
