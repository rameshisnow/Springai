"""
Detailed Binance API diagnostic
"""
import os
import time
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔐 BINANCE API DIAGNOSTIC")
print("=" * 70)

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

print(f"\n📋 API Key Info:")
print(f"   Key: {api_key[:20]}...{api_key[-10:]}")
print(f"   Length: {len(api_key)} characters")

print(f"\n🔑 API Secret Info:")
print(f"   Secret: {'*' * 30}")
print(f"   Length: {len(api_secret)} characters")

# Test with detailed error handling
from binance.spot import Spot

print("\n" + "=" * 70)
print("🧪 TEST 1: Account Status")
print("=" * 70)

client = Spot(api_key=api_key, api_secret=api_secret)

try:
    print("\nAttempting to call account() endpoint...")
    account = client.account()
    
    print("✅ SUCCESS! Account API is working!")
    print(f"\n📊 Account Details:")
    print(f"   Can Trade: {account.get('canTrade', False)}")
    print(f"   Can Withdraw: {account.get('canWithdraw', False)}")
    print(f"   Can Deposit: {account.get('canDeposit', False)}")
    print(f"   Update Time: {account.get('updateTime', 'N/A')}")
    
    # Get balances
    balances = account.get('balances', [])
    non_zero = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
    
    print(f"\n💰 Non-zero Balances ({len(non_zero)} assets):")
    for bal in non_zero[:10]:  # Show first 10
        free = float(bal['free'])
        locked = float(bal['locked'])
        total = free + locked
        if total > 0:
            print(f"   {bal['asset']:6s}: {total:>15,.8f} (Free: {free:,.8f}, Locked: {locked:,.8f})")
    
    # Check USDT specifically
    usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
    if usdt:
        usdt_total = float(usdt['free']) + float(usdt['locked'])
        print(f"\n💵 USDT Balance: ${usdt_total:.2f}")
    else:
        print(f"\n⚠️  No USDT balance")
    
except Exception as e:
    error_str = str(e)
    print(f"\n❌ FAILED: {error_str}\n")
    
    if "401" in error_str and "-2015" in error_str:
        print("🔍 ERROR ANALYSIS: 401 -2015")
        print("   This error means: 'Invalid API-key, IP, or permissions for action'")
        print("\n📋 CHECKLIST - Please verify:")
        print("\n   1️⃣  API KEY PERMISSIONS:")
        print("      Go to: Binance.com → Profile → API Management")
        print("      Your API key should have these ENABLED:")
        print("      ✓ Enable Reading")
        print("      ✓ Enable Spot & Margin Trading (if you want to trade)")
        print("\n   2️⃣  IP WHITELIST:")
        print("      Check that you added:")
        print("      ✓ 127.0.0.1 (for localhost)")
        print("      ✓ Your external IP address")
        print("      Or temporarily set to 'Unrestricted' for testing")
        print("\n   3️⃣  WAIT TIME:")
        print("      After making changes, wait 2-5 minutes")
        print("      Binance needs time to propagate the changes")
        print("\n   4️⃣  VERIFY API KEY:")
        print("      Make sure you copied the CORRECT API key")
        print("      The key in your .env file should match Binance exactly")
        
    elif "403" in error_str:
        print("🔍 ERROR: 403 Forbidden")
        print("   - Your IP is definitely not whitelisted")
        print("   - Add your IP or use 'Unrestricted' access")
        
    elif "signature" in error_str.lower():
        print("🔍 ERROR: Signature issue")
        print("   - Your API SECRET might be incorrect")
        print("   - Verify the secret in your .env file")

print("\n" + "=" * 70)
print("💡 RECOMMENDATION")
print("=" * 70)

print("""
If error persists after checking everything:

1. DELETE the current API key on Binance
2. CREATE a NEW API key with these settings:
   - Label: "Crypto Trading Bot"
   - Enable Reading: ✓
   - Enable Spot & Margin Trading: ✓
   - IP Restriction: Add 127.0.0.1 (or Unrestricted for testing)
3. Copy the NEW key and secret to your .env file
4. Wait 2 minutes
5. Run this test again

Note: Sometimes Binance API keys just don't work properly and 
need to be recreated. This is a known issue.
""")

print("=" * 70)
