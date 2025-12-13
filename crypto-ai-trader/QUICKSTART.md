# 🚀 Quick Start Guide

Get your Crypto AI Trading Bot running in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.9+
- [ ] Binance account (spot trading enabled)
- [ ] Binance API keys (with trading permission)
- [ ] Claude API key (via GitHub Copilot Pro)
- [ ] Telegram bot token and chat ID

---

## Step 1: Get Your API Keys (5 min)

### Binance API Keys
1. Login to [Binance](https://www.binance.com)
2. Go to API Management
3. Create new API key with permissions:
   - ✅ Spot Trading
   - ✅ Read account
   - ❌ Withdraw (for safety)
4. Copy API Key and Secret Key

### Claude API Key
- You already have GitHub Copilot Pro!
- Visit [console.anthropic.com](https://console.anthropic.com)
- Create API key
- OR use your Copilot Pro token

### Telegram Bot
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. `/newbot` → Follow prompts
3. Get bot token
4. Message your bot, then:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
5. Find your chat ID

---

## Step 2: Setup Project (3 min)

```bash
# Navigate to project
cd /Users/rameshrajasekaran/Springai/crypto-ai-trader

# Create Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp .env.example .env
nano .env  # Edit with your API keys
```

**Your .env should look like:**
```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=True
CLAUDE_API_KEY=your_claude_key_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
STARTING_CAPITAL_AUD=1000
```

---

## Step 3: Test on Testnet (2 min)

```bash
# Make sure BINANCE_TESTNET=True in .env

python main.py
```

Expected output:
```
==================================================
Crypto AI Trading Bot Initialized
Starting Capital: $1000.00 AUD
Environment: production
Testnet: True
==================================================
✅ Configuration validated
✅ Binance API ready
```

**Let it run for 5-10 minutes:**
- Check Telegram for alerts
- Verify it fetches market data
- Check logs: `tail -f logs/crypto_trader.log`

---

## Step 4: Go Live (1 min)

```bash
# Edit .env
BINANCE_TESTNET=False

# Make sure you have USDT in your Binance account (min $1000 AUD ≈ $650 USD)

python main.py
```

**Monitor closely:**
- Telegram alerts every hour
- Check P&L updates
- Review trade log

---

## Key Shortcuts

```bash
# Start bot
python main.py

# Stop bot (press Ctrl+C)

# View logs in real-time
tail -f logs/crypto_trader.log

# View trade history
tail -f logs/trades.log

# Check account balance
python -c "from src.trading.binance_client import binance_client; print(binance_client.get_account_balance())"

# Run on background (Linux/Mac)
nohup python main.py &

# Or use tmux (better for VPS)
tmux new-session -d -s trader python main.py
tmux attach-session -t trader
```

---

## Important Notes

⚠️ **CRITICAL:**
1. Start with Testnet first - run for 1 week minimum
2. Use only what you can afford to lose
3. Monitor daily - check Telegram alerts
4. Keep API keys secure - never commit .env to git
5. Have a kill switch - Ctrl+C to stop immediately

📊 **Monitoring:**
- Bot sends Telegram alerts hourly
- Every buy/sell is logged
- Check `logs/` directory regularly
- Review profit/loss weekly

🛡️ **Safety:**
- Max 3% loss per trade
- Max $100 loss per day
- Auto-pause after 3 losses
- Hard stop-loss on all positions

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "BINANCE_API_KEY not set" | Check .env file has correct keys |
| "API error 400" | Verify Binance testnet has funds |
| No Telegram alerts | Check bot token and chat ID |
| "Market order failed" | Ensure USDT balance is sufficient |
| High slippage | Coin volume too low - bot will skip it |

---

## Next Steps

1. ✅ Run on Testnet for 1 week
2. ✅ Review trade log and performance
3. ✅ Adjust parameters if needed
4. ✅ Deploy to VPS for 24/7 trading
5. ✅ Monitor weekly performance

---

## Resources

- 📖 Full README: Read `README.md`
- 🔧 Configuration: Edit `src/config/constants.py`
- 📊 Risk Management: See `src/trading/risk_manager.py`
- 🤖 AI Analysis: Check `src/ai/ai_analyzer.py`

---

**That's it! Happy trading! 🚀**
