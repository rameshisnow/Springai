"""
Test Goldilock Strategy Integration

This tests the strategy system without modifying the main codebase yet.
"""
import sys
import asyncio
import pandas as pd
from datetime import datetime

sys.path.append('/Users/rameshrajasekaran/Springai/crypto-ai-trader')

from src.strategies.strategy_manager import StrategyManager
from src.data.data_fetcher import binance_fetcher
from src.utils.indicators import compute_all_indicators


async def test_goldilock_strategy():
    """Test the Goldilock strategy on DOGE"""
    
    print("\n" + "=" * 80)
    print("GOLDILOCK STRATEGY TEST")
    print("=" * 80)
    
    # Initialize strategy manager
    strategy_manager = StrategyManager()
    
    # Get tracked coins
    tracked_coins = strategy_manager.get_all_tracked_coins()
    print(f"\nTracked coins: {tracked_coins}")
    
    # Test DOGEUSDT
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    if not strategy:
        print(f"❌ No strategy found for {symbol}")
        return
    
    print(f"\n✅ Strategy found: {strategy.name}")
    print(f"   Position size: {strategy.get_position_size_pct() * 100}%")
    print(f"   Min hold: {strategy.get_min_hold_days()} days")
    print(f"   Max hold: {strategy.get_max_hold_days()} days")
    
    # Fetch market data
    print(f"\n📊 Fetching market data for {symbol}...")
    df_1h = await binance_fetcher.get_klines(symbol=symbol, interval='1h', limit=200)
    df_4h = await binance_fetcher.get_klines(symbol=symbol, interval='4h', limit=200)
    
    # Ensure datetime index for all dataframes
    if not isinstance(df_1h.index, pd.DatetimeIndex):
        df_1h.index = pd.to_datetime(df_1h.index)
    if not isinstance(df_4h.index, pd.DatetimeIndex):
        df_4h.index = pd.to_datetime(df_4h.index)
    
    # Resample 1H to daily
    df_daily = df_1h.resample('1D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    print(f"   1H bars: {len(df_1h)}")
    print(f"   4H bars: {len(df_4h)}")
    print(f"   Daily bars: {len(df_daily)}")
    
    # Compute indicators
    df_1h = compute_all_indicators(df_1h)
    df_4h = compute_all_indicators(df_4h)
    
    # Check entry on current bar
    current_idx = len(df_4h) - 1
    should_enter, reason = strategy.check_entry(df_1h, df_4h, df_daily, current_idx)
    
    print(f"\n🎯 Entry Check Result:")
    print(f"   Should Enter: {'✅ YES' if should_enter else '❌ NO'}")
    print(f"   Reason: {reason}")
    
    # Show current price and levels
    current_price = df_4h['close'].iloc[-1]
    print(f"\n💰 Current Price: ${current_price:.6f}")
    
    if should_enter:
        # Show entry levels
        stop_loss = strategy.get_stop_loss(current_price, hold_days=0)
        take_profits = strategy.get_take_profits(current_price)
        
        print(f"\n📈 Entry Levels (if entered now):")
        print(f"   Entry: ${current_price:.6f}")
        print(f"   Stop Loss (Day 0-6): ${stop_loss:.6f} (-{((current_price - stop_loss) / current_price) * 100:.1f}%)")
        
        stop_loss_7d = strategy.get_stop_loss(current_price, hold_days=7)
        print(f"   Stop Loss (Day 7+): ${stop_loss_7d:.6f} (-{((current_price - stop_loss_7d) / current_price) * 100:.1f}%)")
        
        for i, tp in enumerate(take_profits, 1):
            pct_gain = ((tp['price'] - current_price) / current_price) * 100
            print(f"   TP{i}: ${tp['price']:.6f} (+{pct_gain:.1f}%) - Close {tp['size_pct'] * 100:.0f}%")
        
        trailing_pct = strategy.get_trailing_stop_pct()
        print(f"   Trailing Stop (after TP1): {trailing_pct * 100}% from highest")
    
    # Test monthly limit
    can_trade = strategy.can_trade_this_month(datetime.now(), symbol)
    print(f"\n📅 Monthly Limit Check: {'✅ CAN TRADE' if can_trade else '❌ LIMIT REACHED'}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_goldilock_strategy())
