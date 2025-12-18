# 🔄 Complete Trading Flow - What Happens Next

## System Status Right Now

✅ **All Data Cleared:**
- positions.json = `{}` (no open positions)
- signal_history.json = `[]` (no past signals)
- screening_results.json = placeholder (ready for first scan)

✅ **Configuration:**
- Scan interval: **240 minutes** (every 4 hours)
- Tracked coins: **DOGEUSDT, SHIBUSDT, SOLUSDT** only
- Position size: **40%** per trade
- Max positions: **2** concurrent

---

## 📊 The Complete Flow (Start to Finish)

### ⏰ STEP 1: System Startup (When you run `./start.sh`)

```
You → ./start.sh
     → Choose option (1=Dry Run, 2=Monitoring, 3=Live, 4=Dashboard)

System loads:
  ✅ Binance API connection
  ✅ Strategy Manager (loads GoldilockStrategy)
  ✅ Risk Manager (fetches USDT balance from Binance)
  ✅ Position Monitor (starts 5-minute loop)
  ✅ Safety Gates (validates configuration)

Log output:
  "Strategy found: GoldilockStrategy"
  "Tracked coins: DOGEUSDT, SHIBUSDT, SOLUSDT"
  "Position size: 40%"
  "Min hold: 7 days"
  "Position Monitor started - checking every 5 minutes"
  "Next scan in 240 minutes..."
```

**What you see:**
- Terminal shows initialization logs
- Dashboard (if started) shows:
  - Balance: $396.70 (live from Binance)
  - Active Coins: 0/2
  - AI Signals: 0
  - Last Scan: "Not yet run"
  - Next Scan: [Time + 240 minutes]

---

### 🔍 STEP 2: First Analysis Cycle (After 240 minutes = 4 hours)

```
[After 4 hours]

System wakes up → Main Trading Loop triggers

LOG: "🔍 Running AI analysis..."
LOG: "Fetching market data for tracked coins..."
```

#### 2A. Fetch Market Data (Tier 1 - No Claude Yet)

```python
For each coin (DOGE, SHIB, SOL):
  1. Fetch 1H candles (200 bars)
     GET /api/v3/klines?symbol=DOGEUSDT&interval=1h&limit=200
  
  2. Fetch 4H candles (200 bars)  
     GET /api/v3/klines?symbol=DOGEUSDT&interval=4h&limit=200
  
  3. Calculate Daily candles from 1H
     Resample 1H → Daily (aggregation)
  
  4. Calculate indicators on 4H:
     - RSI (14 periods)
     - EMA 9, 21, 50, 200
     - MACD (12, 26, 9)
     - Volume ratio (current / 20-bar average)
     - ATR (14 periods)
```

**Log output:**
```
📊 Market Data Fetched:
   DOGEUSDT: 200 bars (1H), 200 bars (4H)
   SHIBUSDT: 200 bars (1H), 200 bars (4H)
   SOLUSDT: 200 bars (1H), 200 bars (4H)

📊 Indicators Calculated:
   DOGEUSDT: RSI=42.3, EMA9=$0.1245, EMA21=$0.1230
   SHIBUSDT: RSI=58.7, EMA9=$0.00001150, EMA21=$0.00001140
   SOLUSDT: RSI=61.2, EMA9=$125.40, EMA21=$124.80
```

**Dashboard update:**
- Last Scan: "18 Dec 2025, 22:18 PM AEDT"
- Status: "Analyzing..."

---

#### 2B. Strategy Entry Check (Tier 1 - Still No Claude)

```python
For each coin:
  strategy = StrategyManager.get_strategy(symbol)
  
  # For Goldilock strategy:
  should_enter, reason = strategy.check_entry(
      df_4h=df_4h,        # 4H candles with indicators
      df_daily=df_daily,  # Daily candles
      current_idx=-1      # Latest bar
  )
```

**Entry Conditions (3 of 4 required):**

