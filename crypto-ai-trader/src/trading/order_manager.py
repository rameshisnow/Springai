"""
Order Manager - Handles order placement, tracking, and execution
"""
import asyncio
import json
from typing import Dict, Optional, List, Any
from datetime import datetime
from src.utils.logger import trade_logger
from src.utils.database import log_trade_entry, update_trade_exit
from src.trading.binance_client import binance_client
from src.trading.risk_manager import risk_manager
from src.monitoring.notifications import notifier
from src.config.constants import DRY_RUN_ENABLED, MONITORING_ONLY


class TradeRecord:
    """Record of a single trade"""
    
    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        entry_time: datetime,
        stop_loss: float,
        take_profits: list,
        confidence: float = 0.0,
        db_id: Optional[int] = None,
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profits = take_profits
        self.confidence = confidence
        self.entry_order_id = None
        self.exit_order_ids = []
        self.pnl = 0.0
        self.pnl_percent = 0.0
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.status = "PENDING"  # PENDING, OPEN, CLOSED, CANCELLED
        self.db_id = db_id
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'stop_loss': self.stop_loss,
            'take_profits': self.take_profits,
            'confidence': self.confidence,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'status': self.status,
            'exit_reason': self.exit_reason,
        }


class OrderManager:
    """Manages order lifecycle and trade execution"""
    
    def __init__(self):
        """Initialize order manager"""
        self.active_trades: Dict[str, TradeRecord] = {}
        self.active_orders: Dict[str, TradeRecord] = {}
        self.closed_trades: List[TradeRecord] = []
        self.trade_history_file = "/logs/trade_history.jsonl"
        
        trade_logger.info("Order Manager initialized")
    
    async def execute_entry_order(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_levels: list = None,
        confidence: float = 0.0,
    ) -> Optional[TradeRecord]:
        """
        Execute a buy/long order
        
        Args:
            symbol: Trading pair
            quantity: Amount to buy
            entry_price: Entry price (for reference)
            stop_loss_price: Stop loss price
            take_profit_levels: List of TP levels
            confidence: AI confidence score
        
        Returns:
            TradeRecord if successful
        """
        # Validate with risk manager
        is_valid, message = risk_manager.validate_trade(
            symbol, quantity, entry_price, stop_loss_price
        )
        
        if not is_valid:
            trade_logger.warning(f"Entry order rejected: {message}")
            return None
        
        # Add position to risk manager with Claude's take profit levels
        # Convert TP prices to the format risk_manager expects
        tp_targets = []
        if take_profit_levels:
            tp_size = 1.0 / len(take_profit_levels)
            for tp_price in take_profit_levels:
                tp_targets.append({
                    'price': tp_price,
                    'position_percent': tp_size,
                })
        
        position = risk_manager.add_position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_targets=tp_targets if tp_targets else None,
        )
        
        if not position:
            return None
        
        # Create trade record
        trade = TradeRecord(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            stop_loss=stop_loss_price,
            take_profits=take_profit_levels or [],
            confidence=confidence,
        )
        
        # Check if in monitoring mode or dry run
        if MONITORING_ONLY or DRY_RUN_ENABLED:
            trade_logger.warning(f"🔍 MONITORING MODE: Would BUY {quantity} {symbol} @ {entry_price}")
            trade_logger.info(f"   Stop Loss: {stop_loss_price}, TPs: {take_profit_levels}")
            trade.status = "SIMULATED"
            trade.entry_order_id = f"DRY_RUN_{symbol}_{int(datetime.now().timestamp())}"
            
            # Still track in risk manager for simulation
            self.active_orders[trade.entry_order_id] = trade
            
            # Log to database as simulated
            metadata = {
                "source": "dry_run",
                "confidence": confidence,
                "notes": "Monitoring-only simulated entry",
            }
            trade.db_id = log_trade_entry(
                symbol=symbol,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss_price=stop_loss_price,
                take_profit_levels=take_profit_levels,
                confidence=confidence,
                metadata=metadata,
            )
            
            trade_logger.info(f"✅ Simulated trade logged: {symbol}")
            return trade
        
        # Place market order on Binance (REAL MODE)
        try:
            order_result = binance_client.place_market_order(
                symbol=symbol,
                side="BUY",
                quantity=quantity,
            )
            
            if order_result and 'orderId' in order_result:
                trade.entry_order_id = order_result['orderId']
                trade.status = "OPEN"
                
                # Place stop loss order
                await self._place_stop_loss_order(symbol, quantity, stop_loss_price)
                
                # Place take profit orders
                if tp_targets:
                    await self._place_take_profit_orders(symbol, quantity, tp_targets)
                
                # Add to active trades
                self.active_trades[symbol] = trade
                trade.db_id = log_trade_entry(
                    symbol=symbol,
                    side="BUY",
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    take_profit_levels=take_profit_levels,
                    confidence=confidence,
                    metadata={"source": "ai_analysis"},
                )
                
                # Send Telegram alert
                await notifier.send_trade_alert(
                    symbol=symbol,
                    side="BUY",
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss=stop_loss_price,
                    take_profits=take_profit_levels,
                    confidence=confidence,
                )
                
                # Log trade
                self._log_trade(trade)
                
                trade_logger.info(f"Entry order executed: {symbol} {quantity} @ ${entry_price:.8f}")
                return trade
            
            else:
                trade_logger.error(f"Failed to place order: {order_result}")
                trade.status = "CANCELLED"
                return None
        
        except Exception as e:
            trade_logger.error(f"Error executing entry order: {e}")
            trade.status = "CANCELLED"
            return None
    
    async def update_position(self, symbol: str, current_price: float) -> Optional[Dict]:
        """
        Update position and check exit conditions
        
        Returns:
            Exit signal if any
        """
        if symbol not in self.active_trades:
            return None
        
        trade = self.active_trades[symbol]
        
        # Update position in risk manager
        update_result = risk_manager.update_position(symbol, current_price)
        
        if update_result and update_result.get('exit_signal'):
            # Exit condition triggered
            await self.execute_exit_order(
                symbol=symbol,
                exit_price=current_price,
                reason=update_result['reason'],
                exit_type=update_result['exit_signal'],
            )
        
        return update_result
    
    async def execute_exit_order(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "Manual",
        exit_type: str = "MANUAL",
    ) -> Optional[TradeRecord]:
        """
        Execute exit order (sell)
        
        Returns:
            Updated TradeRecord
        """
        if symbol not in self.active_trades:
            return None
        
        trade = self.active_trades[symbol]
        
        # Calculate P&L
        trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        trade.pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.exit_reason = reason
        trade.status = "CLOSED"
        
        # Close position in risk manager
        risk_manager.close_position(symbol, exit_price, reason)

        if trade.db_id:
            update_trade_exit(
                record_id=trade.db_id,
                exit_price=exit_price,
                pnl=trade.pnl,
                pnl_percent=trade.pnl_percent,
                status="CLOSED",
                reason=reason,
            )
        
        # Close stop loss and take profit orders
        await self._cancel_conditional_orders(symbol)
        
        # Place sell market order
        try:
            order_result = binance_client.place_market_order(
                symbol=symbol,
                side="SELL",
                quantity=trade.quantity,
            )
            
            if order_result and 'orderId' in order_result:
                trade.exit_order_ids.append(order_result['orderId'])
                
                # Send exit alert
                await notifier.send_exit_alert(
                    symbol=symbol,
                    exit_price=exit_price,
                    pnl=trade.pnl,
                    pnl_percent=trade.pnl_percent,
                    reason=reason,
                    exit_type=exit_type,
                )
                
                # Move to closed trades
                self.closed_trades.append(trade)
                del self.active_trades[symbol]
                
                # Log trade
                self._log_trade(trade)
                
                trade_logger.info(
                    f"Exit order executed: {symbol} P&L: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%) - {reason}"
                )
                return trade
        
        except Exception as e:
            trade_logger.error(f"Error executing exit order: {e}")
        
        return None
    
    async def _place_stop_loss_order(self, symbol: str, quantity: float, stop_price: float):
        """Place stop loss order"""
        try:
            binance_client.place_stop_loss_order(
                symbol=symbol,
                side="SELL",
                quantity=quantity,
                stop_price=stop_price,
            )
            trade_logger.info(f"Stop loss order placed: {symbol} @ ${stop_price:.8f}")
        except Exception as e:
            trade_logger.error(f"Error placing stop loss: {e}")
    
    async def _place_take_profit_orders(self, symbol: str, quantity: float, take_profits: list):
        """Place partial take profit orders"""
        try:
            for i, tp in enumerate(take_profits):
                tp_quantity = quantity * tp['position_percent']
                binance_client.place_take_profit_order(
                    symbol=symbol,
                    side="SELL",
                    quantity=tp_quantity,
                    stop_price=tp['price'],
                )
                trade_logger.info(
                    f"Take profit {i+1} order placed: {symbol} {tp_quantity:.8f} @ ${tp['price']:.8f}"
                )
        except Exception as e:
            trade_logger.error(f"Error placing take profit orders: {e}")
    
    async def _cancel_conditional_orders(self, symbol: str):
        """Cancel all conditional orders for symbol"""
        try:
            open_orders = binance_client.get_open_orders(symbol)
            for order in open_orders:
                binance_client.cancel_order(symbol, order['orderId'])
            trade_logger.info(f"Cancelled {len(open_orders)} conditional orders for {symbol}")
        except Exception as e:
            trade_logger.error(f"Error cancelling orders: {e}")
    
    def close_position(self, symbol: str, reason: str = "Manual") -> Dict:
        """
        Synchronous wrapper to close a position (for use by position monitor)
        
        Args:
            symbol: Trading pair to close
            reason: Reason for closing (e.g., "STOP LOSS HIT @ $X")
        
        Returns:
            Dict with status and message
        """
        try:
            # Get current price
            current_price = binance_client.get_current_price(symbol)
            
            if not current_price:
                return {
                    'status': 'error',
                    'message': 'Could not fetch current price'
                }
            
            # Check if position exists in risk manager (not active_trades)
            if symbol not in risk_manager.positions:
                return {
                    'status': 'error',
                    'message': f'Position {symbol} not found in risk manager'
                }
            
            position = risk_manager.positions[symbol]
            
            # Execute market sell order
            order_result = binance_client.place_market_order(
                symbol=symbol,
                side="SELL",
                quantity=position.quantity,
            )
            
            if not order_result or 'orderId' not in order_result:
                return {
                    'status': 'error',
                    'message': 'Failed to place sell order'
                }
            
            # Calculate P&L
            pnl_dollars = (current_price - position.entry_price) * position.quantity
            pnl_percent = ((current_price - position.entry_price) / position.entry_price) * 100
            
            # Close position in risk manager
            risk_manager.close_position(symbol, current_price, reason)
            
            # Log the exit
            trade_logger.info(
                f"✅ Position closed: {symbol} @ ${current_price:.2f} | "
                f"P&L: ${pnl_dollars:.2f} ({pnl_percent:+.2f}%) | "
                f"Reason: {reason}"
            )
            
            # Send notification (non-blocking)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(notifier.send_exit_alert(
                        symbol=symbol,
                        exit_price=current_price,
                        pnl=pnl_dollars,
                        pnl_percent=pnl_percent,
                        reason=reason,
                        exit_type="AUTO" if "STOP LOSS" in reason or "TAKE PROFIT" in reason else "MANUAL"
                    ))
            except:
                pass  # Don't fail if notification fails
            
            return {
                'status': 'success',
                'message': f'Position closed at ${current_price:.2f}',
                'pnl': pnl_dollars,
                'pnl_percent': pnl_percent,
            }
        
        except Exception as e:
            trade_logger.error(f"Error closing position {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_active_trades(self) -> Dict[str, TradeRecord]:
        """Get all active trades"""
        return self.active_trades.copy()
    
    def get_trade_history(self, limit: int = 100) -> List[TradeRecord]:
        """Get closed trades"""
        return self.closed_trades[-limit:]
    
    def _log_trade(self, trade: TradeRecord):
        """Log trade to file"""
        try:
            with open(self.trade_history_file, 'a') as f:
                record = trade.to_dict()
                record['db_id'] = trade.db_id
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            trade_logger.error(f"Error logging trade: {e}")


# Singleton instance
order_manager = OrderManager()
