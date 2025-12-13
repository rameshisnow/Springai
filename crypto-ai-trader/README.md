# 🚀 Crypto AI Trading Bot

An intelligent, fully-automated cryptocurrency trading system powered by Claude AI. Analyzes top crypto coins, identifies pump candidates, and executes trades with advanced risk management.

**Status**: ✅ Production Ready | **Capital**: $1000 AUD | **Timeframe**: 4H+ | **Target**: Max Profit

---

## 📋 Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Bot](#running-the-bot)
6. [Trading Strategy](#trading-strategy)
7. [Risk Management](#risk-management)
8. [Monitoring](#monitoring)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

---

## ✨ Features

### AI-Powered Analysis
- **Claude 3.5 Sonnet** AI model for market analysis
- Consensus-based decision making (multiple prompt variations)
- Confidence scoring for each trading signal
- Real-time market sentiment analysis

### Automated Trading
- **Fully automated**: No manual intervention required after setup
- **Smart entry**: Market orders with optimal timing
- **Intelligent exit**: Multiple profit-taking levels + trailing stops
- **Risk-protected**: Hard stop-losses on all positions

### Risk Management
- **Position sizing**: Kelly Criterion-based calculation
- **Capital protection**: 2% risk per trade, max 3 concurrent positions
- **Circuit breakers**: Auto-pause after 3 consecutive losses
- **Drawdown limits**: Stop trading if portfolio down >15%
- **Daily limits**: $100 max loss per day or 10% of capital

### Real-Time Monitoring
- **Telegram alerts**: Hourly reports + trade notifications
- **P&L tracking**: Real-time profit/loss updates
- **System health**: CPU, memory, API status monitoring
- **Trade logging**: Complete audit trail of all trades

### Data Integration
- **Binance API**: Real-time price and volume data
- **CoinGecko**: Market cap, sentiment, on-chain metrics
- **Multi-source**: News, technical indicators, volatility analysis

---

## 🏗️ Architecture

```
crypto-ai-trader/
├── src/
│   ├── config/              # Configuration & constants
│   │   ├── settings.py      # Environment settings
│   │   └── constants.py     # Trading parameters & thresholds
│   │
│   ├── data/                # Data fetching & processing
│   │   └── data_fetcher.py  # Binance, CoinGecko, News APIs
│   │
│   ├── ai/                  # AI analysis & signal generation
│   │   └── ai_analyzer.py   # Claude API integration
│   │
│   ├── trading/             # Order execution & risk management
│   │   ├── binance_client.py    # Binance API wrapper
│   │   ├── order_manager.py     # Order lifecycle management
│   │   └── risk_manager.py      # Position sizing & circuit breakers
│   │
│   ├── monitoring/          # Alerts & monitoring
│   │   └── notifications.py # Telegram bot integration
│   │
│   └── utils/               # Logging & validation
│       ├── logger.py
│       └── validators.py
│
├── backtester/              # Historical backtesting (Phase 2)
├── notebooks/               # Analysis & research
├── logs/                    # Application logs
├── data/                    # Historical data & cache
├── main.py                  # Main entry point
├── requirements.txt         # Python dependencies
├── .env.example            # Configuration template
└── README.md               # This file
```

## 🎨 Web Login & Dashboard

- `ui/login.html` mirrors the SpringAI login mockup with the robot avatar, passcode grid, and gradient background.
- `ui/dashboard.html` is a static replica of the provided dashboard: balance cards, active/closed trade tables, performance stats, and risk metrics.
- Shared stylesheet `ui/styles.css` keeps both pages consistent, and you can drop them into a Flask route later for dynamic data.

To preview, open `ui/login.html` and `ui/dashboard.html` in any browser — no backend required yet.

### Flask Demo Server
1. Install Flask (already listed in `requirements.txt`).
2. Run the web server: `python -m src.web.server` (the server now listens on `SERVER_PORT`, default 8080).
3. Browse `http://localhost:8080/` to see the login page.
4. Submitting the 6-digit passcode (any numbers) redirects to `/dashboard`, which now renders the live metrics pulled from the SQLite history and risk manager.

     You can override the listen host/port with the `SERVER_HOST` and `SERVER_PORT` variables in your `.env` file (e.g., `SERVER_HOST=0.0.0.0`, `SERVER_PORT=8080`).

The Flask server serves the same `styles.css` from the `ui/` directory, so the login/dashboard styling matches the mockups while being backed by real trade data.

---

## 💻 Installation

### Prerequisites
- Python 3.9+
- Binance account with API keys
- Claude API key (via GitHub Copilot Pro or Anthropic)
- Telegram bot token & chat ID

### Step 1: Clone Repository
```bash
cd /Users/rameshrajasekaran/Springai/crypto-ai-trader
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
nano .env
```

---

## ⚙️ Configuration

### `.env` File Setup

```env
# Binance API Credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=False  # Set to True to test on Testnet first

# Claude API
CLAUDE_API_KEY=your_claude_api_key_here

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Trading Config
STARTING_CAPITAL_AUD=1000
TARGET_PROFIT_PERCENT=20
RISK_PER_TRADE_PERCENT=2

# System
ENVIRONMENT=production
BACKTEST_MODE=False
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
```

### Key Configuration Parameters

**Risk Management** (`src/config/constants.py`):
- `STARTING_CAPITAL_AUD`: $1000 (DO NOT CHANGE)
- `RISK_PER_TRADE_PERCENT`: 2% per trade
- `STOP_LOSS_PERCENT`: 3% hard stop
- `DAILY_MAX_LOSS_AUD`: $100 daily limit
- `MAX_CONSECUTIVE_LOSSES`: 3 (triggers circuit breaker)

**Trading Rules**:
- `MAX_CONCURRENT_POSITIONS`: 3 (max 3 coins at once)
- `MIN_CONFIDENCE_SCORE`: 70% (only trade high-confidence signals)
- `ANALYSIS_INTERVAL_MINUTES`: 60 (run analysis every hour)

---

## 🚀 Running the Bot

### Option 1: Local Testing (Testnet)
```bash
# Set BINANCE_TESTNET=True in .env first
python main.py
```

### Option 2: Production Mode
```bash
# Ensure BINANCE_TESTNET=False in .env
python main.py
```

### Expected Output
```
==================================================
Crypto AI Trading Bot Initialized
Starting Capital: $1000.00 AUD
Analysis Interval: 60 minutes
Environment: production
Testnet: False
==================================================
✅ Configuration validated
✅ Binance API ready
🔍 Running AI analysis...
📊 AI identified 3 pump candidates
✉️  Hourly report sent
```

---

## 📊 Trading Strategy

### ⏰ Optimum Execution Strategy

**Analysis Frequency:**
- **Intraday Trading (Default)**: 30-minute intervals for fast signals and more trades
- **Swing Trading (Alternative)**: 60-240 minute intervals for quality over quantity
- Configurable via `ANALYSIS_INTERVAL_MINUTES` in `constants.py`

**Execution Hours (UTC):**
- **Active**: 8:00 - 22:00 UTC (overlaps US, EU, and Asia markets)
- **Inactive**: 22:00 - 8:00 UTC (avoid low liquidity periods)
- Peak liquidity typically occurs during US/EU trading overlap (12:00-18:00 UTC)

**Timeframe Selection:**
- **1h candles**: Best for intraday (1-24 hour holds)
- **4h candles**: Best for swing trades (1-7 day holds)
- Primary timeframe: `PREFERRED_TIMEFRAME` in `constants.py`

### Data Collection & Signal Generation Pipeline

**Step 1: Data Collection**
1. Pull top 10 coins by 24h volume from CoinGecko
2. Fetch OHLCV (1h or 4h candles) from Binance API
3. Optionally pull social sentiment / news indicators

**Step 2: Technical Analysis**
Preprocess data and compute indicators:
- **RSI** (14-period): Overbought/oversold momentum
- **EMA** (20, 50, 200): Trend direction and support/resistance
- **ATR** (14-period): Volatility measurement
- **MACD**: Momentum and trend confirmation
- **Volume Spike**: Current volume vs 20-period average
- **Momentum**: 10-period rate of change
- **Bollinger Bands**: Price position relative to volatility bands

**Step 3: Claude AI Signal Generation**
Feed structured data snapshot to Claude with JSON prompt:
```json
{
  "signal": "BUY / SELL / HOLD",
  "confidence": 78,
  "stop_loss": 0.92,
  "take_profit": [1.05, 1.10, 1.15],
  "rationale": "Price broke above EMA200 with strong momentum; RSI shows room to run."
}
```

**Claude Prompt Design:**
- Includes last 10 OHLCV candles in table format
- All computed indicators with context
- Optional social sentiment score
- Short-term focus (1-24 hour trades)
- Strict JSON response format for parsing

**Step 4: Risk Management**
Apply risk rules before execution:
- Only trade if confidence ≥ 70%
- Only trade if volume ≥ $10M (24h)
- Only trade if within position limits (max 3 concurrent)
- Only trade during active hours (8-22 UTC)
- Apply 2% capital risk per trade with Kelly Criterion sizing

**Step 5: Trade Execution**
- Place market or limit orders via Binance API
- Track open positions with automated SL/TP management
- Monitor trailing stops and partial exits

**Step 6: Logging & Feedback**
- Record all decisions, reasoning, and outcomes
- Build historical context for prompt refinement
- Telegram notifications for all trades

### Signal Generation (Every 30 Minutes)
1. **Fetch top 10 coins** by volume from CoinGecko
2. **Filter by criteria**:
   - Min market cap: $100M
   - Min 24h volume: $10M
   - Exclude stablecoins and delisted coins
3. **Fetch OHLCV**: Last 100 candles (1h or 4h)
4. **Compute Indicators**: RSI, EMA, ATR, MACD, momentum, volume spike
5. **AI Analysis**: Feed data + indicators to Claude for structured signal
6. **Confidence check**: Require ≥70% confidence score
7. **Risk validation**: Check position limits, trading hours, circuit breakers

### Entry Rules
- **Order type**: Market order (instant execution)
- **Entry signal**: AI BUY signal with ≥70% confidence
- **Position size**: Calculated based on Kelly Criterion (2% risk)
- **Stop loss**: AI-suggested or 3% below entry (whichever is closer)
- **Take profits**: AI-suggested targets (typically +5%, +10%, +15%)

### Exit Rules
1. **Stop loss hit**: Automatic exit at -3% (or AI-suggested level)
2. **Trailing stop**: Exit if price falls 2% from highest price
3. **Take profit**: Partial exits at AI-suggested levels
4. **Time stop**: None (hold until profit target or stop loss)

### Risk Management Safeguards
```
Position Entry
     ↓
Risk validation checks
     ├─ Circuit breaker active? REJECT
     ├─ Max positions reached? REJECT
     ├─ Daily loss limit? REJECT
     ├─ Insufficient balance? REJECT
     └─ All checks pass → EXECUTE
     ↓
Order Placement
     ├─ Market buy order
     ├─ Stop-loss order
     └─ Take-profit orders
     ↓
Position Tracking
     ├─ Update P&L every minute
     ├─ Check exit conditions
     └─ Execute exits automatically
     ↓
Position Closed
     ├─ Log trade
     ├─ Update portfolio
     └─ Send Telegram alert
```

---

## 🛡️ Risk Management

### Daily Circuit Breaker
- **Trigger**: 3 consecutive losses
- **Action**: Pause trading for 24 hours
- **Recovery**: Automatic after 24h

### Position Limits
| Limit | Value |
|-------|-------|
| Max concurrent positions | 3 |
| Max per-trade risk | 2% of capital |
| Max position exposure | 6% of capital |
| Min trading volume | $10M 24h |
| Min market cap | $100M |

### Stop Loss & Take Profit
```
Entry: $100
  ├─ Stop Loss: $97 (-3%)
  ├─ TP1: $103 (+3%) → exit 33%
  ├─ TP2: $105 (+5%) → exit 33%
  ├─ TP3: $108 (+8%) → exit 34%
  └─ Trailing stop: 2% below highest price
```

### Drawdown Protection
- **Max portfolio drawdown**: 15%
- **Action**: Stop all trading if exceeded
- **Recovery**: Manual review required

---

## 📱 Monitoring & Alerts

### Telegram Notifications

**Hourly Report** (every hour on the hour)
```
📊 HOURLY REPORT
━━━━━━━━━━━━━━━━━━━━━━━
Status: 🟢 ACTIVE
Balance: $1,050.00 AUD
Total P&L: +$50.00 (+5.00%)
Drawdown: 2.5%
Open Positions: 2
Closed Trades: 5
Time: 2025-12-13 14:00:00
```

**Trade Alerts**
- 🔔 Entry signal detected
- ✅ Position closed with profit
- ❌ Position closed with loss
- ⚠️ Circuit breaker activated

**Error Alerts**
- API connection issues
- Order placement failures
- System health warnings

### Logs
All activities logged to `logs/` directory:
- `crypto_trader.log` - Main application log
- `trades.log` - Trade execution log
- `ai_analyzer.log` - AI analysis log
- `risk_manager.log` - Risk events log
- `binance_client.log` - API calls log

---

## 🌐 Deployment on VPS

### Step 1: VPS Setup (Ubuntu 20.04+)
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python & dependencies
sudo apt-get install -y python3.9 python3.9-venv python3-pip git

# Create application user
sudo useradd -m -s /bin/bash crypto-trader
sudo su - crypto-trader
```

### Step 2: Deploy Application
```bash
# Clone repository
git clone <your-repo-url>
cd crypto-ai-trader

# Setup virtual environment
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your credentials
```

### Step 3: Create Systemd Service
Create `/etc/systemd/system/crypto-trader.service`:

```ini
[Unit]
Description=Crypto AI Trading Bot
After=network.target

[Service]
Type=simple
User=crypto-trader
WorkingDirectory=/home/crypto-trader/crypto-ai-trader
ExecStart=/home/crypto-trader/crypto-ai-trader/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Step 4: Enable & Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-trader
sudo systemctl start crypto-trader

# Monitor logs
sudo journalctl -u crypto-trader -f
```

### Step 5: Monitoring
```bash
# Check status
sudo systemctl status crypto-trader

# View logs
sudo journalctl -u crypto-trader --since "1 hour ago"

# Restart if needed
sudo systemctl restart crypto-trader
```

---

## 📈 Performance Tracking

### Key Metrics
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **ROI**: Total return on investment

### Expected Performance
```
Conservative estimate (60% win rate):
- Avg win: +3%
- Avg loss: -2%
- Per trade: (0.60 × 3%) + (0.40 × -2%) = +1%
- Monthly: ~30 trades × 1% = +30% (if consistent)

Realistic range: 5-15% monthly
```

### Trade Analysis Dashboard
Access trade history in `logs/trade_history.jsonl`:
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "entry_price": 42500.00,
  "exit_price": 43275.00,
  "pnl": 247.50,
  "pnl_percent": 1.82,
  "status": "CLOSED"
}
```

---

## 🧪 Testing & Validation

### Testnet Trading
```bash
# Edit .env
BINANCE_TESTNET=True

# Run with test funds (no real money)
python main.py
```

### Backtesting (Phase 2)
```bash
# Run backtest on historical data
python -m src.backtester.backtest_engine \
  --start-date 2023-01-01 \
  --end-date 2025-01-01 \
  --capital 1000
```

### API Testing
```bash
# Test Binance connectivity
python -c "from src.trading.binance_client import binance_client; print(binance_client.test_connectivity())"

# Test Claude API
python -c "from src.ai.ai_analyzer import ai_analyzer; print('Claude API ready')"

# Test Telegram
python -c "from src.monitoring.notifications import notifier; print('Telegram ready' if notifier.enabled else 'Telegram disabled')"
```

---

## ⚠️ Important Warnings

### Before Going Live:

1. ✅ **Test thoroughly on Testnet first** - Run for at least 1 week
2. ✅ **Start with small capital** - Use only what you can afford to lose
3. ✅ **Monitor daily** - Check logs and Telegram alerts
4. ✅ **Set up alerts** - Ensure Telegram notifications work
5. ✅ **Have a kill switch** - Know how to stop the bot immediately

### Risk Disclaimers:

- **No guarantee**: Past performance ≠ future results
- **Market risk**: Crypto markets are highly volatile
- **AI risk**: LLMs can make confident mistakes
- **Technical risk**: System failures can cause losses
- **Start small**: Test with minimal capital first

---

## 🐛 Troubleshooting

### Common Issues

**"BINANCE_API_KEY not set"**
```bash
# Solution: Check .env file has correct API credentials
cat .env | grep BINANCE
```

**"Circuit breaker active"**
```bash
# Means: 3 consecutive losses triggered auto-pause
# Solution: Wait 24 hours or manually reset in code
# Check logs: cat logs/risk_manager.log
```

**"Failed to fetch market data"**
```bash
# Solution: Check internet connection
ping coingecko.api
curl https://api.binance.com/api/v3/ping
```

**"Order placement failed"**
```bash
# Check balance: Verify you have enough USDT
# Check volume: Ensure coin has >$10M daily volume
# Check testnet: If on testnet, request test funds
```

**"Telegram not sending alerts"**
```bash
# Test: python -c "from src.monitoring.notifications import notifier; print(notifier.enabled)"
# Fix: Verify bot token and chat ID in .env
```

### Debug Mode
```bash
# Enable verbose logging
# Edit src/config/constants.py
VERBOSE_AI_RESPONSES = True
LOG_AI_DECISIONS = True
```

---

## 📞 Support & Monitoring

### Daily Checklist
- ✅ Check Telegram alerts received
- ✅ Verify P&L updates hourly
- ✅ Monitor system health
- ✅ Review trade log for patterns
- ✅ Confirm API connectivity

### Weekly Review
- Check win rate trend
- Analyze profitable vs losing trades
- Review risk metrics
- Verify no bugs/errors in logs

### Monthly Analysis
- Calculate Sharpe ratio
- Review drawdown events
- Optimize parameters based on data
- Plan next improvements

---

## 🚀 Roadmap

**Phase 2 (Next):**
- [ ] Backtesting engine with historical data
- [ ] Portfolio optimization
- [ ] Advanced technical indicators
- [ ] Sentiment analysis integration
- [ ] On-chain metrics integration

**Phase 3:**
- [ ] Machine learning parameter optimization
- [ ] Multiple AI model consensus
- [ ] News-driven trading signals
- [ ] Whale movement detection
- [ ] Advanced risk metrics

---

## 📄 License & Disclaimer

This software is provided "AS IS" without warranty. Cryptocurrency trading involves substantial risk of loss. Use at your own risk. Always start with small amounts and test thoroughly before deploying capital.

---

**Happy Trading! 🚀**

*Last Updated: December 13, 2025*
