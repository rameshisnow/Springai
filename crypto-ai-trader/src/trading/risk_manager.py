"""
Risk Management - Position sizing, stop-loss, profit-taking, circuit breakers
"""
import json
import os
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from src.utils.logger import risk_logger
from src.config.settings import config
from src.config.constants import (
    STARTING_CAPITAL_AUD,
    RISK_PER_TRADE_PERCENT,
    MAX_POSITION_SIZE_USD,
    KELLY_CRITERION_FRACTION,
    MAX_OPEN_POSITIONS,
    STOP_LOSS_PERCENT,
    TRAILING_STOP_PERCENT,
    TAKE_PROFIT_LEVELS,
    DAILY_MAX_LOSS_AUD,
    DAILY_MAX_LOSS_PERCENT,
    MAX_CONSECUTIVE_LOSSES,
    COOLDOWN_AFTER_LOSS_MINUTES,
    MAX_DRAWDOWN_PERCENT,
    MAX_POSITION_EXPOSURE_PERCENT,
    USE_DYNAMIC_BALANCE,
    BALANCE_BUFFER_PERCENT,
    GLOBAL_TRADING_PAUSE,
)


class Position:
    """Represents an open trading position"""
    
    def __init__(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        entry_time: datetime = None,
        stop_loss: float = None,
        take_profit_targets: list = None,
        status: str = "active",  # "active" or "dust" - dust positions don't count toward capacity
    ):
        self.symbol = symbol
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time or datetime.now()
        self.stop_loss = stop_loss
        self.take_profit_targets = take_profit_targets or []
        self.status = status  # Track whether position is active or dust
        self.closed = False
        self.exit_price = None
        self.exit_time = None
        self.pnl = 0.0
        self.pnl_percent = 0.0
        self.highest_price = entry_price
        self.current_price = entry_price  # Track latest price for dashboard display
        self.last_price_update = entry_time or datetime.now()  # Track when price was last updated
        self.tp1_hit = False  # Track if TP1 has been hit (for Goldilock trailing stop)
    
    def update_highest_price(self, current_price: float):
        """Track highest price for trailing stops"""
        if current_price > self.highest_price:
            self.highest_price = current_price
    
    def update_current_price(self, current_price: float):
        """Update current price for dashboard display (called every 5 min by position monitor)"""
        self.current_price = current_price
        self.last_price_update = datetime.now()
    
    def get_current_pnl(self, current_price: float) -> Tuple[float, float]:
        """Calculate current P&L"""
        pnl = (current_price - self.entry_price) * self.quantity
        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        return pnl, pnl_percent
    
    def close(self, exit_price: float, exit_time: datetime = None):
        """Close position and mark as dust (no longer counts toward capacity)"""
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.now()
        self.pnl = (exit_price - self.entry_price) * self.quantity
        self.pnl_percent = ((exit_price - self.entry_price) / self.entry_price) * 100
        self.closed = True
        self.status = "dust"  # Mark as dust so it doesn't count toward capacity limits