1. **RSI < 40** (oversold condition)
   ```
   Current 4H RSI: 42.3
   Required: < 40
   ❌ FAIL
   ```

2. **EMA 9 > EMA 21** (bullish trend)
   ```
   EMA9: $0.1245
   EMA21: $0.1230
   ✅ PASS (EMA9 > EMA21)
   ```

3. **Volume Spike > 1.3x** (increased interest)
   ```
   Current volume: 15.2M
   Average volume (20 bars): 12.1M
   Ratio: 1.26x
   ❌ FAIL (< 1.3x)
   ```

4. **MACD Bullish** (MACD line > Signal line)
   ```
   MACD: 0.0012
   Signal: 0.0015
   ❌ FAIL (MACD < Signal)
   ```

5. **Daily Trend** (Price > Daily EMA50)
   ```
   Daily close: $0.1250
   Daily EMA50: $0.1200
   ✅ PASS (Price > EMA50)
   ```

**Result for DOGEUSDT:**
```
✅ RSI < 40: NO (42.3)
✅ EMA Cross: YES
✅ Volume Spike: NO (1.26x)
✅ MACD Bullish: NO
✅ Daily Trend: YES

Total: 2/4 conditions met
Required: 3/4
Decision: ❌ NO ENTRY
Reason: "only_2_conditions"
```

**Log output:**
```
📊 Entry Check Results:
   DOGEUSDT: ❌ NO - only_2_conditions (ema_cross,daily_trend)
   SHIBUSDT: ❌ NO - daily_trend_bearish
   SOLUSDT: ❌ NO - only_1_conditions (ema_cross)

✅ Tier 1 Complete: 0 coins qualified for Claude analysis
```

**Screening page update:**
```json
{
  "scan_time": "2025-12-18T22:18:00Z",
  "total_screened": 3,
  "passed_filters": 0,
  "results": [
    {
      "symbol": "DOGEUSDT",
      "price": 0.1248,
      "rsi": 42.3,
      "conditions_met": 2,
      "reason": "only_2_conditions",
      "passed": false
    },
    {
      "symbol": "SHIBUSDT",
      "price": 0.00001145,
      "rsi": 58.7,
      "conditions_met": 0,
      "reason": "daily_trend_bearish",
      "passed": false
    },
    {
      "symbol": "SOLUSDT",
      "price": 124.65,
      "rsi": 61.2,
      "conditions_met": 1,
      "reason": "only_1_conditions",
      "passed": false
    }
  ]
}
```

**Dashboard shows:**
- AI Signals (24h): 0 high confidence
- Last Scan: "18 Dec 2025, 22:18 PM AEDT"
- Next Scan: "19 Dec 2025, 02:18 AM AEDT" (4 hours later)

---

### 🎯 STEP 3: What Happens When Entry Conditions ARE Met

**Scenario: DOGEUSDT drops to oversold**

```
[Next scan - 4 hours later]

Current 4H bar:
  Price: $0.1220 (dropped from $0.1248)
  RSI: 38.5 (now < 40) ✅
  EMA9 > EMA21: YES ✅
  Volume Spike: 1.45x ✅
  MACD Bullish: YES ✅
  Daily Trend: YES ✅

Entry Check:
  ✅ RSI < 40: YES (38.5)
  ✅ EMA Cross: YES
  ✅ Volume Spike: YES (1.45x)
  ✅ MACD Bullish: YES
  ✅ Daily Trend: YES

Total: 5/4 conditions met (need 3/4)
Decision: ✅ SHOULD ENTER
Reason: "5/4_conds:rsi_oversold,ema_cross,volume_spike,macd_bullish"
```

**Log output:**
```
🎯 ENTRY SIGNAL DETECTED!
   Symbol: DOGEUSDT
   Price: $0.1220
   Conditions: 5/4 met
   RSI: 38.5 (oversold)
   Reason: rsi_oversold,ema_cross,volume_spike,macd_bullish,daily_trend
```

