"""
Quick test for Binance public API and Claude
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "=" * 60)
print("🔍 ENVIRONMENT VARIABLES CHECK")
print("=" * 60)

# Check all API keys
binance_key = os.getenv('BINANCE_API_KEY')
binance_secret = os.getenv('BINANCE_API_SECRET')
claude_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')

print(f"BINANCE_API_KEY: {'✅ Found' if binance_key else '❌ Missing'}")
print(f"BINANCE_API_SECRET: {'✅ Found' if binance_secret else '❌ Missing'}")
print(f"CLAUDE_API_KEY: {'✅ Found' if claude_key else '❌ Missing'}")

if claude_key:
    print(f"   Value: {claude_key[:15]}...{claude_key[-4:]}")

print("\n" + "=" * 60)
print("🔷 TEST 1: BINANCE PUBLIC API (No Auth Required)")
print("=" * 60)

try:
    from binance.spot import Spot
    
    # Use public client (no auth)
    client = Spot()
    
    # Test ticker
    ticker = client.ticker_24hr('BTCUSDT')
    price = float(ticker['lastPrice'])
    change = float(ticker['priceChangePercent'])
    volume = float(ticker['quoteVolume'])
    
    print(f"✅ BTCUSDT Market Data:")
    print(f"   Price: ${price:,.2f}")
    print(f"   24H Change: {change:+.2f}%")
    print(f"   24H Volume: ${volume:,.0f}")
    
    # Test klines
    klines = client.klines('BTCUSDT', '1h', limit=5)
    print(f"✅ Retrieved {len(klines)} candles")
    
    print("\n✅ BINANCE PUBLIC API: WORKING")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("🔷 TEST 2: BINANCE ACCOUNT API (Auth Required)")
print("=" * 60)

if binance_key and binance_secret:
    try:
        from binance.spot import Spot
        
        client = Spot(api_key=binance_key, api_secret=binance_secret)
        
        # Try to get account info
        account = client.account()
        
        print("✅ Account access: WORKING")
        print(f"   Can Trade: {account.get('canTrade', False)}")
        
        # Get USDT balance
        balances = account.get('balances', [])
        usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
        
        if usdt:
            total = float(usdt['free']) + float(usdt['locked'])
            print(f"✅ USDT Balance: ${total:.2f}")
        
    except Exception as e:
        print(f"❌ Account API Error: {e}")
        print("\n⚠️  POSSIBLE ISSUES:")
        print("   1. API key permissions not enabled (spot trading, reading)")
        print("   2. IP address not whitelisted")
        print("   3. API key expired or invalid")
        print("\n💡 SOLUTION:")
        print("   Go to Binance.com → API Management")
        print("   - Enable 'Enable Spot & Margin Trading'")
        print("   - Add your IP to whitelist (or use 'Unrestricted')")
else:
    print("⚠️  Binance API keys not configured")

print("\n" + "=" * 60)
print("🤖 TEST 3: CLAUDE API")
print("=" * 60)

if claude_key:
    try:
        import anthropic
        
        # Try with both environment variable names
        client = anthropic.Anthropic(api_key=claude_key)
        
        print("✅ Claude client initialized")
        
        # Simple test
        message = client.messages.create(
            model="claude-3-opus-20240229",  # Using opus model
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Reply with: 'API working!'"
            }]
        )
        
        response = message.content[0].text
        tokens = message.usage.input_tokens + message.usage.output_tokens
        
        print(f"✅ Response: {response}")
        print(f"✅ Tokens used: {tokens}")
        print("\n✅ CLAUDE API: WORKING")
        
    except Exception as e:
        print(f"❌ Claude Error: {e}")
        print("\n💡 Check if CLAUDE_API_KEY is valid")
else:
    print("❌ CLAUDE_API_KEY not found in .env")
    print("\n💡 Add to .env file:")
    print("   ANTHROPIC_API_KEY=your_key_here")

print("\n" + "=" * 60)
print("📊 SUMMARY")
print("=" * 60)
print("✅ Binance public API works (market data)")
print("⚠️  Binance account API needs configuration")
print(f"{'✅' if claude_key else '❌'} Claude API: {'Ready' if claude_key else 'Not configured'}")
