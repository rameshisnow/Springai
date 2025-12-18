"""
Goldilock Strategy - Optimized for DOGE, SHIB, SOL

Key Features:
- RSI < 40 oversold entry
- 3/4 conditions required (EMA, RSI, Volume, MACD)
- Daily trend filter (price > daily EMA50)
- 7-day minimum hold with 8% stop
- After 7 days: 3% stop, 15%/30% TPs, 5% trailing
- 40% position size
- Max 1 trade per month per coin
"""
from typing import Dict, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from .base_strategy import BaseStrategy


class GoldilockStrategy(BaseStrategy):
    """
    Goldilock Strategy for DOGE, SHIB, SOL
    
    Entry: RSI < 40, 3/4 conditions (EMA9>21, Volume spike, MACD bull, Daily trend)
    Exit: 7-day min hold (8% stop) → 15%/30% TPs + 5% trailing (3% stop)
    """
    
    DEFAULT_CONFIG = {
        # Entry conditions
        'rsi_entry': 40,
        'min_conditions': 3,
        'require_daily_trend': True,
        'volume_spike': 1.3,
        
        # Exit strategy
        'initial_stop_pct': 0.08,    # 8% stop during min hold
        'regular_stop_pct': 0.03,    # 3% stop after min hold
        'tp1_pct': 0.15,             # 15% first target
        'tp2_pct': 0.30,             # 30% second target
        'tp1_size': 0.50,            # Close 50% at TP1
        'trailing_stop_pct': 0.05,   # 5% trailing after TP1
        
        # Holding period
        'min_hold_days': 7,
        'max_hold_days': 90,
        
        # Position sizing
        'position_size_pct': 0.40,   # 40% per position
        
        # Trade frequency
        'max_trades_per_month': 1,
    }
    
    def __init__(self, config: Dict = None):
        """Initialize with config override"""
        final_config = self.DEFAULT_CONFIG.copy()
        if config:
            final_config.update(config)
        super().__init__(final_config)
        
        # Track monthly trades per coin
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
    
    def check_entry(self, df_1h: pd.DataFrame, df_4h: pd.DataFrame,
                    df_daily: pd.DataFrame, current_idx: int) -> Tuple[bool, str]:
        """
        Check Goldilock entry conditions
        
        Returns:
            (should_enter, reason)
        """
        # Calculate indicators on 4H timeframe
        df_4h = self.calculate_indicators(df_4h)
        
        # Handle negative index (e.g., -1 for latest bar)
        if current_idx < 0:
            current_idx = len(df_4h) + current_idx
        
        # Get current time from 4H data
        if current_idx >= len(df_4h) or current_idx < 0:
            return False, "invalid_index"
        
        current_time = df_4h.index[current_idx]
        
        # Daily trend filter
        df_daily = self.calculate_indicators(df_daily)
        
        # Find nearest daily bar
        daily_bars_before = df_daily[df_daily.index <= current_time]
        if len(daily_bars_before) == 0:
            return False, "no_daily_data"
        
        daily_close = daily_bars_before['close'].iloc[-1]
        daily_ema50 = daily_bars_before['ema_50'].iloc[-1]
        
        if pd.isna(daily_close) or pd.isna(daily_ema50):
            return False, "daily_indicators_na"
        
        if daily_close <= daily_ema50:
            return False, "daily_trend_bearish"
        
        # Check 4H conditions
        conditions_met = []
        
        # 1. EMA9 > EMA21
        if df_4h['ema_9'].iloc[current_idx] > df_4h['ema_21'].iloc[current_idx]:
            conditions_met.append('ema_cross')
        
        # 2. RSI < 40 (oversold)
        rsi_val = df_4h['rsi'].iloc[current_idx]
        if not pd.isna(rsi_val) and rsi_val < self.config['rsi_entry']:
            conditions_met.append('rsi_oversold')
        
        # 3. Volume spike
        vol_ratio = df_4h['volume_ratio'].iloc[current_idx]
        if not pd.isna(vol_ratio) and vol_ratio > self.config['volume_spike']:
            conditions_met.append('volume_spike')
        
        # 4. MACD bullish
        if df_4h['macd_bullish'].iloc[current_idx]:
            conditions_met.append('macd_bullish')
        
        # Require 3 of 4 conditions
        if len(conditions_met) >= self.config['min_conditions']:
            reason = f"{len(conditions_met)}/4_conds:{','.join(conditions_met)}"
            return True, reason
        
        return False, f"only_{len(conditions_met)}_conditions"
    
    def can_trade_this_month(self, timestamp: datetime, symbol: str) -> bool:
        """Check if monthly trade limit allows trading"""
        month_key = (symbol, timestamp.year, timestamp.month)
        trades_this_month = self.monthly_trades.get(month_key, 0)
        return trades_this_month < self.config['max_trades_per_month']
    
    def record_trade(self, timestamp: datetime, symbol: str):
        """Record a trade for monthly limit tracking"""
        month_key = (symbol, timestamp.year, timestamp.month)
        self.monthly_trades[month_key] = self.monthly_trades.get(month_key, 0) + 1
    
    def get_stop_loss(self, entry_price: float, hold_days: int) -> float:
        """
        Calculate stop loss based on holding period
        
        During minimum hold (< 7 days): 8% stop
        After minimum hold: 3% stop
        """
        if hold_days < self.config['min_hold_days']:
            stop_pct = self.config['initial_stop_pct']
        else:
            stop_pct = self.config['regular_stop_pct']
        
        return entry_price * (1 - stop_pct)
    
    def get_take_profits(self, entry_price: float) -> list:
        """
        Get take profit levels
        
        Returns:
            [
                {'price': float, 'size_pct': 0.50},  # TP1: 15%, close 50%
                {'price': float, 'size_pct': 0.50},  # TP2: 30%, close 50%
            ]
        """
        tp1_price = entry_price * (1 + self.config['tp1_pct'])
        tp2_price = entry_price * (1 + self.config['tp2_pct'])
        
        return [
            {'price': tp1_price, 'size_pct': self.config['tp1_size']},
            {'price': tp2_price, 'size_pct': 0.50},  # Remaining 50%
        ]
    
    def get_trailing_stop_pct(self) -> float:
        """Get trailing stop percentage (5% from highest)"""
        return self.config['trailing_stop_pct']
    
    def get_min_hold_days(self) -> int:
        """Minimum hold period: 7 days"""
        return self.config['min_hold_days']
    
    def get_max_hold_days(self) -> int:
        """Maximum hold period: 90 days"""
        return self.config['max_hold_days']
    
    def get_position_size_pct(self) -> float:
        """Position size: 40% of capital"""
        return self.config['position_size_pct']
