# Dashboard & System Flow Explanation

## 📊 How the Dashboard Works

### Overview
The SpringAI dashboard is a Flask web application that displays real-time trading data, positions, AI signals, and system health. It refreshes every 60 seconds and pulls data from multiple sources.

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MAIN TRADING LOOP                        │
│                   (main.py - Every 240 min)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────┐
    │   Signal Generator (signal_generator.py)          │
    │   - Fetches top coins (DOGE/SHIB/SOL for Goldilock)│
    │   - Gets 1H, 4H, Daily candles from Binance      │
    │   - Runs strategy.check_entry() logic            │
    │   - Calls Claude AI for analysis                 │
    └───────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────┐
    │   Safety Gates (safety_gates.py)                  │
    │   - Monthly trade limit check                     │
    │   - Liquidity validation ($50M min)               │
    │   - Position sizing (40% for Goldilock)           │
    │   - Confidence/edge threshold                     │
    └───────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────┐
    │   Order Manager (order_manager.py)                │
    │   - Executes market buy order on Binance          │
    │   - Creates Position object                       │
    │   - Sets TP/SL levels                             │
    │   - Saves to positions.json                       │
    └───────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────┐
    │   Position Monitor (position_monitor.py)          │
    │   - Runs EVERY 5 MINUTES independently            │
    │   - Checks all open positions                     │
    │   - Executes exits (SL, TP1, TP2, Trailing)      │
    │   - Updates positions.json with current prices    │
    └───────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────┐
    │   Dashboard (server.py)                           │
    │   - Reads positions.json                          │
    │   - Reads signal_history.db (SQLite)              │
    │   - Fetches live USDT balance from Binance        │
    │   - Auto-refreshes every 60 seconds               │
    └───────────────────────────────────────────────────┘
```

---

## 🔍 Position Monitoring Process

### Monitoring Frequency
**Every 5 minutes** (300 seconds)
```python
POSITION_CHECK_INTERVAL_MINUTES = 5
```

### What Happens Each Check Cycle

```python
# position_monitor.py - monitor_positions()

while self.running:
    # 1. Get all active positions from risk_manager
    active_positions = risk_manager.positions
    
    for symbol, position in active_positions.items():
        # 2. Fetch current price from Binance
        current_price = binance_client.get_current_price(symbol)
        
        # 3. Update position's current_price and save to file
        position.update_current_price(current_price)
        risk_manager._save_positions_to_file()
        
        # 4. Calculate hold days
        hold_days = (datetime.now() - position.entry_time).days
        
        # 5. Get strategy for this coin
        strategy = strategy_manager.get_strategy(symbol)
        
        # 6. Apply Goldilock exit logic (see below)
        
    # 7. Wait 5 minutes before next check
    await asyncio.sleep(300)
```

---

## 📈 Candle Data Processing

### Data Sources
All market data comes from **Binance Spot API**:

```python
# Example: Fetching candles
df_1h = await binance_fetcher.get_klines(
    symbol='DOGEUSDT',
    interval='1h',
    limit=200  # Last 200 1-hour candles
)

df_4h = await binance_fetcher.get_klines(
    symbol='DOGEUSDT',
    interval='4h',
    limit=200  # Last 200 4-hour candles
)

# Resample 1H to Daily
df_daily = df_1h.resample('1D').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
})
```

### Candle Structure
Each candle contains:
```python
{
    'open': 0.12400,      # Opening price
    'high': 0.12850,      # Highest price in period
    'low': 0.12350,       # Lowest price in period
    'close': 0.12675,     # Closing price
    'volume': 45823000,   # Trading volume
    'timestamp': datetime(2025, 12, 18, 10, 0)
}
```

### Usage in Strategy
```python
# goldilock_strategy.py - check_entry()

# Calculate indicators on 4H timeframe
df_4h = self.calculate_indicators(df_4h)

# Current bar
current_idx = len(df_4h) - 1
current_rsi = df_4h['rsi'].iloc[current_idx]
current_ema9 = df_4h['ema_9'].iloc[current_idx]
current_ema21 = df_4h['ema_21'].iloc[current_idx]