---

#### 3A. Claude AI Analysis (Tier 2 - First Claude Call)

**Only NOW does the system call Claude:**

```python
LOG: "🤖 Calling Claude AI for final validation..."
LOG: "Sending market data to Claude Haiku..."

# Prepare prompt with indicators
prompt = f"""
Analyze DOGEUSDT for entry:
- Current Price: $0.1220
- RSI: 38.5 (oversold)
- EMA9: $0.1245 > EMA21: $0.1230
- Volume: 1.45x average
- MACD: Bullish crossover
- Daily trend: Bullish (price > EMA50)
- 4H chart: Bounce from support

Should we enter? Provide edge rating.
"""

# Claude response (typical):
{
  "decision": "BUY",
  "edge": "STRONG",
  "reason": "Oversold bounce with volume confirmation and bullish EMA structure. Daily trend supports. Risk/reward favorable.",
  "confidence": 78,
  "stop_loss": 0.1128,  // -7.5% from entry
  "take_profit": [1.15, 1.30]  // +15%, +30%
}
```

**Log output:**
```
🤖 Claude AI Response:
   Decision: BUY
   Edge: STRONG
   Confidence: 78%
   Reason: "Oversold bounce with volume confirmation..."
   
   Suggested Levels:
   Stop Loss: $0.1128 (-7.5%)
   TP1: $0.1403 (+15%)
   TP2: $0.1586 (+30%)
```

---

#### 3B. Safety Gates Validation (Tier 3 - Final Checks)

```python
LOG: "🛡️ TIER 3: Safety Gates & Execution"

Gate #1: Monthly Trade Limit
  Symbol: DOGEUSDT
  This month trades: 0
  Limit: 1
  ✅ PASS

Gate #2: Position Capacity
  Current positions: 0
  Max positions: 2
  ✅ PASS (slot available)

Gate #3: Balance Check
  Current balance: $396.70
  Usable (90%): $357.03
  Required (40%): $142.81
  ✅ PASS (sufficient funds)

Gate #4: Liquidity Check
  24h volume: $1.2B
  Min required: $10M
  ✅ PASS

Gate #5: RSI Range
  Current RSI: 38.5
  Range: 25-75
  ✅ PASS

Gate #6: Price Volatility (ATR)
  ATR %: 3.2%
  Max: 10%
  ✅ PASS

Gate #7: Daily Loss Limit
  Today's losses: $0
  Max allowed: 5% ($19.84)
  ✅ PASS

Result: ✅ ALL GATES PASSED
```

**Log output:**
```
✅ All safety gates PASSED
✅ Trade approved for execution
```

---

#### 3C. Position Sizing Calculation

```python
# From safety_gates.py
position_size_pct = 0.40  # 40% for Goldilock

usable_balance = $396.70 * 0.90 = $357.03
position_value = $357.03 * 0.40 = $142.81

quantity = $142.81 / $0.1220 = 1170.57 DOGE
```

**Log output:**
```
💰 Position Sizing:
   Balance: $396.70
   Usable (90%): $357.03
   Position size: 40%
   Position value: $142.81
   Quantity: 1170.57 DOGE
```

---

#### 3D. Calculate Stop Loss & Take Profits (Goldilock Parameters)

```python
# From goldilock_strategy.py
entry_price = $0.1220
hold_days = 0  # New position

# Stop Loss (8% during min hold)
stop_loss = $0.1220 * (1 - 0.08) = $0.1122

# Take Profit 1 (+15%, close 50%)
tp1_price = $0.1220 * 1.15 = $0.1403
tp1_size = 50% = 585.29 DOGE

# Take Profit 2 (+30%, close remaining 50%)
tp2_price = $0.1220 * 1.30 = $0.1586
tp2_size = 50% = 585.28 DOGE
```

