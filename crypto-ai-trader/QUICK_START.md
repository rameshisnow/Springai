# 🚀 Quick Start Guide - Goldilock Strategy

## ✅ Pre-Run Checklist

- [x] On `goldilock` branch
- [x] `.env` file exists
- [ ] Virtual environment activated
- [ ] Dependencies installed

---

## 🎯 Quick Start (3 Steps)

### Option 1: Using Startup Script (Recommended)

```bash
./start.sh
```

Then choose:
- **1** = Dry Run (Safe testing, no real trades)
- **2** = Monitoring (Track signals only)
- **3** = Live Trading (⚠️ Real money!)
- **4** = Dashboard Only
- **5** = Run Tests

### Option 2: Manual Start

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Install dependencies (if not done)
pip install -r requirements.txt

# 3. Run in your preferred mode:

# Dry Run Mode (Recommended for first run)
export DRY_RUN_ENABLED=true
export MONITORING_ONLY=false
python3 main.py

# OR Monitoring Mode
export MONITORING_ONLY=true
export DRY_RUN_ENABLED=false
python3 main.py

# OR Dashboard Only
python3 -m src.web.server
```

---

## 📊 What Will Happen

### Main Trading Bot
```
1. System starts up (5-10 seconds)
2. Connects to Binance API
3. Loads Goldilock strategy (DOGE/SHIB/SOL)
4. Runs every 240 minutes (4 hours)
5. Each cycle:
   - Fetches candles (1H, 4H, Daily)
   - Checks entry conditions (RSI<40, 3/4 conditions)
   - Calls Claude AI for analysis
   - Executes trades if conditions met
6. Position Monitor runs every 5 minutes
   - Checks stop losses
   - Executes take profits
   - Manages trailing stops
```

### Dashboard
- Access at: http://localhost:8080
- Default passcode: Check `.env` file
- Auto-refreshes every 60 seconds
- Shows:
  - Active positions with hold days
  - Dynamic stop loss levels (8% or 3%)
  - TP1 hit status
  - Trailing stop activation
  - Strategy phase indicators

---

## 🧪 Recommended First Run: DRY RUN MODE

```bash
./start.sh
# Choose: 1 (Dry Run)
```

**What it does:**
- Simulates all trades
- No real orders sent to Binance
- Safe to test strategy logic
- Logs all decisions
- Shows what would happen in live mode

**Look for in logs:**
```
✅ Strategy found: GoldilockStrategy
✅ Tracked coins: DOGEUSDT, SHIBUSDT, SOLUSDT
📊 Fetching market data for DOGEUSDT...
🎯 Entry Check Result: Should Enter: ❌ NO
   Reason: daily_trend_bearish
```

---

## 🔍 Testing Before Live Trading

### Run All Tests
```bash
./start.sh
# Choose: 5 (Run Tests)
```

This runs:
1. **Exit Logic Test** - Validates TP/SL mechanics
2. **Integration Test** - Tests entry conditions

**Expected Output:**
```
✅ PASS: Dynamic Stop Loss (8% → 3%)
✅ PASS: Minimum Hold (7 days)
✅ PASS: Take Profit Levels
✅ PASS: Trailing Stop (5%)
✅ PASS: Maximum Hold (90 days)
✅ PASS: Position Sizing (40%)
✅ PASS: TP1 Hit Tracking
✅ PASS: Exit Logic Flow

Results: 8/8 tests passed
🎉 ALL TESTS PASSED
```

---

## 📱 Monitor Your System

### Terminal Output
Watch for these key messages:

**✅ Good Signs:**
```
✅ Strategy found: GoldilockStrategy
✅ Tracked coins: DOGEUSDT, SHIBUSDT, SOLUSDT
✅ All safety gates passed
✅ Position sizing: 40%
✅ Monthly limit: OK
```

**⚠️ Normal Rejections:**
```
❌ Entry Check: daily_trend_bearish
❌ Monthly trade limit reached
❌ Insufficient liquidity
```

**🚨 Errors to Investigate:**
```
❌ Binance API error
❌ Claude API timeout
❌ Position monitor error
```

### Dashboard Monitoring

1. **Open dashboard:** http://localhost:8080
2. **Check metrics:**
   - USDT Balance (live from Binance)
   - Active Coins (X/2)
   - AI Signals (24h count)
   - Kill Switch status

3. **Watch Active Trades table:**
   - Hold Days counter
   - Strategy Status (Min Hold / Trailing / etc.)
   - TP1 Hit status
   - Dynamic SL levels

---

## 🎛️ System Controls

### Stop the Bot
```bash
Press Ctrl+C in terminal
```

### Pause Trading (Kill Switch)
```bash
# Edit: data/system_health.json
{
  "global_trading_pause": true,
  "status_message": "Manual pause"
}
```

### Change Trading Mode
```bash
# Via Dashboard: Toggle "MONITORING" ↔ "LIVE"
# Via Code: Edit .env or constants.py
MONITORING_ONLY=true/false
DRY_RUN_ENABLED=true/false
```

---

## 📋 First Run Checklist

### Before Starting:

1. **Check Balance**
   ```bash
   # Should have at least $100 USDT
   # Recommended: $250+
   ```

2. **Verify API Keys**
   ```bash
   # In .env file:
   BINANCE_API_KEY=your_key
   BINANCE_SECRET_KEY=your_secret
   ANTHROPIC_API_KEY=your_claude_key
   ```

3. **Set Mode**
   ```
   First time? → DRY RUN
   Testing? → MONITORING
   Ready? → LIVE (with small balance)
   ```

### During First Run:

1. **Watch logs** for 5-10 minutes
2. **Check dashboard** shows correct balance
3. **Verify** only DOGE/SHIB/SOL tracked
4. **Confirm** no unexpected errors

### After First Cycle (4 hours):

1. **Review logs** for entry checks
2. **Check signals** in dashboard
3. **Validate** monthly limits working
4. **Test** position monitor (if position opened)

---

## 🔧 Troubleshooting

### Bot won't start
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Reinstall dependencies
pip install -r requirements.txt

# Check .env file
cat .env  # Verify API keys present
```

