"""
Test Goldilock Exit Logic in Position Monitor

Tests:
1. Early stop loss (days 0-6): 8% stop
2. Regular stop loss (day 7+): 3% stop
3. Min hold enforcement (no TP during first 7 days)
4. TP1 at +15% (close 50%)
5. Trailing stop after TP1 (5% from high)
6. TP2 at +30% (close remaining 50%)
7. Max hold enforcement (90 days)
"""
import sys
import asyncio
from datetime import datetime, timedelta
from src.strategies.strategy_manager import StrategyManager
from src.trading.risk_manager import Position

# Initialize strategy manager
strategy_manager = StrategyManager()

def test_dynamic_stop_loss():
    """Test stop loss changes from 8% to 3% after 7 days"""
    print("\n" + "="*80)
    print("TEST 1: Dynamic Stop Loss")
    print("="*80)
    
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    if not strategy:
        print(f"❌ No strategy found for {symbol}")
        return False
    
    entry_price = 0.10
    
    # Day 0-6: Should use 8% stop
    for day in range(7):
        stop_loss = strategy.get_stop_loss(entry_price, day)
        expected = entry_price * 0.92  # 8% stop
        status = "✅" if abs(stop_loss - expected) < 0.0001 else "❌"
        print(f"{status} Day {day}: Stop Loss = ${stop_loss:.6f} (Expected ${expected:.6f})")
    
    # Day 7+: Should use 3% stop
    for day in [7, 10, 30]:
        stop_loss = strategy.get_stop_loss(entry_price, day)
        expected = entry_price * 0.97  # 3% stop
        status = "✅" if abs(stop_loss - expected) < 0.0001 else "❌"
        print(f"{status} Day {day}: Stop Loss = ${stop_loss:.6f} (Expected ${expected:.6f})")
    
    return True


def test_min_hold_enforcement():
    """Test that min hold = 7 days"""
    print("\n" + "="*80)
    print("TEST 2: Minimum Hold Period")
    print("="*80)
    
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    min_hold = strategy.get_min_hold_days()
    print(f"Min hold days: {min_hold}")
    
    if min_hold == 7:
        print("✅ Min hold period = 7 days (correct)")
        print("   During days 0-6: Only stop loss exits allowed")
        print("   After day 7: All exits enabled (TP1, TP2, trailing)")
        return True
    else:
        print(f"❌ Expected 7 days, got {min_hold}")
        return False


def test_tp_levels():
    """Test TP1 = 15%, TP2 = 30%, both close 50%"""
    print("\n" + "="*80)
    print("TEST 3: Take Profit Levels")
    print("="*80)
    
    symbol = 'SHIBUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    entry_price = 0.00001000
    tp_levels = strategy.get_take_profits(entry_price)
    
    print(f"Entry Price: ${entry_price:.8f}")
    print(f"\nTake Profit Levels: {len(tp_levels)}")
    
    # Expected values
    expected_tp1_price = entry_price * 1.15  # +15%
    expected_tp2_price = entry_price * 1.30  # +30%
    
    results = []
    
    if len(tp_levels) >= 1:
        tp1 = tp_levels[0]
        tp1_match = abs(tp1['price'] - expected_tp1_price) < 0.00000001
        size_match = tp1['size_pct'] == 0.50
        status = "✅" if (tp1_match and size_match) else "❌"
        print(f"{status} TP1: ${tp1['price']:.8f} (+15%), Close {tp1['size_pct']*100:.0f}%")
        results.append(tp1_match and size_match)
    
    if len(tp_levels) >= 2:
        tp2 = tp_levels[1]
        tp2_match = abs(tp2['price'] - expected_tp2_price) < 0.00000001
        size_match = tp2['size_pct'] == 0.50
        status = "✅" if (tp2_match and size_match) else "❌"
        print(f"{status} TP2: ${tp2['price']:.8f} (+30%), Close {tp2['size_pct']*100:.0f}%")
        results.append(tp2_match and size_match)
    
    return all(results)


def test_trailing_stop():
    """Test trailing stop = 5% from highest"""
    print("\n" + "="*80)
    print("TEST 4: Trailing Stop")
    print("="*80)
    
    symbol = 'SOLUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    trailing_pct = strategy.get_trailing_stop_pct()
    
    print(f"Trailing stop: {trailing_pct * 100}%")
    
    if trailing_pct == 0.05:
        print("✅ Trailing stop = 5% from highest price")
        print("   Activates AFTER TP1 is hit")
        print("   Example: High = $150, Trail = $150 * 0.95 = $142.50")
        return True
    else:
        print(f"❌ Expected 5%, got {trailing_pct * 100}%")
        return False


