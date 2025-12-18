"""
Main orchestrator - Runs the automated trading bot
"""
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.utils.logger import logger
from src.config.settings import config
from src.config.constants import (
    ANALYSIS_INTERVAL_MINUTES,
    EXCLUDED_COINS,
    QUOTE_ASSET,
)
from src.data.data_fetcher import binance_fetcher, data_processor
from src.ai.ai_analyzer import ai_analyzer
from src.trading.order_manager import order_manager
from src.trading.risk_manager import risk_manager
from src.monitoring.notifications import notifier


class CryptoTradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        """Initialize trading bot"""
        self.running = False
        self.last_analysis_time = None
        self.analysis_interval = timedelta(minutes=ANALYSIS_INTERVAL_MINUTES)
        
        logger.info("=" * 50)
        logger.info("Crypto AI Trading Bot Initialized")
        logger.info(f"Starting Capital: ${config.STARTING_CAPITAL_AUD:.2f} AUD")
        logger.info(f"Analysis Interval: {ANALYSIS_INTERVAL_MINUTES} minutes")
        logger.info(f"Environment: {config.ENVIRONMENT}")
        logger.info(f"Testnet: {config.BINANCE_TESTNET}")
        logger.info("=" * 50)
    
    async def start(self):
        """Start the trading bot"""
        try:
            # Validate configuration
            config.validate()
            
            # Test Binance connectivity
            if not binance_fetcher.base_url:
                logger.error("Failed to initialize Binance API")
                return
            
            logger.info("✅ Configuration validated")
            logger.info("✅ Binance API ready")
            
            self.running = True
            
            # Start main loop
            await self._main_loop()
        
        except Exception as e:
            logger.error(f"Fatal error starting bot: {e}")
            await notifier.send_error_alert(
                "Bot Startup Failed",
                str(e),
                "CRITICAL"
            )
    
    async def _main_loop(self):
        """Main trading loop"""
        try:
            while self.running:
                try:
                    # Run analysis every N minutes
                    if self._should_run_analysis():
                        logger.info("🔍 Running AI analysis...")
                        await self._run_analysis()
                    
                    # Update all open positions
                    await self._update_positions()
                    
                    # Send hourly report
                    if self._should_send_report():
                        await self._send_status_report()
                    
                    # Wait before next iteration
                    await asyncio.sleep(30)  # Check every 30 seconds
                
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await notifier.send_error_alert(
                        "Main Loop Error",
                        str(e),
                        "WARNING"
                    )
                    await asyncio.sleep(60)
        
        except KeyboardInterrupt:
            logger.info("Bot interrupted by user")
            await self.stop()
    
    async def _run_analysis(self):
        """Run AI analysis and execute trades"""
        try:
            # Fetch top coins from Binance by volume
            logger.info("Fetching top 20 coins by volume from Binance...")
            coins_data = await data_processor.get_top_n_coins_by_volume(n=20)
            
            if not coins_data:
                logger.warning("No coins data fetched")
                return
            
            logger.info(f"Fetched {len(coins_data)} coins for analysis")
            
            # Run AI analysis with consensus
            logger.info("Running AI consensus analysis...")
            analysis_result = ai_analyzer.validate_with_consensus(
                coins_data,
                num_variations=2,  # Run 2 times for speed, 3 for accuracy
            )
            
            consensus_coins = analysis_result.get('consensus_coins', [])
            
            if not consensus_coins:
                logger.info("No consensus found for pump candidates")
                await notifier.send_strategy_signal(
                    coins=[],
                    market_sentiment="neutral",
                    analysis="No strong signals found"
                )
                return
            
            logger.info(f"📊 AI identified {len(consensus_coins)} pump candidates")
            
            # Send signal notification
            await notifier.send_strategy_signal(
                coins=consensus_coins,
                market_sentiment=analysis_result.get('all_analyses', [{}])[0].get('market_sentiment', 'neutral'),
                analysis=analysis_result.get('all_analyses', [{}])[0].get('analysis', ''),
            )
            
            # Execute trades for top coins
            for i, coin in enumerate(consensus_coins[:3]):  # Trade top 3
                if risk_manager.is_circuit_breaker_active():
                    logger.warning("Circuit breaker active - stopping trades")
                    break
                
                await self._execute_trade_for_coin(coin)
                await asyncio.sleep(2)  # Delay between trades
            
            self.last_analysis_time = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            await notifier.send_error_alert(
                "AI Analysis Error",
                str(e),
                "WARNING"
            )
    
    async def _execute_trade_for_coin(self, coin_data: Dict[str, Any]):
        """Execute a trade for specific coin"""
        try:
            symbol = coin_data.get('symbol', '').upper() + QUOTE_ASSET
            confidence = coin_data.get('confidence', 0)
            
            logger.info(f"Executing trade for {symbol} (confidence: {confidence:.1%})")
            
            # Get current price
            current_price = coin_data.get('current_price', 0)
            if current_price <= 0:
                logger.warning(f"Invalid price for {symbol}")
                return
            
            # Calculate position size and stop loss
            stop_loss_percent = 3.0  # 3% stop loss
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)
            
            quantity = risk_manager.calculate_position_size(
                current_balance=risk_manager.current_balance,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
            )
            
            if quantity <= 0:
                logger.warning(f"Invalid position size for {symbol}")
                return
            
            # Calculate take profit levels
            take_profits = [
                {'price': current_price * 1.03, 'percent': 3, 'position_percent': 0.33},
                {'price': current_price * 1.05, 'percent': 5, 'position_percent': 0.33},
                {'price': current_price * 1.08, 'percent': 8, 'position_percent': 0.34},
            ]
            
            # Execute entry order
            trade = await order_manager.execute_entry_order(
                symbol=symbol,
                quantity=quantity,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
                take_profit_levels=take_profits,
                confidence=confidence,
            )
            
            if trade:
                logger.info(f"✅ Trade executed for {symbol}")
            else:
                logger.warning(f"❌ Failed to execute trade for {symbol}")
        
        except Exception as e:
            logger.error(f"Error executing trade for {coin_data}: {e}")
    
    async def _update_positions(self):
        """Update all open positions"""
        try:
            active_trades = order_manager.get_active_trades()
            
            if not active_trades:
                return
            
            for symbol, trade in list(active_trades.items()):
                try:
                    current_price = binance_fetcher.client.get_symbol_ticker(symbol=symbol)
                    if current_price:
                        current_price = float(current_price['price'])
                        await order_manager.update_position(symbol, current_price)
                
                except Exception as e:
                    logger.error(f"Error updating position for {symbol}: {e}")
        
        except Exception as e:
            logger.error(f"Error in position update: {e}")
    
    async def _send_status_report(self):
        """Send hourly status report"""
        try:
            summary = risk_manager.get_portfolio_summary()
            await notifier.send_hourly_report(summary)
            logger.info("✉️  Hourly report sent")
        except Exception as e:
            logger.error(f"Error sending status report: {e}")
    
    def _should_run_analysis(self) -> bool:
        """Check if analysis should run"""
        if self.last_analysis_time is None:
            return True
        
        return datetime.now() - self.last_analysis_time >= self.analysis_interval
    
    def _should_send_report(self) -> bool:
        """Check if hourly report should be sent"""
        return datetime.now().minute == 0  # Send at the top of every hour
    
    async def stop(self):
        """Stop the trading bot gracefully"""
        logger.info("Stopping trading bot...")
        self.running = False
        
        # Close all open positions
        active_trades = order_manager.get_active_trades()
        for symbol, trade in active_trades.items():
            logger.info(f"Closing position: {symbol}")
            # Note: Implement graceful position closing logic
        
        logger.info("Trading bot stopped")
        sys.exit(0)


async def main():
    """Main entry point"""
    bot = CryptoTradingBot()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start bot
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
