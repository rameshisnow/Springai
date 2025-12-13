# ⚙️ Configuration Reference Guide

Complete guide to all configurable parameters in the trading bot.

---

## Environment Variables (.env)

### Binance API Configuration
```env
# Your Binance API credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Set to True for testing, False for live trading
BINANCE_TESTNET=False
```

### AI/LLM Configuration
```env
# Claude API key (required)
CLAUDE_API_KEY=sk-ant-...

# OpenAI API key (optional, for backup)
OPENAI_API_KEY=sk-...
```

### Telegram Configuration
```env
# Get from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmnoPQRstuvWXYZ...

# Your Telegram chat ID (get from https://api.telegram.org/botYOUR_TOKEN/getUpdates)
TELEGRAM_CHAT_ID=123456789
```

### Trading Configuration
```env
# Starting capital in AUD
STARTING_CAPITAL_AUD=1000

# Monthly profit target (%) - informational only
TARGET_PROFIT_PERCENT=20

# Risk per trade (% of capital)
RISK_PER_TRADE_PERCENT=2
```

### System Configuration
```env
# development, testing, or production
ENVIRONMENT=production

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Set to True to simulate trades without real execution
BACKTEST_MODE=False

# API timeout in seconds
REQUEST_TIMEOUT=30
```

### Data Source Configuration
```env
# CoinGecko API key (use 'free' for free tier)
COINGECKO_API_KEY=free

# NewsAPI key for crypto news (optional)
NEWS_API_KEY=your_newsapi_key_here
```

---

## Trading Parameters (src/config/constants.py)

### Capital & Position Sizing
```python
STARTING_CAPITAL_AUD = 1000              # Initial capital
RISK_PER_TRADE_PERCENT = 2.0             # Risk 2% per trade = $20
MAX_POSITION_SIZE_USD = 20               # Max position size (calculated)
KELLY_CRITERION_FRACTION = 0.25          # Conservative Kelly
```

### Position Management
```python
MAX_CONCURRENT_POSITIONS = 3             # Max 3 coins at once
MIN_TRADING_VOLUME_USD = 10_000_000      # Min $10M 24h volume
MIN_MARKET_CAP_USD = 100_000_000         # Min $100M market cap
MIN_COIN_AGE_DAYS = 90                   # Min 90 days old
```

### Entry & Exit Rules
```python
# Take Profit Levels
TAKE_PROFIT_LEVELS = [
    {"percent": 3, "position_percent": 0.33},   # Exit 33% at +3%
    {"percent": 5, "position_percent": 0.33},   # Exit 33% at +5%
    {"percent": 8, "position_percent": 0.34},   # Exit 34% at +8%
]

# Stop Loss
STOP_LOSS_PERCENT = 3.0                  # Hard stop at -3%
TRAILING_STOP_PERCENT = 2.0              # Trailing stop at 2%

# Timing
ANALYSIS_INTERVAL_MINUTES = 60           # Run analysis every 60 min
TRADING_TIMEFRAMES = ["1h", "4h"]        # Analyze these timeframes
PREFERRED_TIMEFRAME = "4h"               # Primary timeframe
```

### AI Validation & Filtering
```python
MIN_CONFIDENCE_SCORE = 0.70              # Only trade >70% confidence
MIN_CONSENSUS_AGREEMENTS = 2             # Need 2/3 agreements
HALLUCINATION_CHECK_ENABLED = True       # Verify data accuracy

# Thresholds for buy signals
BULLISH_THRESHOLD = 0.70                 # >=70% = strong buy
NEUTRAL_THRESHOLD = 0.30                 # 30-70% = wait
```

