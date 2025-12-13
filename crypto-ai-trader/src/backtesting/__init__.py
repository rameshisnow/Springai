"""
Backtesting module for Oracle Mode validation

Uses Proxy Backtest + Decision Replay methodology since:
- Claude is non-deterministic
- Cannot call Claude on 1000s of historical candles
- LLMs don't reproduce identical reasoning

Strategy:
1. Backtest risk engine + filters (deterministic)
2. Simulate Oracle decisions via composite scoring (proxy)
3. Build confidence calibration curve (live trades)
"""
