"""
Trade Safety Gates - Non-negotiable rules before executing any trade
Enforces: Dynamic balance sizing, confidence gates, position limits, safety circuits
"""
from typing import Dict, Optional
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


class TradeSafetyGates:
    """Enforce strict safety rules before allowing any trade execution"""
    
    # Safety thresholds
    MIN_24H_VOLUME_USD = 50_000_000  # $50M minimum liquidity
    MAX_SPREAD_PERCENT = 0.15  # 0.15% max spread
    MAX_POSITION_SIZE_PERCENT = 2.0  # 2% account risk max
    MIN_RSI = 25  # Avoid extremely oversold
    MAX_RSI = 78  # Avoid overextended
    
    @staticmethod
    def validate_trade(
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
        
        # Gate 1: AI Action must be BUY
        if ai_decision.get('action') != 'BUY':
            return False, "AI decision is not BUY"
        
        # Gate 2: Liquidity Check
        if volume_24h_usd < TradeSafetyGates.MIN_24H_VOLUME_USD:
            return False, f"Insufficient liquidity: ${volume_24h_usd/1e6:.1f}M < $50M"
        
        # Gate 3: Confidence Threshold - ✅ ENFORCED per best practices
        confidence = ai_decision.get('confidence', 0)
        if confidence < MIN_CONFIDENCE_TO_TRADE:
            return False, f"Low confidence: {confidence}% < {MIN_CONFIDENCE_TO_TRADE}%"
        
        # Gate 4: RSI Range
        if rsi < TradeSafetyGates.MIN_RSI:
            return False, f"RSI too low (extreme oversold): {rsi:.0f}"
        if rsi > TradeSafetyGates.MAX_RSI:
            return False, f"RSI overextended: {rsi:.0f} > {TradeSafetyGates.MAX_RSI}"
        
        # Gate 5: Position Limit - ✅ REDUCED to 2 per best practices
        if active_positions >= MAX_OPEN_POSITIONS:
            return False, f"Max positions reached: {active_positions}/{MAX_OPEN_POSITIONS}"
        
        # Gate 6: Account Balance Check
        if account_balance < 10:  # Minimum $10 to trade
            return False, f"Insufficient balance: ${account_balance:.2f}"
        
        # All gates passed
        logger.info(f"✅ All safety gates passed for {symbol}")
        return True, None
    
    @staticmethod
    def calculate_position_size(
        account_balance: float,
        current_price: float,
        atr_percent: float,
    ) -> tuple[float, float]:
        """
        ✅ FIXED: Calculate position size from DYNAMIC account balance
        NOT from hardcoded starting capital
        
        Args:
            account_balance: Current FREE balance (not starting capital!)
            current_price: Entry price
            atr_percent: ATR as percentage
        
        Returns:
            (quantity, position_value_usd)
        """
        # ✅ Apply 90% buffer to account balance (10% safety margin for fees/slippage)
        usable_balance = account_balance * BALANCE_BUFFER_PERCENT
        
        # Risk percentage per trade (1.5%)
        risk_amount = usable_balance * (RISK_PER_TRADE_PERCENT / 100)
        
        # Position value based on risk and volatility (ATR)
        # If ATR is 3%, position_value = risk / 0.03
        if atr_percent > 0:
            position_value = risk_amount / (atr_percent / 100)
        else:
            position_value = risk_amount
        
        # ✅ Cap at max 2% of account per position (never exceed)
        position_value = min(
            position_value,
            usable_balance * (MAX_POSITION_EXPOSURE_PERCENT / 100)
        )
        
        # ✅ Final safety check: must have balance for the trade
        if position_value > usable_balance:
            logger.warning(f"Position size ${position_value:.2f} exceeds usable balance ${usable_balance:.2f}")
            position_value = usable_balance * 0.5  # Use only 50% if unsure
        
        # Calculate quantity
        quantity = position_value / current_price if current_price > 0 else 0
        
        logger.info(
            f"✅ Dynamic position sizing: "
            f"{quantity:.6f} units (${position_value:.2f}) from balance ${account_balance:.2f}"
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
