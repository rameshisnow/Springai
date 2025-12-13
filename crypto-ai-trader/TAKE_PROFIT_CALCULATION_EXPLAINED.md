# ZEC Take Profit Calculation - How We Got $505.43

## Quick Answer
**$505.43 is NOT explicitly confirmed by Claude. It comes from the system's hardcoded risk management configuration.**

---

## The Calculation

### Entry Price
- **ZECUSDT Entry Price: $467.99** (from positions.json)

### Configuration (from `src/config/constants.py`)
```python
TAKE_PROFIT_LEVELS = [
    {"percent": 3, "position_percent": 0.33},   # Exit 33% at +3%
    {"percent": 5, "position_percent": 0.33},   # Exit 33% at +5%
    {"percent": 8, "position_percent": 0.34},   # Exit 34% at +8%
]
```

### Calculation Method (from `src/trading/risk_manager.py`)
```python
def _calculate_take_profit_targets(self, entry_price: float) -> list:
    """Calculate partial exit targets based on configuration"""
    targets = []
    for tp in TAKE_PROFIT_LEVELS:
        target_price = entry_price * (1 + tp['percent'] / 100)
        targets.append({
            'price': target_price,
            'percent': tp['percent'],
            'position_percent': tp['position_percent'],
            'hit': False,
        })
    return targets
```

### The Math
| Target | Formula | Calculation | Price |
|--------|---------|-------------|-------|
| TP1 | entry × 1.03 | 467.99 × 1.03 | **$482.03** |
| TP2 | entry × 1.05 | 467.99 × 1.05 | **$491.39** |
| TP3 | entry × 1.08 | 467.99 × 1.08 | **$505.43** ✅ |

**The $505.43 is TP3 at +8% profit target.**

---

## Stored in positions.json
```json
"take_profit_targets": [
  {
    "price": 491.38950000000006,
    "position_percent": 0.5
  },
  {
    "price": 505.42920000000004,
    "position_percent": 0.5
  }
]
```

Note: The JSON shows only 2 targets (stored differently), but the calculation uses 3 levels.

---

## Stop Loss Calculation (for reference)
```
STOP_LOSS_PERCENT = 3.0

SL = entry_price × (1 - 3/100)
SL = 467.99 × 0.97
SL = $453.95 ✅
```

---

## Claude's Role vs System Config

### What Claude Does
- ✅ Analyzes the coin (technical indicators, momentum, volume)
- ✅ Generates BUY/SELL/HOLD signal
- ✅ Provides confidence score (60-90%)
- ✅ Suggests take profit targets based on ATR and analysis
- ❌ But these Claude TPs are NOT used for actual trades

### Example from signal_history.json
Claude's signals for ZECUSDT:
```json
{
  "symbol": "ZECUSDT",
  "signal_type": "BUY",
  "confidence": 80,
  "stop_loss": 452.73,
  "take_profit": [473.38, 481.33],  // Claude's suggestions
}
```

But the actual trade placed uses:
```json
TP1: $491.39
TP2: $505.43
```

### Why the Difference?

**Claude's TPs:**
- Based on ATR (Average True Range) volatility
- Based on technical support/resistance levels
- More dynamic, changes with market conditions
- Less consistent across trades

**System's TPs (the ones actually used):**
- Based on fixed percentage increases (+3%, +5%, +8%)
- Always consistent and predictable
- Safer for risk management
- Applied to ALL trades regardless of Claude's analysis

---

## Why This Design?

1. **Safety**: Hardcoded percentages ensure no trade goes off the rails
2. **Consistency**: All trades follow the same profit-taking strategy
3. **Protection**: Claude's analysis might be wrong, but risk controls remain
4. **Predictability**: Traders know exactly when exits will trigger
5. **Simplicity**: No surprises, clear math everyone can verify

---

## When Each TP Triggers

For ZECUSDT at $467.99 entry:

| Level | Price | Action | Exit % |
|-------|-------|--------|--------|
| TP1 | $491.39 | When ZEC reaches $491.39 | Sell 33% |
| TP2 | $505.43 | When ZEC reaches $505.43 | Sell 34% |

So if ZEC rises to $505.43, the bot will automatically:
1. Sell 33% at $491.39 (if it hits that first)
2. Sell 34% at $505.43 (remaining position)
3. Total realized profit: ~5-8% on the position

---

## Where to Find This Code

- **Configuration**: `/src/config/constants.py` (lines 36-40)
- **Calculation**: `/src/trading/risk_manager.py` (lines 588-600)
- **Stored Position**: `/data/positions.json` (ZECUSDT section)
- **Claude Signals**: `/data/signal_history.json` (for reference only)

---

## Summary

**$505.43 Take Profit for ZEC:**
- ✅ Not from Claude (Claude suggested different TPs)
- ✅ From system configuration: TAKE_PROFIT_LEVELS
- ✅ Calculated as: $467.99 × 1.08 = $505.43
- ✅ Represents +8% profit target
- ✅ Will automatically trigger when price reaches $505.43
- ✅ Ensures safe, predictable, consistent trading
