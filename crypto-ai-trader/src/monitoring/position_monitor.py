"""
Position Monitor - Continuous monitoring of open positions for profit/loss booking
Runs independently from signal generation every 5 minutes
"""
import asyncio
from datetime import datetime
from src.utils.logger import logger
from src.trading.order_manager import order_manager
from src.trading.binance_client import binance_client
from src.monitoring.notifications import notifier
from src.config.constants import MONITORING_ONLY, DRY_RUN_ENABLED

# Configuration
POSITION_CHECK_INTERVAL_MINUTES = 5  # Check every 5 minutes for exits
POSITION_CHECK_INTERVAL_SECONDS = POSITION_CHECK_INTERVAL_MINUTES * 60


class PositionMonitor:
    """Monitor open positions continuously and execute exits"""
    
    def __init__(self):
        """Initialize position monitor"""
        self.running = False
        logger.info(f"Position Monitor initialized (check interval: {POSITION_CHECK_INTERVAL_MINUTES} min)")
    
    async def monitor_positions(self):
        """
        Continuously monitor open positions for profit-taking and loss-cutting
        
        Checks every POSITION_CHECK_INTERVAL_MINUTES:
        - Stop loss hits
        - Take profit targets
        - Trailing stops
        - Time-based exits
        """
        logger.info(f"🔍 Position Monitor started - checking every {POSITION_CHECK_INTERVAL_MINUTES} minutes")
        self.running = True
        
        while self.running:
            try:
                # Get active positions from risk_manager (persisted)
                from src.trading.risk_manager import risk_manager
                active_positions = risk_manager.positions
                
                if active_positions:
                    logger.info(f"\n📊 Position Monitor: Checking {len(active_positions)} open position(s)")
                    
                    # Check each position
                    for symbol, position in active_positions.items():
                        try:
                            # Get current price
                            current_price = binance_client.get_current_price(symbol)
                            
                            if current_price <= 0:
                                logger.warning(f"⚠️  Could not fetch price for {symbol}")
                                continue
                            
                            # Update position's current price and save to file
                            position.update_current_price(current_price)
                            risk_manager._save_positions_to_file()
                            
                            # Calculate P&L
                            entry_price = position.entry_price
                            pnl_value = (current_price - entry_price) * position.quantity
                            pnl_percent = ((current_price - entry_price) / entry_price) * 100
                            
                            # Check for exit conditions
                            exit_triggered = False
                            exit_reason = ""
                            
                            # Check stop loss
                            if current_price <= position.stop_loss:
                                exit_triggered = True
                                exit_reason = f"STOP LOSS HIT @ ${current_price:.2f}"
                                logger.warning(f"🚨 {symbol}: {exit_reason}")
                                
                                # EXECUTE STOP LOSS - Close entire position
                                try:
                                    if not DRY_RUN_ENABLED and not MONITORING_ONLY:
                                        logger.info(f"🔴 Executing stop loss sell for {symbol}...")
                                        
                                        # Close position via order manager
                                        result = order_manager.close_position(
                                            symbol=symbol,
                                            reason=exit_reason
                                        )
                                        
                                        if result.get('status') == 'success':
                                            logger.info(f"✅ Stop loss executed: {result.get('message')}")
                                            
                                            # Send notification
                                            await notifier.send_trade_alert(
                                                f"🚨 STOP LOSS EXECUTED\n"
                                                f"{symbol}\n"
                                                f"Entry: ${entry_price:.2f}\n"
                                                f"Exit: ${current_price:.2f}\n"
                                                f"Loss: {pnl_percent:.2f}%"
                                            )
                                        else:
                                            logger.error(f"❌ Stop loss execution failed: {result.get('message')}")
                                    else:
                                        logger.info(f"📝 DRY RUN: Would close {symbol} at stop loss")
                                
                                except Exception as e:
                                    logger.error(f"Error executing stop loss for {symbol}: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # Check take profit targets
                            elif position.take_profit_targets:
                                for i, tp in enumerate(position.take_profit_targets):
                                    if current_price >= tp['price']:
                                        exit_triggered = True
                                        exit_reason = f"TAKE PROFIT {i+1} HIT @ ${current_price:.2f}"
                                        logger.info(f"✅ {symbol}: {exit_reason}")

                                        # EXECUTE TAKE PROFIT - Partial exit based on tp['position_percent']
                                        try:
                                            if not DRY_RUN_ENABLED and not MONITORING_ONLY:
                                                logger.info(f"🟢 Executing partial take profit for {symbol}...")

                                                # Compute partial quantity
                                                tp_percent = tp.get('position_percent', 0)
                                                if tp_percent <= 0:
                                                    logger.warning(
                                                        f"⚠️ TP level {i+1} for {symbol} has invalid position_percent; skipping"
                                                    )
                                                else:
                                                    # Determine how much is still available to sell
                                                    total_quantity = position.quantity
                                                    target_quantity = total_quantity * tp_percent

                                                    # If this is the last TP level, sell whatever remains
                                                    if i == len(position.take_profit_targets) - 1:
                                                        sell_quantity = total_quantity
                                                    else:
                                                        sell_quantity = min(target_quantity, total_quantity)

                                                    if sell_quantity <= 0:
                                                        logger.warning(
                                                            f"⚠️ Computed sell quantity <= 0 for {symbol} at TP {i+1}; skipping"
                                                        )
                                                    else:
                                                        result = order_manager.close_position(
                                                            symbol=symbol,
                                                            reason=exit_reason,
                                                            quantity_override=sell_quantity,
                                                            keep_open=True,
                                                        )

                                                        if result.get('status') == 'success':
                                                            logger.info(f"✅ Take profit executed: {result.get('message')}")

                                                            await notifier.send_trade_alert(
                                                                f"✅ PARTIAL TAKE PROFIT EXECUTED\n"
                                                                f"{symbol}\n"
                                                                f"Entry: ${entry_price:.2f}\n"
                                                                f"Exit: ${current_price:.2f}\n"
                                                                f"Sold: {sell_quantity:.6f}\n"
                                                                f"Profit: +{pnl_percent:.2f}%"
                                                            )
                                                        else:
                                                            logger.error(
                                                                f"❌ Take profit execution failed: {result.get('message')}"
                                                            )
                                            else:
                                                logger.info(
                                                    f"📝 DRY RUN: Would execute partial take profit for {symbol} at TP {i+1}"
                                                )

                                        except Exception as e:
                                            logger.error(f"Error executing take profit for {symbol}: {e}")
                                            import traceback
                                            traceback.print_exc()

                                        break
                            
                            if not exit_triggered:
                                # Position still open, show current P&L
                                emoji = "📈" if pnl_value >= 0 else "📉"
                                logger.info(f"{emoji} {symbol}: ${current_price:.2f} | P&L: ${pnl_value:+.2f} ({pnl_percent:+.2f}%)")
                        
                        except Exception as e:
                            logger.error(f"Error checking position {symbol}: {e}")
                            continue
                
                else:
                    # No open positions
                    if self.running:  # Only log if monitor is still running
                        logger.debug("No open positions to monitor")
                
                # Wait before next check
                logger.info(f"⏱️  Next position check in {POSITION_CHECK_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(POSITION_CHECK_INTERVAL_SECONDS)
            
            except Exception as e:
                logger.error(f"Error in position monitor: {e}")
                import traceback
                traceback.print_exc()
                # Continue monitoring even on error
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Position Monitor stopped")


# Singleton instance
position_monitor = PositionMonitor()