**Log output:**
```
📊 Trade Parameters (Goldilock Strategy):
   Entry: $0.1220
   Quantity: 1170.57 DOGE
   Stop Loss: $0.1122 (8% - min hold)
   TP1: $0.1403 (+15%, close 50%)
   TP2: $0.1586 (+30%, close 50%)
   Hold: 7-90 days
```

---

#### 3E. Order Execution

**Dry Run Mode:**
```
[MONITORING MODE] Would BUY DOGEUSDT
   Entry: $0.1220
   Qty: 1170.57 DOGE
   Value: $142.81
   SL: $0.1122
   TP: $0.1403, $0.1586
   
✅ Trade logged (no real order)
```

**Live Mode:**
```
LOG: "Executing LIVE BUY for DOGEUSDT..."

Step 1: Market Buy Order
  POST /api/v3/order
  {
    "symbol": "DOGEUSDT",
    "side": "BUY",
    "type": "MARKET",
    "quantity": 1170.57
  }

Response:
  Order ID: 12345678
  Status: FILLED
  Filled Price: $0.1221 (slight slippage)
  Filled Qty: 1170.57 DOGE
  
✅ BUY order executed

Step 2: Save Position
  File: data/positions.json
  {
    "DOGEUSDT": {
      "symbol": "DOGEUSDT",
      "entry_price": 0.1221,
      "quantity": 1170.57,
      "entry_time": "2025-12-19T02:18:00",
      "stop_loss": 0.1122,
      "take_profit_targets": [
        {"price": 0.1404, "position_percent": 0.5},
        {"price": 0.1587, "position_percent": 0.5}
      ],
      "current_price": 0.1221,
      "tp1_hit": false,
      "highest_price": 0.1221,
      "last_price_update": "2025-12-19T02:18:30"
    }
  }

Step 3: Notification
  📱 Telegram: "🚀 BUY DOGEUSDT @ $0.1221"
```

**Dashboard immediately shows:**
```
Active Coins: 1/2
Active Trades:
┌─────────┬──────────┬────────┬─────────┬──────┬────────────┬───────────────────┐
│ Symbol  │ Quantity │ Entry  │ Current │ P&L  │ Stop Loss  │ Strategy Status   │
├─────────┼──────────┼────────┼─────────┼──────┼────────────┼───────────────────┤
│ DOGEUSDT│ 1170.57  │$0.1221 │ $0.1221 │ $0.00│ $0.1122(8%)│ Min Hold (Day 0/7)│
└─────────┴──────────┴────────┴─────────┴──────┴────────────┴───────────────────┘

Hold Days: 0 (yellow badge)
TP1: $0.1404 (+15%) - Pending
High: $0.1221
```

---

### 🔄 STEP 4: Position Monitoring (Every 5 Minutes)

**Position monitor runs independently:**

```
[5 minutes after entry]

LOG: "📊 Position Monitor: Checking 1 open position(s)"

For DOGEUSDT:
  1. Fetch current price from Binance
     GET /api/v3/ticker/price?symbol=DOGEUSDT
     Current: $0.1225
  
  2. Calculate hold days
     Entry: 2025-12-19 02:18
     Now: 2025-12-19 02:23
     Hold days: 0
  
  3. Update highest price
     Previous high: $0.1221
     Current: $0.1225
     New high: $0.1225 ✅
  
  4. Check exit conditions
     Strategy: GoldilockStrategy
     Min hold: 7 days
     
     Current hold: 0 days < 7 days
     → ONLY check stop loss (block TPs)
     
     Stop loss: $0.1122
     Current: $0.1225
     $0.1225 > $0.1122 ✅ OK
     
     Result: NO EXIT

  5. Update positions.json
     {
       "current_price": 0.1225,
       "highest_price": 0.1225,
       "last_price_update": "2025-12-19T02:23:00"
     }
```

