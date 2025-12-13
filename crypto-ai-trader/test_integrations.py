"""
Test Binance and Claude integrations
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_binance():
    """Test Binance API connection and data fetching"""
    print("\n" + "=" * 60)
    print("🔷 TESTING BINANCE CONNECTION")
    print("=" * 60)
    
    try:
        from binance.spot import Spot
        
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            print("❌ BINANCE_API_KEY or BINANCE_API_SECRET not found in .env")
            return False
        
        print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
        print(f"✅ API Secret found: {'*' * 20}")
        
        # Initialize client
        client = Spot(api_key=api_key, api_secret=api_secret)
        print("✅ Binance client initialized")
        
        # Test 1: Get account info
        print("\n--- Test 1: Account Info ---")
        account = client.account()
        print(f"✅ Account retrieved")
        print(f"   Can Trade: {account.get('canTrade', False)}")
        print(f"   Can Withdraw: {account.get('canWithdraw', False)}")
        print(f"   Can Deposit: {account.get('canDeposit', False)}")
        
        # Test 2: Get USDT balance
        print("\n--- Test 2: USDT Balance ---")
        balances = account.get('balances', [])
        usdt_balance = next((b for b in balances if b['asset'] == 'USDT'), None)
        
        if usdt_balance:
            free = float(usdt_balance['free'])
            locked = float(usdt_balance['locked'])
            total = free + locked
            print(f"✅ USDT Balance:")
            print(f"   Free: ${free:.2f}")
            print(f"   Locked: ${locked:.2f}")
            print(f"   Total: ${total:.2f}")
        else:
            print("⚠️  No USDT balance found")
        
        # Test 3: Get market data for BTC
        print("\n--- Test 3: Market Data (BTCUSDT) ---")
        ticker = client.ticker_24hr('BTCUSDT')
        print(f"✅ 24h Ticker:")
        print(f"   Symbol: {ticker['symbol']}")
        print(f"   Last Price: ${float(ticker['lastPrice']):,.2f}")
        print(f"   24h Change: {float(ticker['priceChangePercent']):.2f}%")
        print(f"   24h Volume: ${float(ticker['quoteVolume']):,.0f}")
        print(f"   24h High: ${float(ticker['highPrice']):,.2f}")
        print(f"   24h Low: ${float(ticker['lowPrice']):,.2f}")
        
        # Test 4: Get klines (candlestick data)
        print("\n--- Test 4: Klines Data (BTCUSDT 1h) ---")
        klines = client.klines('BTCUSDT', '1h', limit=5)
        print(f"✅ Retrieved {len(klines)} candles:")
        for i, kline in enumerate(klines[-3:], 1):
            open_price = float(kline[1])
            close_price = float(kline[4])
            change = ((close_price - open_price) / open_price) * 100
            print(f"   Candle {i}: Open=${open_price:,.2f}, Close=${close_price:,.2f}, Change={change:+.2f}%")
        
        print("\n✅ ALL BINANCE TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ BINANCE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_claude():
    """Test Claude API connection and response"""
    print("\n" + "=" * 60)
    print("🤖 TESTING CLAUDE API")
    print("=" * 60)
    
    try:
        import anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            print("❌ ANTHROPIC_API_KEY not found in .env")
            return False
        
        print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
        
        # Initialize client
        client = anthropic.Anthropic(api_key=api_key)
        print("✅ Claude client initialized")
        
        # Test 1: Simple prompt
        print("\n--- Test 1: Simple Response ---")
        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": "Respond with exactly: 'Claude API is working perfectly!'"
            }]
        )
        
        response_text = message.content[0].text
        print(f"✅ Claude Response: {response_text}")
        print(f"   Model: {message.model}")
        print(f"   Usage: {message.usage.input_tokens} input tokens, {message.usage.output_tokens} output tokens")
        
        # Test 2: Trading analysis prompt
        print("\n--- Test 2: Trading Analysis ---")
        trading_prompt = """You are a crypto trading analyst. Analyze this market snapshot:

