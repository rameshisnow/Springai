"""
Goldilock Strategy - Optimized for DOGE, SHIB, SOL

Key Features:
- RSI < 40 oversold entry
- 3/4 conditions required (EMA, RSI, Volume, MACD)
- Daily trend filter (price > daily EMA50)
- 7-day minimum hold with 8% stop
- After 7 days: 3% stop, 15%/30% TPs, 5% trailing
- Position size is managed by portfolio allocation (live)
- Max 1 trade per month per coin
"""
from typing import Dict, Tuple, Optional
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
        'position_size_pct': 0.20,   # Placeholder; live sizing uses portfolio allocation
        
        # Trade frequency
        'max_trades_per_month': 1,

        # End-of-month (EOM) quality filter
        # Applies a stricter entry gate during the last N days of the UTC month.
        'eom_filter_days': 3,
        'eom_require_all_conditions': True,  # require 4/4 instead of min_conditions
        'eom_min_rsi': 35,
        'eom_min_volume_ratio': 1.5,
        'eom_min_quality_score': 85,
    }
    
    def __init__(self, config: Optional[Dict] = None):
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

    def _is_end_of_month_utc(self, timestamp: pd.Timestamp) -> tuple[bool, int]:
        """Return (is_eom, days_until_month_end) using UTC calendar month."""
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')
        else:
            ts = ts.tz_convert('UTC')

        month_end = ts + pd.offsets.MonthEnd(0)
        days_until_month_end = (month_end.normalize() - ts.normalize()).days
        return days_until_month_end < int(self.config.get('eom_filter_days', 0)), days_until_month_end

    def _calculate_setup_quality_score(self, df_4h: pd.DataFrame, idx: int, df_daily: pd.DataFrame) -> int:
        """Compute a 0-100 quality score similar to the provided EOM reference."""
        score = 0

        rsi_val = df_4h['rsi'].iloc[idx]
        if not pd.isna(rsi_val):
            if rsi_val < 30:
                score += 25
            elif rsi_val < 35:
                score += 20
            elif rsi_val < 40:
                score += 15
            elif rsi_val < 45:
                score += 5

        vol_ratio = df_4h['volume_ratio'].iloc[idx]
        if not pd.isna(vol_ratio):
            if vol_ratio > 2.0:
                score += 25
            elif vol_ratio > 1.5:
                score += 20
            elif vol_ratio > 1.3:
                score += 15
            elif vol_ratio > 1.1:
                score += 5

        trend_score = 0
        if df_4h['ema_9'].iloc[idx] > df_4h['ema_21'].iloc[idx]:
            trend_score += 10
        if df_4h['ema_21'].iloc[idx] > df_4h['ema_50'].iloc[idx]:
            trend_score += 10
        score += trend_score

        macd_strength = (df_4h['macd'].iloc[idx] - df_4h['macd_signal'].iloc[idx]) / df_4h['close'].iloc[idx]
        if not pd.isna(macd_strength):
            if macd_strength > 0.005:
                score += 15
            elif macd_strength > 0.002:
                score += 10
            elif bool(df_4h['macd_bullish'].iloc[idx]):
                score += 5

        current_time = df_4h.index[idx]
        daily_bars_before = df_daily[df_daily.index <= current_time]
        if len(daily_bars_before) > 0:
            daily_close = daily_bars_before['close'].iloc[-1]
            daily_ema50 = daily_bars_before['ema_50'].iloc[-1]
            if not pd.isna(daily_close) and not pd.isna(daily_ema50) and daily_ema50 != 0:
                daily_trend_strength = (daily_close - daily_ema50) / daily_ema50
                if daily_trend_strength > 0.10:
                    score += 15
                elif daily_trend_strength > 0.05:
                    score += 10
                elif daily_trend_strength > 0:
                    score += 5

        return int(min(score, 100))
    
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
        
        # Build the 4H condition set (EMA/RSI/Volume/MACD)
        ema_cross = df_4h['ema_9'].iloc[current_idx] > df_4h['ema_21'].iloc[current_idx]
        rsi_val = df_4h['rsi'].iloc[current_idx]
        vol_ratio = df_4h['volume_ratio'].iloc[current_idx]
        macd_bullish = bool(df_4h['macd_bullish'].iloc[current_idx])

        # Apply EOM quality filter only in last N days of month (UTC)
        is_eom, days_left = self._is_end_of_month_utc(pd.Timestamp(current_time))
        quality_score = self._calculate_setup_quality_score(df_4h, current_idx, df_daily)
        if is_eom and int(self.config.get('eom_filter_days', 0)) > 0:
            if quality_score < int(self.config.get('eom_min_quality_score', 0)):
                return False, f"eom_low_quality_{quality_score}"

            eom_rsi_ok = (not pd.isna(rsi_val)) and (rsi_val < float(self.config.get('eom_min_rsi', self.config['rsi_entry'])))
            eom_vol_ok = (not pd.isna(vol_ratio)) and (vol_ratio > float(self.config.get('eom_min_volume_ratio', self.config['volume_spike'])))

            conditions_met = []
            if ema_cross:
                conditions_met.append('ema_cross')
            if eom_rsi_ok:
                conditions_met.append('rsi_oversold')
            if eom_vol_ok:
                conditions_met.append('volume_spike')
            if macd_bullish:
                conditions_met.append('macd_bullish')

            required = 4 if bool(self.config.get('eom_require_all_conditions', True)) else int(self.config.get('min_conditions', 3))
            if len(conditions_met) < required:
                return False, f"eom_only_{len(conditions_met)}_conditions"

            # Additional EOM daily strength: price must be > 2% above daily EMA50
            if daily_close <= daily_ema50 * 1.02:
                return False, "eom_weak_daily_trend"

            reason = f"eom_strong_{len(conditions_met)}/4:{quality_score}:days_left_{days_left}"
            return True, reason

        # Normal (non-EOM) entry rules
        conditions_met = []
        if ema_cross:
            conditions_met.append('ema_cross')
        if not pd.isna(rsi_val) and rsi_val < self.config['rsi_entry']:
            conditions_met.append('rsi_oversold')
        if not pd.isna(vol_ratio) and vol_ratio > self.config['volume_spike']:
            conditions_met.append('volume_spike')
        if macd_bullish:
            conditions_met.append('macd_bullish')

        if len(conditions_met) >= self.config['min_conditions']:
            reason = f"{len(conditions_met)}/4_conds:{quality_score}:{','.join(conditions_met)}"
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
        """Placeholder position sizing (overridden by portfolio allocation in live)."""
        return self.config['position_size_pct']
