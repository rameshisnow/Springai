"""Generic entry strategy for additional tracked coins.

Purpose:
- Provide Tier-1 screening (entry yes/no + reason) for coins that are tracked
  but should NOT receive Goldilock exits.

Design goals:
- Conservative, simple, explainable.
- Uses similar indicators to Goldilock, but without coin-specific tuning.
- Exits are intentionally generic and should not be used in live exit wiring.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

from .base_strategy import BaseStrategy


class GenericEntryStrategy(BaseStrategy):
    """A lightweight strategy used only for entry screening."""

    DEFAULT_CONFIG: Dict = {
        # Entry conditions (4H)
        "rsi_entry": 45,  # less strict than Goldilock's 40
        "min_conditions": 3,
        "require_daily_trend": True,
        "volume_spike": 1.2,

        # Exit placeholders (NOT used for live exit logic)
        "initial_stop_pct": 0.03,
        "regular_stop_pct": 0.03,
        "tp1_pct": 0.03,
        "tp2_pct": 0.05,
        "tp1_size": 0.50,
        "trailing_stop_pct": 0.02,

        # Holding period placeholders
        "min_hold_days": 0,
        "max_hold_days": 90,

        # Sizing placeholder
        "position_size_pct": 0.10,

        # Monthly limit: keep the system-wide TradeSafetyGates monthly limit behavior
        # only for Goldilock. For generic, we do not enforce per-strategy monthly caps.
        "max_trades_per_month": 999,
    }

    def __init__(self, config: Optional[Dict] = None):
        final_config = self.DEFAULT_CONFIG.copy()
        if config:
            final_config.update(config)
        super().__init__(final_config)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # EMAs
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()

        # RSI (14)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # Volume ratio
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]

        # MACD
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_bullish"] = df["macd"] > df["macd_signal"]

        return df

    def check_entry(
        self,
        df_1h: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_daily: pd.DataFrame,
        current_idx: int,
    ) -> Tuple[bool, str]:
        df_4h = self.calculate_indicators(df_4h)

        if current_idx < 0:
            current_idx = len(df_4h) + current_idx
        if current_idx >= len(df_4h) or current_idx < 0:
            return False, "invalid_index"

        current_time = df_4h.index[current_idx]

        # Daily trend filter
        df_daily = self.calculate_indicators(df_daily)
        daily_bars_before = df_daily[df_daily.index <= current_time]
        if len(daily_bars_before) == 0:
            return False, "no_daily_data"

        daily_close = daily_bars_before["close"].iloc[-1]
        daily_ema50 = daily_bars_before["ema_50"].iloc[-1]
        if pd.isna(daily_close) or pd.isna(daily_ema50):
            return False, "daily_indicators_na"

        if bool(self.config.get("require_daily_trend", True)) and daily_close <= daily_ema50:
            return False, "daily_trend_bearish"

        # 4H condition set
        ema_cross = df_4h["ema_9"].iloc[current_idx] > df_4h["ema_21"].iloc[current_idx]
        rsi_val = df_4h["rsi"].iloc[current_idx]
        vol_ratio = df_4h["volume_ratio"].iloc[current_idx]
        macd_bullish = bool(df_4h["macd_bullish"].iloc[current_idx])

        conditions_met = []
        if ema_cross:
            conditions_met.append("ema_cross")
        if (not pd.isna(rsi_val)) and (rsi_val < float(self.config.get("rsi_entry", 45))):
            conditions_met.append("rsi_oversold")
        if (not pd.isna(vol_ratio)) and (vol_ratio > float(self.config.get("volume_spike", 1.2))):
            conditions_met.append("volume_spike")
        if macd_bullish:
            conditions_met.append("macd_bullish")

        required = int(self.config.get("min_conditions", 3))
        if len(conditions_met) >= required:
            return True, f"generic_{len(conditions_met)}/4:{','.join(conditions_met)}"

        return False, f"generic_only_{len(conditions_met)}_conditions"

    # The following methods are placeholders to satisfy BaseStrategy.
    # Live exit logic is intentionally handled elsewhere (generic exits).

    def get_stop_loss(self, entry_price: float, hold_days: int) -> float:
        stop_pct = float(self.config.get("regular_stop_pct", 0.03))
        return entry_price * (1 - stop_pct)

    def get_take_profits(self, entry_price: float) -> list:
        tp1_price = entry_price * (1 + float(self.config.get("tp1_pct", 0.03)))
        tp2_price = entry_price * (1 + float(self.config.get("tp2_pct", 0.05)))
        return [
            {"price": tp1_price, "size_pct": float(self.config.get("tp1_size", 0.5))},
            {"price": tp2_price, "size_pct": 0.50},
        ]

    def get_trailing_stop_pct(self) -> float:
        return float(self.config.get("trailing_stop_pct", 0.02))

    def get_min_hold_days(self) -> int:
        return int(self.config.get("min_hold_days", 0))

    def get_max_hold_days(self) -> int:
        return int(self.config.get("max_hold_days", 90))

    def get_position_size_pct(self) -> float:
        return float(self.config.get("position_size_pct", 0.10))
