# SpringAI VPS Deployment Guide

## Prerequisites
- Vultr VPS IP: `67.219.108.145`
- GitHub repo: `https://github.com/rameshisnow/Springai.git`
- Your API keys ready (Binance, Claude, Telegram)

## Step 1: Initial VPS Setup (as root)

```bash
# SSH into VPS
ssh root@67.219.108.145

# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y git python3.11 python3.11-venv python3-pip nginx ufw

# Setup firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Create deploy user
adduser deploy
usermod -aG sudo deploy

# Setup SSH key for deploy user (paste your laptop's public key)
mkdir -p /home/deploy/.ssh
nano /home/deploy/.ssh/authorized_keys
# Paste your SSH public key from: cat ~/.ssh/id_ed25519.pub
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

# Test: exit and try ssh deploy@67.219.108.145
```

## Step 2: Clone and Setup Application

```bash
# SSH as deploy user
ssh deploy@67.219.108.145

# Clone repo
sudo mkdir -p /opt
sudo chown deploy:deploy /opt
cd /opt
git clone https://github.com/rameshisnow/Springai.git springai
cd springai/crypto-ai-trader

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create runtime directories
mkdir -p data logs
```

## Step 3: Configure Environment

```bash
# Create .env file
nano /opt/springai/crypto-ai-trader/.env
```

Paste this content (replace with your actual keys):
```env
# Binance API
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_secret_here
BINANCE_TESTNET=false

# Claude AI
ANTHROPIC_API_KEY=your_claude_api_key_here

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Server
PORT=8080
```

Save and secure it:
```bash
chmod 600 /opt/springai/crypto-ai-trader/.env
```

## Step 4: Create Systemd Service (Web Only)

```bash
sudo nano /etc/systemd/system/springai-web.service
```

Paste:
```ini
[Unit]
Description=SpringAI Web Dashboard
After=network.target

[Service]
User=deploy
WorkingDirectory=/opt/springai/crypto-ai-trader
Environment=PYTHONPATH=/opt/springai/crypto-ai-trader
EnvironmentFile=/opt/springai/crypto-ai-trader/.env
ExecStart=/opt/springai/crypto-ai-trader/venv/bin/python -m src.web.server
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/springai/web.log
StandardError=append:/var/log/springai/web.log

[Install]
WantedBy=multi-user.target
```

Setup logs and enable:
```bash
sudo mkdir -p /var/log/springai
sudo chown deploy:deploy /var/log/springai
sudo systemctl daemon-reload
sudo systemctl enable springai-web
sudo systemctl start springai-web
sudo systemctl status springai-web
```

## Step 5: Setup Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/springai
```

Paste:
```nginx
server {
    listen 80;
    server_name 67.219.108.145;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/springai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 6: Verify Deployment

```bash
# Check service status
sudo systemctl status springai-web

# View logs
sudo journalctl -u springai-web -f

# Test locally
curl http://127.0.0.1:8080

# Test from internet (on your laptop)
curl http://67.219.108.145
```

Open browser: `http://67.219.108.145`

## Step 7: Deploy Updates (Future)

```bash
# SSH into VPS
ssh deploy@67.219.108.145

# Pull latest changes
cd /opt/springai
git pull origin main

# Restart service
sudo systemctl restart springai-web
sudo systemctl status springai-web
```

## Troubleshooting

### Check logs
```bash
# Web server logs
tail -f /var/log/springai/web.log

# Systemd logs
sudo journalctl -u springai-web -n 50 --no-pager

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Service commands
```bash
sudo systemctl status springai-web    # Check status
sudo systemctl restart springai-web   # Restart
sudo systemctl stop springai-web      # Stop
sudo systemctl start springai-web     # Start
```

### Port check
```bash
sudo lsof -i :8080  # Check what's using port 8080
sudo netstat -tlnp | grep 8080
```

## Optional: SSL Certificate (If you have a domain)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is handled by certbot
```

## Security Hardening (Recommended)

```bash
# Disable root SSH login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart ssh

# Setup automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```