# Check daily trend (price > daily EMA50)
daily_close = df_daily['close'].iloc[-1]
daily_ema50 = df_daily['ema_50'].iloc[-1]

if daily_close > daily_ema50:
    # Bullish daily trend ✅
```

---

## 🎯 Take Profit (TP) Process - Goldilock Strategy

### TP Configuration
```python
# goldilock_strategy.py
DEFAULT_CONFIG = {
    'tp1_pct': 0.15,      # +15% first target
    'tp2_pct': 0.30,      # +30% second target
    'tp1_size': 0.50,     # Close 50% at TP1
}
```

### TP Execution Flow

#### Example: DOGEUSDT Trade

**Entry:**
```python
Entry Price: $0.10000
Quantity: 1000 DOGE
Position Value: $100 (40% of $250 balance)
```

**TP Levels Calculated:**
```python
tp_levels = strategy.get_take_profits(entry_price=0.10)
# Returns:
[
    {'price': 0.115, 'size_pct': 0.50},  # TP1: +15%, close 50%
    {'price': 0.130, 'size_pct': 0.50},  # TP2: +30%, close 50%
]
```

**TP1 Execution (Day 10):**
```
Position Monitor Check (5-min cycle):
  Current Price: $0.11510
  TP1 Price: $0.11500
  Price >= TP1? YES ✅
  
  Action:
  1. Close 50% of position (500 DOGE)
     Sell 500 DOGE @ $0.11510
     Profit: ($0.11510 - $0.10000) × 500 = $7.55
  
  2. Mark position.tp1_hit = True
  
  3. Set position.highest_price = $0.11510
  
  4. Activate trailing stop (5%)
     Trail Price: $0.11510 × 0.95 = $0.10935
  
  5. Update positions.json
  
  6. Send notification:
     "✅ TAKE PROFIT 1 EXECUTED
      DOGEUSDT
      Entry: $0.10000
      Exit: $0.11510
      Sold: 50% (500 DOGE)
      Hold: 10 days
      Profit: +15.1%
      🔔 Trailing stop now active (5%)"
```

**Trailing Stop Active (Days 10-15):**
```
Day 11: Price = $0.12000
  → Update highest_price = $0.12000
  → Trail = $0.12000 × 0.95 = $0.11400

Day 12: Price = $0.12500
  → Update highest_price = $0.12500
  → Trail = $0.12500 × 0.95 = $0.11875

Day 15: Price = $0.13050 (hits TP2!)
  → Execute TP2...
```

**TP2 Execution (Day 15):**
```
Position Monitor Check:
  Current Price: $0.13050
  TP2 Price: $0.13000
  Price >= TP2? YES ✅
  position.tp1_hit? TRUE ✅
  
  Action:
  1. Close remaining 50% (500 DOGE)
     Sell 500 DOGE @ $0.13050
     Profit: ($0.13050 - $0.10000) × 500 = $15.25
  
  2. Close position completely
  
  3. Total P&L:
     TP1: $7.55 (+15.1%)
     TP2: $15.25 (+30.5%)
     Total: $22.80 (+22.8% on $100)
  
  4. Record trade in database
  
  5. Send notification:
     "✅ TAKE PROFIT 2 EXECUTED
      DOGEUSDT
      Entry: $0.10000
      Exit: $0.13050
      Hold: 15 days
      Profit: +30.5%"
