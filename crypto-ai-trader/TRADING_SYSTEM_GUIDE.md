# SpringAI Trading System - Complete Guide

## 🔐 Login Issue Fix

**Problem:** Button was outside form tag, so submit wasn't working.  
**Fixed:** Button now inside `<form>` tag.

**Login:**
- Open: http://localhost:8080
- Passcode: **232307**
- Just type the numbers, they'll fill in automatically

---

## 📊 Dashboard Display

### What You'll See:

#### 1. **Top Metrics Cards**
```
┌─────────────────────────────────────────────────────────────┐
│ Total Balance    │ Active Trades   │ AI Signals (24h) │ Mode  │
│ $1,000.00        │ 0 open          │ 15 signals       │ 🔍    │
│ +0.00%           │ 0 positions     │ 5 high conf      │ MONITOR│
└─────────────────────────────────────────────────────────────┘
```

#### 2. **Recent AI Signals Table**
```
Symbol   | Signal | Confidence | Price    | Stop Loss | Take Profit      | Rationale
---------|--------|------------|----------|-----------|------------------|------------------
BTCUSDT  | BUY    | 78%       | $42,150  | $40,886   | [43.5K, 45K]    | RSI oversold, EMA cross
ETHUSDT  | HOLD   | 45%       | $2,240   | N/A       | N/A             | Low volume, wait
SOLUSDT  | BUY    | 82%       | $98.50   | $95.65    | [102, 105, 110] | Strong momentum
```

#### 3. **Active Trades** (when live mode enabled)
```
Symbol   | Entry  | Current | P&L    | Stop Loss | Take Profit | Status
---------|--------|---------|--------|-----------|-------------|--------
BTCUSDT  | 41,000 | 42,150  | +$34.5 | 39,780    | 42,230     | ACTIVE
```

#### 4. **Closed Trades History**
```
Symbol   | Entry  | Exit   | P&L     | Duration | Exit Reason
---------|--------|--------|---------|----------|-------------
ETHUSDT  | 2,200  | 2,266  | +$19.80 | 2h 15m  | TP HIT
SOLUSDT  | 95.00  | 92.15  | -$8.55  | 45m     | SL HIT
```

#### 5. **Signal Statistics**
```
Total Signals: 24
├─ BUY:  8 (33%)
├─ SELL: 2 (8%)
└─ HOLD: 14 (59%)

High Confidence (≥70%): 5 signals
Average Confidence: 62.3%
```

---

## 🤖 Automated Trading Flow

### **When Active Mode is Enabled:**

```
┌─────────────────────────────────────────────────────────────────┐
│                   TRADING CYCLE (Every 30 minutes)               │
└─────────────────────────────────────────────────────────────────┘

1️⃣ DATA COLLECTION (2-3 seconds)
   ├─ Fetch top 10 coins by 24h volume
   ├─ Get 100 candles of 1h OHLCV data
   └─ Calculate: RSI, EMA, ATR, MACD, momentum, volume spike

2️⃣ AI SIGNAL GENERATION (5-10 seconds)
   ├─ Send data to Claude with structured prompt
   ├─ Receive: BUY/SELL/HOLD + confidence + stop/profit levels
   └─ Example Response:
      {
        "signal": "BUY",
        "confidence": 78,
        "stop_loss": 40886,
        "take_profit": [43500, 45000, 47000],
        "rationale": "Price broke above EMA200, RSI oversold recovery"
      }

3️⃣ RISK VALIDATION (1 second)
   ├─ Confidence ≥ 70%? ✓
   ├─ Max 3 positions? ✓
   ├─ Not in circuit breaker? ✓
   ├─ Sufficient capital? ✓
   └─ Daily loss limit OK? ✓

4️⃣ ORDER PLACEMENT (2-3 seconds)
   ├─ Calculate position size: 2% of capital = $20
   ├─ BTCUSDT @ $42,150 → Buy 0.000474 BTC
   ├─ Place MARKET BUY order
   ├─ Confirm execution
   └─ Place protective orders:
       ├─ STOP LOSS @ $40,886 (-3%)
       └─ TAKE PROFIT orders @ $43,500, $45,000, $47,000

5️⃣ POSITION TRACKING (Continuous)
   ├─ Monitor price every 60 seconds
   ├─ Check if SL/TP hit
   ├─ Update trailing stop (if price rises)
   └─ Log P&L changes

6️⃣ EXIT EXECUTION (Automatic)
   ├─ Scenario A: Price hits $43,500 → Sell 33% (lock +$4.68 profit)
   ├─ Scenario B: Price hits $40,886 → Sell 100% (loss -$0.60)
   ├─ Scenario C: Trailing stop hit → Sell 100% (lock profit)
   └─ Log trade, update balance, send Telegram alert
```

