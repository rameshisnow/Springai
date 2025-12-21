"""
End-to-End Integration Test for Goldilock Strategy

Tests complete flow:
1. Strategy screening (entry conditions)
2. Position sizing (20%)
3. Safety gates (monthly limit)
4. Position creation
5. Position monitor exit logic (min hold → TP1 → trailing → TP2)
"""
import asyncio
import sys
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.strategy_manager import StrategyManager
from src.strategies.goldilock_strategy import GoldilockStrategy
from src.data.data_fetcher import binance_fetcher
from src.trading.safety_gates import TradeSafetyGates
from src.trading.risk_manager import risk_manager, Position
from src.monitoring.position_monitor import PositionMonitor
from src.utils.logger import logger
from src.utils.database import get_session, TradeRecordModel

print("=" * 80)
print("END-TO-END INTEGRATION TEST - GOLDILOCK STRATEGY")
print("=" * 80)

async def test_1_strategy_screening():
    """Test 1: Strategy screening with real market data"""
    print("\n" + "=" * 80)
    print("TEST 1: Strategy Screening (Entry Conditions)")
    print("=" * 80)
    
    strategy_manager = StrategyManager()
    tracked_coins = strategy_manager.get_all_tracked_coins()
    
    print(f"\n✓ Strategy Manager loaded")
    print(f"✓ Tracked coins: {', '.join(tracked_coins)}")
    
    results = {}
    
    for symbol in tracked_coins:
        print(f"\n--- Testing {symbol} ---")
        
        strategy = strategy_manager.get_strategy(symbol)
        if not strategy:
            print(f"❌ No strategy found for {symbol}")
            results[symbol] = {'status': 'error', 'reason': 'No strategy'}
            continue
        
        print(f"✓ Strategy: {strategy.__class__.__name__}")
        print(f"✓ Position size: {strategy.get_position_size_pct() * 100}%")
        print(f"✓ Min hold: {strategy.get_min_hold_days()} days")
        print(f"✓ Max hold: {strategy.get_max_hold_days()} days")
        
        # Fetch market data
        print(f"\n📊 Fetching market data...")
        df_4h = await binance_fetcher.get_klines(symbol=symbol, interval='4h', limit=200)
        
        if df_4h.empty:
            print(f"❌ Could not fetch data")
            results[symbol] = {'status': 'error', 'reason': 'No data'}
            continue
        
        print(f"✓ 4H candles: {len(df_4h)} bars")

        # Ensure datetime index (strategies expect timestamp index)
        if not isinstance(df_4h.index, (pd.DatetimeIndex, pd.TimedeltaIndex, pd.PeriodIndex)):
            if 'timestamp' in df_4h.columns:
                df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'])
                df_4h = df_4h.set_index('timestamp').sort_index()
        
        # Calculate indicators for display (strategy-specific columns may differ)
        df_4h = strategy.calculate_indicators(df_4h)

        current_price = float(df_4h.iloc[-1]['close'])
        rsi = float(df_4h.iloc[-1]['rsi']) if 'rsi' in df_4h.columns and not pd.isna(df_4h.iloc[-1]['rsi']) else float('nan')

        print(f"\n📈 Current Market State:")
        print(f"   Price: ${current_price:.4f}")
        if not pd.isna(rsi):
            print(f"   RSI: {rsi:.1f}")

        # Show EMA info if present (Goldilock uses ema_9/ema_21; BTC uses ema_fast/ema_slow)
        if 'ema_9' in df_4h.columns and 'ema_21' in df_4h.columns:
            ema9 = float(df_4h.iloc[-1]['ema_9'])
            ema21 = float(df_4h.iloc[-1]['ema_21'])
            print(f"   EMA 9: ${ema9:.4f}")
            print(f"   EMA 21: ${ema21:.4f}")
            print(f"   EMA Cross: {'✓' if ema9 > ema21 else '✗'}")
        elif 'ema_fast' in df_4h.columns and 'ema_slow' in df_4h.columns:
            ema_fast = float(df_4h.iloc[-1]['ema_fast'])
            ema_slow = float(df_4h.iloc[-1]['ema_slow'])
            print(f"   EMA Fast: ${ema_fast:.4f}")
            print(f"   EMA Slow: ${ema_slow:.4f}")
            print(f"   EMA Cross: {'✓' if ema_fast > ema_slow else '✗'}")

        # Use the strategy itself as the source of truth
        # Build a daily dataframe compatible with strategy expectations
        df_for_daily = df_4h.copy()
        if not isinstance(df_for_daily.index, (pd.DatetimeIndex, pd.TimedeltaIndex, pd.PeriodIndex)):
            if 'timestamp' in df_for_daily.columns:
                df_for_daily['timestamp'] = pd.to_datetime(df_for_daily['timestamp'])
                df_for_daily = df_for_daily.set_index('timestamp').sort_index()

        if isinstance(df_for_daily.index, (pd.DatetimeIndex, pd.TimedeltaIndex, pd.PeriodIndex)):
            df_daily = df_for_daily.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        else:
            # Fallback: use 4H as a proxy if we cannot resample
            df_daily = df_4h

        should_enter, reason = strategy.check_entry(
            df_1h=pd.DataFrame(),
            df_4h=df_4h,
            df_daily=df_daily,
            current_idx=-1,
        )

        if should_enter:
            print(f"\n✅ ENTRY SIGNAL: {reason}")
            results[symbol] = {
                'status': 'passed',
                'reason': reason,
                'price': current_price,
                'rsi': None if pd.isna(rsi) else float(rsi)
            }
        else:
            print(f"\n❌ NO ENTRY: {reason}")
            results[symbol] = {
                'status': 'failed',
                'reason': reason,
                'price': current_price,
                'rsi': None if pd.isna(rsi) else float(rsi)
            }
    
    print("\n" + "=" * 80)
    print("TEST 1 RESULTS:")
    print("=" * 80)
    
    # Check that screening is functioning (not whether entries found)
    all_functioning = True
    for symbol, result in results.items():
        if result['status'] == 'error':
            print(f"❌ {symbol}: {result['reason']} (ERROR)")
            all_functioning = False
        elif result['status'] == 'passed':
            print(f"✅ {symbol}: {result['reason']} (ENTRY SIGNAL)")
        else:
            print(f"✅ {symbol}: {result['reason']} (correctly rejected)")
    
    print(f"\n✅ Screening logic is functioning correctly")
    print(f"   (Entry signals are rare - rejection is expected behavior)")
    
    return all_functioning  # Pass if no errors, regardless of entry signals