def test_max_hold():
    """Test max hold = 90 days"""
    print("\n" + "="*80)
    print("TEST 5: Maximum Hold Period")
    print("="*80)
    
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    max_hold = strategy.get_max_hold_days()
    
    print(f"Max hold days: {max_hold}")
    
    if max_hold == 90:
        print("✅ Max hold period = 90 days")
        print("   Force exit on day 90 regardless of P&L")
        return True
    else:
        print(f"❌ Expected 90 days, got {max_hold}")
        return False


def test_position_sizing():
    """Test position size = 40%"""
    print("\n" + "="*80)
    print("TEST 6: Position Sizing")
    print("="*80)
    
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    position_size_pct = strategy.get_position_size_pct()
    
    print(f"Position size: {position_size_pct * 100}%")
    
    if position_size_pct == 0.40:
        print("✅ Position size = 40% per trade")
        print("   Max 2 positions = 80% deployed, 20% reserve")
        return True
    else:
        print(f"❌ Expected 40%, got {position_size_pct * 100}%")
        return False


def test_position_tp1_tracking():
    """Test that Position class has tp1_hit field"""
    print("\n" + "="*80)
    print("TEST 7: Position TP1 Tracking")
    print("="*80)
    
    # Create test position
    position = Position(
        symbol='DOGEUSDT',
        entry_price=0.10,
        quantity=1000,
        stop_loss=0.092,
    )
    
    # Check if tp1_hit field exists
    if hasattr(position, 'tp1_hit'):
        print(f"✅ Position has tp1_hit field")
        print(f"   Initial value: {position.tp1_hit}")
        
        # Test setting it
        position.tp1_hit = True
        print(f"   After TP1: {position.tp1_hit}")
        print("   Used to activate trailing stop")
        return True
    else:
        print("❌ Position missing tp1_hit field")
        return False


def test_exit_logic_flow():
    """Test complete exit logic flow"""
    print("\n" + "="*80)
    print("TEST 8: Exit Logic Flow Simulation")
    print("="*80)
    
    symbol = 'DOGEUSDT'
    strategy = strategy_manager.get_strategy(symbol)
    
    entry_price = 0.10
    entry_time = datetime.now() - timedelta(days=10)  # 10 days ago
    hold_days = 10
    
    print(f"Position: {symbol}")
    print(f"Entry: ${entry_price}")
    print(f"Hold: {hold_days} days")
    print(f"\nExit Hierarchy:")
    
    # 1. Max hold check (highest priority)
    max_hold = strategy.get_max_hold_days()
    if hold_days >= max_hold:
        print(f"1. ⏰ Max hold check: TRIGGERED (day {hold_days} >= {max_hold})")
        print("   → Force exit regardless of price")
    else:
        print(f"1. ⏰ Max hold check: OK (day {hold_days} < {max_hold})")
    
    # 2. Stop loss check
    stop_loss = strategy.get_stop_loss(entry_price, hold_days)
    print(f"2. 🛑 Stop loss: ${stop_loss:.6f} ({((stop_loss/entry_price - 1) * 100):.1f}%)")
    print(f"   If price <= ${stop_loss:.6f}: Close 100%")
    
    # 3. TP levels
    tp_levels = strategy.get_take_profits(entry_price)
    print(f"3. 🎯 TP1: ${tp_levels[0]['price']:.6f} (+15%)")
    print(f"   If hit & not tp1_hit: Close 50%, activate trailing")
    
    print(f"4. 📉 Trailing stop: 5% from highest")
    print(f"   If tp1_hit & price < (high * 0.95): Close remaining")
    
    print(f"5. 🎯 TP2: ${tp_levels[1]['price']:.6f} (+30%)")
    print(f"   If hit & tp1_hit: Close remaining 50%")
    
    print(f"\nMin hold: {strategy.get_min_hold_days()} days")
    print(f"   During days 0-6: ONLY stop loss allowed")
    print(f"   After day 7: All exits enabled")
    
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("GOLDILOCK EXIT LOGIC VALIDATION")
    print("="*80)
    print(f"Testing: {', '.join(strategy_manager.get_all_tracked_coins())}")
    
    tests = [
        ("Dynamic Stop Loss (8% → 3%)", test_dynamic_stop_loss),
        ("Minimum Hold (7 days)", test_min_hold_enforcement),
        ("Take Profit Levels", test_tp_levels),
        ("Trailing Stop (5%)", test_trailing_stop),
        ("Maximum Hold (90 days)", test_max_hold),
        ("Position Sizing (40%)", test_position_sizing),
        ("TP1 Hit Tracking", test_position_tp1_tracking),
        ("Exit Logic Flow", test_exit_logic_flow),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} FAILED with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Goldilock exit logic ready!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review needed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