### Circuit Breakers & Safety
```python
# Daily Loss Limits
DAILY_MAX_LOSS_AUD = 100                 # Stop if lost $100/day
DAILY_MAX_LOSS_PERCENT = 10              # Stop if down 10%
MAX_CONSECUTIVE_LOSSES = 3               # Stop after 3 losses
COOLDOWN_AFTER_LOSS_MINUTES = 120        # Wait 2h after loss

# Portfolio Limits
MAX_DRAWDOWN_PERCENT = 15                # Stop if down 15%
CIRCUIT_BREAKER_RECOVERY_HOURS = 24      # Wait 24h to resume

# Position Limits
MAX_POSITION_EXPOSURE_PERCENT = 6        # Max 6% in one position
LEVERAGE_MULTIPLIER = 1                  # No leverage (1x)
```

### Market Conditions
```python
# Volatility Requirements
MIN_VOLATILITY_PERCENT = 2.0             # Min 2% movement
VOLATILITY_LOOKBACK_HOURS = 24           # Lookback window

# Volume Conditions
MIN_RELATIVE_VOLUME = 1.5                # 1.5x average volume
VOLUME_LOOKBACK_BARS = 20                # Last 20 candles

# Liquidity
SLIPPAGE_TOLERANCE_PERCENT = 0.15        # Max 0.15% slippage
LIQUIDITY_CHECK_ENABLED = True           # Check liquidity
```

### Notification Settings
```python
TELEGRAM_HOURLY_REPORT = True            # Send hourly reports
TELEGRAM_TRADE_ALERTS = True             # Alert on buy/sell
TELEGRAM_PNL_UPDATES = True              # Alert on P&L changes
TELEGRAM_ERROR_ALERTS = True             # Alert on errors
```

### Binance Trading Parameters
```python
ORDER_TYPE = "MARKET"                    # Use market orders
LIMIT_ORDER_TIMEOUT_MINUTES = 5          # Cancel limit after 5min

# Commission
BINANCE_MAKER_FEE = 0.001                # 0.1% maker fee
BINANCE_TAKER_FEE = 0.001                # 0.1% taker fee
TOTAL_TRADING_COST_PERCENT = 0.002       # Entry + exit

# Trading Settings
QUOTE_ASSET = "USDT"                     # Trade in USDT pairs
STABLECOIN_PAIRS = ["USDT", "BUSD", "USDC", "DAI"]
```

### AI Model Configuration
```python
AI_PROVIDER = "claude"                   # claude, openai, or hybrid

# Claude Settings
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS = 1500
CLAUDE_TEMPERATURE = 0.3                 # Lower = consistent

# OpenAI Settings (backup)
OPENAI_MODEL = "gpt-4-turbo"
OPENAI_MAX_TOKENS = 1500
OPENAI_TEMPERATURE = 0.3
```

### Backtesting Parameters
```python
BACKTEST_START_DATE = "2023-01-01"       # Start date
BACKTEST_END_DATE = "2025-01-01"         # End date
BACKTEST_LOOKBACK_MONTHS = 24            # 2 years data

# Success Criteria
BACKTEST_MIN_WIN_RATE = 0.60             # 60% win rate
BACKTEST_MIN_PROFIT_FACTOR = 1.5         # 1.5x profit factor
BACKTEST_MAX_DRAWDOWN = 0.20             # Max 20% drawdown
BACKTEST_MIN_SHARPE_RATIO = 1.5          # Sharpe ratio >1.5
```

### Logging & Data
```python
LOG_TRADES = True                        # Log all trades
LOG_PRICE_UPDATES = False                # Don't log every price (verbose)
LOG_AI_DECISIONS = True                  # Log AI decisions
LOG_RISK_CHECKS = True                   # Log risk checks

KEEP_TRADE_HISTORY = True                # Store trades
TRADE_HISTORY_RETENTION_DAYS = 365       # Keep 1 year
```

### Advanced Features
```python
# Sentiment Analysis
USE_SENTIMENT_ANALYSIS = False           # Not enabled yet
SENTIMENT_WEIGHT = 0.2                   # 20% if enabled

# Technical Indicators
USE_TECHNICAL_CONFIRMATION = True        # Use RSI, MACD
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_SIGNAL_CROSSOVER_REQUIRED = True

# On-chain Metrics
USE_ONCHAIN_METRICS = False              # Requires paid API
WHALE_MOVEMENT_THRESHOLD_USD = 1_000_000 # $1M minimum
```