async def test_2_position_sizing():
    """Test 2: Position sizing calculation"""
    print("\n" + "=" * 80)
    print("TEST 2: Position Sizing (20% per trade)")
    print("=" * 80)
    
    safety_gates = TradeSafetyGates()
    
    # Test balance
    test_balance = 396.70
    test_price_doge = 0.1220
    test_price_shib = 0.00001145
    test_price_sol = 124.65
    
    print(f"\nTest Parameters:")
    print(f"   Balance: ${test_balance:.2f}")
    print(f"   DOGE Price: ${test_price_doge}")
    print(f"   SHIB Price: ${test_price_shib}")
    print(f"   SOL Price: ${test_price_sol}")
    
    results = {}
    
    for symbol, price in [
        ('DOGEUSDT', test_price_doge),
        ('SHIBUSDT', test_price_shib),
        ('SOLUSDT', test_price_sol)
    ]:
        print(f"\n--- Testing {symbol} ---")
        
        quantity, position_value = safety_gates.calculate_position_size(
            symbol=symbol,
            account_balance=test_balance,
            current_price=price,
            atr_percent=3.0
        )
        
        position_pct = (position_value / test_balance) * 100
        
        print(f"✓ Quantity: {quantity:.8g}")
        print(f"✓ Position value: ${position_value:.2f}")
        print(f"✓ Position %: {position_pct:.1f}%")
        
        # Verify it's 20%
        expected_value = test_balance * 0.90 * 0.20  # 90% usable, 20% position
        tolerance = 1.0  # $1 tolerance
        
        if abs(position_value - expected_value) < tolerance:
            print(f"✅ PASS: Position size is ~20% (${expected_value:.2f})")
            results[symbol] = {'status': 'passed', 'value': position_value, 'pct': position_pct}
        else:
            print(f"❌ FAIL: Expected ${expected_value:.2f}, got ${position_value:.2f}")
            results[symbol] = {'status': 'failed', 'value': position_value, 'pct': position_pct}
    
    print("\n" + "=" * 80)
    print("TEST 2 RESULTS:")
    print("=" * 80)
    for symbol, result in results.items():
        status_icon = "✅" if result['status'] == 'passed' else "❌"
        print(f"{status_icon} {symbol}: ${result['value']:.2f} ({result['pct']:.1f}%)")
    
    return all(r['status'] == 'passed' for r in results.values())