---

## 💰 Sample Trading Scenarios

### **Scenario 1: Successful Trade (TP Hit)**

```
Initial Setup:
- Balance: $1,000
- Risk per trade: 2% = $20
- Signal: BUY BTCUSDT @ $42,000, Confidence: 82%

Order Placement:
- Entry: $42,000
- Position size: $20 ÷ $42,000 = 0.000476 BTC
- Stop loss: $40,740 (-3%)
- Take profits: $43,260 (+3%), $44,100 (+5%), $45,360 (+8%)

Timeline:
00:00 → BUY 0.000476 BTC @ $42,000 (cost: $20.00)
00:45 → Price: $42,800 (unrealized P&L: +$0.38)
01:30 → Price: $43,260 → TP1 HIT → Sell 33% = 0.000157 BTC
        ├─ Realized profit: +$0.20
        └─ Remaining: 0.000319 BTC
02:15 → Price: $44,100 → TP2 HIT → Sell 33% = 0.000157 BTC
        ├─ Realized profit: +$0.33
        └─ Remaining: 0.000162 BTC
03:00 → Price: $45,360 → TP3 HIT → Sell 34% = 0.000162 BTC
        └─ Realized profit: +$0.54

Total Profit: $1.07 (+5.35% on $20 position)
New Balance: $1,001.07
```

### **Scenario 2: Stop Loss Hit**

```
Initial Setup:
- Balance: $1,000
- Signal: BUY ETHUSDT @ $2,200, Confidence: 75%

Order Placement:
- Entry: $2,200
- Position size: $20 ÷ $2,200 = 0.00909 ETH
- Stop loss: $2,134 (-3%)

Timeline:
00:00 → BUY 0.00909 ETH @ $2,200 (cost: $20.00)
00:20 → Price: $2,180 (unrealized P&L: -$0.18)
00:45 → Price: $2,134 → STOP LOSS HIT → Sell 100%
        └─ Realized loss: -$0.60

Total Loss: -$0.60 (-3% on $20 position)
New Balance: $999.40
```

### **Scenario 3: Prediction Close But Not Hit**

```
Signal: BUY SOLUSDT @ $100
- Target: $105 (+5%)
- Stop loss: $97 (-3%)

Actual Movement:
00:00 → Entry @ $100
01:00 → Price: $103.50 (+3.5%, not hit TP of +5%)
02:00 → Price: $104.20 (+4.2%, still below TP)
02:30 → Price starts dropping: $103.80
03:00 → Price: $102.50 (+2.5%)

Bot Response:
├─ Trailing Stop Activated (when price was $104.20)
│   └─ Set trailing stop @ $102.11 (2% below peak)
└─ Price hits $102.11 → EXIT
    └─ Profit: $2.11 (+2.11% instead of target +5%)

Outcome: Didn't hit TP target, but trailing stop locked in profit!
```

---

## 🎯 Position Management Rules

### **Maximum Positions**
```
Max Concurrent: 3 positions
Example:
├─ Position 1: BTCUSDT ($20)
├─ Position 2: ETHUSDT ($20)
└─ Position 3: SOLUSDT ($20)

Total Exposure: $60 (6% of capital)

When 3 positions active:
└─ New signals → Logged but NOT executed
    └─ Wait for position to close before opening new one
```

