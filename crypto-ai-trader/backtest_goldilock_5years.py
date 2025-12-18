"""
Backtest Goldilock Strategy on Historical Data
- Fetches 4H candles for DOGEUSDT, SHIBUSDT, SOLUSDT using authenticated Binance API
- Tests entry conditions (RSI < 40 + 3/4 indicators)
- Simulates position management (min/max hold, dynamic SL, TP1/TP2, trailing)
- Tracks P&L, win rate, drawdown

NOTE: Uses Binance production API keys from .env for extended historical data access.
Authenticated API has higher rate limits and can fetch data with start_time/end_time parameters.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.goldilock_strategy import GoldilockStrategy
from src.data.data_fetcher import binance_fetcher
from src.utils.logger import logger

class BacktestEngine:
    def __init__(self, initial_capital: float = 1000.0, allocation: Dict[str, float] = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.strategy = GoldilockStrategy()
        
        # Capital allocation per symbol (40:40:20 for DOGE:SHIB:SOL)
        self.allocation = allocation or {
            'DOGEUSDT': 0.40,
            'SHIBUSDT': 0.40,
            'SOLUSDT': 0.20
        }
        
        # Position tracking
        self.open_positions: Dict[str, Dict] = {}  # symbol -> position details
        self.closed_trades: List[Dict] = []
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0
        self.max_drawdown = 0
        self.peak_capital = initial_capital
        
        # Track trades per symbol
        self.symbol_trades: Dict[str, List[Dict]] = {
            'DOGEUSDT': [],
            'SHIBUSDT': [],
            'SOLUSDT': []
        }
        
    def can_open_position(self, symbol: str, current_time: datetime) -> bool:
        """Check if can open new position (monthly limit + max positions)"""
        # Check if already have position
        if symbol in self.open_positions:
            return False
        
        # Check max positions (2 for Goldilock)
        if len(self.open_positions) >= 2:
            return False
        
        # Check monthly limit (1 trade per month per coin)
        month_key = current_time.strftime('%Y-%m')
        monthly_trades_this_coin = [
            trade for trade in self.closed_trades 
            if trade['symbol'] == symbol and 
            trade['entry_time'].strftime('%Y-%m') == month_key
        ]
        
        if len(monthly_trades_this_coin) >= 1:
            return False
        
        return True
    
    def calculate_position_size(self, symbol: str) -> float:
        """Calculate position size based on allocation (40:40:20)"""
        allocation_pct = self.allocation.get(symbol, 0.33)
        position_size = self.initial_capital * allocation_pct
        return position_size
    
    def open_position(self, symbol: str, entry_price: float, entry_time: datetime, 
                     entry_reason: str, indicators: Dict):
        """Open a new position"""
        position_size = self.calculate_position_size(symbol)
        quantity = position_size / entry_price
        
        # Calculate initial stop loss (8% for first 7 days)
        stop_loss = self.strategy.get_stop_loss(entry_price, hold_days=0)
        
        # Calculate take profit levels
        take_profits = self.strategy.get_take_profits(entry_price)
        
        self.open_positions[symbol] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'quantity': quantity,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profits': take_profits,
            'highest_price': entry_price,
            'tp1_hit': False,
            'remaining_quantity': quantity,
            'entry_reason': entry_reason,
            'indicators': indicators,
        }
        
        self.total_trades += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📈 OPEN POSITION #{self.total_trades}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Entry: ${entry_price:.4f}")
        logger.info(f"Time: {entry_time}")
        logger.info(f"Quantity: {quantity:.6f}")
        logger.info(f"Position Size: ${position_size:.2f} (40%)")
        logger.info(f"Initial SL: ${stop_loss:.4f} (-8%)")
        logger.info(f"TP1: ${take_profits[0]['price']:.4f} (+15%)")
        logger.info(f"TP2: ${take_profits[1]['price']:.4f} (+30%)")
        logger.info(f"Reason: {entry_reason}")
        logger.info(f"Capital: ${self.current_capital:.2f}")
        logger.info(f"{'='*60}")
    
    def close_position(self, symbol: str, exit_price: float, exit_time: datetime, 
                      exit_reason: str, partial: bool = False):
        """Close position (full or partial)"""
        if symbol not in self.open_positions:
            return
        
        position = self.open_positions[symbol]
        
        if partial:
            # Close 50% (TP1 hit)
            close_quantity = position['quantity'] * 0.5
            position['remaining_quantity'] = position['quantity'] * 0.5
            position['tp1_hit'] = True
        else:
            # Close 100%
            close_quantity = position['remaining_quantity']
        
        entry_price = position['entry_price']
        pnl_value = (exit_price - entry_price) * close_quantity
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        
        # Update capital
        self.current_capital += pnl_value
        self.total_pnl += pnl_value
        
        # Track win/loss
        if pnl_value > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Calculate hold time
        hold_days = (exit_time - position['entry_time']).days
        
        # Record closed trade
        trade_record = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': position['entry_time'],
            'exit_price': exit_price,
            'exit_time': exit_time,
            'quantity': close_quantity,
            'position_size': position['position_size'] * (close_quantity / position['quantity']),
            'pnl_value': pnl_value,
            'pnl_percent': pnl_percent,
            'hold_days': hold_days,
            'exit_reason': exit_reason,
            'partial': partial,
        }
        
        self.closed_trades.append(trade_record)
        self.symbol_trades[symbol].append(trade_record)
        
        emoji = "✅" if pnl_value > 0 else "❌"
        logger.info(f"\n{'='*60}")
        logger.info(f"{emoji} CLOSE POSITION {'(PARTIAL 50%)' if partial else '(FULL)'}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f}")
        logger.info(f"Time: {position['entry_time']} → {exit_time}")
        logger.info(f"Hold: {hold_days} days")
        logger.info(f"Quantity: {close_quantity:.6f}")
        logger.info(f"P&L: ${pnl_value:+.2f} ({pnl_percent:+.2f}%)")
        logger.info(f"Reason: {exit_reason}")
        logger.info(f"Capital: ${self.current_capital:.2f}")
        logger.info(f"{'='*60}")
        
        # Remove position if fully closed
        if not partial:
            del self.open_positions[symbol]
        
        # Update drawdown
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        drawdown = ((self.peak_capital - self.current_capital) / self.peak_capital) * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
    
    def check_exits(self, symbol: str, current_price: float, current_time: datetime):
        """Check if position should exit"""
        if symbol not in self.open_positions:
            return
        
        position = self.open_positions[symbol]
        entry_price = position['entry_price']
        entry_time = position['entry_time']
        
        # Calculate hold days
        hold_days = (current_time - entry_time).days
        
        # Update highest price for trailing stop
        if current_price > position['highest_price']:
            position['highest_price'] = current_price
        
        # Calculate dynamic stop loss based on hold days
        dynamic_sl = self.strategy.get_stop_loss(entry_price, hold_days)
        position['stop_loss'] = dynamic_sl
        
        min_hold = self.strategy.get_min_hold_days()
        max_hold = self.strategy.get_max_hold_days()
        
        # Check max hold (90 days)
        if hold_days >= max_hold:
            self.close_position(symbol, current_price, current_time, 
                              f"MAX_HOLD ({hold_days} days)")
            return
        
        # During min hold (0-6 days), only allow stop loss
        if hold_days < min_hold:
            if current_price <= dynamic_sl:
                self.close_position(symbol, current_price, current_time,
                                  f"STOP_LOSS_EARLY (Day {hold_days}, -8%)")
            return
        
        # After min hold, check all exit conditions
        
        # 1. Stop loss (3% after day 7)
        if current_price <= dynamic_sl:
            self.close_position(symbol, current_price, current_time,
                              f"STOP_LOSS (Day {hold_days}, -3%)")
            return
        
        # 2. TP1 (+15%)
        tp1_price = position['take_profits'][0]['price']
        if not position['tp1_hit'] and current_price >= tp1_price:
            self.close_position(symbol, current_price, current_time,
                              f"TP1 (Day {hold_days}, +15%)", partial=True)
            return
        
        # 3. Trailing stop (5% from highest, after TP1)
        if position['tp1_hit']:
            trailing_stop = position['highest_price'] * (1 - self.strategy.get_trailing_stop_pct())
            if current_price <= trailing_stop:
                self.close_position(symbol, current_price, current_time,
                                  f"TRAILING_STOP (Day {hold_days}, -5% from high)")
                return
        
        # 4. TP2 (+30%)
        tp2_price = position['take_profits'][1]['price']
        if position['tp1_hit'] and current_price >= tp2_price:
            self.close_position(symbol, current_price, current_time,
                              f"TP2 (Day {hold_days}, +30%)")
            return
    
    async def fetch_historical_data(self, symbol: str, years: int = 5) -> pd.DataFrame:
        """Fetch historical 4H candles using authenticated Binance API"""
        logger.info(f"\n📊 Fetching {years} years of 4H data for {symbol}...")
        logger.info(f"   Using authenticated Binance API for extended history...")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=years*365)
        
        all_candles = []
        current_start = start_time
        batch_size = 1000  # Binance limit per request
        
        # Fetch data in chunks moving forward in time
        while current_start < end_time:
            # Calculate batch end time (1000 * 4 hours = 166.67 days)
            batch_end = current_start + timedelta(hours=4*batch_size)
            if batch_end > end_time:
                batch_end = end_time
            
            try:
                df_chunk = await binance_fetcher.get_klines(
                    symbol=symbol,
                    interval='4h',
                    limit=batch_size,
                    start_time=int(current_start.timestamp() * 1000),
                    end_time=int(batch_end.timestamp() * 1000)
                )
                
                if df_chunk.empty:
                    logger.warning(f"  Empty response for {current_start} → {batch_end}")
                    break
                
                all_candles.append(df_chunk)
                
                oldest_time = df_chunk['timestamp'].iloc[0]
                newest_time = df_chunk['timestamp'].iloc[-1]
                
                logger.info(f"  Fetched {len(df_chunk)} candles: {oldest_time} → {newest_time}")
                
                # Save historical data to CSV for future use
                data_dir = Path('backtest_results/historical_data')
                data_dir.mkdir(parents=True, exist_ok=True)
                data_file = data_dir / f'{symbol}_4h_historical.csv'
                
                # Append or create
                if data_file.exists():
                    existing_df = pd.read_csv(data_file)
                    existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
                    combined_df = pd.concat([existing_df, df_chunk], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=['timestamp'], keep='last')
                    combined_df = combined_df.sort_values('timestamp')
                    combined_df.to_csv(data_file, index=False)
                else:
                    df_chunk.to_csv(data_file, index=False)
                
                # Move to next batch
                current_start = newest_time + timedelta(hours=4)
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"  Error fetching batch: {e}")
                break
        
        if not all_candles:
            return pd.DataFrame()
        
        # Combine all chunks
        df = pd.concat(all_candles, ignore_index=True)
        
        # Remove duplicates (in case of overlap)
        df = df.drop_duplicates(subset=['timestamp'], keep='first')
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"✅ Total candles: {len(df)}")
        logger.info(f"   Date range: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        logger.info(f"   Coverage: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days} days")
        
        # Save final consolidated data
        data_dir = Path('backtest_results/historical_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        final_file = data_dir / f'{symbol}_4h_complete.csv'
        df.to_csv(final_file, index=False)
        logger.info(f"💾 Saved complete historical data to: {final_file}")
        
        return df
        df = pd.concat(all_candles, ignore_index=True)
        
        # Remove duplicates (in case of overlap)
        df = df.drop_duplicates(subset=['timestamp'], keep='first')
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"✅ Total candles: {len(df)}")
        logger.info(f"   Date range: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        logger.info(f"   Coverage: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days} days")
        
        return df
    
    async def run_backtest(self, symbols: List[str], years: int = 5):
        """Run backtest on multiple symbols"""
        logger.info("\n" + "="*80)
        logger.info("🚀 GOLDILOCK STRATEGY BACKTEST")
        logger.info("="*80)
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Target Period: {years} years (Limited by API to ~167 days)")
        logger.info(f"Initial Capital: ${self.initial_capital:.2f}")
        logger.info(f"Position Size: 40% per trade")
        logger.info(f"Max Positions: 2")
        logger.info(f"="*80)
        
        # Fetch data for all symbols
        data = {}
        for symbol in symbols:
            df = await self.fetch_historical_data(symbol, years)
            if df.empty:
                logger.warning(f"⚠️  No data for {symbol}")
                continue
            
            # Calculate indicators
            df = self.strategy.calculate_indicators(df)
            data[symbol] = df
        
        if not data:
            logger.error("❌ No data fetched for any symbol")
            return
        
        # Find common date range
        earliest_start = max(df['timestamp'].iloc[0] for df in data.values())
        latest_end = min(df['timestamp'].iloc[-1] for df in data.values())
        
        total_days = (latest_end - earliest_start).days
        
        logger.info(f"\n📅 Common date range: {earliest_start} → {latest_end}")
        logger.info(f"📊 Testing period: {total_days} days")
        logger.info(f"🔄 Starting backtest simulation...\n")
        
        # Create daily data for each symbol (for daily trend filter)
        daily_data = {}
        for symbol, df_4h in data.items():
            # Create daily OHLCV by grouping 4H bars
            df_daily = df_4h.copy()
            df_daily['date'] = df_daily['timestamp'].dt.date
            
            df_daily_agg = df_daily.groupby('date').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).reset_index()
            
            df_daily_agg['timestamp'] = pd.to_datetime(df_daily_agg['date'])
            df_daily_agg = df_daily_agg.drop('date', axis=1)
            df_daily_agg = self.strategy.calculate_indicators(df_daily_agg)
            df_daily_agg = df_daily_agg.set_index('timestamp')
            
            daily_data[symbol] = df_daily_agg
        
        # Simulate time-by-time
        current_idx = 0
        total_bars = len(next(iter(data.values())))
        
        while current_idx < total_bars:
            current_time = next(iter(data.values()))['timestamp'].iloc[current_idx]
            
            # Skip if before common start
            if current_time < earliest_start:
                current_idx += 1
                continue
            
            # Check exits for open positions
            for symbol in list(self.open_positions.keys()):
                if symbol in data:
                    current_price = float(data[symbol]['close'].iloc[current_idx])
                    self.check_exits(symbol, current_price, current_time)
            
            # Check entries for each symbol
            for symbol, df_4h in data.items():
                # Skip if can't open position
                if not self.can_open_position(symbol, current_time):
                    continue
                
                # Get current 4H data up to this point - set timestamp as index
                df_4h_slice = df_4h.iloc[:current_idx+1].copy()
                df_4h_slice = df_4h_slice.set_index('timestamp')
                
                # Get daily data up to this date
                current_date = current_time.date()
                df_daily_slice = daily_data[symbol]
                df_daily_slice = df_daily_slice[df_daily_slice.index.date <= current_date]
                
                if len(df_4h_slice) < 50 or len(df_daily_slice) < 50:
                    continue  # Not enough data for indicators
                
                # Check entry conditions (use last index)
                should_enter, reason = self.strategy.check_entry(
                    df_4h=df_4h_slice,
                    df_1h=df_4h_slice,  # Use 4H as proxy
                    df_daily=df_daily_slice,
                    current_idx=-1  # Last bar
                )
                
                if should_enter:
                    entry_price = float(df_4h_slice['close'].iloc[-1])
                    indicators = {
                        'rsi': float(df_4h_slice['rsi'].iloc[-1]) if 'rsi' in df_4h_slice.columns else 0,
                        'ema_9': float(df_4h_slice['ema_9'].iloc[-1]) if 'ema_9' in df_4h_slice.columns else 0,
                        'ema_21': float(df_4h_slice['ema_21'].iloc[-1]) if 'ema_21' in df_4h_slice.columns else 0,
                    }
                    self.open_position(symbol, entry_price, current_time, reason, indicators)
            
            # Progress update every 1000 bars
            if current_idx % 1000 == 0:
                progress = (current_idx / total_bars) * 100
                logger.info(f"⏳ Progress: {progress:.1f}% | Date: {current_time} | Capital: ${self.current_capital:.2f}")
            
            current_idx += 1
        
        # Close any remaining open positions at end
        for symbol in list(self.open_positions.keys()):
            final_price = float(data[symbol]['close'].iloc[-1])
            final_time = data[symbol]['timestamp'].iloc[-1]
            self.close_position(symbol, final_price, final_time, "BACKTEST_END")
        
        # Print results with CAGR
        self.print_results(start_date=earliest_start, end_date=latest_end)
        
        # Save results to CSV
        self.save_results_to_csv(start_date=earliest_start, end_date=latest_end)
    
    def calculate_cagr(self, start_date: datetime, end_date: datetime) -> float:
        """Calculate Compound Annual Growth Rate"""
        years = (end_date - start_date).days / 365.25
        if years <= 0:
            return 0.0
        cagr = (pow(self.current_capital / self.initial_capital, 1/years) - 1) * 100
        return cagr
    
    def print_results(self, start_date: datetime = None, end_date: datetime = None):
        """Print comprehensive backtest results"""
        logger.info("\n" + "="*80)
        logger.info("📊 BACKTEST RESULTS - GOLDILOCK STRATEGY")
        logger.info("="*80)
        
        # Calculate CAGR
        cagr = 0.0
        if start_date and end_date:
            cagr = self.calculate_cagr(start_date, end_date)
            years = (end_date - start_date).days / 365.25
            logger.info(f"\n📅 PERIOD")
            logger.info(f"   Start: {start_date.strftime('%Y-%m-%d')}")
            logger.info(f"   End: {end_date.strftime('%Y-%m-%d')}")
            logger.info(f"   Duration: {years:.2f} years ({(end_date - start_date).days} days)")
        
        logger.info(f"\n💰 CAPITAL PERFORMANCE")
        logger.info(f"   Initial Capital: ${self.initial_capital:.2f}")
        logger.info(f"   Final Capital: ${self.current_capital:.2f}")
        logger.info(f"   Total P&L: ${self.total_pnl:+.2f}")
        logger.info(f"   ROI: {((self.current_capital - self.initial_capital) / self.initial_capital * 100):+.2f}%")
        if cagr != 0.0:
            logger.info(f"   CAGR: {cagr:+.2f}%")
        
        logger.info(f"\n💼 ALLOCATION (40:40:20)")
        logger.info(f"   DOGEUSDT: ${self.initial_capital * 0.40:.2f} (40%)")
        logger.info(f"   SHIBUSDT: ${self.initial_capital * 0.40:.2f} (40%)")
        logger.info(f"   SOLUSDT: ${self.initial_capital * 0.20:.2f} (20%)")
        
        logger.info(f"\n📈 TRADE STATISTICS")
        logger.info(f"   Total Trades: {self.total_trades}")
        logger.info(f"   Profitable Trades: {self.winning_trades}")
        logger.info(f"   Loss Trades: {self.losing_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            logger.info(f"   Win Rate: {win_rate:.1f}%")
            logger.info(f"   Profit/Loss Ratio: {self.winning_trades}/{self.losing_trades}")
        
        logger.info(f"\n📉 RISK METRICS")
        logger.info(f"   Max Drawdown: {self.max_drawdown:.2f}%")
        logger.info(f"   Peak Capital: ${self.peak_capital:.2f}")
        
        if self.closed_trades:
            avg_pnl = sum(t['pnl_value'] for t in self.closed_trades) / len(self.closed_trades)
            avg_hold = sum(t['hold_days'] for t in self.closed_trades) / len(self.closed_trades)
            
            # Calculate profit/loss trade metrics
            profit_trades = [t for t in self.closed_trades if t['pnl_value'] > 0]
            loss_trades = [t for t in self.closed_trades if t['pnl_value'] <= 0]
            
            avg_profit = sum(t['pnl_value'] for t in profit_trades) / len(profit_trades) if profit_trades else 0
            avg_loss = sum(t['pnl_value'] for t in loss_trades) / len(loss_trades) if loss_trades else 0
            
            logger.info(f"\n📊 TRADE AVERAGES")
            logger.info(f"   Avg P&L per trade: ${avg_pnl:+.2f}")
            logger.info(f"   Avg Profit (winners): ${avg_profit:+.2f}")
            logger.info(f"   Avg Loss (losers): ${avg_loss:+.2f}")
            logger.info(f"   Avg Hold: {avg_hold:.1f} days")
            if avg_loss != 0:
                profit_factor = abs(avg_profit / avg_loss)
                logger.info(f"   Profit Factor: {profit_factor:.2f}x")
            
            # Best and worst trades
            best_trade = max(self.closed_trades, key=lambda t: t['pnl_percent'])
            worst_trade = min(self.closed_trades, key=lambda t: t['pnl_percent'])
            
            logger.info(f"\n🏆 BEST TRADE")
            logger.info(f"   {best_trade['symbol']}: {best_trade['pnl_percent']:+.2f}% (${best_trade['pnl_value']:+.2f})")
            logger.info(f"   {best_trade['entry_time']} → {best_trade['exit_time']}")
            logger.info(f"   Reason: {best_trade['exit_reason']}")
            
            logger.info(f"\n💔 WORST TRADE")
            logger.info(f"   {worst_trade['symbol']}: {worst_trade['pnl_percent']:+.2f}% (${worst_trade['pnl_value']:+.2f})")
            logger.info(f"   {worst_trade['entry_time']} → {worst_trade['exit_time']}")
            logger.info(f"   Reason: {worst_trade['exit_reason']}")
            
            # Exit reasons breakdown
            exit_reasons = {}
            for trade in self.closed_trades:
                reason = trade['exit_reason'].split('(')[0].strip()
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            
            logger.info(f"\n🎯 EXIT REASONS")
            for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
                pct = (count / len(self.closed_trades)) * 100
                logger.info(f"   {reason}: {count} ({pct:.1f}%)")
            
            # Per-symbol breakdown
            logger.info(f"\n🪙 PER-SYMBOL PERFORMANCE")
            for symbol in ['DOGEUSDT', 'SHIBUSDT', 'SOLUSDT']:
                symbol_trades_list = self.symbol_trades[symbol]
                if symbol_trades_list:
                    total_pnl = sum(t['pnl_value'] for t in symbol_trades_list)
                    winners = len([t for t in symbol_trades_list if t['pnl_value'] > 0])
                    losers = len([t for t in symbol_trades_list if t['pnl_value'] <= 0])
                    win_rate_sym = (winners / len(symbol_trades_list)) * 100 if symbol_trades_list else 0
                    
                    logger.info(f"\n   {symbol}:")
                    logger.info(f"      Trades: {len(symbol_trades_list)}")
                    logger.info(f"      Profit Trades: {winners} | Loss Trades: {losers}")
                    logger.info(f"      Win Rate: {win_rate_sym:.1f}%")
                    logger.info(f"      Total P&L: ${total_pnl:+.2f}")
                    logger.info(f"      Allocation: ${self.allocation[symbol] * self.initial_capital:.2f} ({self.allocation[symbol]*100:.0f}%)")
        
        logger.info("\n" + "="*80)
    
    def save_results_to_csv(self, start_date: datetime = None, end_date: datetime = None):
        """Save backtest results to CSV files"""
        # Create backtest_results directory
        results_dir = Path('backtest_results')
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Save all trades
        if self.closed_trades:
            trades_df = pd.DataFrame(self.closed_trades)
            trades_file = results_dir / f'trades_{timestamp}.csv'
            trades_df.to_csv(trades_file, index=False)
            logger.info(f"\n💾 Saved {len(trades_df)} trades to: {trades_file}")
        
        # 2. Save summary statistics
        summary_data = {
            'metric': [],
            'value': []
        }
        
        if start_date and end_date:
            cagr = self.calculate_cagr(start_date, end_date)
            years = (end_date - start_date).days / 365.25
            summary_data['metric'].extend(['start_date', 'end_date', 'duration_years', 'duration_days'])
            summary_data['value'].extend([
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                f'{years:.2f}',
                str((end_date - start_date).days)
            ])
            summary_data['metric'].append('cagr_percent')
            summary_data['value'].append(f'{cagr:.2f}')
        
        # Capital metrics
        summary_data['metric'].extend([
            'initial_capital',
            'final_capital',
            'total_pnl',
            'roi_percent',
            'max_drawdown_percent',
            'peak_capital'
        ])
        summary_data['value'].extend([
            f'${self.initial_capital:.2f}',
            f'${self.current_capital:.2f}',
            f'${self.total_pnl:+.2f}',
            f'{((self.current_capital - self.initial_capital) / self.initial_capital * 100):+.2f}',
            f'{self.max_drawdown:.2f}',
            f'${self.peak_capital:.2f}'
        ])
        
        # Trade statistics
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        summary_data['metric'].extend([
            'total_trades',
            'profitable_trades',
            'loss_trades',
            'win_rate_percent'
        ])
        summary_data['value'].extend([
            str(self.total_trades),
            str(self.winning_trades),
            str(self.losing_trades),
            f'{win_rate:.1f}'
        ])
        
        # Allocation
        summary_data['metric'].extend([
            'allocation_dogeusdt',
            'allocation_shibusdt',
            'allocation_solusdt'
        ])
        summary_data['value'].extend([
            f'${self.initial_capital * 0.40:.2f} (40%)',
            f'${self.initial_capital * 0.40:.2f} (40%)',
            f'${self.initial_capital * 0.20:.2f} (20%)'
        ])
        
        # Trade averages
        if self.closed_trades:
            avg_pnl = sum(t['pnl_value'] for t in self.closed_trades) / len(self.closed_trades)
            avg_hold = sum(t['hold_days'] for t in self.closed_trades) / len(self.closed_trades)
            profit_trades = [t for t in self.closed_trades if t['pnl_value'] > 0]
            loss_trades = [t for t in self.closed_trades if t['pnl_value'] <= 0]
            avg_profit = sum(t['pnl_value'] for t in profit_trades) / len(profit_trades) if profit_trades else 0
            avg_loss = sum(t['pnl_value'] for t in loss_trades) / len(loss_trades) if loss_trades else 0
            
            summary_data['metric'].extend([
                'avg_pnl_per_trade',
                'avg_profit_winners',
                'avg_loss_losers',
                'avg_hold_days',
                'profit_factor'
            ])
            summary_data['value'].extend([
                f'${avg_pnl:+.2f}',
                f'${avg_profit:+.2f}',
                f'${avg_loss:+.2f}',
                f'{avg_hold:.1f}',
                f'{abs(avg_profit / avg_loss):.2f}' if avg_loss != 0 else 'N/A'
            ])
        
        summary_df = pd.DataFrame(summary_data)
        summary_file = results_dir / f'summary_{timestamp}.csv'
        summary_df.to_csv(summary_file, index=False)
        logger.info(f"💾 Saved summary to: {summary_file}")
        
        # 3. Save per-symbol performance
        symbol_data = []
        for symbol in ['DOGEUSDT', 'SHIBUSDT', 'SOLUSDT']:
            symbol_trades_list = self.symbol_trades[symbol]
            if symbol_trades_list:
                total_pnl = sum(t['pnl_value'] for t in symbol_trades_list)
                winners = len([t for t in symbol_trades_list if t['pnl_value'] > 0])
                losers = len([t for t in symbol_trades_list if t['pnl_value'] <= 0])
                win_rate_sym = (winners / len(symbol_trades_list)) * 100 if symbol_trades_list else 0
                
                symbol_data.append({
                    'symbol': symbol,
                    'total_trades': len(symbol_trades_list),
                    'profit_trades': winners,
                    'loss_trades': losers,
                    'win_rate_percent': f'{win_rate_sym:.1f}',
                    'total_pnl': f'${total_pnl:+.2f}',
                    'allocation': f'${self.allocation[symbol] * self.initial_capital:.2f}',
                    'allocation_percent': f'{self.allocation[symbol]*100:.0f}%'
                })
        
        if symbol_data:
            symbol_df = pd.DataFrame(symbol_data)
            symbol_file = results_dir / f'per_symbol_{timestamp}.csv'
            symbol_df.to_csv(symbol_file, index=False)
            logger.info(f"💾 Saved per-symbol performance to: {symbol_file}")
        
        logger.info(f"\n✅ All results saved to: {results_dir}/")
        return results_dir


async def main():
    """Run backtest with 40:40:20 allocation"""
    symbols = ['DOGEUSDT', 'SHIBUSDT', 'SOLUSDT']
    
    # Initialize with $1000 and 40:40:20 allocation
    allocation = {
        'DOGEUSDT': 0.40,  # $400
        'SHIBUSDT': 0.40,  # $400
        'SOLUSDT': 0.20    # $200
    }
    
    engine = BacktestEngine(initial_capital=1000.0, allocation=allocation)
    await engine.run_backtest(symbols, years=5)

if __name__ == "__main__":
    asyncio.run(main())

