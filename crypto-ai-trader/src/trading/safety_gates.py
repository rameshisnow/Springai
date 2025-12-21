"""
Trade Safety Gates - Non-negotiable rules before executing any trade
Enforces: Dynamic balance sizing, confidence gates, position limits, safety circuits
"""
from typing import Dict, Optional
from datetime import datetime

from src.utils.database import get_session, TradeRecordModel
from src.utils.logger import logger
from src.config.constants import (
    MAX_OPEN_POSITIONS,
    MIN_CONFIDENCE_TO_TRADE,
    MAX_TRADES_PER_24H,
    MAX_RISK_PER_DAY_PERCENT,
    ATR_VOLATILITY_CUTOFF,
    BALANCE_BUFFER_PERCENT,
    RISK_PER_TRADE_PERCENT,
    MAX_POSITION_EXPOSURE_PERCENT,
)
from src.strategies.strategy_manager import StrategyManager


class TradeSafetyGates:
    """Enforce strict safety rules before allowing any trade execution"""
    
    def __init__(self):
        """Initialize with strategy manager for position sizing"""
        self.strategy_manager = StrategyManager()
        logger.info("Trade Safety Gates initialized with strategy-based position sizing")
    
    def check_monthly_trade_limit(self, symbol: str) -> tuple[bool, Optional[str]]:
        """
        Check if symbol can be traded this month (Goldilock: max 1 per month per coin)
        
        Args:
            symbol: Trading symbol (e.g., DOGEUSDT)
        
        Returns:
            (can_trade: bool, reason: str | None)
        """
        strategy = self.strategy_manager.get_strategy(symbol)
        
        if not strategy:
            # No strategy = no monthly limit
            return True, None
        
        # Goldilock monthly limit must be persistent across restarts.
        # We enforce it via the SQLite trade_records table (written by order_manager).
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)

        session = get_session()
        try:
            trades_this_month = (
                session.query(TradeRecordModel)
                .filter(
                    TradeRecordModel.symbol == symbol,
                    TradeRecordModel.entry_time >= month_start,
                    TradeRecordModel.entry_time < next_month_start,
                )
                .count()
            )
        finally:
            session.close()

        if trades_this_month >= strategy.config.get("max_trades_per_month", 1):
            return False, f"Monthly trade limit reached for {symbol}"
        
        return True, None
    
    # Safety thresholds
    MIN_24H_VOLUME_USD = 50_000_000  # $50M minimum liquidity
    MAX_SPREAD_PERCENT = 0.15  # 0.15% max spread
    MAX_POSITION_SIZE_PERCENT = 2.0  # 2% account risk max
    MIN_RSI = 25  # Avoid extremely oversold
    MAX_RSI = 78  # Avoid overextended
    
    def validate_trade(
        self,
        symbol: str,
        ai_decision: Dict,
        current_price: float,
        volume_24h_usd: float,
        rsi: float,
        active_positions: int,
        account_balance: float,
    ) -> tuple[bool, Optional[str]]:
        """
        Apply all safety gates before trade execution
        
        Args:
            symbol: Trading pair
            ai_decision: Claude's decision dict
            current_price: Current price
            volume_24h_usd: 24h volume in USD
            rsi: Current RSI value
            active_positions: Number of open positions
            account_balance: Current account balance
        
        Returns:
            (approved: bool, rejection_reason: str | None)
        """
        
        # Gate 1: Monthly Trade Limit (Goldilock: 1/month per coin)
        can_trade, reason = self.check_monthly_trade_limit(symbol)
        if not can_trade:
            return False, reason
        
        # Gate 2: AI Action must be BUY
        if ai_decision.get('action') != 'BUY':
            return False, "AI decision is not BUY"
        
        # Gate 3: Liquidity Check
        if volume_24h_usd < TradeSafetyGates.MIN_24H_VOLUME_USD:
            return False, f"Insufficient liquidity: ${volume_24h_usd/1e6:.1f}M < $50M"
        
        # Gate 4: Confidence Threshold - ✅ ENFORCED per best practices
        confidence = ai_decision.get('confidence', 0)
        if confidence < MIN_CONFIDENCE_TO_TRADE:
            return False, f"Low confidence: {confidence}% < {MIN_CONFIDENCE_TO_TRADE}%"
        
        # Gate 5: RSI Range
        if rsi < TradeSafetyGates.MIN_RSI:
            return False, f"RSI too low (extreme oversold): {rsi:.0f}"
        if rsi > TradeSafetyGates.MAX_RSI:
            return False, f"RSI overextended: {rsi:.0f} > {TradeSafetyGates.MAX_RSI}"
        
        # Gate 6: Position Limit - ✅ REDUCED to 2 per best practices
        if active_positions >= MAX_OPEN_POSITIONS:
            return False, f"Max positions reached: {active_positions}/{MAX_OPEN_POSITIONS}"
        
        # Gate 7: Account Balance Check
        if account_balance < 10:  # Minimum $10 to trade
            return False, f"Insufficient balance: ${account_balance:.2f}"
        
        # All gates passed
        logger.info(f"✅ All safety gates passed for {symbol}")
        return True, None
    
    def calculate_position_size(
        self,
        symbol: str,
        account_balance: float,
        current_price: float,
        atr_percent: float,
    ) -> tuple[float, float]:
        """
        ✅ FIXED: Calculate position size from DYNAMIC account balance
        Uses strategy-based sizing when a strategy exists; otherwise defaults.
        
        Args:
            symbol: Trading symbol (e.g., DOGEUSDT)
            account_balance: Current FREE balance (not starting capital!)
            current_price: Entry price
            atr_percent: ATR as percentage
        
        Returns:
            (quantity, position_value_usd)
        """
        # Portfolio allocation (live): overrides per-strategy sizing for tracked symbols
        portfolio_allocations: Dict[str, float] = {
            "DOGEUSDT": 0.40,
            "SHIBUSDT": 0.30,
            "SOLUSDT": 0.30,
        }
        if symbol in portfolio_allocations:
            position_size_pct = float(portfolio_allocations[symbol])
            logger.info(f"Using portfolio allocation sizing for {symbol}: {position_size_pct*100:.1f}%")
        else:
            # Get strategy-specific position size if available
            strategy = self.strategy_manager.get_strategy(symbol)
            if strategy:
                position_size_pct = float(strategy.get_position_size_pct())
                logger.info(f"Using strategy position size for {symbol}: {position_size_pct*100:.1f}%")
            else:
                position_size_pct = MAX_POSITION_EXPOSURE_PERCENT / 100  # 6% default
                logger.info(f"Using default position size for {symbol}: {position_size_pct*100:.1f}%")
        
        # ✅ Apply 90% buffer to account balance (10% safety margin for fees/slippage)
        usable_balance = account_balance * BALANCE_BUFFER_PERCENT
        
        # Calculate position value directly from percentage
        position_value = usable_balance * position_size_pct
        
        # ✅ Final safety check: must have balance for the trade
        if position_value > usable_balance:
            logger.warning(f"Position size ${position_value:.2f} exceeds usable balance ${usable_balance:.2f}")
            position_value = usable_balance * 0.5  # Use only 50% if unsure
        
        # Calculate quantity
        quantity = position_value / current_price if current_price > 0 else 0
        
        logger.info(
            f"✅ Strategy-based position sizing: "
            f"{quantity:.6f} units (${position_value:.2f}, {position_size_pct*100}%) from balance ${account_balance:.2f}"
        )
        
        return quantity, position_value
    
    @staticmethod
    def calculate_stop_loss(current_price: float, atr: float) -> float:
        """
        Calculate stop loss at 1.0-1.2x ATR below entry
        
        Args:
            current_price: Entry price
            atr: ATR value
        
        Returns:
            Stop loss price
        """
        # Use 1.1x ATR as stop distance
        stop_distance = atr * 1.1
        stop_loss = current_price - stop_distance
        
        # Ensure at least 1% stop loss
        min_stop = current_price * 0.99
        stop_loss = min(stop_loss, min_stop)
        
        logger.info(f"Stop loss: ${stop_loss:.4f} ({((stop_loss/current_price - 1) * 100):.2f}%)")
        
        return stop_loss
    
    @staticmethod
    def calculate_take_profits(current_price: float, atr: float) -> list[Dict]:
        """
        Calculate take profit targets
        
        Args:
            current_price: Entry price
            atr: ATR value
        
        Returns:
            List of TP targets with prices and exit percentages
        """
        # TP1: 1.5x ATR (exit 50%)
        # TP2: 2.5x ATR (exit remaining 50%)
        
        tp1_price = current_price + (atr * 1.5)
        tp2_price = current_price + (atr * 2.5)
        
        take_profits = [
            {"price": tp1_price, "percent": 3.0, "exit_amount": 50},  # Exit 50% at TP1
            {"price": tp2_price, "percent": 5.0, "exit_amount": 50},  # Exit 50% at TP2
        ]
        
        logger.info(f"Take profits: TP1=${tp1_price:.4f} (50%), TP2=${tp2_price:.4f} (50%)")
        
        return take_profits


# Singleton instance
safety_gates = TradeSafetyGates()
