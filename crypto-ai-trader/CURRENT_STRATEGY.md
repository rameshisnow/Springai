# Current Trading Strategy - Full Technical Specification

**Last Updated:** December 17, 2025  
**Status:** PRODUCTION (Live Trading)  
**Assessment:** NO STATISTICAL EDGE (Backtest Sharpe -1.65 after fees)

---

## 📊 CURRENT FILTERING STRATEGY

### **Tier 1: Market Watch (Lightweight Screening)**

**Purpose:** Filter top coins to pass to Claude AI for detailed analysis

**Input:** Top 200 coins by trading volume (USDT pairs)  
**Output:** 8 qualified candidates for Claude analysis

---

## 🔍 TIER 1 PRIMARY FILTERS

All of these must pass to qualify:

### 1. **EMA Trend Filter**
```
Requirement: 1H Price > EMA9 > EMA21 AND 4H Price > EMA21
Current Setting: EMA 9-period fast, 21-period slow
Logic: Only uptrends allowed
Status: ACTIVE
```

### 2. **RSI Momentum Filter**
```
Requirement: RSI between 55-70 on BOTH 1H and 4H
Current Setting: MIN=55, MAX=70
Logic: Avoid overbought, avoid oversold
Status: ACTIVE
```

### 3. **Breakout Filter**
```
Requirement: 1H close above EITHER 20-bar high OR 50-bar high
Current Setting: SCREEN_BREAKOUT_WINDOW=50 bars
Logic: Price momentum + new highs (entry signal)
Status: ACTIVE
```

### 4. **BTC Relative Strength Filter**
```
Requirement: Coin % change > BTC % change on BOTH 1H and 4H
Current Setting: Must outperform BTC
Logic: Only trade coins with stronger momentum than Bitcoin
Status: ACTIVE
```

---

## 📈 TIER 2: AI ANALYSIS (Claude Decision)

Once 8 coins pass Tier 1, they go to Claude for:

- Full technical analysis (MACD, Bollinger Bands, etc.)
- Market regime detection (trending vs range-bound)
- Momentum confirmation
- Risk/reward assessment
- Final buy/sell recommendation

**AI Model:** Claude 3.5 Haiku (cost optimized)

---

## 💰 TIER 3: EXECUTION GATES

### Position Management
```
MAX_OPEN_POSITIONS = 2          # Max 2 simultaneous trades
MAX_TRADES_PER_24H = 4          # Max 4 trades per day
COIN_COOLDOWN_HOURS = 4         # Wait 4H before re-entering same coin
```

### Entry Rules
```
STOP_LOSS_PERCENT = 3.0%        # Hard stop at -3%
TAKE_PROFIT_LEVELS:
  - TP1: +3% (exit 33%)
  - TP2: +5% (exit 33%)
  - TP3: +8% (exit 34%)
MAX_HOLD_HOURS = 4              # Exit after 4 hours max
```

### Risk Management
```
MAX_RISK_PER_DAY_PERCENT = 4.0%        # Circuit breaker at -4% daily loss
MAX_DRAWDOWN_PERCENT = 15%              # Circuit breaker at -15% max DD
REENTRY_COOLDOWN_MINUTES = 90           # Wait 90min after loss
```

---

## ⚠️ WHY THIS STRATEGY FAILS

### **Problem 1: Weak Entry Filters**
```
Current filters pass 1,964 trades over 2 years
Of those: 46.3% are winners, 53.7% are losers
Result: Coin flip with fees = NEGATIVE EXPECTANCY
```

### **Problem 2: Entry Lacks Conviction**
- EMA 9/21: Too fast, whipsaws in choppy markets
- RSI 55-70: Too wide, let's in weak signals
- Breakout alone: No quality confirmation
- BTC strength: Only relative, not absolute

### **Problem 3: Fees Destroy Profits**
```
Gross return over 2 years: +24.21%
Trading fees (1,963 trades × 0.2%): -392.60%
NET RESULT: -390.89% ❌
```