### **Circuit Breaker System**
```
Triggers:
├─ 3 consecutive losses → PAUSE 24 hours
├─ Daily loss > $100 → STOP trading
└─ Drawdown > 15% → STOP all trades

Recovery:
└─ Automatic resume after 24 hours
```

### **Partial Exit Strategy**
```
Position: $20 in BTCUSDT

Take Profit Levels:
├─ TP1 @ +3%: Exit 33% → Lock $0.20
├─ TP2 @ +5%: Exit 33% → Lock $0.33
└─ TP3 @ +8%: Exit 34% → Lock $0.54

Total Potential: $1.07 (+5.35%)

Benefits:
├─ Reduce risk after first profit
├─ Capture gains incrementally
└─ Let winners run for maximum profit
```

---

## 🔄 Real-Time Order Tracking

### **Active Order Dashboard**

```
┌────────────────────────────────────────────────────────────────┐
│ BTCUSDT - LONG Position                                        │
├────────────────────────────────────────────────────────────────┤
│ Entry: $42,000 @ 00:15:32                                     │
│ Current: $43,200 (+2.86%)                                     │
│ Unrealized P&L: +$0.57                                        │
│                                                                │
│ Orders:                                                        │
│  🔴 Stop Loss: $40,740 (-3.0%)                                │
│  🟢 TP1: $43,260 (+3%) - Pending (97% filled)                │
│  🟢 TP2: $44,100 (+5%) - Pending                             │
│  🟢 TP3: $45,360 (+8%) - Pending                             │
│                                                                │
│ Trailing Stop: Active @ $42,336 (highest: $43,200)           │
│ Duration: 2h 14m                                              │
└────────────────────────────────────────────────────────────────┘
```

### **Order State Machine**

```
PENDING → OPEN → [PARTIAL_FILLED] → CLOSED
          ↓
          ↓ (if SL hit)
          ↓
       CANCELLED
```

---

## 🎛️ Enable Live Trading

**Current State:** MONITORING MODE (safe, no real trades)

**To Enable Live Trading:**

1. Update `src/config/constants.py`:
```python
MONITORING_ONLY = False  # Change from True
DRY_RUN_ENABLED = False  # Change from True
```

2. **Important:** Start with Testnet first:
```python
BINANCE_TESTNET = True  # in .env file
```

3. Get Binance API key with **Spot Trading** permissions

4. Restart the signal generator:
```bash
python -m src.ai.signal_generator
```

**Bot will then:**
- ✅ Generate signals every 30 minutes
- ✅ Execute real orders automatically
- ✅ Manage stop-loss/take-profit
- ✅ Send Telegram alerts for all trades
- ✅ Track P&L in real-time
- ✅ Stop if circuit breaker triggers

---

## 📈 Risk Management Summary

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Capital | $1,000 | Starting amount |
| Risk/Trade | 2% = $20 | Max loss per position |
| Max Positions | 3 | Diversification |
| Stop Loss | 3% | Hard exit |
| Take Profits | 3%, 5%, 8% | Graduated exits |
| Daily Loss Limit | $100 (10%) | Daily cap |
| Max Drawdown | 15% | Portfolio protection |
| Circuit Breaker | 3 losses in row | Automatic pause |

**Expected Performance:**
- Win Rate Target: 60%+
- Avg Win: ~4-5%
- Avg Loss: ~3%
- Profit Factor: >1.5
- Daily Trades: 2-4 (30min intervals, max 3 concurrent)

---

## 🚀 Quick Start Checklist

- [x] Claude API working (model: claude-3-opus-20240229)
- [x] Dashboard password: 232307
- [x] Monitoring mode active (safe)
- [x] Order system ready
- [ ] Start signal generator
- [ ] Monitor for 24 hours
- [ ] Review signal quality
- [ ] Enable live mode (when ready)

**Dashboard is now fixed and ready at http://localhost:8080!**
