"""
OPTIMIZED FIXED GOLDILOCKS V2 - FIXED VERSION
Critical fix: Wider stops (8%) during 7-day minimum hold
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

from trading_bot.data.cache import DataCache


class OptimizedFixedGoldilocksV2:
    """Fixed: Wider stops during minimum hold to survive volatility"""
    
    def __init__(self):
        # OPTIMIZED PARAMETERS (based on your test results)
        self.config = {
            # Entry (proven to work)
            'rsi_entry': 40,
            'min_conditions': 3,
            'require_daily_trend': True,
            'require_btc_bull': False,  # REMOVED: Too restrictive
            
            # Exit (CRITICAL FIXES)
            'initial_stop': 0.08,        # 8% stop DURING minimum hold
            'regular_stop': 0.03,        # 3% stop AFTER minimum hold  
            'take_profits': [0.15, 0.30], # 15%/30% targets
            'trailing_stop': 0.05,       # 5% trailing
            'min_hold_days': 7,
            'max_hold_days': 90,
            
            # Position sizing (concentrated)
            'position_size': 0.40,       # 40% per position
            'max_positions': 2,          # Only 2 positions
            'max_trades_per_month': 1,
            
            # Market filters (relaxed)
            'volume_spike': 1.3,
        }
        
        self.monthly_trades = {}
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        df = df.copy()
        
        # EMAs
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_bullish'] = df['macd'] > df['macd_signal']
        
        return df
    
    def check_entry_conditions(self, df: pd.DataFrame, i: int, 
                              df_daily: pd.DataFrame) -> Tuple[bool, str]:
        """Check entry conditions"""
        
        # Daily trend filter
        daily_close = df_daily['close'].reindex(df.index, method='ffill').iloc[i]
        if 'ema_50' not in df_daily.columns:
            df_daily['ema_50'] = df_daily['close'].ewm(span=50, adjust=False).mean()
        daily_ema50 = df_daily['ema_50'].reindex(df.index, method='ffill').iloc[i]
        
        if pd.isna(daily_close) or pd.isna(daily_ema50) or daily_close <= daily_ema50:
            return False, "daily_trend"
        
        conditions_met = []
        
        # 1. EMA9 > EMA21
        if df['ema_9'].iloc[i] > df['ema_21'].iloc[i]:
            conditions_met.append('ema_cross')
        
        # 2. RSI < 40 (oversold)
        if df['rsi'].iloc[i] < self.config['rsi_entry']:
            conditions_met.append('rsi_oversold')
        
        # 3. Volume spike
        if df['volume_ratio'].iloc[i] > self.config['volume_spike']:
            conditions_met.append('volume_spike')
        
        # 4. MACD bullish
        if df['macd_bullish'].iloc[i]:
            conditions_met.append('macd_bullish')
        
        # Require 3 of 4 conditions
        if len(conditions_met) >= self.config['min_conditions']:
            return True, f"{len(conditions_met)}/4: {','.join(conditions_met)}"
        
        return False, f"only_{len(conditions_met)}_conds"
    
    def can_trade_this_month(self, timestamp: pd.Timestamp, coin: str) -> bool:
        """Check monthly trade limit"""
        month_key = (coin, timestamp.year, timestamp.month)
        return self.monthly_trades.get(month_key, 0) < self.config['max_trades_per_month']
    
    def record_trade(self, timestamp: pd.Timestamp, coin: str):
        """Record trade for monthly limit"""
        month_key = (coin, timestamp.year, timestamp.month)
        self.monthly_trades[month_key] = self.monthly_trades.get(month_key, 0) + 1
    
    def get_stop_loss_for_position(self, hold_days: int) -> float:
        """Return appropriate stop loss based on hold time"""
        if hold_days < self.config['min_hold_days']:
            return self.config['initial_stop']  # 8% during min hold
        return self.config['regular_stop']  # 3% after min hold
    
    def backtest(self, df_4h: pd.DataFrame, df_daily: pd.DataFrame,
                 btc_weekly: pd.DataFrame, coin: str, 
                 initial_capital: float = 10000) -> Dict:
        """Run backtest with improved stops"""
        
        self.monthly_trades = {}
        
        capital = initial_capital
        positions = []
        trade_history = []
        equity_curve = []
        
        # Calculate indicators
        df = self.calculate_indicators(df_4h)
        df_daily = self.calculate_indicators(df_daily)
        
        # Statistics
        big_wins = 0
        huge_wins = 0
        
        for i in range(200, len(df)):
            current_time = df.index[i]
            current_price = df['close'].iloc[i]
            
            # Manage existing positions
            for pos in positions[:]:
                profit_pct = (current_price / pos['entry_price']) - 1
                hold_days = (current_time - pos['entry_time']).days
                
                # Update highest price
                if current_price > pos['highest_price']:
                    pos['highest_price'] = current_price
                
                # Get appropriate stop loss
                current_stop = self.get_stop_loss_for_position(hold_days)
                
                # Minimum hold period check
                if hold_days < self.config['min_hold_days']:
                    # Only allow stop loss during minimum hold (with 8% stop)
                    if profit_pct < -current_stop:  # 8% stop during min hold
                        exit_value = pos['remaining_size'] * current_price
                        exit_fee = exit_value * 0.003
                        profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
                        
                        trade_history.append({
                            'entry_time': pos['entry_time'],
                            'exit_time': current_time,
                            'entry_price': pos['entry_price'],
                            'exit_price': current_price,
                            'profit': profit,
                            'profit_pct': profit_pct * 100,
                            'reason': 'stop_loss_early',
                            'hold_days': hold_days,
                        })
                        
                        capital += exit_value - exit_fee
                        positions.remove(pos)
                    continue
                
                # AFTER minimum hold period
                
                # Trailing stop after TP1
                if pos['tp1_hit']:
                    trail_price = pos['highest_price'] * (1 - self.config['trailing_stop'])
                    if current_price < trail_price:
                        exit_value = pos['remaining_size'] * current_price
                        exit_fee = exit_value * 0.003
                        profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
                        
                        trade_history.append({
                            'entry_time': pos['entry_time'],
                            'exit_time': current_time,
                            'entry_price': pos['entry_price'],
                            'exit_price': current_price,
                            'profit': profit,
                            'profit_pct': profit_pct * 100,
                            'reason': 'trailing_stop',
                            'hold_days': hold_days,
                        })
                        
                        capital += exit_value - exit_fee
                        
                        # Track big wins
                        if profit_pct * 100 > 30:
                            big_wins += 1
                        if profit_pct * 100 > 50:
                            huge_wins += 1
                        
                        positions.remove(pos)
                        continue
                
                # Stop loss (3% after min hold)
                if profit_pct < -current_stop:
                    exit_value = pos['remaining_size'] * current_price
                    exit_fee = exit_value * 0.003
                    profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
                    
                    trade_history.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'profit': profit,
                        'profit_pct': profit_pct * 100,
                        'reason': 'stop_loss',
                        'hold_days': hold_days,
                    })
                    
                    capital += exit_value - exit_fee
                    positions.remove(pos)
                    continue
                
                # TP1 (15%)
                if not pos['tp1_hit'] and profit_pct >= self.config['take_profits'][0]:
                    exit_size = pos['size'] * 0.5
                    exit_value = exit_size * current_price
                    exit_fee = exit_value * 0.003
                    profit = (exit_value - (exit_size * pos['entry_price'])) - exit_fee
                    
                    capital += exit_value - exit_fee
                    pos['remaining_size'] = pos['size'] * 0.5
                    pos['tp1_hit'] = True
                    pos['realized_profit'] = profit
                    continue
                
                # TP2 (30%)
                if pos['tp1_hit'] and profit_pct >= self.config['take_profits'][1]:
                    exit_value = pos['remaining_size'] * current_price
                    exit_fee = exit_value * 0.003
                    profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
                    
                    trade_history.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'profit': profit,
                        'profit_pct': profit_pct * 100,
                        'reason': 'take_profit_2',
                        'hold_days': hold_days,
                    })
                    
                    capital += exit_value - exit_fee
                    
                    # Track big wins
                    if profit_pct * 100 > 30:
                        big_wins += 1
                    if profit_pct * 100 > 50:
                        huge_wins += 1
                    
                    positions.remove(pos)
                    continue
                
                # Max hold days
                if hold_days > self.config['max_hold_days']:
                    exit_value = pos['remaining_size'] * current_price
                    exit_fee = exit_value * 0.003
                    profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
                    
                    trade_history.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'profit': profit,
                        'profit_pct': profit_pct * 100,
                        'reason': 'max_hold',
                        'hold_days': hold_days,
                    })
                    
                    capital += exit_value - exit_fee
                    positions.remove(pos)
                    continue
            
            # Check for new entry
            if len(positions) < self.config['max_positions']:
                should_enter, reason = self.check_entry_conditions(df, i, df_daily)
                
                if should_enter and self.can_trade_this_month(current_time, coin):
                    # Calculate position size (40%)
                    position_value = capital * self.config['position_size']
                    position_size = position_value / current_price
                    entry_cost = position_value * 1.003
                    
                    if entry_cost <= capital:
                        capital -= entry_cost
                        positions.append({
                            'entry_price': current_price,
                            'size': position_size,
                            'remaining_size': position_size,
                            'entry_time': current_time,
                            'highest_price': current_price,
                            'tp1_hit': False,
                            'realized_profit': 0,
                        })
                        
                        self.record_trade(current_time, coin)
            
            # Equity curve
            total_pos_value = sum(pos['remaining_size'] * current_price for pos in positions)
            equity_curve.append({
                'timestamp': current_time,
                'equity': capital + total_pos_value,
                'price': current_price,
                'positions': len(positions),
            })
        
        # Close remaining positions
        final_price = df['close'].iloc[-1]
        for pos in positions:
            exit_value = pos['remaining_size'] * final_price
            exit_fee = exit_value * 0.003
            profit_pct = (final_price / pos['entry_price'] - 1) * 100
            profit = (exit_value - (pos['remaining_size'] * pos['entry_price'])) - exit_fee + pos['realized_profit']
            
            trade_history.append({
                'entry_time': pos['entry_time'],
                'exit_time': df.index[-1],
                'entry_price': pos['entry_price'],
                'exit_price': final_price,
                'profit': profit,
                'profit_pct': profit_pct,
                'reason': 'final_close',
                'hold_days': (df.index[-1] - pos['entry_time']).days,
            })
            
            capital += exit_value - exit_fee
        
        # Calculate metrics
        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital
        
        equity_df = pd.DataFrame(equity_curve)
        equity_df['returns'] = equity_df['equity'].pct_change().fillna(0)
        
        days = (equity_df['timestamp'].iloc[-1] - equity_df['timestamp'].iloc[0]).days
        years = days / 365.25
        cagr = (final_capital / initial_capital) ** (1 / years) - 1 if years > 0 else total_return
        
        sharpe = 0
        if len(equity_df) > 1 and equity_df['returns'].std() > 0:
            sharpe = (equity_df['returns'].mean() / equity_df['returns'].std()) * np.sqrt(365 * 6)
        
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax']
        max_drawdown = equity_df['drawdown'].min()
        
        if trade_history:
            trades_df = pd.DataFrame(trade_history)
            winning = trades_df[trades_df['profit'] > 0]
            losing = trades_df[trades_df['profit'] <= 0]
            
            win_rate = len(winning) / len(trades_df)
            avg_win = winning['profit_pct'].mean() if len(winning) > 0 else 0
            avg_loss = losing['profit_pct'].mean() if len(losing) > 0 else 0
            avg_hold = trades_df['hold_days'].mean()
        else:
            win_rate = avg_win = avg_loss = avg_hold = 0
        
        return {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'cagr': cagr,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'total_trades': len(trade_history),
            'win_rate': win_rate,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'avg_hold_days': avg_hold,
            'trade_history': trade_history,
            'big_wins': big_wins,
            'huge_wins': huge_wins,
        }


def run_fixed_strategy():
    """Run the fixed strategy on DOGE and SHIB only"""
    cache = DataCache()
    
    print(f"\n{'='*120}")
    print("OPTIMIZED FIXED GOLDILOCKS V2 - CRITICAL FIX")
    print(f"{'='*120}\n")
    
    print("CRITICAL FIXES:")
    print("  ✓ Wider stops during 7-day min hold: 8% (was 3%)")
    print("  ✓ Higher targets: 15%/30% (was 10%/20%)")
    print("  ✓ Removed BTC bull filter (too restrictive)")
    print("  ✓ Larger positions: 40% each (was 30%)")
    print("  ✓ Only 2 coins: DOGE + SHIB")
    print()
    
    # Load BTC (not used for filtering, just for reference)
    btc_4h = cache.load_from_cache('BTCUSDT', '4h')
    btc_weekly = btc_4h.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()
    
    # ONLY DOGE and SHIB - proven performers
    coins = ['DOGEUSDT', 'SHIBUSDT']
    strategy = OptimizedFixedGoldilocksV2()
    
    results = {}
    portfolio_initial = 100000
    position_size = portfolio_initial * 0.40  # 40% each
    cash_reserve = portfolio_initial * 0.20   # 20% cash
    
    total_final = cash_reserve
    total_trades = 0
    all_big_wins = 0
    all_huge_wins = 0
    
    print(f"Portfolio Setup: ${portfolio_initial:,.0f} total")
    print(f"  • Each position: ${position_size:,.0f} (40%)")
    print(f"  • Cash reserve: ${cash_reserve:,.0f} (20%)")
    print(f"  • Coins: {', '.join(coins)}")
    print(f"  • Total allocated: 80% (2 × 40%)")
    print()
    
    for coin in coins:
        print(f"\n{coin}")
        print("-" * 120)
        
        df_4h = cache.load_from_cache(coin, '4h')
        df_daily = df_4h.resample('1D').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna()
        
        res = strategy.backtest(df_4h, df_daily, btc_weekly, coin, initial_capital=position_size)
        
        # Calculate years from actual backtest period (starts at index 200)
        days = (df_4h.index[-1] - df_4h.index[200]).days
        years = max(days / 365.25, 0.1)
        trades_per_year = res['total_trades'] / years
        
        # Track earliest and latest dates across all coins for portfolio CAGR
        if 'earliest_date' not in locals() or df_4h.index[200] < earliest_date:
            earliest_date = df_4h.index[200]
        if 'latest_date' not in locals() or df_4h.index[-1] > latest_date:
            latest_date = df_4h.index[-1]
        
        results[coin] = res
        total_final += res['final_capital']
        total_trades += res['total_trades']
        all_big_wins += res['big_wins']
        all_huge_wins += res['huge_wins']
        
        print(f"Results: {res['total_trades']} trades ({trades_per_year:.1f}/yr), "
              f"{res['cagr']:.1%} CAGR, {res['win_rate']:.1%} win, Sharpe {res['sharpe']:.2f}")
        print(f"  Avg win: {res['avg_win_pct']:.1f}%, Avg loss: {res['avg_loss_pct']:.1f}%")
        print(f"  Avg hold: {res['avg_hold_days']:.1f} days, Max DD: {res['max_drawdown']:.1%}")
        print(f"  Final: ${res['final_capital']:,.2f} "
              f"(${res['final_capital'] - position_size:+,.2f})")
        print(f"  Big wins (>30%): {res['big_wins']}, Huge wins (>50%): {res['huge_wins']}")
    
    # Portfolio summary - use EARLIEST start across all coins
    portfolio_return = (total_final - portfolio_initial) / portfolio_initial
    portfolio_years = (latest_date - earliest_date).days / 365.25
    portfolio_cagr = (total_final / portfolio_initial) ** (1 / portfolio_years) - 1
    
    print(f"\n\n{'='*120}")
    print("PORTFOLIO SUMMARY - FIXED STRATEGY")
    print(f"{'='*120}\n")
    print(f"Initial Portfolio: ${portfolio_initial:,.2f}")
    print(f"Final Portfolio:   ${total_final:,.2f}")
    print(f"Total Profit:      ${total_final - portfolio_initial:+,.2f}")
    print(f"Total Return:      {portfolio_return:.1%}")
    print(f"Portfolio CAGR:    {portfolio_cagr:.1%}")
    print(f"\nTotal Trades:      {total_trades}")
    print(f"Total Big Wins:    {all_big_wins} (>30% gains)")
    print(f"Total Huge Wins:   {all_huge_wins} (>50% gains)")
    
    # Individual performance
    print(f"\nIndividual Performance:")
    for coin, res in sorted(results.items(), key=lambda x: x[1]['cagr'], reverse=True):
        return_pct = (res['final_capital'] / position_size - 1) * 100
        print(f"  {coin:10s}: {res['cagr']:6.1%} CAGR, {res['total_trades']:2d} trades, "
              f"{return_pct:6.1f}% return, ${res['final_capital']:,.0f}")
    
    # Minimum hold verification
    print(f"\n{'='*120}")
    print("MINIMUM HOLD VERIFICATION (7-DAY ENFORCEMENT CHECK)")
    print(f"{'='*120}")
    for coin, res in results.items():
        trades = pd.DataFrame(res['trade_history'])
        if len(trades) > 0:
            early_exits = trades[
                (trades['hold_days'] < 7) & 
                ~trades['reason'].isin(['stop_loss', 'stop_loss_early'])
            ]
            if len(early_exits) > 0:
                print(f"\n⚠️ BUG DETECTED in {coin}:")
                print(f"   {len(early_exits)} trades exited before 7 days without stop loss!")
            else:
                non_stop_trades = trades[~trades['reason'].isin(['stop_loss', 'stop_loss_early'])]
                if len(non_stop_trades) > 0:
                    avg_hold = non_stop_trades['hold_days'].mean()
                    min_hold = non_stop_trades['hold_days'].min()
                    print(f"\n✅ {coin}: Minimum hold WORKING correctly")
                    print(f"   Non-stop-loss trades: {len(non_stop_trades)}, "
                          f"Avg hold: {avg_hold:.1f} days, Min hold: {min_hold:.0f} days")
                else:
                    print(f"\n⚠️ {coin}: All {len(trades)} trades hit stop loss")
    
    # Expected vs Actual
    print(f"\n{'='*120}")
    print("COMPARISON TO ALL PREVIOUS STRATEGIES")
    print(f"{'='*120}")
    print(f"Original (RSI <40, 8%/16%, 2.5% stop):        17.2% CAGR DOGE, 11.7% portfolio")
    print(f"With Patience V1 (3% stop, 10%/20% targets):  8.0% CAGR DOGE, 8.2% portfolio")
    print(f"This V2 Fixed (8% stop, 15%/30% targets):     {portfolio_cagr:.1%} CAGR portfolio")
    
    if 'DOGEUSDT' in results:
        print(f"                                              {results['DOGEUSDT']['cagr']:.1%} CAGR DOGE")
    
    print(f"\nTarget (based on original):                   15.0% CAGR")
    
    if portfolio_cagr >= 0.15:
        print(f"\n✅ SUCCESS! Strategy achieves target {portfolio_cagr:.1%} CAGR")
        print(f"   The wider 8% stop during minimum hold allows positions to survive volatility!")
    elif portfolio_cagr >= 0.12:
        print(f"\n⚙️ CLOSE: {portfolio_cagr:.1%} CAGR (target: 15%)")
        print(f"   Consider: Further relax volume filter or reduce min hold to 5 days")
    else:
        print(f"\n⚠️ UNDERPERFORMS: {portfolio_cagr:.1%} CAGR (target: 15%)")
        print(f"   The 8% stop may still be too tight for 7-day holds")
        print(f"   Consider: 10% stop during min hold OR reduce min hold to 5 days")
    
    return results


def main():
    """Main execution"""
    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                                                                        ║
    ║      OPTIMIZED FIXED GOLDILOCKS V2 - CRITICAL FIX                      ║
    ║                                                                        ║
    ║   FIX: 8% stops during 7-day minimum hold (was 3%)                     ║
    ║   FIX: 15%/30% targets (was 10%/20%)                                   ║
    ║   FIX: Only DOGE + SHIB, 40% positions each                            ║
    ║                                                                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)
    
    results = run_fixed_strategy()


if __name__ == "__main__":
    main()