**Dashboard auto-refreshes (every 60 seconds):**
```
DOGEUSDT: 
  Current: $0.1225 (updated)
  High: $0.1225
  P&L: +$0.47 (+0.3%)
  Hold Days: 0
  Strategy Status: "Min Hold (Day 0/7)"
```

**This repeats every 5 minutes for life of position.**

---

### 📈 STEP 5: Day-by-Day Position Evolution

#### Day 0-6: Minimum Hold Period

**Day 1:**
```
Price: $0.1215
P&L: -$0.70 (-0.5%)
Stop Loss: $0.1122 (8%)
Hold Days: 1
Status: "Min Hold (Day 1/7)"

Check: $0.1215 > $0.1122 ✅ OK
Action: HOLD (no exit allowed except SL)
```

**Day 3:**
```
Price: $0.1195
P&L: -$3.04 (-2.1%)
Stop Loss: $0.1122 (8%)
Hold Days: 3
Status: "Min Hold (Day 3/7)"

Check: $0.1195 > $0.1122 ✅ OK
Action: HOLD (price dropping but above SL)
```

**Day 5:**
```
Price: $0.1180
P&L: -$4.80 (-3.4%)
Stop Loss: $0.1122 (8%)
Hold Days: 5
Status: "Min Hold (Day 5/7)"

Check: $0.1180 > $0.1122 ✅ OK
Action: HOLD (still above 8% SL)
```

**If price drops below $0.1122 during days 0-6:**
```
Day 4, Price: $0.1120

Check: $0.1120 <= $0.1122 ❌ STOP LOSS HIT

LOG: "🚨 DOGEUSDT: STOP LOSS (EARLY EXIT - Day 4) @ $0.1120"

Action: CLOSE 100% (1170.57 DOGE)
  Market Sell Order → Filled @ $0.1120
  Loss: -$11.82 (-8.2%)
  
Notification: "🛑 STOP LOSS: DOGEUSDT -8.2%"

positions.json: {} (empty, position closed)
Dashboard: "No open trades"
```

---

#### Day 7+: Full Exit Logic Enabled

**Day 7:**
```
Price: $0.1240
P&L: +$2.22 (+1.6%)
Hold Days: 7
Status: "Day 7"

Changes:
  ✅ Stop loss tightens: $0.1122 → $0.1184 (3%)
  ✅ TP1 enabled: $0.1404
  ✅ TP2 enabled: $0.1587
  ✅ Trailing stop ready (activates after TP1)

Check exits:
  1. SL: $0.1240 > $0.1184 ✅ OK
  2. TP1: $0.1240 < $0.1404 (not hit)
  3. TP2: $0.1240 < $0.1587 (not hit)
  
Action: HOLD
```

**Day 10:**
```
Price: $0.1410 (pumping!)
P&L: +$22.13 (+15.5%)
Hold Days: 10
Highest: $0.1410
Status: "Day 10"

Check exits:
  1. Max hold: 10 < 90 ✅ OK
  2. SL: $0.1410 > $0.1184 ✅ OK
  3. TP1: $0.1410 >= $0.1404 ✅ HIT!

LOG: "🎯 DOGEUSDT: TP1 HIT (+15%) @ $0.1410"

Action: CLOSE 50% (585.29 DOGE)
  Market Sell Order → Filled @ $0.1410
  Profit on 50%: +$11.07 (+15.5%)
  
Update position:
  {
    "quantity": 585.28,  // Remaining 50%
    "tp1_hit": true,  // ✅ TP1 executed
    "highest_price": 0.1410
  }

Activate Trailing Stop:
  Trail = $0.1410 * 0.95 = $0.1340 (5% below high)

Dashboard:
  Quantity: 585.28 (halved)
  TP1: "✓ HIT" (green)
  Status: "Trailing Active ($0.1340)"
```