### No trades executing (in LIVE mode)
```
Possible reasons:
1. ✅ Monthly limit reached (1 per coin)
2. ✅ Entry conditions not met (RSI, EMA, etc.)
3. ✅ Daily trend bearish (price < daily EMA50)
4. ✅ Max positions reached (2 positions)
5. ❌ Safety gates blocking (check logs)
```

### Dashboard shows $0 balance
```bash
# Check Binance API connection
# Verify USDT in Spot wallet
# Check API key permissions (read + trade)
```

### Position monitor not updating
```bash
# Check: Position monitor runs every 5 min
# Look for: "📊 Position Monitor: Checking X positions"
# If missing: Position monitor may have crashed
# Solution: Restart bot
```

---

## 📊 Expected Behavior

### Normal Operation:

**Every 4 hours (Main Loop):**
- Fetches DOGE, SHIB, SOL data
- Checks entry conditions
- Calls Claude AI (if conditions met)
- Executes orders (if all gates pass)
- Logs: "Next scan in 240 minutes"

**Every 5 minutes (Position Monitor):**
- Checks all open positions
- Updates current prices
- Checks stop losses
- Executes take profits
- Manages trailing stops
- Logs: "Next position check in 5 minutes"

**Every 60 seconds (Dashboard):**
- Auto-refreshes
- Shows updated P&L
- Displays latest signals

### First Trade Cycle:

```
Day 0:  Entry @ $0.1250 (40% = $100 if balance is $250)
        SL: $0.1150 (8% wide)
        TP1: $0.1438 (+15%)
        Status: "Min Hold (Day 0/7)"

Day 1-6: Only 8% SL checked
         No TP exits allowed
         Status: "Min Hold (Day X/7)"

Day 7:  SL tightens to 3% ($0.1213)
        TP1/TP2 enabled
        Status: "Day 7"

Day 10: TP1 hits @ $0.1450
        Close 50% (profit: +16%)
        Trailing activates
        Status: "Trailing Active ($0.1378)"

Day 15: TP2 hits @ $0.1630
        Close remaining 50% (profit: +30.4%)
        Total: +23.2% over 15 days
        Position closed
```

---

## 🎯 Quick Command Reference

```bash
# Start with menu
./start.sh

# Run tests
python3 test_goldilock_exits.py

# Check strategy
python3 test_goldilock_integration.py

# Dashboard only
python3 -m src.web.server

# Stop bot
Ctrl+C

# Check logs
tail -f logs/crypto_trader.log

# Check positions
cat data/positions.json

# Check git branch
git branch --show-current
```

---

## 🚀 Ready to Start?

### Recommended Path:

1. **Run Tests First** ✅
   ```bash
   ./start.sh → Choose 5
   ```

2. **Start in Dry Run** ✅
   ```bash
   ./start.sh → Choose 1
   ```

3. **Watch for 1-2 cycles** (8 hours)

4. **Switch to Monitoring** ✅
   ```bash
   ./start.sh → Choose 2
   ```

5. **Monitor for 24 hours**

6. **Go Live with small balance** ($100-250)
   ```bash
   ./start.sh → Choose 3
   ```

7. **Scale up** after successful trades

---

## ⚠️ Important Reminders

- **Start small:** $100-250 for first live trades
- **Monitor closely:** First 48 hours
- **Monthly limit:** Max 1 trade per coin per month
- **Max positions:** Only 2 at a time (DOGE + SHIB/SOL)
- **Min hold:** 7 days (don't panic on day 3!)
- **Check dashboard:** http://localhost:8080

---

Ready? Run: `./start.sh` 🚀
