#!/usr/bin/env python3
"""
Oracle Mode Validation Dashboard

Shows:
1. Confidence calibration (Claude accuracy)
2. Trade statistics (win rate, expectancy)
3. Next steps based on data
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.confidence_calibration import confidence_calibration
from src.backtesting.trade_journal import trade_journal


def print_validation_dashboard():
    """Print comprehensive validation dashboard"""
    
    print("\n" + "="*80)
    print(" "*25 + "ORACLE MODE VALIDATION DASHBOARD")
    print("="*80)
    
    # 1. Trade Statistics
    print("\n📊 TRADE STATISTICS")
    print("-"*80)
    
    stats = trade_journal.get_stats()
    
    if stats.get('total_trades', 0) == 0:
        print("⚠️  No closed trades yet")
        print("   Start trading to collect data for validation")
    else:
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']}")
        print(f"Expectancy: {stats['expectancy']}")
        print(f"Total P&L: {stats['total_pnl']}")
        print(f"Avg Hold Time: {stats['avg_holding_hours']}")
    
    open_trades = trade_journal.get_open_trades()
    print(f"\nOpen Positions: {len(open_trades)}")
    for trade in open_trades:
        print(f"  - {trade.symbol} @ ${trade.entry_price:.2f} (confidence: {trade.confidence}%)")
    
    # 2. Confidence Calibration
    confidence_calibration.print_report()
    
    # 3. Next Steps
    print("\n" + "="*80)
    print("📋 NEXT STEPS")
    print("="*80)
    
    total_trades = stats.get('total_trades', 0)
    
    if total_trades == 0:
        print("\n🔴 PHASE 1: DATA COLLECTION (0/20 trades)")
        print("   Status: Just starting")
        print("   Action: Continue paper/live trading to collect first 20 trades")
        print("   Goal: Establish baseline confidence calibration")
        print("   Recommendation: DO NOT make strategy changes yet")
    
    elif total_trades < 20:
        print(f"\n🟡 PHASE 1: DATA COLLECTION ({total_trades}/20 trades)")
        print("   Status: Collecting initial data")
        print(f"   Progress: {(total_trades/20)*100:.0f}%")
        print("   Action: Need {0} more trades for initial assessment".format(20 - total_trades))
        print("   Recommendation: Continue trading, avoid tuning parameters")
    
    elif total_trades < 50:
        print(f"\n🟡 PHASE 2: INITIAL VALIDATION ({total_trades}/50 trades)")
        print("   Status: Preliminary patterns emerging")
        print("   Action: Review confidence calibration report above")
        
        is_healthy, reason = confidence_calibration.is_healthy()
        
        if is_healthy:
            print("   ✅ Calibration looks healthy - continue trading")
            print("   Goal: Reach 50 trades for statistical confidence")
        else:
            print(f"   ⚠️  Calibration issue: {reason}")
            print("   Recommendation: Review strategy before continuing")
        
        # Check expectancy
        try:
            exp_str = stats.get('expectancy', '0.00R')
            exp_val = float(exp_str.replace('R', ''))
            
            if exp_val >= 0.3:
                print(f"   ✅ Expectancy positive ({exp_str}) - good sign")
            elif exp_val >= 0:
                print(f"   ⚠️  Expectancy marginal ({exp_str}) - monitor closely")
            else:
                print(f"   🔴 Expectancy negative ({exp_str}) - consider stopping")
        except:
            pass
    
    else:
        print(f"\n🟢 PHASE 3: VALIDATED ({total_trades} trades)")
        print("   Status: Sufficient data for assessment")
        
        is_healthy, reason = confidence_calibration.is_healthy()
        
        if is_healthy:
            print("   ✅ System validated - Oracle Mode working")
            print(f"   {reason}")
            
            rec_threshold = confidence_calibration.get_recommended_threshold()
            print(f"\n   Recommended settings:")
            print(f"   - MIN_CONFIDENCE_TO_TRADE: {rec_threshold}")
            print(f"   - Current confidence distribution is working")
        else:
            print(f"   🔴 System NOT validated")
            print(f"   {reason}")
            print("\n   Recommendations:")
            print("   1. Review Claude's selection logic")
            print("   2. Consider switching to Veto or Confirmer mode")
            print("   3. Analyze losing trades for patterns")
    
    # 4. Data Quality
    print("\n" + "-"*80)
    print("📈 DATA QUALITY")
    print("-"*80)
    
    if total_trades < 20:
        quality = "INSUFFICIENT"
        icon = "🔴"
        action = f"Need {20 - total_trades} more trades"
    elif total_trades < 50:
        quality = "PRELIMINARY"
        icon = "🟡"
        action = "Patterns emerging, continue collecting"
    else:
        quality = "SUFFICIENT"
        icon = "🟢"
        action = "Can make strategic decisions"
    
    print(f"{icon} Quality: {quality}")
    print(f"   {action}")
    
    print("\n" + "="*80)
    print()


if __name__ == "__main__":
    print_validation_dashboard()