BTCUSDT: $42,150
- 1H change: +2.1%
- 4H change: +3.5%
- 24H change: +5.2%
- Volume: $2.5B
- RSI: 65
- ATR: 2.1%
- Trend: Upward

Should we BUY or NO_TRADE? Respond in JSON format:
{"action": "BUY" or "NO_TRADE", "confidence": 0-100, "reason": "brief reason"}"""

        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=200,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": trading_prompt
            }]
        )
        
        response_text = message.content[0].text
        print(f"✅ Trading Analysis:")
        print(f"   {response_text}")
        print(f"   Tokens: {message.usage.input_tokens} in, {message.usage.output_tokens} out")
        print(f"   Total: {message.usage.input_tokens + message.usage.output_tokens} tokens")
        
        # Verify token count is reasonable
        total_tokens = message.usage.input_tokens + message.usage.output_tokens
        if total_tokens <= 500:
            print(f"✅ Token usage is optimal (≤500): {total_tokens} tokens")
        else:
            print(f"⚠️  Token usage is high: {total_tokens} tokens (target: ≤500)")
        
        print("\n✅ ALL CLAUDE TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ CLAUDE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_integration():
    """Test complete integration: Binance data → Claude analysis"""
    print("\n" + "=" * 60)
    print("🔄 TESTING FULL INTEGRATION")
    print("=" * 60)
    
    try:
        from binance.spot import Spot
        import anthropic
        
        # Get Binance data
        print("\n--- Step 1: Fetch Binance Data ---")
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        client = Spot(api_key=api_key, api_secret=api_secret)
        
        # Get BTC ticker
        ticker = client.ticker_24hr('BTCUSDT')
        price = float(ticker['lastPrice'])
        change_24h = float(ticker['priceChangePercent'])
        volume = float(ticker['quoteVolume'])
        
        print(f"✅ BTCUSDT Data:")
        print(f"   Price: ${price:,.2f}")
        print(f"   24H Change: {change_24h:+.2f}%")
        print(f"   24H Volume: ${volume:,.0f}")
        
        # Get klines for % changes
        klines = client.klines('BTCUSDT', '1h', limit=25)
        close_now = float(klines[-1][4])
        close_1h = float(klines[-2][4])
        close_4h = float(klines[-5][4])
        
        change_1h = ((close_now - close_1h) / close_1h) * 100
        change_4h = ((close_now - close_4h) / close_4h) * 100
        
        print(f"   1H Change: {change_1h:+.2f}%")
        print(f"   4H Change: {change_4h:+.2f}%")
        
        # Send to Claude
        print("\n--- Step 2: Claude Analysis ---")
        claude_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        analysis_prompt = f"""Analyze BTCUSDT:
Price: ${price:,.2f}
1H: {change_1h:+.2f}%
4H: {change_4h:+.2f}%
24H: {change_24h:+.2f}%
Volume: ${volume:,.0f}

Decide: BUY or NO_TRADE
Respond JSON: {{"action": "BUY"|"NO_TRADE", "confidence": 0-100, "reason": "brief"}}"""

        message = claude_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=200,
            temperature=0.3,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        response = message.content[0].text
        print(f"✅ Claude Decision:")
        print(f"   {response}")
        print(f"   Total tokens: {message.usage.input_tokens + message.usage.output_tokens}")
        
        print("\n✅ FULL INTEGRATION TEST PASSED")
        print("   Real Binance data → Claude analysis → Decision received")
        return True
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n🚀 STARTING INTEGRATION TESTS")
    print(f"Time: {asyncio.get_event_loop().time()}")
    
    results = {
        'binance': await test_binance(),
        'claude': await test_claude(),
        'integration': await test_full_integration(),
    }
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.upper()}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! System is ready for trading.")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
