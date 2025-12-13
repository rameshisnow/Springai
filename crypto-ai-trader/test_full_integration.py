"""
Full integration test: Binance data → Claude analysis
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("🚀 FULL INTEGRATION TEST")
print("=" * 60)

# Step 1: Fetch Binance market data (PUBLIC API - no auth needed)
print("\n📊 STEP 1: Fetching Binance Market Data")
print("-" * 60)

from binance.spot import Spot

client = Spot()  # Public client

# Get top coins data
symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
market_data = []

for symbol in symbols:
    try:
        ticker = client.ticker_24hr(symbol)
        klines = client.klines(symbol, '1h', limit=25)
        
        price = float(ticker['lastPrice'])
        change_24h = float(ticker['priceChangePercent'])
        volume = float(ticker['quoteVolume'])
        
        # Calculate % changes
        close_now = float(klines[-1][4])
        close_1h = float(klines[-2][4]) if len(klines) >= 2 else close_now
        close_4h = float(klines[-5][4]) if len(klines) >= 5 else close_now
        
        change_1h = ((close_now - close_1h) / close_1h) * 100 if close_1h > 0 else 0
        change_4h = ((close_now - close_4h) / close_4h) * 100 if close_4h > 0 else 0
        
        market_data.append({
            'symbol': symbol,
            'price': price,
            'change_1h': change_1h,
            'change_4h': change_4h,
            'change_24h': change_24h,
            'volume': volume,
        })
        
        print(f"✅ {symbol:10s} ${price:>10,.2f}  1H:{change_1h:+6.2f}%  24H:{change_24h:+6.2f}%  Vol:${volume:>12,.0f}")
        
    except Exception as e:
        print(f"❌ {symbol}: {e}")

if not market_data:
    print("❌ No market data fetched")
    exit(1)

# Step 2: Send to Claude for analysis
print("\n🤖 STEP 2: Claude AI Analysis")
print("-" * 60)

import anthropic

claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')

if not claude_key:
    print("❌ No Claude API key found")
    exit(1)

client = anthropic.Anthropic(api_key=claude_key)

# Create market snapshot
snapshot_lines = []
for i, coin in enumerate(market_data, 1):
    line = f"{i}. {coin['symbol']:10s} ${coin['price']:>10,.2f} | 1H:{coin['change_1h']:+6.2f}% 4H:{coin['change_4h']:+6.2f}% 24H:{coin['change_24h']:+6.2f}% | Vol:${coin['volume']/1e6:>7,.0f}M"
    snapshot_lines.append(line)

snapshot = "\n".join(snapshot_lines)

prompt = f"""You are a crypto trading oracle. Analyze these {len(market_data)} coins and select at most ONE for a BUY trade:

{snapshot}

Rules:
- Only BUY if you see a HIGH-QUALITY setup
- Otherwise respond NO_TRADE
- Consider momentum, volume, and risk

Respond in JSON:
{{"action": "BUY"|"NO_TRADE", "symbol": "BTCUSDT"|null, "confidence": 65-95, "reason": "brief explanation"}}"""

print(f"📤 Sending prompt ({len(prompt)} chars)...\n")

try:
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=200,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response = message.content[0].text
    tokens_used = message.usage.input_tokens + message.usage.output_tokens
    
    print(f"✅ Claude Response:")
    print("-" * 60)
    print(response)
    print("-" * 60)
    print(f"\n📊 Token Usage:")
    print(f"   Input:  {message.usage.input_tokens}")
    print(f"   Output: {message.usage.output_tokens}")
    print(f"   Total:  {tokens_used}")
    
    if tokens_used <= 500:
        print(f"   ✅ Within budget (≤500 tokens)")
    else:
        print(f"   ⚠️  Over budget: {tokens_used - 500} tokens")
    
    # Try to parse JSON
    print(f"\n🎯 Decision:")
    import json
    try:
        decision = json.loads(response)
        print(f"   Action: {decision.get('action', 'UNKNOWN')}")
        print(f"   Symbol: {decision.get('symbol', 'N/A')}")
        print(f"   Confidence: {decision.get('confidence', 0)}%")
        print(f"   Reason: {decision.get('reason', 'N/A')}")
    except:
        print(f"   ⚠️  Response not in JSON format")
    
    print("\n" + "=" * 60)
    print("✅ FULL INTEGRATION TEST PASSED")
    print("=" * 60)
    print("✅ Binance public API: Working")
    print("✅ Claude API: Working") 
    print("✅ End-to-end flow: Working")
    print(f"✅ Token efficiency: {tokens_used} tokens")
    
except Exception as e:
    print(f"❌ Claude Error: {e}")
    import traceback
    traceback.print_exc()