### **Problem 4: Exit Strategy Fails**
```
- 46% of trades hit stop loss (expected)
- 19% time exit (4H max hold is too short)
- Only 14% hit target 1 (+3%)
- Avg return per trade: -0.199% (losing money!)
```

---

## 📋 PARAMETER SUMMARY TABLE

| Parameter | Current Value | Purpose | Status |
|-----------|---|---------|--------|
| **SCREEN_TOP_N** | 200 | Initial coin pool | ✅ Active |
| **SCREEN_MAX_CANDIDATES** | 8 | Coins to Claude | ✅ Active |
| **SCREEN_BREAKOUT_WINDOW** | 50 | Bars for breakout high | ✅ Active |
| **SCREEN_RSI_MIN** | 55 | RSI lower bound | ✅ Active |
| **SCREEN_RSI_MAX** | 70 | RSI upper bound | ✅ Active |
| **EMA_FAST** | 9 | Fast EMA | ✅ Active |
| **EMA_SLOW** | 21 | Slow EMA | ✅ Active |
| **ATR_VOLATILITY_CUTOFF** | 3.5% | Max volatility allowed | ⚠️ No effect |
| **MIN_RELATIVE_VOLUME** | 1.5x | Volume multiplier | ⚠️ No effect |
| **STOP_LOSS_PERCENT** | 3.0% | Hard stop | ✅ Working |
| **MAX_HOLD_HOURS** | 4 | Time exit | ❌ Too aggressive |
| **COIN_COOLDOWN_HOURS** | 4 | Reentry wait | ✅ Working |

---

## 🔴 CRITICAL ISSUES

### Issue 1: No R/R Filter
```
Current: Any setup with -3% stop and +3% target is allowed
Problem: Fees make 1:1 R/R negative expectancy
Missing: Minimum 2:1 R/R requirement at entry
```

### Issue 2: Fixed Position Sizing
```
Current: Always risk 3% stop loss
Problem: Doesn't scale with volatility or Kelly Criterion
Missing: Position size = Risk / (ATR × Entry Price)
```

### Issue 3: Poor Exit Strategy
```
Current: 4H time exit, fixed targets
Problems:
  - 73.5% of trades exit on time (not targets)
  - No trailing stops (let winners run)
  - No scale-out (capture partial gains)
Missing: ATR-based trailing stops, scale-out at 2%
```

### Issue 4: No Market Regime Detection
```
Current: Same filters for bull/bear/sideways
Problem: EMA 9/21 works in trends, fails in chop
Missing: Detect regime, adapt EMA settings
```

---

## 💡 RECOMMENDATIONS (In Priority Order)

### Phase 1: IMMEDIATE
✅ **PAUSE live trading** - Strategy has negative edge after fees  
✅ **Document current performance** - Validate backtest findings vs live results  
✅ **Archive this configuration** - Before making any changes

### Phase 2: RESEARCH
1. **Add R/R filter** - Reject entries with <2:1 risk/reward
2. **Improve position sizing** - Use Kelly Criterion or volatility-adjusted
3. **Fix exit strategy** - ATR trailing stops + scale-out
4. **Extend hold time** - 12H instead of 4H max hold

### Phase 3: VALIDATION
- **Backtest improvements** - Run 2-year test with fixes
- **Paper trade** - 2 weeks live simulation before deploying
- **Only deploy if Sharpe > 1.5** after fees

---

## 📁 Key Configuration Files

```
src/config/constants.py          # All parameters above
src/ai/signal_generator.py       # Tier 1 & 2 logic (lines 247-450)
src/trading/order_manager.py     # Tier 3 execution
src/trading/risk_manager.py      # Position sizing
src/trading/safety_gates.py      # Circuit breakers
```

---

## 🎯 Next Steps

**Starting fresh means:**
1. Understand what's currently deployed ✅ (done - this doc)
2. Measure live performance vs backtest (next)
3. Identify root causes of poor performance (next)
4. Design improvements with evidence (next)
5. Validate improvements before deploying (final)

Would you like to:
- A) Run 2-week live performance audit?
- B) Test specific improvements in backtest first?
- C) Analyze individual trade examples from live trading?
- D) Something else?