```

---

## 🛑 Stop Loss (SL) Process - Dynamic

### SL Configuration
```python
# goldilock_strategy.py
DEFAULT_CONFIG = {
    'initial_stop_pct': 0.08,    # 8% during min hold
    'regular_stop_pct': 0.03,    # 3% after min hold
    'min_hold_days': 7,
}
```

### SL Execution Flow

#### Example: SHIBUSDT Trade Goes Bad

**Entry:**
```python
Entry Price: $0.00001000
Quantity: 10,000,000 SHIB
Position Value: $100
Entry Time: Day 0
```

**Day 3 - Early Stop Loss:**
```
Position Monitor Check:
  Current Price: $0.00000920
  Hold Days: 3
  
  Calculate Dynamic SL:
  hold_days < 7? YES
  → Use 8% stop
  → SL = $0.00001000 × 0.92 = $0.00000920
  
  Price <= SL? YES ($0.00000920 <= $0.00000920) ✅
  
  Action:
  1. Close 100% of position (10M SHIB)
     Sell 10M SHIB @ $0.00000920
     Loss: ($0.00000920 - $0.00001000) × 10M = -$8.00
  
  2. Record in database
  
  3. Send notification:
     "🚨 STOP LOSS (EARLY EXIT - Day 3)
      SHIBUSDT
      Entry: $0.00001000
      Exit: $0.00000920
      Hold: 3 days
      Loss: -8.0%"
```

**Day 10 - Regular Stop Loss:**
```
Position Monitor Check:
  Current Price: $0.00000971
  Hold Days: 10
  
  Calculate Dynamic SL:
  hold_days >= 7? YES
  → Use 3% stop (tighter)
  → SL = $0.00001000 × 0.97 = $0.00000970
  
  Price <= SL? YES ($0.00000971 <= $0.00000970) ✅
  
  Action:
  1. Close 100% of position
     Sell @ $0.00000971
     Loss: -$2.90 (-2.9%)
  
  2. Send notification:
     "🚨 STOP LOSS EXECUTED
      SHIBUSDT
      Entry: $0.00001000
      Exit: $0.00000971
      Hold: 10 days
      Loss: -2.9%"
```

---

## 📉 Trailing Stop Process

### Activation Conditions
- Only activates AFTER TP1 is hit
- Trails 5% below the highest price reached

### Example: SOLUSDT Trade

**TP1 Hit (Day 12):**
```
Entry: $100.00
TP1: $115.00 (hits!)
→ Close 50%
→ position.tp1_hit = True
→ position.highest_price = $115.00
→ Trailing active: Trail = $115.00 × 0.95 = $109.25
```

**Price Rises (Day 13-15):**
```
Day 13: Price = $118.00
  → highest_price = $118.00
  → Trail = $118.00 × 0.95 = $112.10
  → Price > Trail? YES, continue holding

Day 14: Price = $125.00
  → highest_price = $125.00
  → Trail = $125.00 × 0.95 = $118.75
  → Price > Trail? YES, continue holding

Day 15: Price = $127.50
  → highest_price = $127.50
  → Trail = $127.50 × 0.95 = $121.13
  → Price > Trail? YES, continue holding
```

**Trailing Stop Triggered (Day 16):**
```
Position Monitor Check:
  Current Price: $120.00
  highest_price = $127.50
  Trail Price = $127.50 × 0.95 = $121.13
  
  Price < Trail? YES ($120.00 < $121.13) ✅
  
  Action:
  1. Close remaining 50% @ $120.00
     Profit on remaining half: +20%
  
  2. Total P&L:
     TP1 (50%): +15% = +7.5%
     Trailing (50%): +20% = +10%
     Total: +17.5%
  
  3. Send notification:
     "📉 TRAILING STOP EXECUTED
      SOLUSDT
      Entry: $100.00
      High: $127.50
      Exit: $120.00
      Hold: 16 days
      Profit: +20%"
```

---

## 📊 Dashboard Data Display

### Sample Active Trade Display

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Symbol  │ Qty      │ Entry   │ Current │ P&L          │ SL      │ TP       │
├─────────────────────────────────────────────────────────────────────────────┤
│ DOGEUSDT│ 800.5    │ $0.1241 │ $0.1285 │ +$3.52 (+3.5%)│ $0.1208 │ $0.1427 │
│ SHIBUSDT│ 8500000  │ $0.00001│ $0.00001│ +$1.20 (+1.2%)│ $0.00000│ $0.00001│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Source Flow
```python
# Dashboard reads from positions.json (updated every 5 min by monitor)

