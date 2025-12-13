#!/usr/bin/env python3
"""
Quick test script for batch signal generation (bypasses trading hours check)
"""
import asyncio
import sys
from src.ai.signal_generator import SignalOrchestrator
from src.utils.logger import logger

async def test_batch_signals():
    """Test the batch signal generation"""
    logger.info("=" * 70)
    logger.info("🧪 TESTING BATCH SIGNAL GENERATION (Token Optimized)")
    logger.info("=" * 70)
    
    orchestrator = SignalOrchestrator()
    
    # Temporarily override trading hours check by directly running analysis
    from datetime import datetime, timezone
    from src.data.data_fetcher import binance_fetcher, data_processor
    from src.utils.indicators import compute_all_indicators, format_indicators_for_prompt
    from src.ai.ai_analyzer import ai_analyzer
    from src.monitoring.signal_monitor import signal_monitor
    from src.config.constants import PREFERRED_TIMEFRAME, MIN_CONFIDENCE_SCORE, MONITORING_ONLY, DRY_RUN_ENABLED
    from src.trading.risk_manager import risk_manager
    
    try:
        logger.info("Step 1: Fetching top 10 coins...")
        top_coins = await data_processor.get_top_n_coins_by_volume(n=10)
        
        if not top_coins:
            logger.error("No coins found!")
            return
        
        logger.info(f"Found {len(top_coins)} coins")
        
        # Collect data for all coins
        logger.info("\n" + "=" * 70)
        logger.info("📊 PHASE 1: Collecting OHLCV + Indicators")
        logger.info("=" * 70)
        
        coins_batch_data = []
        
        for idx, coin in enumerate(top_coins, 1):
            symbol = coin.get('symbol', '').upper()
            binance_symbol = f"{symbol}USDT"
            
            try:
                logger.info(f"[{idx}/{len(top_coins)}] {binance_symbol}...")
                
                df = await binance_fetcher.get_klines(
                    symbol=binance_symbol,
                    interval=PREFERRED_TIMEFRAME,
                    limit=100
                )
                
                if df.empty:
                    continue
                
                df = compute_all_indicators(df)
                current_price = float(df.iloc[-1]['close'])
                indicators = format_indicators_for_prompt(df)
                ohlcv_str = data_processor.format_ohlcv_for_prompt(df, last_n=3)
                
                coins_batch_data.append({
                    'symbol': binance_symbol,
                    'current_price': current_price,
                    'indicators': indicators,
                    'ohlcv_data': ohlcv_str,
                })
                
            except Exception as e:
                logger.error(f"Error: {e}")
                continue
        
        logger.info(f"✅ Collected {len(coins_batch_data)} coins")
        
        # Batch AI analysis
        logger.info("\n" + "=" * 70)
        logger.info(f"🤖 PHASE 2: Batch AI Analysis ({len(coins_batch_data)} coins → 1 API call)")
        logger.info("=" * 70)
        
        batch_signals = ai_analyzer.generate_signals_batch(coins_batch_data)
        
        logger.info(f"✅ Received {len(batch_signals)} signals")
        
        # Store signals for dashboard
        signals_generated = []
        
        for coin_data, signal in zip(coins_batch_data, batch_signals):
            binance_symbol = coin_data['symbol']
            signal_type = signal.get('signal', 'HOLD')
            confidence = signal.get('confidence', 0)
            
            logger.info(f"\n{binance_symbol}: {signal_type} @ {confidence}%")
            logger.info(f"  Rationale: {signal.get('rationale', 'N/A')}")
            
            signal_monitor.add_signal({
                'symbol': binance_symbol,
                'signal_type': signal_type,
                'confidence': confidence,
                'stop_loss': signal.get('stop_loss', 0),
                'take_profit': signal.get('take_profit', []),
                'rationale': signal.get('rationale', ''),
                'current_price': coin_data['current_price'],
                'indicators': coin_data['indicators'],
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })
            
            signals_generated.append({
                'symbol': binance_symbol,
                'signal': signal_type,
                'confidence': confidence,
            })
        
        logger.info("\n" + "=" * 70)
        logger.info("📊 TEST RESULTS")
        logger.info("=" * 70)
        logger.info(f"Coins Analyzed: {len(coins_batch_data)}")
        logger.info(f"Signals Generated: {len(signals_generated)}")
        logger.info(f"\n🎯 High Confidence Signals (≥70%):")
        
        high_conf = [s for s in signals_generated if s['confidence'] >= 70]
        if high_conf:
            for sig in high_conf:
                logger.info(f"  • {sig['symbol']}: {sig['signal']} @ {sig['confidence']}%")
        else:
            logger.info("  None")
        
        logger.info("\n✅ Test complete! Signals saved to dashboard")
        logger.info(f"🌐 View at: http://localhost:8080 (passcode: 232307)")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(test_batch_signals())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
