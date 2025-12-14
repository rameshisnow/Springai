# 📊 Live Screening Results Dashboard - Setup Complete

## Overview
You now have a **live screening results endpoint** that displays detailed coin screening data from every scan cycle. The results are automatically saved to `data/screening_results.json` and can be viewed through:

1. **Web Dashboard** → `http://67.219.108.145/screening` (via Nginx proxy)
2. **API Endpoint** → `http://67.219.108.145/api/screening_results` (JSON)

---

## What Gets Displayed

The screening results show for **each coin evaluated**:

### Summary Statistics
- ✅ **Passed Screening** - Coins that met all 4 filter criteria
- ❌ **Failed Screening** - Coins that missed at least one filter
- 📊 **Total Evaluated** - Total coins checked (top 100 by volume)
- 🕐 **Last Scan** - Timestamp of the screening run

### Per-Coin Breakdown
For each coin (e.g., ETHUSDT, SOLUSDT, etc.), you see:

#### 1. **EMA Filter** (Exponential Moving Averages)
   - Criteria: Close > EMA9 > EMA21 (on 1H) AND Close > EMA21 (on 4H)
   - Shows actual values for each
   - ✅ PASSED or ❌ FAILED status

#### 2. **RSI Filter** (Relative Strength Index)
   - Criteria: RSI between 55-70 on both 1H and 4H (not overbought)
   - Shows RSI values for each timeframe
   - Acceptable range: 55-70

#### 3. **Breakout Filter**
   - Criteria: Close above prior 20-bar OR 50-bar high (excluding current bar)
   - Shows both conditions
   - Must pass at least one to qualify

#### 4. **BTC Strength Filter**
   - Criteria: Coin % change outperforms BTC on both 1H and 4H
   - Shows coin change vs BTC change for each timeframe
   - Must beat BTC on both to pass

### Failure Reasons
- If coin fails, reason is shown (e.g., "RSI 1H:36.6 4H:53.8 (need 55-70)")

---

## How to Access

### Option 1: Web Browser (Recommended)
```
http://67.219.108.145/screening
```
- Visually formatted with color coding (passed=green, failed=red)
- Auto-refreshes every 30 seconds
- Filter details organized in collapsible sections
- Shows price for each coin

### Option 2: API (For Integration)
```bash
curl http://67.219.108.145/api/screening_results | python3 -m json.tool
```

Returns JSON with structure:
```json
{
  "timestamp": "2025-12-14T21:55:24.253628+00:00",
  "total_coins_evaluated": 32,
  "passed": 0,
  "failed": 32,
  "coins": {
    "ETHUSDT": {
      "status": "failed",
      "current_price": 3081.05,
      "filters": { ... },
      "reason": "EMA... | RSI... | Breakout... | BTC strength..."
    }
  }
}
```

### Option 3: Direct File Access
SSH into VPS:
```bash
cat /opt/springai/crypto-ai-trader/data/screening_results.json | python3 -m json.tool
```

---

## How It Works

1. **Signal Generator runs every 60 minutes** (configurable)
2. **During each cycle:**
   - Fetches top 100 coins by volume
   - Evaluates each against 4 primary screening filters
   - Records pass/fail status + detailed metrics
   - Saves to `data/screening_results.json`
   - Overwrites previous results (latest always current)

3. **Dashboard reads the JSON** and renders it with detailed filter breakdowns

---

## Integration with Dashboard

The screening results page is **linked from the main dashboard**:
- Look for **📊 Screening** button in the top navigation bar
- Click to view live results
- Results auto-refresh every 30 seconds
- Back button returns to main dashboard

---

## Current Status (Last Scan)

**Timestamp:** 2025-12-14T21:55:24.253628+00:00  
**Total Evaluated:** 32 coins  
**Passed:** 0  
**Failed:** 32  

**Why no coins passed:** 
- Most had RSI below 55 (oversold - normal at start of trend)
- Most were below EMAs (not in uptrend)
- No significant breakouts detected in 1H timeframe

---

## Key Observations for Your Testing

The first-level screening shows why SOL, BNB, ETH didn't pass:

**SOLUSDT:**
- Close: $129.93, EMA9: $130.59, EMA21: $131.37 → **EMA FAILED** (price below both EMAs)
- RSI 1H: 20.9, RSI 4H: 30.6 → **RSI FAILED** (need 55-70, coin is oversold)
- No breakout detected
- BTC relative strength failed

**ETHUSDT:**
- Close: $3081.05, EMA9: $3090.74, EMA21: $3097.91 → **EMA FAILED** (price below both)
- RSI 1H: 36.6, RSI 4H: 53.8 → **RSI FAILED** (1H is way too low)
- No breakout
- BTC strength failed

---

## To Trigger Immediate Scan (Testing)

The signal generator runs automatically every 60 minutes. To test immediately:

```bash
ssh root@67.219.108.145 "cd /opt/springai/crypto-ai-trader && timeout 90 python3 << 'PYEOF'
import asyncio
from src.ai.signal_generator import SignalOrchestrator
from src.data.data_fetcher import binance_fetcher

async def test():
    orch = SignalOrchestrator()
    top_coins = await binance_fetcher.get_top_coins_by_volume(100)
    await orch._screen_primary_setups(top_coins)
    
asyncio.run(test())
PYEOF
"
```

Results will appear in the JSON file within 60-90 seconds.

---

## Files Modified

- `src/ai/signal_generator.py` - Enhanced `_screen_primary_setups()` with detailed logging & JSON export
- `src/web/server.py` - Added `/api/screening_results` and `/screening` endpoints
- `src/web/templates/screening_results.html` - New HTML page with visual display
- `src/web/templates/dashboard.html` - Added link to screening page
- `data/screening_results.json` - Auto-created, updated on every scan

---

## Next Steps

1. ✅ **Endpoint working** - Can access via HTTP
2. ✅ **Results persisting** - JSON updated on each scan
3. ✅ **Dashboard integrated** - Link on main page
4. → **Monitor over time** - Watch multiple scan cycles to see pattern
5. → **Adjust filters if needed** - Based on what you observe

---

**All changes deployed to VPS and running live!**