class RiskManager:
    """Manage trading risk, position sizing, and circuit breakers"""
    
    def __init__(self, starting_capital: float = STARTING_CAPITAL_AUD):
        """
        Initialize risk manager
        
        Args:
            starting_capital: Starting capital in AUD (used as fallback if dynamic balance fails)
        """
        # Try to fetch actual USDT balance from Binance
        actual_balance = self._fetch_usdt_balance_from_binance()
        
        if actual_balance is not None and actual_balance > 0:
            # Use dynamic balance from Binance
            self.starting_capital = actual_balance
            self.current_balance = actual_balance * BALANCE_BUFFER_PERCENT  # Apply buffer
            self.balance_source = "BINANCE (DYNAMIC)"
            risk_logger.info(f"✅ Fetched USDT balance from Binance: ${actual_balance:.2f}")
            risk_logger.info(f"   Using 90% for trading (10% buffer): ${self.current_balance:.2f}")
        else:
            # Fallback to configured capital
            self.starting_capital = starting_capital
            self.current_balance = starting_capital
            self.balance_source = "CONFIG (FALLBACK)"
            risk_logger.warning(f"⚠️  Could not fetch balance from Binance, using configured: ${starting_capital:.2f}")
        
        self.positions: Dict[str, Position] = {}
        self.closed_positions = []
        self.positions_file = os.path.join(config.DATA_DIR, "positions.json")
        
        # Daily tracking
        self.daily_start_time = datetime.now().replace(hour=0, minute=0, second=0)
        self.daily_loss = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.last_loss_time = None
        self.circuit_breaker_active = False
        self.circuit_breaker_time = None
        
        # Portfolio metrics
        self.max_drawdown = 0.0
        self.peak_balance = self.current_balance
        
        # Load persisted positions on startup
        self._load_positions_from_file()
        
        risk_logger.info(f"Risk Manager initialized with capital: ${self.current_balance:.2f} ({self.balance_source})")
    
    def _fetch_usdt_balance_from_binance(self) -> Optional[float]:
        """
        Fetch actual USDT balance from Binance account
        
        Returns:
            USDT balance or None if fetch fails
        """
        if not USE_DYNAMIC_BALANCE:
            return None
        
        try:
            from src.trading.binance_client import binance_client
            
            # Get all balances
            balances = binance_client.get_account_balance()
            
            # Look for USDT balance
            usdt_balance = balances.get('USDT', 0.0)
            
            if usdt_balance > 0:
                return usdt_balance
            else:
                risk_logger.warning("No USDT balance found in Binance account")
                return None
        except Exception as e:
            risk_logger.error(f"Error fetching USDT balance from Binance: {e}")
            return None
    
    def sync_positions_from_binance(self):
        """
        Sync positions with actual Binance holdings
        Load any positions that exist on Binance but aren't tracked locally
        """
        try:
            from src.trading.binance_client import binance_client
            
            risk_logger.info("🔄 Syncing positions from Binance...")
            
            # Get all balances from Binance
            balances = binance_client.get_account_balance()
            
            # Track which coins have holdings
            holdings_to_add = {}
            
            for asset, amount in balances.items():
                if amount <= 0:
                    continue
                
                # Skip USDT (that's balance, not a position)
                if asset == 'USDT':
                    continue
                
                # Check if this position is already tracked
                symbol = f"{asset}USDT"
                if symbol in self.positions:
                    continue  # Already tracked
                
                # This is a position not yet tracked
                holdings_to_add[symbol] = amount
                risk_logger.warning(f"⚠️  Found untracked position: {symbol} ({amount:.8f})")
            
            # For each untracked holding, try to get entry price and add it
            if holdings_to_add:
                risk_logger.info(f"Found {len(holdings_to_add)} untracked holdings, adding to tracking...")
                
                for symbol, quantity in holdings_to_add.items():
                    try:
                        # Get current price as reference
                        current_price = binance_client.get_current_price(symbol)
                        
                        # Add to positions with current price as entry (best estimate)
                        position = Position(
                            symbol=symbol,
                            entry_price=current_price,
                            quantity=quantity,
                            stop_loss=current_price * 0.97,  # 3% SL
                            take_profit_targets=[
                                {"price": current_price * 1.05, "position_percent": 0.5},
                                {"price": current_price * 1.08, "position_percent": 0.5},
                            ]
                        )
                        
                        self.positions[symbol] = position
                        risk_logger.info(f"✅ Added untracked position: {symbol} ({quantity:.8f} @ ${current_price:.2f})")
                    except Exception as e:
                        risk_logger.error(f"Error adding position {symbol}: {e}")
            
            # Persist positions to file
            if holdings_to_add:
                self._save_positions_to_file()
            
            return len(holdings_to_add)
        except Exception as e:
            risk_logger.error(f"Error syncing positions from Binance: {e}")
            return 0
    
    def _save_positions_to_file(self):
        """Persist current positions to JSON file"""
        try:
            positions_data = {}
            for symbol, position in self.positions.items():
                positions_data[symbol] = {
                    'symbol': position.symbol,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'entry_time': position.entry_time.isoformat() if position.entry_time else None,
                    'stop_loss': position.stop_loss,
                    'take_profit_targets': position.take_profit_targets,
                    'current_price': position.current_price,
                    'last_price_update': position.last_price_update.isoformat() if position.last_price_update else None,
                    'status': position.status,  # Save status: active or dust
                }
            
            os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
            with open(self.positions_file, 'w') as f:
                json.dump(positions_data, f, indent=2)
            
            risk_logger.debug(f"💾 Saved {len(positions_data)} positions to {self.positions_file}")
        except Exception as e:
            risk_logger.error(f"Error saving positions to file: {e}")
    
    def _load_positions_from_file(self):
        """Load persisted positions from JSON file"""
        try:
            if not os.path.exists(self.positions_file):
                return
            
            with open(self.positions_file, 'r') as f:
                positions_data = json.load(f)
            
            risk_logger.info(f"📂 Loading {len(positions_data)} positions from file...")
            
            for symbol, pos_data in positions_data.items():
                try:
                    entry_time = datetime.fromisoformat(pos_data['entry_time']) if pos_data['entry_time'] else None
                    last_price_update = datetime.fromisoformat(pos_data['last_price_update']) if pos_data.get('last_price_update') else None
                    
                    # Validate and fix stop_loss if it's zero or invalid
                    stop_loss = pos_data['stop_loss']
                    if stop_loss == 0 or stop_loss is None:
                        stop_loss = pos_data['entry_price'] * 0.97  # Default 3% SL
                        risk_logger.warning(f"⚠️  {symbol}: Stop loss was 0, auto-calculated to ${stop_loss:.2f}")
                    
                    position = Position(
                        symbol=pos_data['symbol'],
                        entry_price=pos_data['entry_price'],
                        quantity=pos_data['quantity'],
                        entry_time=entry_time,
                        stop_loss=stop_loss,
                        take_profit_targets=pos_data['take_profit_targets'],
                        status=pos_data.get('status', 'active'),  # Load status: active or dust
                    )
                    
                    # Restore current price and last update time
                    if pos_data.get('current_price'):
                        position.current_price = pos_data['current_price']
                        risk_logger.info(f"   {symbol}: Entry=${pos_data['entry_price']:.2f}, Current=${pos_data['current_price']:.2f}, SL=${stop_loss:.2f}")
                    if last_price_update:
                        position.last_price_update = last_price_update
                    
                    self.positions[symbol] = position
                except Exception as e:
                    risk_logger.error(f"Error loading position {symbol}: {e}")
            
            if positions_data:
                risk_logger.info(f"✅ Loaded {len(self.positions)} persisted positions from file")
        except Exception as e:
            risk_logger.error(f"Error loading positions from file: {e}")
    
    
    def calculate_position_size(
        self,
        current_balance: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size using Kelly Criterion (conservative)
        
        Args:
            current_balance: Current account balance
            entry_price: Entry price for the trade
            stop_loss_price: Stop loss price
        
        Returns:
            Position size in quote currency
        """
        # Risk amount: 2% of balance per trade
        risk_amount = current_balance * (RISK_PER_TRADE_PERCENT / 100)
        
        # Loss per unit = entry - stop loss
        loss_per_unit = entry_price - stop_loss_price
        
        if loss_per_unit <= 0:
            risk_logger.warning("Invalid stop loss: must be below entry price")
            return 0.0
        
        # Position size = risk amount / loss per unit
        position_size = risk_amount / loss_per_unit
        
        # Cap at maximum position exposure
        max_exposure = current_balance * (MAX_POSITION_EXPOSURE_PERCENT / 100)
        position_size = min(position_size, max_exposure)
        
        risk_logger.info(
            f"Calculated position size: ${position_size:.2f} "
            f"(risk: ${risk_amount:.2f}, SL distance: ${loss_per_unit:.2f})"
        )
        
        return position_size
    
    def validate_trade(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> Tuple[bool, str]:
        """
        Validate if a trade meets risk criteria.
        Only counts positions with value >= $1 (filters dust positions < $1).
        
        Returns:
            (is_valid, message)
        """
        # Global kill switch
        if GLOBAL_TRADING_PAUSE:
            return False, "Global trading pause is enabled"

        # Check circuit breaker
        if self.is_circuit_breaker_active():
            return False, "Circuit breaker active - trading paused"
        
        # Check max concurrent positions (excluding dust positions < $1)
        meaningful_positions = 0
        for pos_symbol, position in self.positions.items():
            try:
                from src.trading.binance_client import binance_client
                current_price = binance_client.get_current_price(pos_symbol)
                position_value = position.quantity * current_price
                if position_value >= 1.0:
                    meaningful_positions += 1
            except Exception:
                # If we can't get price, count it to be safe
                meaningful_positions += 1
        
        if meaningful_positions >= MAX_OPEN_POSITIONS:
            return False, f"Max concurrent positions ({MAX_OPEN_POSITIONS}) reached (excluding dust < $1)"
        
        # Check daily loss limit
        if self.daily_loss >= DAILY_MAX_LOSS_AUD:
            return False, f"Daily loss limit (${DAILY_MAX_LOSS_AUD}) reached"
        
        # Check daily loss percentage
        daily_loss_percent = (self.daily_loss / self.starting_capital) * 100
        if daily_loss_percent >= DAILY_MAX_LOSS_PERCENT:
            return False, f"Daily loss limit ({DAILY_MAX_LOSS_PERCENT}%) reached"
        
        # Check position size (MAX_POSITION_SIZE_USD is calculated dynamically, so skip if None)
        position_exposure = quantity * entry_price
        if MAX_POSITION_SIZE_USD and position_exposure > MAX_POSITION_SIZE_USD * 1.5:
            return False, f"Position size too large: ${position_exposure:.2f}"
        
        # Check stop loss validity
        if stop_loss_price >= entry_price:
            return False, "Stop loss must be below entry price"
        
        # Check balance
        if quantity * entry_price > self.current_balance:
            return False, "Insufficient balance"
        
        # Check minimum position value (prevent dust positions)
        from src.config.constants import MIN_POSITION_VALUE_USD
        position_value_usd = quantity * entry_price
        if position_value_usd < MIN_POSITION_VALUE_USD:
            return False, f"Position value ${position_value_usd:.2f} below minimum ${MIN_POSITION_VALUE_USD}"
        
        return True, "Trade valid"
    
    def add_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        stop_loss_price: float,
        take_profit_targets: list = None,
    ) -> Optional[Position]:
        """
        Add new position to tracking
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            quantity: Position quantity
            stop_loss_price: Stop loss price
            take_profit_targets: Claude's suggested TP levels (if None, use hardcoded fallback)
        
        Returns:
            Position object or None if invalid
        """
        is_valid, message = self.validate_trade(symbol, quantity, entry_price, stop_loss_price)
        if not is_valid:
            risk_logger.warning(f"Trade rejected: {message}")
            return None
        
        # Use provided take profit targets (from Claude) or calculate default ones
        tp_targets = take_profit_targets if take_profit_targets else self._calculate_take_profit_targets(entry_price)
        
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss_price,
            take_profit_targets=tp_targets,
        )
        
        self.positions[symbol] = position
        self._save_positions_to_file()  # Persist position
        risk_logger.info(
            f"Position added: {symbol} - Entry: ${entry_price:.2f}, "
            f"Qty: {quantity:.8f}, SL: ${stop_loss_price:.2f}"
        )
        
        return position
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
    ) -> Dict[str, any]:
        """
        Update position P&L and check exit conditions
        
        Returns:
            Dictionary with position status and any exit signals
        """
        if symbol not in self.positions:
            return {}
        
        position = self.positions[symbol]
        pnl, pnl_percent = position.get_current_pnl(current_price)
        position.update_highest_price(current_price)
        
        result = {
            "symbol": symbol,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_signal": None,
            "reason": "",
        }
        
        # Check stop loss
        if current_price <= position.stop_loss:
            result["exit_signal"] = "STOP_LOSS"
            result["reason"] = f"Hit stop loss at ${current_price:.2f}"
            return result
        
        # Check trailing stop
        trailing_stop = position.highest_price * (1 - TRAILING_STOP_PERCENT / 100)
        if current_price <= trailing_stop:
            result["exit_signal"] = "TRAILING_STOP"
            result["reason"] = f"Trailing stop activated at ${current_price:.2f}"
            return result
        
        # Check take profit targets
        for i, target in enumerate(position.take_profit_targets):
            if current_price >= target['price'] and not target['hit']:
                result["exit_signal"] = "TAKE_PROFIT"
                result["take_profit_level"] = i + 1
                result["reason"] = f"Take profit {i+1} hit at ${current_price:.2f}"
                target['hit'] = True
                # Partial exit, don't close position yet
                return result
        
        return result
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "Manual",
    ) -> Optional[Position]:
        """Close a position"""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        position.close(exit_price)
        
        # Track daily loss/gain
        if position.pnl < 0:
            self.daily_loss += abs(position.pnl)
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now()
            risk_logger.warning(
                f"Loss closed: {symbol} - Loss: ${position.pnl:.2f} "
                f"({position.pnl_percent:.2f}%) - Reason: {reason}"
            )
        else:
            self.consecutive_losses = 0
            risk_logger.info(
                f"Profit closed: {symbol} - Profit: ${position.pnl:.2f} "
                f"({position.pnl_percent:.2f}%) - Reason: {reason}"
            )
        
        # Update balance
        self.current_balance += position.pnl
        self.closed_positions.append(position)
        del self.positions[symbol]
        self._save_positions_to_file()  # Persist after closing
        
        # Check circuit breaker
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.activate_circuit_breaker()
        
        return position
    
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage"""
        if self.peak_balance == 0:
            return 0.0
        
        current_total = self.current_balance + sum(
            p.entry_price * p.quantity for p in self.positions.values()
        )
        
        drawdown = ((self.peak_balance - current_total) / self.peak_balance) * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)
        
        return drawdown
    
    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is active"""
        if not self.circuit_breaker_active:
            return False
        
        # Check if cooldown period has passed
        if datetime.now() - self.circuit_breaker_time > timedelta(hours=24):
            self.circuit_breaker_active = False
            risk_logger.info("Circuit breaker deactivated - recovery period passed")
            return False
        
        return True
    
    def activate_circuit_breaker(self):
        """Activate circuit breaker after max consecutive losses"""
        self.circuit_breaker_active = True
        self.circuit_breaker_time = datetime.now()
        risk_logger.critical(
            f"CIRCUIT BREAKER ACTIVATED - {self.consecutive_losses} consecutive losses. "
            f"Trading paused for 24 hours."
        )
    
    def is_in_cooldown(self) -> bool:
        """Check if position is in cooldown after loss"""
        if not self.last_loss_time:
            return False
        
        return datetime.now() - self.last_loss_time < timedelta(minutes=COOLDOWN_AFTER_LOSS_MINUTES)
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary"""
        open_pnl = sum(
            (p.entry_price * p.quantity) - (p.entry_price * p.quantity)
            for p in self.positions.values()
        )
        
        closed_pnl = sum(p.pnl for p in self.closed_positions)
        
        total_pnl = open_pnl + closed_pnl
        total_pnl_percent = (total_pnl / self.starting_capital) * 100
        
        return {
            "starting_capital": self.starting_capital,
            "current_balance": self.current_balance,
            "open_positions": len(self.positions),
            "closed_trades": len(self.closed_positions),
            "open_pnl": open_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "daily_loss": self.daily_loss,
            "consecutive_losses": self.consecutive_losses,
            "current_drawdown": self.calculate_drawdown(),
            "max_drawdown": self.max_drawdown,
            "circuit_breaker_active": self.is_circuit_breaker_active(),
        }
    
    def _calculate_take_profit_targets(self, entry_price: float) -> list:
        """Calculate partial exit targets based on configuration"""
        targets = []
        for tp in TAKE_PROFIT_LEVELS:
            target_price = entry_price * (1 + tp['percent'] / 100)
            targets.append({
                'price': target_price,
                'percent': tp['percent'],
                'position_percent': tp['position_percent'],
                'hit': False,
            })
        return targets


# Singleton instance
risk_manager = RiskManager()