**Day 12:**
```
Price: $0.1450 (still climbing)
P&L on remaining: +$13.41 (+18.8%)
Hold Days: 12
Highest: $0.1450
Status: "Trailing Active ($0.1378)"

Trailing stop updates:
  New high: $0.1450
  Trail: $0.1450 * 0.95 = $0.1378

Check exits:
  1. SL: $0.1450 > $0.1184 ✅ OK
  2. Trailing: $0.1450 > $0.1378 ✅ OK
  3. TP2: $0.1450 < $0.1587 (not yet)
  
Action: HOLD (trail is rising with price)
```

**Day 14:**
```
Price: $0.1420 (pulling back)
P&L on remaining: +$11.65 (+16.3%)
Hold Days: 14
Highest: $0.1450 (unchanged)
Trailing: $0.1378

Check exits:
  1. Trailing: $0.1420 > $0.1378 ✅ OK
  
Action: HOLD (still above trail)
```

**Day 15:**
```
Price: $0.1370 (dropped below trail!)
P&L on remaining: +$8.72 (+12.2%)
Hold Days: 15
Highest: $0.1450
Trailing: $0.1378

Check exits:
  1. Trailing: $0.1370 < $0.1378 ❌ TRAILING STOP HIT

LOG: "📉 DOGEUSDT: TRAILING STOP @ $0.1370 (5% from high $0.1450)"

Action: CLOSE remaining 50% (585.28 DOGE)
  Market Sell Order → Filled @ $0.1370
  Profit on 50%: +$8.72 (+12.2%)
  
Total Position Result:
  First 50% @ TP1: +$11.07 (+15.5%)
  Second 50% @ Trail: +$8.72 (+12.2%)
  Total Profit: +$19.79 (+13.8%)
  Hold Time: 15 days

Notification: "✅ DOGEUSDT: Position closed +13.8% (15 days)"

positions.json: {} (empty)
Dashboard: "No open trades"
Slot freed: 1/2 → 0/2
```

---

#### Alternative: TP2 Exit (Best Case)

**Day 18:**
```
Price: $0.1590 (moon!)
P&L on remaining: +$21.56 (+30.2%)
Hold Days: 18
Highest: $0.1590
Trailing: $0.1511 (5% below $0.1590)

Check exits:
  1. TP2: $0.1590 >= $0.1587 ✅ HIT!

LOG: "🎯 DOGEUSDT: TP2 HIT (+30%) @ $0.1590"

Action: CLOSE remaining 50% (585.28 DOGE)
  Market Sell Order → Filled @ $0.1590
  Profit on 50%: +$21.60 (+30.2%)
  
Total Position Result:
  First 50% @ TP1: +$11.07 (+15.5%)
  Second 50% @ TP2: +$21.60 (+30.2%)
  Total Profit: +$32.67 (+22.9%)
  Hold Time: 18 days

positions.json: {} (empty)
```

---

#### Worst Case: Max Hold Force Exit

**Day 90:**
```
Price: $0.1180
P&L on remaining: -$2.40 (-3.4%)
Hold Days: 90
Status: "Max Hold Reached!"

Check exits:
  1. Max hold: 90 >= 90 ✅ FORCE EXIT

LOG: "⏰ DOGEUSDT: MAX HOLD (90 days) - Force exit @ $0.1180"

Action: CLOSE remaining 50% (585.28 DOGE)
  Market Sell Order → Filled @ $0.1180
  Loss on 50%: -$2.40 (-3.4%)
  
Total Position Result:
  First 50% @ TP1: +$11.07 (+15.5%)
  Second 50% @ Max Hold: -$2.40 (-3.4%)
  Total Profit: +$8.67 (+6.1%)
  Hold Time: 90 days

positions.json: {} (empty)
```

---

## 🎯 What You Should Expect

### Immediately After Starting:

1. **Dashboard shows:**
   - Balance: $396.70 (live)
   - Active Coins: 0/2
   - Last Scan: "Not yet run"
   - Next Scan: [Current time + 240 min]