### System Health
```python
HEARTBEAT_INTERVAL_SECONDS = 300         # Check every 5 min
API_TIMEOUT_SECONDS = 30                 # API timeout
RECONNECT_ATTEMPTS = 5                   # Retry 5 times
RECONNECT_WAIT_SECONDS = 10              # Wait 10s between retries

# Database
AUTO_BACKUP_ENABLED = True               # Auto-backup trades
AUTO_BACKUP_INTERVAL_HOURS = 24          # Daily backup
```

### Debugging
```python
DEBUG_MODE = False                       # Debug logging
DRY_RUN_ENABLED = False                  # Test without orders
VERBOSE_AI_RESPONSES = False             # Print full AI responses
```

---

## Recommended Configuration Profiles

### Conservative (Risk-Averse)
```python
# For risk-averse traders starting out
STARTING_CAPITAL_AUD = 500
RISK_PER_TRADE_PERCENT = 1.0             # 1% risk
MAX_CONCURRENT_POSITIONS = 2             # Max 2 positions
STOP_LOSS_PERCENT = 2.5                  # 2.5% stop
DAILY_MAX_LOSS_AUD = 50                  # $50/day limit
MIN_CONFIDENCE_SCORE = 0.80              # Need 80% confidence
```

### Balanced (Recommended)
```python
# Default configuration - good for most traders
STARTING_CAPITAL_AUD = 1000
RISK_PER_TRADE_PERCENT = 2.0             # 2% risk
MAX_CONCURRENT_POSITIONS = 3             # Max 3 positions
STOP_LOSS_PERCENT = 3.0                  # 3% stop
DAILY_MAX_LOSS_AUD = 100                 # $100/day limit
MIN_CONFIDENCE_SCORE = 0.70              # 70% confidence
```

### Aggressive (Higher Risk/Reward)
```python
# For experienced traders with higher capital
STARTING_CAPITAL_AUD = 5000
RISK_PER_TRADE_PERCENT = 3.0             # 3% risk
MAX_CONCURRENT_POSITIONS = 5             # Max 5 positions
STOP_LOSS_PERCENT = 4.0                  # 4% stop
DAILY_MAX_LOSS_AUD = 300                 # $300/day limit
MIN_CONFIDENCE_SCORE = 0.65              # 65% confidence
```

---

## How to Adjust Parameters

### For More Trades Per Day
```python
ANALYSIS_INTERVAL_MINUTES = 30           # Run every 30 min instead of 60
MIN_CONFIDENCE_SCORE = 0.65              # Lower threshold
MIN_CONSENSUS_AGREEMENTS = 1             # Accept single opinion
```

### For Larger Profits Per Trade
```python
TAKE_PROFIT_LEVELS = [
    {"percent": 5, "position_percent": 0.5},   # +5% exit 50%
    {"percent": 10, "position_percent": 0.5},  # +10% exit rest
]
STOP_LOSS_PERCENT = 4.0                  # Wider stop (accept more loss)
```

### For Faster Exits (Risk Control)
```python
STOP_LOSS_PERCENT = 2.0                  # Tighter stop
TRAILING_STOP_PERCENT = 1.5              # More aggressive trailing
TAKE_PROFIT_LEVELS = [
    {"percent": 2, "position_percent": 0.5},   # Exit fast at 2%
    {"percent": 4, "position_percent": 0.5},   # Then at 4%
]
```

### For More Conservative Trading
```python
MIN_TRADING_VOLUME_USD = 50_000_000      # Require $50M+ volume
MIN_MARKET_CAP_USD = 500_000_000         # Require $500M+ cap
MIN_CONFIDENCE_SCORE = 0.80              # Need 80%+ confidence
DAILY_MAX_LOSS_AUD = 50                  # Only $50/day loss allowed
```

---

## Validation Rules