positions.json:
{
  "DOGEUSDT": {
    "entry_price": 0.1241,
    "quantity": 800.5,
    "current_price": 0.1285,      # ← Updated by position monitor
    "last_price_update": "2025-12-18T10:35:00",  # ← Every 5 min
    "stop_loss": 0.1208,
    "take_profit_targets": [
      {"price": 0.1427, "size_pct": 0.50},  # TP1: +15%
      {"price": 0.1613, "size_pct": 0.50}   # TP2: +30%
    ],
    "tp1_hit": false,
    "highest_price": 0.1285,
    "entry_time": "2025-12-08T06:00:00"
  }
}
```

### Dashboard Calculation
```python
# server.py - _build_active_trades()

for symbol, position_data in positions_data.items():
    entry_price = position_data['entry_price']
    current_price = position_data['current_price']  # From 5-min monitor
    quantity = position_data['quantity']
    
    # Calculate P&L
    pnl = (current_price - entry_price) * quantity
    pnl_percent = ((current_price - entry_price) / entry_price) * 100
    
    # Get TP/SL for display
    stop_loss = position_data['stop_loss']
    tp_targets = position_data['take_profit_targets']
    take_profit = tp_targets[0]['price'] if tp_targets else entry_price
    
    trades.append({
        'symbol': symbol,
        'quantity': quantity,
        'entry': entry_price,
        'current': current_price,
        'pnl': pnl,
        'pnl_percent': pnl_percent,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'last_update': position_data['last_price_update']
    })
```

---

## 🔄 Complete Trade Lifecycle Example

### DOGEUSDT - Full Journey

```
DAY 0 (Entry):
─────────────────────────────────────────────────────────────
Main Loop Run (4:00 PM Sydney):
  1. Signal Generator fetches DOGEUSDT 1H/4H/Daily candles
  2. Strategy checks entry: RSI=38, EMA9>21, Volume spike
     → 3/4 conditions met ✅
  3. Claude AI analysis: "STRONG edge - oversold bounce setup"
  4. Safety Gates: Monthly limit OK, Liquidity $85M ✅
  5. Position Sizing: 40% of $250 = $100
  6. Order: BUY 800 DOGE @ $0.1250
  7. Set TP1=$0.14375 (+15%), TP2=$0.1625 (+30%)
  8. Set SL=$0.115 (8% wide for first 7 days)
  9. Save to positions.json
  10. Dashboard shows: 1 active position

DAYS 1-6 (Min Hold Period):
─────────────────────────────────────────────────────────────
Position Monitor (every 5 min):
  - Fetch current price
  - Check: hold_days < 7? YES
  - Only check 8% stop loss
  - Block all TP exits
  - Update current_price in positions.json
  - Dashboard shows live P&L

Day 3: Price drops to $0.1175 (-6%)
  → SL at $0.115 not hit, continue holding

Day 6: Price recovers to $0.1295 (+3.6%)
  → Min hold not over yet, no TP check

DAY 7 (Min Hold Ends):
─────────────────────────────────────────────────────────────
Position Monitor:
  - hold_days = 7
  - Switch to 3% stop loss: SL=$0.12125
  - Enable TP1/TP2 checks
  - Enable trailing stop (after TP1)

DAY 10 (TP1 Hit):
─────────────────────────────────────────────────────────────
Position Monitor (10:35 AM):
  1. Fetch price: $0.14420
  2. Check TP1: $0.14375
  3. Price >= TP1? YES ✅
  4. EXECUTE:
     - Sell 400 DOGE @ $0.14420
     - Profit: $7.76 (+15.4%)
     - Keep 400 DOGE (50%)
  5. Mark tp1_hit=True
  6. Set highest_price=$0.14420
  7. Activate trailing: Trail=$0.13699 (5% below)
  8. Update positions.json
  9. Dashboard shows: P&L +$7.76, Status: "TP1 HIT"

DAYS 11-15 (Trailing Active):
─────────────────────────────────────────────────────────────
Day 11: Price=$0.1485
  → highest_price=$0.1485
  → Trail=$0.14108
  → Hold

