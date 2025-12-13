"""
Connection and credential test suite
Tests Binance, Claude API, and Telegram connections
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import config
from src.utils.logger import logger


def test_env_credentials():
    """Check if all required credentials are present in .env"""
    logger.info("=" * 60)
    logger.info("TESTING ENVIRONMENT CREDENTIALS")
    logger.info("=" * 60)
    
    results = {}
    
    # Binance credentials
    results['BINANCE_API_KEY'] = bool(config.BINANCE_API_KEY and config.BINANCE_API_KEY != 'your_binance_api_key_here')
    results['BINANCE_API_SECRET'] = bool(config.BINANCE_API_SECRET and config.BINANCE_API_SECRET != 'your_binance_api_secret_here')
    results['BINANCE_TESTNET'] = config.BINANCE_TESTNET
    
    # Claude API
    results['CLAUDE_API_KEY'] = bool(config.CLAUDE_API_KEY and config.CLAUDE_API_KEY != 'your_claude_api_key_here')
    
    # Telegram
    results['TELEGRAM_BOT_TOKEN'] = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_BOT_TOKEN != 'your_telegram_bot_token_here')
    results['TELEGRAM_CHAT_ID'] = bool(config.TELEGRAM_CHAT_ID and config.TELEGRAM_CHAT_ID != 'your_telegram_chat_id_here')
    
    # Optional
    results['COINGECKO_API_KEY'] = bool(config.COINGECKO_API_KEY)
    
    logger.info("\n📋 Credential Status:")
    for key, value in results.items():
        status = "✅" if value else "❌"
        logger.info(f"  {status} {key}: {'Configured' if value else 'Missing/Placeholder'}")
    
    return results


def test_binance_connection():
    """Test Binance API connection"""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING BINANCE CONNECTION")
    logger.info("=" * 60)
    
    try:
        from src.trading.binance_client import binance_client
        
        # Test connectivity
        if binance_client.test_connectivity():
            logger.info("✅ Binance API: Connected")
            
            # Test account access
            try:
                balance = binance_client.get_account_balance()
                logger.info(f"✅ Account Access: OK ({len(balance)} assets)")
                
                # Show USDT balance
                usdt_balance = balance.get('USDT', 0)
                logger.info(f"💰 USDT Balance: ${usdt_balance:,.2f}")
                
                return True, f"Connected, USDT: ${usdt_balance:,.2f}"
            except Exception as e:
                logger.warning(f"⚠️  Account access limited: {e}")
                return True, "Connected (read-only)"
        else:
            logger.error("❌ Binance API: Connection failed")
            return False, "Connection failed"
    
    except Exception as e:
        logger.error(f"❌ Binance test failed: {e}")
        return False, str(e)


def test_claude_api():
    """Test Claude API connection"""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING CLAUDE API")
    logger.info("=" * 60)
    
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=config.CLAUDE_API_KEY)
        
        # Simple test prompt - try multiple models
        models_to_try = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
        
        last_error = None
        for model in models_to_try:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=100,
                    temperature=0.0,
                    messages=[{
                        "role": "user",
                        "content": "Reply with exactly: 'API test successful'"
                    }]
                )
                break  # Success!
            except Exception as e:
                last_error = e
                continue
        
        if last_error and 'response' not in locals():
            raise last_error
        
        response_text = response.content[0].text
        
        if "successful" in response_text.lower():
            logger.info("✅ Claude API: Connected and working")
            logger.info(f"📝 Test response: {response_text}")
            
            # Check token usage
            usage = response.usage
            logger.info(f"🔢 Token usage - Input: {usage.input_tokens}, Output: {usage.output_tokens}")
            
            return True, f"Working (test used {usage.input_tokens + usage.output_tokens} tokens)"
        else:
            logger.warning(f"⚠️  Claude API responded but unexpected output: {response_text}")
            return True, "Connected but unexpected response"
    
    except Exception as e:
        logger.error(f"❌ Claude API test failed: {e}")
        return False, str(e)


def test_telegram():
    """Test Telegram bot connection"""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING TELEGRAM BOT")
    logger.info("=" * 60)
    
    try:
        from src.monitoring.notifications import telegram_notifier
        
        # Send test message
        success = telegram_notifier.send_message("🧪 Connection test from SpringAI")
        
        if success:
            logger.info("✅ Telegram: Message sent successfully")
            return True, "Connected"
        else:
            logger.warning("⚠️  Telegram: Send failed")
            return False, "Send failed"
    
    except Exception as e:
        logger.error(f"❌ Telegram test failed: {e}")
        return False, str(e)


def test_order_system():
    """Test order management system (dry run)"""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING ORDER MANAGEMENT SYSTEM")
    logger.info("=" * 60)
    
    try:
        from src.trading.order_manager import order_manager
        from src.trading.risk_manager import risk_manager
        
        logger.info("✅ Order Manager: Loaded")
        logger.info("✅ Risk Manager: Loaded")
        
        # Check risk manager status
        summary = risk_manager.get_portfolio_summary()
        logger.info(f"💼 Portfolio:")
        logger.info(f"   Balance: ${summary['current_balance']:,.2f}")
        logger.info(f"   Active Positions: {len(risk_manager.positions)}")
        logger.info(f"   Max Positions: {risk_manager.max_concurrent_positions}")
        logger.info(f"   Circuit Breaker: {'ACTIVE' if risk_manager.circuit_breaker_active else 'OK'}")
        
        # Check if can open position
        can_trade = risk_manager.can_open_position("BTCUSDT")
        logger.info(f"🔄 Can Open New Position: {'✅ Yes' if can_trade else '❌ No'}")
        
        return True, f"{len(risk_manager.positions)} active, circuit breaker {'ON' if risk_manager.circuit_breaker_active else 'OFF'}"
    
    except Exception as e:
        logger.error(f"❌ Order system test failed: {e}")
        return False, str(e)


def run_all_tests():
    """Run all connection tests"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 SPRINGAI CONNECTION TEST SUITE")
    logger.info("=" * 60)
    
    results = {}
    
    # Test credentials
    creds = test_env_credentials()
    results['credentials'] = all([creds['BINANCE_API_KEY'], creds['BINANCE_API_SECRET'], creds['CLAUDE_API_KEY']])
    
    # Test Binance
    binance_ok, binance_msg = test_binance_connection()
    results['binance'] = (binance_ok, binance_msg)
    
    # Test Claude
    claude_ok, claude_msg = test_claude_api()
    results['claude'] = (claude_ok, claude_msg)
    
    # Test Telegram (optional)
    telegram_ok, telegram_msg = test_telegram()
    results['telegram'] = (telegram_ok, telegram_msg)
    
    # Test Order System
    order_ok, order_msg = test_order_system()
    results['orders'] = (order_ok, order_msg)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"\n✅ Credentials: {'PASS' if results['credentials'] else 'FAIL'}")
    logger.info(f"✅ Binance: {'PASS' if results['binance'][0] else 'FAIL'} - {results['binance'][1]}")
    logger.info(f"✅ Claude API: {'PASS' if results['claude'][0] else 'FAIL'} - {results['claude'][1]}")
    logger.info(f"{'✅' if results['telegram'][0] else '⚠️ '} Telegram: {'PASS' if results['telegram'][0] else 'FAIL'} - {results['telegram'][1]}")
    logger.info(f"✅ Order System: {'PASS' if results['orders'][0] else 'FAIL'} - {results['orders'][1]}")
    
    all_critical = results['credentials'] and results['binance'][0] and results['claude'][0] and results['orders'][0]
    
    logger.info("\n" + "=" * 60)
    if all_critical:
        logger.info("🎉 ALL CRITICAL TESTS PASSED - SYSTEM READY")
    else:
        logger.info("⚠️  SOME TESTS FAILED - CHECK CREDENTIALS")
    logger.info("=" * 60)
    
    return results


if __name__ == "__main__":
    run_all_tests()