**Never change these without understanding consequences:**

❌ **Don't set:**
- `RISK_PER_TRADE_PERCENT > 5%` - Too risky
- `MAX_CONCURRENT_POSITIONS > 10` - Too many to manage
- `STOP_LOSS_PERCENT < 1%` - Too tight, false exits
- `STOP_LOSS_PERCENT > 10%` - Too loose, large losses
- `MIN_CONFIDENCE_SCORE < 0.5` - Too many false signals

✅ **Safe ranges:**
- Risk per trade: 0.5% - 3%
- Concurrent positions: 1 - 5
- Stop loss: 2% - 5%
- Confidence: 0.6 - 0.9
- Take profits: +2% to +15%

---

## Testing Different Parameters

### Small Capital Testing ($100)
```python
STARTING_CAPITAL_AUD = 100
RISK_PER_TRADE_PERCENT = 2.0             # $2 per trade
BINANCE_TESTNET = True                   # Use testnet
```

### Slow Trading (Conservative)
```python
ANALYSIS_INTERVAL_MINUTES = 240          # Run every 4 hours
MAX_CONCURRENT_POSITIONS = 1             # One position at a time
STOP_LOSS_PERCENT = 5.0                  # Wide stop for less noise
```

### Fast Trading (Aggressive)
```python
ANALYSIS_INTERVAL_MINUTES = 15           # Run every 15 min
MAX_CONCURRENT_POSITIONS = 5             # Multiple positions
STOP_LOSS_PERCENT = 2.0                  # Tight stop for quick exits
```

---

## Monitoring Configuration Impact

After changing parameters, monitor these metrics:

| Metric | Good Sign | Bad Sign |
|--------|-----------|----------|
| Win Rate | >55% | <40% |
| Profit Factor | >1.5 | <1.0 |
| Avg Trade Duration | 1-4 hours | >1 day |
| Daily Max Loss Hits | <1/week | >2/week |
| Sharpe Ratio | >1.0 | <0.5 |
| Max Drawdown | <10% | >20% |

---

## Emergency Overrides

If the bot is losing money consistently:

### Immediate Actions
1. Stop the bot: `Ctrl+C`
2. Lower `MIN_CONFIDENCE_SCORE` to `0.75` (temporary)
3. Reduce `RISK_PER_TRADE_PERCENT` to `1.0`
4. Increase `STOP_LOSS_PERCENT` to `4.0` (allow more room)
5. Run again and monitor

### If Still Losing
1. Stop the bot
2. Switch to `BINANCE_TESTNET = True`
3. Test new parameters
4. Review `src/ai/ai_analyzer.py` for signal issues
5. Check market conditions (bear market vs bull)

### Nuclear Option
```python
# If everything fails - super conservative
STARTING_CAPITAL_AUD = 100
RISK_PER_TRADE_PERCENT = 0.5             # Only $0.50 per trade
MAX_CONCURRENT_POSITIONS = 1
ANALYSIS_INTERVAL_MINUTES = 480          # Once per 8 hours
DAILY_MAX_LOSS_AUD = 10
```

---

## Configuration Checklist Before Going Live

- [ ] BINANCE_API_KEY is set and correct
- [ ] BINANCE_API_SECRET is set and correct
- [ ] BINANCE_TESTNET = False for production
- [ ] CLAUDE_API_KEY is set
- [ ] TELEGRAM_BOT_TOKEN is set
- [ ] TELEGRAM_CHAT_ID is set (numeric)
- [ ] STARTING_CAPITAL_AUD matches your account
- [ ] Binance account has USDT balance ready
- [ ] Risk per trade is reasonable (1-3%)
- [ ] Stop loss is set (2-5%)
- [ ] Take profit levels look good
- [ ] Daily max loss makes sense
- [ ] You've tested on testnet for 1 week
- [ ] Telegram alerts are working
- [ ] Logs are being created
- [ ] You understand the parameters

---

**Configuration is flexible - start conservative and adjust based on results!**