Day 13: Price=$0.1595
  → highest_price=$0.1595
  → Trail=$0.15153
  → Hold

Day 15: Price=$0.1635 (TP2 hit!)
  → highest_price=$0.1635
  → Trail=$0.15533

DAY 15 (TP2 Hit):
─────────────────────────────────────────────────────────────
Position Monitor (2:15 PM):
  1. Fetch price: $0.1638
  2. Check TP2: $0.1625
  3. Price >= TP2? YES ✅
  4. tp1_hit? YES ✅
  5. EXECUTE:
     - Sell remaining 400 DOGE @ $0.1638
     - Profit: $15.52 (+31.0%)
  6. Close position completely
  7. Record in database:
     - Entry: $0.1250
     - Exit: Avg $0.1540 (weighted)
     - Total profit: $23.28 (+23.3%)
     - Hold: 15 days
  8. Remove from positions.json
  9. Dashboard shows: Closed trade, +$23.28

FINAL RESULTS:
─────────────────────────────────────────────────────────────
Total Investment: $100
Total Return: $123.28
Net Profit: $23.28 (+23.3%)
Hold Time: 15 days
Strategy: Goldilock (DOGE)

Breakdown:
  TP1 (50%): +15.4% = $7.76
  TP2 (50%): +31.0% = $15.52
  Total: +23.3%
```

---

## 🎛️ Dashboard Features

### 1. **Real-Time Metrics**
- USDT Balance (fetched live from Binance)
- Total Balance (calculated from positions + USDT)
- Active Positions (X/2 with Goldilock)
- AI Signals count (last 24h)
- Kill Switch status

### 2. **Active Trades Table**
- Updates every 60 seconds (auto-refresh)
- Shows current price (from 5-min monitor updates)
- Live P&L calculation
- TP/SL levels
- Last update timestamp

### 3. **Closed Trades History**
- Last 5 trades from database
- Entry/exit prices
- P&L and percentage
- Duration (hold time)
- Status (TP HIT / SL HIT)

### 4. **AI Signals Panel**
- Last 24h signals from Claude
- Edge rating (STRONG/MODERATE/WEAK)
- Rationale snippets
- Price and TP/SL recommendations

### 5. **Scan Schedule**
- Last scan time (Sydney timezone)
- Next scan countdown
- Interval (default: 240 minutes)
- Scan status

### 6. **Trading Mode Toggle**
- Switch between MONITORING and LIVE
- Visual indicator
- Persists across restarts

---

## 🔧 Key Configuration

```python
# Position Monitor
POSITION_CHECK_INTERVAL_MINUTES = 5  # Check every 5 min

# Main Trading Loop
ANALYSIS_INTERVAL_MINUTES = 240      # Scan every 4 hours

# Dashboard
AUTO_REFRESH_SECONDS = 60            # Refresh every 60 sec

# Goldilock Strategy (DOGE/SHIB/SOL)
POSITION_SIZE_PCT = 0.40             # 40% per trade
MIN_HOLD_DAYS = 7                    # Min 7 days hold
MAX_HOLD_DAYS = 90                   # Max 90 days
INITIAL_STOP_LOSS = 0.08             # 8% (days 0-6)
REGULAR_STOP_LOSS = 0.03             # 3% (day 7+)
TP1 = 0.15                           # +15%
TP2 = 0.30                           # +30%
TRAILING_STOP = 0.05                 # 5%
MAX_TRADES_PER_MONTH = 1             # Per coin
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `positions.json` | Active positions (updated every 5 min) |
| `signal_history.db` | SQLite database of AI signals |
| `last_scan.json` | Last scan metadata |
| `system_health.json` | Kill switch / health status |
| `trading_mode.json` | MONITORING vs LIVE mode |

---

This system provides complete visibility into:
- Entry signals (why we entered)
- Live position tracking (5-min updates)
- Exit execution (TP1, TP2, SL, Trailing)
- Performance metrics (P&L, win rate, etc.)

All data flows automatically from the trading engine to the dashboard with minimal latency.