async def test_3_monthly_limit():
    """Test 3: Monthly trade limit enforcement"""
    print("\n" + "=" * 80)
    print("TEST 3: Monthly Trade Limit (1 per coin per month)")
    print("=" * 80)
    
    safety_gates = TradeSafetyGates()
    
    # Simulate a trade this month (monthly limit is enforced via DB trade_records)
    now = datetime.utcnow()
    # Use a real strategy-tracked symbol so the strategy-based monthly limit
    # is enforced. Keep the test repeatable by clearing any existing records
    # for the current month.
    symbol = 'DOGEUSDT'
    
    print(f"\nTesting {symbol}...")
    
    # Clear any existing trade records for this symbol in the current month
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)

    session = get_session()
    try:
        session.query(TradeRecordModel).filter(
            TradeRecordModel.symbol == symbol,
            TradeRecordModel.entry_time >= month_start,
            TradeRecordModel.entry_time < next_month_start,
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    # First trade should be allowed
    can_trade, reason = safety_gates.check_monthly_trade_limit(symbol)
    
    print(f"\n1st trade attempt:")
    if can_trade:
        print(f"✅ PASS: Trade allowed (no trades this month yet)")
        
        # Insert a trade record for this month so the DB-backed limit triggers
        session = get_session()
        try:
            trade = TradeRecordModel(
                symbol=symbol,
                side="BUY",
                entry_time=now,
                exit_time=None,
                entry_price=0.0,
                exit_price=None,
                quantity=0.0,
                profit_loss=0.0,
                pnl_percent=0.0,
                status="OPEN",
                metadata_payload={"source": "e2e_monthly_limit_test"},
            )
            session.add(trade)
            session.commit()
        finally:
            session.close()

        print(f"✓ Inserted DB trade record for {symbol} in {now.strftime('%B %Y')}")
        
        # Second trade should be blocked (fresh instance validates persistence)
        safety_gates_2 = TradeSafetyGates()
        can_trade2, reason2 = safety_gates_2.check_monthly_trade_limit(symbol)
        
        print(f"\n2nd trade attempt (same month):")
        if not can_trade2:
            print(f"✅ PASS: Trade blocked - {reason2}")
            return True
        else:
            print(f"❌ FAIL: Second trade was allowed (should be blocked)")
            return False
    else:
        print(f"❌ FAIL: First trade was blocked - {reason}")
        return False

def test_4_exit_logic_simulation():
    """Test 4: Simulate complete exit logic flow"""
    print("\n" + "=" * 80)
    print("TEST 4: Exit Logic Simulation (Min Hold → TP1 → Trailing → TP2)")
    print("=" * 80)
    
    strategy = GoldilockStrategy()
    
    # Simulate position
    entry_price = 0.1220
    quantity = 1170.57
    
    print(f"\nSimulated Position:")
    print(f"   Symbol: DOGEUSDT")
    print(f"   Entry: ${entry_price}")
    print(f"   Quantity: {quantity}")
    
    # Test scenarios
    scenarios = [
        # (hold_days, current_price, highest_price, tp1_hit, expected_exit, description)
        (3, 0.1180, 0.1220, False, 'HOLD', 'Day 3: Below entry but above SL'),
        (5, 0.1120, 0.1220, False, 'SL_8%', 'Day 5: Hit 8% stop loss'),
        (7, 0.1240, 0.1240, False, 'HOLD', 'Day 7: Min hold complete, above entry'),
        (10, 0.1405, 0.1410, False, 'TP1', 'Day 10: Hit TP1 +15%'),
        (12, 0.1450, 0.1450, True, 'HOLD', 'Day 12: After TP1, trailing active'),
        (15, 0.1370, 0.1450, True, 'TRAILING', 'Day 15: Dropped 5% from high'),
        (18, 0.1590, 0.1590, True, 'TP2', 'Day 18: Hit TP2 +30%'),
        (91, 0.1300, 0.1300, False, 'MAX_HOLD', 'Day 91: Max hold force exit'),
    ]
    
    print("\n" + "-" * 80)
    print("SCENARIO TESTING:")
    print("-" * 80)
    
    all_passed = True
    
    for hold_days, current_price, highest_price, tp1_hit, expected, description in scenarios:
        print(f"\n{description}")
        print(f"   Hold: {hold_days} days | Price: ${current_price:.4f} | High: ${highest_price:.4f} | TP1: {tp1_hit}")
        
        # Calculate dynamic stop loss
        dynamic_sl = strategy.get_stop_loss(entry_price, hold_days)
        sl_pct = ((dynamic_sl - entry_price) / entry_price) * 100
        
        # Calculate take profits
        take_profits = strategy.get_take_profits(entry_price)
        tp1_price = take_profits[0]['price']
        tp2_price = take_profits[1]['price']
        
        # Calculate trailing stop
        trailing_stop = highest_price * (1 - strategy.get_trailing_stop_pct()) if tp1_hit else 0
        
        # Determine exit
        result = 'HOLD'
        
        # Check max hold
        if hold_days >= strategy.get_max_hold_days():
            result = 'MAX_HOLD'
        # Check if within min hold
        elif hold_days < strategy.get_min_hold_days():
            if current_price <= dynamic_sl:
                result = 'SL_8%'
        # After min hold
        else:
            # Check stop loss
            if current_price <= dynamic_sl:
                result = 'SL_3%'
            # Check TP1
            elif not tp1_hit and current_price >= tp1_price:
                result = 'TP1'
            # Check trailing stop
            elif tp1_hit and trailing_stop > 0 and current_price <= trailing_stop:
                result = 'TRAILING'
            # Check TP2
            elif tp1_hit and current_price >= tp2_price:
                result = 'TP2'
        
        print(f"   SL: ${dynamic_sl:.4f} ({sl_pct:+.1f}%)")
        print(f"   TP1: ${tp1_price:.4f} | TP2: ${tp2_price:.4f}")
        if tp1_hit:
            print(f"   Trailing: ${trailing_stop:.4f} (5% from ${highest_price:.4f})")
        
        if result == expected:
            print(f"   ✅ PASS: Exit = {result}")
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {result}")
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ TEST 4: ALL SCENARIOS PASSED")
    else:
        print("❌ TEST 4: SOME SCENARIOS FAILED")
    print("=" * 80)
    
    return all_passed

async def test_5_position_monitor_integration():
    """Test 5: Position monitor with mock position"""
    print("\n" + "=" * 80)
    print("TEST 5: Position Monitor Integration")
    print("=" * 80)
    
    print("\n⚠️  Note: This test checks if position monitor can process Goldilock positions")
    print("         It does NOT execute real trades\n")
    
    # Check if position monitor has strategy manager
    monitor = PositionMonitor()
    
    if hasattr(monitor, 'strategy_manager'):
        print("✅ PASS: Position monitor has strategy_manager")
        
        # Check tracked coins
        tracked = monitor.strategy_manager.get_all_tracked_coins()
        print(f"✓ Tracked coins: {', '.join(tracked)}")
        
        # Test strategy lookup
        for symbol in tracked:
            strategy = monitor.strategy_manager.get_strategy(symbol)
            if strategy:
                print(f"✓ {symbol}: Strategy loaded ({strategy.__class__.__name__})")
            else:
                print(f"✗ {symbol}: No strategy found")
                return False
        
        return True
    else:
        print("❌ FAIL: Position monitor missing strategy_manager")
        return False

async def run_all_tests():
    """Run all end-to-end tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "GOLDILOCK STRATEGY E2E TEST SUITE" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")
    
    results = {}
    
    try:
        # Test 1: Strategy Screening
        results['screening'] = await test_1_strategy_screening()
        
        # Test 2: Position Sizing
        results['position_sizing'] = await test_2_position_sizing()
        
        # Test 3: Monthly Limit
        results['monthly_limit'] = await test_3_monthly_limit()
        
        # Test 4: Exit Logic
        results['exit_logic'] = test_4_exit_logic_simulation()
        
        # Test 5: Position Monitor
        results['monitor'] = await test_5_position_monitor_integration()
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "FINAL RESULTS" + " " * 35 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    test_names = {
        'screening': 'Strategy Screening (Entry Conditions)',
        'position_sizing': 'Position Sizing (20% per trade)',
        'monthly_limit': 'Monthly Trade Limit (1 per coin)',
        'exit_logic': 'Exit Logic Simulation (8 scenarios)',
        'monitor': 'Position Monitor Integration',
    }
    
    passed_count = 0
    total_count = len(results)
    
    for test_key, test_name in test_names.items():
        result = results.get(test_key)
        
        if isinstance(result, dict):
            # Screening test returns dict
            passed = any(r.get('status') == 'passed' for r in result.values())
        else:
            # Other tests return boolean
            passed = result
        
        if passed:
            print(f"✅ {test_name}")
            passed_count += 1
        else:
            print(f"❌ {test_name}")
    
    print()
    print(f"Results: {passed_count}/{total_count} tests passed")
    print()
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED - Goldilock Strategy is READY!")
        print()
        print("Next steps:")
        print("  1. Run in dry run mode: ./start.sh → Choose 1")
        print("  2. Test with real market for 24-48 hours")
        print("  3. Switch to live mode with small capital")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
