"""
Base strategy class for all coin-specific strategies
"""
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional
import pandas as pd


class BaseStrategy(ABC):
    """Base class for trading strategies"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    def check_entry(self, df_1h: pd.DataFrame, df_4h: pd.DataFrame, 
                    df_daily: pd.DataFrame, current_idx: int) -> Tuple[bool, str]:
        """
        Check if entry conditions are met
        
        Returns:
            (should_enter, reason)
        """
        pass
    
    @abstractmethod
    def get_stop_loss(self, entry_price: float, hold_days: int) -> float:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            hold_days: Days position has been held
            
        Returns:
            Stop loss price
        """
        pass
    
    @abstractmethod
    def get_take_profits(self, entry_price: float) -> list:
        """
        Calculate take profit levels
        
        Returns:
            List of {'price': float, 'size_pct': float} dicts
        """
        pass
    
    @abstractmethod
    def get_trailing_stop_pct(self) -> float:
        """Get trailing stop percentage after TP1"""
        pass
    
    @abstractmethod
    def get_min_hold_days(self) -> int:
        """Get minimum holding period in days"""
        pass
    
    @abstractmethod
    def get_max_hold_days(self) -> int:
        """Get maximum holding period in days"""
        pass
    
    @abstractmethod
    def get_position_size_pct(self) -> float:
        """Get position size as percentage of capital"""
        pass
