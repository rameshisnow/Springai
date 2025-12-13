# Binance API Configuration Guide

## Status Check: ✅ CONFIGURATION SYSTEM FIXED

The `.env` loading and API configuration system has been fixed. The Flask web server can now correctly read and apply Binance API settings.

---

## Current Setup

**Environment:** `BINANCE_TESTNET=True` (Testnet Mode)  
**Base URL:** `https://testnet.binance.vision`  
**API Keys Status:** Placeholder testnet keys (need valid credentials)

### Configuration Files Updated

1. **`.env`** - Binance API credentials
   - `BINANCE_TESTNET=True` (switch to testnet for development)
   - `BINANCE_API_KEY=vmPFU...` (placeholder, replace with real key)
   - `BINANCE_API_SECRET=BQwMw...` (placeholder, replace with real secret)

2. **`src/config/settings.py`** - Fixed
   - Now reads `BINANCE_TESTNET` from environment variable
   - `ProductionConfig` no longer hardcodes `BINANCE_TESTNET=False`
   - Properly respects `.env` settings

3. **`src/trading/binance_client.py`** - Already correct
   - Uses `config.BINANCE_TESTNET` to select correct base URL
   - Order execution methods implemented: `place_market_order`, `place_limit_order`, `place_stop_loss_order`, etc.

4. **`src/trading/order_manager.py`** - Fixed
   - Buy/Sell order execution logic in place
   - Monitoring mode support (MONITORING_ONLY=True shows signals without trading)
   - Dry-run support (DRY_RUN_ENABLED=True simulates orders without API calls)

---

## How to Use Valid API Keys

### Option 1: Testnet (Development/Testing)

1. Go to **https://testnet.binance.vision**
2. Create a test account (or use an existing one)
3. Generate API Keys:
   - Under "API Management"
   - Create a new key with "Spot Trading" permission
   - Enable IP whitelist (if required)
4. Update `.env`:
   ```
   BINANCE_TESTNET=True
   BINANCE_API_KEY=your_testnet_key
   BINANCE_API_SECRET=your_testnet_secret
   ```
5. Restart the Flask server: `python3 -m src.web.server`

### Option 2: Production (Live Trading)

1. Go to **https://www.binance.com** (mainnet)
2. Create or login to account
3. Generate API Keys:
   - Account → API Management
   - Create new key with minimum permissions needed
   - Enable "Spot Trading" ONLY (not "Enable Withdrawals")
   - Add IP whitelist (recommended for security)
4. Update `.env`:
   ```
   BINANCE_TESTNET=False
   BINANCE_API_KEY=your_mainnet_key
   BINANCE_API_SECRET=your_mainnet_secret
   ```
5. Restart the Flask server

---

## Testing the Connection

```bash
cd /Users/rameshrajasekaran/Springai/crypto-ai-trader
python3 << 'PY'
from src.trading.binance_client import binance_client
from src.config.settings import config

# Show current config
print(f"Testnet Mode: {config.BINANCE_TESTNET}")
print(f"API Key (first 10): {config.BINANCE_API_KEY[:10]}")

# Test connectivity
ok = binance_client.test_connectivity()
print(f"Connectivity: {ok}")

# Test authenticated endpoint
balance = binance_client.get_asset_balance('USDT')
print(f"USDT Balance: ${balance:.2f}")

# Test public endpoint (no auth required)
price = binance_client.get_current_price("BTCUSDT")
print(f"BTC Price: ${price:.2f}")
PY
```

Expected output with VALID API keys:
```
Testnet Mode: True
API Key (first 10): vmPFU02ago...
Connectivity: True
USDT Balance: $1000.00  (or actual balance)
BTC Price: $90333.44
```

---

## Order Execution Features

All order types are implemented in `src/trading/binance_client.py`:

| Method | Purpose | Example |
|--------|---------|---------|
| `place_market_order(symbol, side, quantity)` | Instant market buy/sell | `place_market_order("BTCUSDT", "BUY", 0.001)` |
| `place_limit_order(symbol, side, quantity, price)` | Limit buy/sell at specific price | `place_limit_order("ETHUSDT", "BUY", 1.0, 3000)` |
| `place_stop_loss_order(symbol, side, quantity, stop_price)` | Stop loss execution | `place_stop_loss_order("BTCUSDT", "SELL", 0.001, 85000)` |
| `place_take_profit_order(symbol, side, quantity, stop_price)` | Take profit execution | `place_take_profit_order("BTCUSDT", "SELL", 0.001, 95000)` |
| `cancel_order(symbol, order_id)` | Cancel open order | `cancel_order("BTCUSDT", 123456789)` |
| `get_open_orders(symbol)` | List active orders | `get_open_orders("BTCUSDT")` |
| `get_order_history(symbol, limit)` | Historical orders | `get_order_history("BTCUSDT", limit=100)` |
| `get_my_trades(symbol, limit)` | Trade history | `get_my_trades("BTCUSDT", limit=50)` |

---

## Safety Features

### Monitoring Mode (Dashboard Only)
```
MONITORING_ONLY=True  # Shows signals but doesn't execute trades
```
Dashboard displays Claude AI signals without placing actual orders.

### Dry-Run Mode (Test Orders Locally)
```
DRY_RUN_ENABLED=True  # Simulates orders without hitting API
```
Orders are simulated and logged to database but not sent to Binance.

### Risk Management
- Daily loss limits
- Max position sizes
- Stop loss enforcement
- Circuit breakers

---

## Dashboard Features

Once API keys are configured:
- **USDT Balance Card** shows live account balance from Binance API
- **AI Signals** display coins Claude analyzed
- **Buy/Sell Orders** execute based on signal confidence
- **Stop Loss & Take Profit** automatically placed
- **Order History** tracked in SQLite database
- **Telegram Alerts** notify on trades (if configured)

---

## Troubleshooting

### 401 Invalid API Key Error
- ❌ API keys are invalid or expired
- ✅ Solution: Generate new API keys from Binance

### Base URL Shows `https://api.binance.com` Not Testnet
- ❌ `BINANCE_TESTNET=False` in `.env` or config
- ✅ Solution: Set `BINANCE_TESTNET=True` and restart server

### Balance Shows $0.00
- ❌ Testnet account has no balance OR API key doesn't have account permission
- ✅ Solution: Check API key permissions include "Read" for account

### Orders Not Executing
- ❌ `MONITORING_ONLY=True` or `DRY_RUN_ENABLED=True`
- ✅ Solution: Set both to `False` for live trading (be careful!)

---

## Next Steps

1. ✅ Verify configuration system (DONE)
2. ⏳ Get valid Binance testnet API keys
3. ⏳ Update `.env` with your keys
4. ⏳ Test connection with diagnostic script above
5. ⏳ Start Flask server: `python3 -m src.web.server`
6. ⏳ Access dashboard at `http://localhost:8080` (passcode: `232307`)
7. ⏳ Run signal generator: `python3 -m src.ai.signal_generator`

