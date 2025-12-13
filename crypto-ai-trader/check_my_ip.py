"""
Check your current IP address that Binance sees
"""
import requests

print("=" * 60)
print("🔍 CHECKING YOUR IP ADDRESS")
print("=" * 60)

# Check your external IP (what Binance sees)
print("\n📡 Your External IP (what Binance API sees):")
try:
    response = requests.get('https://api.ipify.org?format=json', timeout=5)
    external_ip = response.json()['ip']
    print(f"   {external_ip}")
    print(f"\n✅ Add this IP to your Binance API whitelist: {external_ip}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check localhost
print("\n🏠 Localhost IPs:")
print("   127.0.0.1 (IPv4)")
print("   ::1 (IPv6)")
print("\n✅ Also add localhost IPs to whitelist for local testing")

print("\n" + "=" * 60)
print("📋 STEPS TO UPDATE BINANCE API WHITELIST:")
print("=" * 60)
print("1. Go to: https://www.binance.com/en/my/settings/api-management")
print("2. Find your API key (starts with: SZGGxAe1sq...)")
print("3. Click 'Edit restrictions'")
print("4. Under 'IP access restrictions', add these IPs:")
print(f"   - {external_ip if 'external_ip' in locals() else 'Your external IP'}")
print("   - 127.0.0.1")
print("   - ::1")
print("5. Click 'Save' and confirm with 2FA")
print("\n⚠️  After adding IPs, wait 1-2 minutes for changes to take effect")
