"""
Strategy Manager - Maps coins to their specific trading strategies
"""
from typing import Dict, Optional
from .base_strategy import BaseStrategy
from .goldilock_strategy import GoldilockStrategy
from .generic_entry_strategy import GenericEntryStrategy


class StrategyManager:
    """
    Manages coin-specific trading strategies
    
    Usage:
        manager = StrategyManager()
        strategy = manager.get_strategy('DOGEUSDT')
        should_enter, reason = strategy.check_entry(...)
    """
    
    def __init__(self):
        """Initialize strategy manager"""
        self.strategies = {}
        self.coin_strategy_map = {}
        
        # Register strategies
        self._register_strategies()
    
    def _register_strategies(self):
        """Register available strategies and map coins to them"""
        
        # Create Goldilock strategy instance
        goldilock = GoldilockStrategy()
        self.strategies['goldilock'] = goldilock

        # Create Generic Entry strategy instance (for additional tracked coins)
        generic_entry = GenericEntryStrategy()
        self.strategies['generic_entry'] = generic_entry

        # Map coins to Goldilock strategy (LIVE SCOPE)
        goldilock_coins = ['DOGEUSDT', 'SHIBUSDT', 'SOLUSDT']
        for coin in goldilock_coins:
            self.coin_strategy_map[coin] = 'goldilock'

        # Map additional tracked coins to generic entry strategy.
        # NOTE: This is entry-only; exit wiring remains generic because RiskManager
        # applies Goldilock exits only for DOGE/SHIB/SOL.
        for coin in ['PEPEUSDT', 'ENAUSDT', 'SUIUSDT', 'TRXUSDT']:
            self.coin_strategy_map[coin] = 'generic_entry'
    
    def get_strategy(self, symbol: str) -> Optional[BaseStrategy]:
        """
        Get strategy for a specific coin
        
        Args:
            symbol: Trading pair symbol (e.g., 'DOGEUSDT')
            
        Returns:
            Strategy instance or None if no strategy assigned
        """
        strategy_name = self.coin_strategy_map.get(symbol)
        if strategy_name:
            return self.strategies.get(strategy_name)
        return None
    
    def get_all_tracked_coins(self) -> list:
        """Get list of all coins that are tracked (strategy or generic)."""
        return [symbol for symbol in self.coin_strategy_map.keys() if isinstance(symbol, str) and symbol]
    
    def has_strategy(self, symbol: str) -> bool:
        """Check if a coin has a strategy assigned"""
        return symbol in self.coin_strategy_map
    
    def get_strategy_info(self, symbol: str) -> Dict:
        """Get information about the strategy for a coin"""
        strategy = self.get_strategy(symbol)
        if strategy:
            return {
                'name': strategy.name,
                'position_size_pct': strategy.get_position_size_pct(),
                'min_hold_days': strategy.get_min_hold_days(),
                'max_hold_days': strategy.get_max_hold_days(),
                'config': strategy.config,
            }
        return {}