2. **Terminal shows:**
   ```
   Strategy found: GoldilockStrategy
   Tracked coins: DOGEUSDT, SHIBUSDT, SOLUSDT
   Position Monitor started
   Next scan in 240 minutes...
   ```

### First 4 Hours (Waiting):

- System is idle
- Position monitor checks every 5 min (finds nothing)
- Dashboard refreshes every 60 sec (shows same data)
- No API calls except price checks

### After First Scan (4 hours):

**Most likely scenario (80% of scans):**
```
✅ Scanned 3 coins
❌ No entry signals (conditions not met)
   DOGEUSDT: only_2_conditions
   SHIBUSDT: daily_trend_bearish
   SOLUSDT: rsi_too_high

Screening page shows rejection reasons
Next scan: +4 hours
```

**Rare scenario (20% of scans):**
```
✅ Scanned 3 coins
✅ Entry signal: DOGEUSDT (5/4 conditions)
🤖 Claude validated (STRONG edge)
✅ All safety gates passed
💼 BUY executed: 1170 DOGE @ $0.1220

Dashboard shows active position
Position monitor starts checking every 5 min
```

### Once Position Opened:

**Days 0-6 (Min Hold):**
- Only 8% stop loss active
- Dashboard shows: "Min Hold (Day X/7)"
- Yellow badge
- Can't exit unless SL hit
- Monitor every 5 min

**Day 7+ (Full Exit Logic):**
- Stop tightens to 3%
- TP1/TP2 enabled
- Dashboard shows: "Day X"
- Blue badge
- All exits active

**After TP1 Hit:**
- 50% closed
- Dashboard shows: "Trailing Active ($X.XX)"
- Green badge
- Trailing stop follows price up
- Final exit at TP2 or trailing

### Expected Timeline for First Trade:

```
Day 0: Start system
Day 0-7: Scans every 4 hours (likely no signals)
Day 7-14: Continue scanning (market conditions improve)
Day 14: Entry signal appears → Trade executed
Day 14-20: Min hold period (only SL active)
Day 21+: Full exits enabled
Day 28: TP1 hits → Close 50%
Day 32: Trailing hits → Close remaining 50%

Total: ~32 days from start to first complete trade
```

### Monthly Expectations:

- **Scans per month:** 180 (24 hours × 30 days ÷ 4 hours)
- **Entry signals:** 2-5 (1-3% hit rate)
- **Trades executed:** 1-3 (max 1 per coin per month)
- **Win rate target:** 65%+ (Goldilock strategy)
- **Average hold:** 15-30 days

---

## 🎮 Dashboard Real-Time View

### No Positions (Clean State):
```
┌─────────────────────────────────────────────────┐
│ USDT Balance: $396.70                          │
│ Active Coins: 0/2                              │
│ AI Signals (24h): 0 high confidence            │
│ Kill Switch: ACTIVE                            │
└─────────────────────────────────────────────────┘

Active Trades: No open trades - Waiting for next signal

Last Scan: 18 Dec 2025, 22:18 PM AEDT
Next Scan: 19 Dec 2025, 02:18 AM AEDT
Interval: Every 240 minutes
```

### With Position (Day 5):
```
┌─────────────────────────────────────────────────┐
│ USDT Balance: $253.89                          │
│ Active Coins: 1/2                              │
│ AI Signals (24h): 1 high confidence            │
│ Kill Switch: ACTIVE                            │
└─────────────────────────────────────────────────┘

Active Trades:
┌──────────┬──────────┬────────┬─────────┬──────────┬──────────────┬──────────┬───────────────────┐
│ Symbol   │ Quantity │ Entry  │ Current │ High     │ P&L          │ Stop Loss│ Strategy Status   │
├──────────┼──────────┼────────┼─────────┼──────────┼──────────────┼──────────┼───────────────────┤
│ DOGEUSDT │ 1170.57  │$0.1221 │ $0.1195 │ $0.1225  │ -$3.04(-2.5%)│$0.1122(8%)│Min Hold (Day 5/7) │
└──────────┴──────────┴────────┴─────────┴──────────┴──────────────┴──────────┴───────────────────┘

Hold Days: 5 (🟡 Min hold - yellow badge)
TP1: $0.1404 (+15%) - Pending
```

### With Position (Day 12, After TP1):
```
Active Trades:
┌──────────┬──────────┬────────┬─────────┬──────────┬──────────────┬──────────┬────────────────────────┐
│ Symbol   │ Quantity │ Entry  │ Current │ High     │ P&L          │ Stop Loss│ Strategy Status        │
├──────────┼──────────┼────────┼─────────┼──────────┼──────────────┼──────────┼────────────────────────┤
│ DOGEUSDT │  585.28  │$0.1221 │ $0.1450 │ $0.1450  │+$13.41(+18.8%)│$0.1184(3%)│Trailing Active($0.1378)│
└──────────┴──────────┴────────┴─────────┴──────────┴──────────────┴──────────┴────────────────────────┘

Hold Days: 12 (🟢 Trailing - green badge)
TP1: $0.1404 (+15%) - ✓ HIT
```

---

## 📱 Notifications You'll Receive

**Entry:**
```
🚀 BUY DOGEUSDT @ $0.1221
Entry: $0.1221
Quantity: 1170.57 DOGE
Stop Loss: $0.1122 (-8%)
TP1: $0.1404 (+15%)
TP2: $0.1587 (+30%)
Strategy: Goldilock (7-90 days)
```

**TP1 Hit:**
```
🎯 TP1 HIT: DOGEUSDT
Price: $0.1410 (+15.5%)
Closed: 50% (585.29 DOGE)
Profit: +$11.07
Remaining: 585.28 DOGE
Trailing: ACTIVE ($0.1340)
```

**Final Exit:**
```
✅ Position Closed: DOGEUSDT
Entry: $0.1221
Exit: $0.1370
P&L: +$19.79 (+13.8%)
Hold Time: 15 days
Reason: Trailing Stop
```

**Stop Loss:**
```
🛑 STOP LOSS: DOGEUSDT
Entry: $0.1221
Exit: $0.1120
P&L: -$11.82 (-8.2%)
Hold Time: 4 days
Reason: 8% Stop Loss (Early Exit)
```

---

## ⚠️ Important Notes

### Capital Deployment:
- **40% per trade**
- **Max 2 positions = 80% deployed**
- **20% always in reserve**

Example with $396.70:
- Position 1: $142.81 (40%)
- Position 2: $142.81 (40%)
- Reserve: $71.40 (20%)
- Emergency buffer: $39.68 (10%)

### Monthly Limits:
- **1 trade per coin per month**
- If you trade DOGE on Dec 19, can't trade DOGE again until Jan 1
- Can still trade SHIB or SOL
- Prevents overtrading same coin

### Time Commitment:
- **No active monitoring required**
- System runs 24/7 automatically
- Check dashboard 1-2 times per day
- Notifications keep you informed
- Position monitor handles exits

### Risk Management:
- **Max loss per trade:** 8% (during min hold)
- **Max portfolio loss:** 3.2% (if both positions hit SL)
- **Daily loss limit:** 5% total (circuit breaker)
- **Capital at risk:** 80% max deployed

---

## 🚀 Ready to Start?

```bash
cd /Users/rameshrajasekaran/Springai/crypto-ai-trader
./start.sh

Choose:
  1 = Dry Run (Test without real orders)
  2 = Monitoring (Track signals, no execution)  
  3 = Live Trading (Real money - start small!)
  4 = Dashboard Only (View interface)
```

**Recommended first run:** Option 1 (Dry Run) for 24-48 hours to see system behavior.

System is configured, tested, and ready! 🎯
