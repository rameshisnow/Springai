#!/bin/bash
# Script to fix and restart the Goldilock bot on VPS
# Run this on your VPS: ssh root@67.219.108.145 'bash -s' < fix_vps_bot.sh

set -e  # Exit on error

echo "🔧 Fixing Goldilock Bot on VPS..."
echo "=================================="

# Navigate to project directory
cd /opt/springai/crypto-ai-trader

# Stop any running bots
echo "⏹️  Stopping old bots..."
pkill -f "main.py" || true
pkill -f "signal_generator" || true
sleep 2

# Backup current code
echo "💾 Creating backup..."
cp main.py main.py.backup.$(date +%Y%m%d_%H%M%S) || true
cp src/config/constants.py src/config/constants.py.backup.$(date +%Y%m%d_%H%M%S) || true

# Fix 1: Update main.py - change tradeable_coins to coins_data
echo "🔧 Fix 1: Updating main.py..."
sed -i 's/tradeable_coins,/coins_data,/g' main.py

# Fix 2: Update scan interval to 30 minutes
echo "🔧 Fix 2: Updating scan interval to 30 minutes..."
sed -i 's/ANALYSIS_INTERVAL_MINUTES = 240/ANALYSIS_INTERVAL_MINUTES = 30/g' src/config/constants.py

# Fix 3: Update signal_generator.py - ensure df_1h is passed to check_entry
echo "🔧 Fix 3: Updating signal_generator.py..."
# Check if the file needs the fix
if grep -q "should_enter, reason = strategy.check_entry(" src/ai/signal_generator.py; then
    # Create a temporary Python script to fix it properly
    python3 << 'PYTHON_SCRIPT'
import re

# Read the file
with open('src/ai/signal_generator.py', 'r') as f:
    content = f.read()

# Fix the check_entry call to include df_1h
# Pattern: should_enter, reason = strategy.check_entry(\n    df_4h=df_4h,
old_pattern = r'should_enter, reason = strategy\.check_entry\(\s*df_4h=df_4h,'
new_pattern = 'should_enter, reason = strategy.check_entry(\n                    df_1h=df_1h,\n                    df_4h=df_4h,'

if re.search(old_pattern, content) and 'df_1h=df_1h,' not in content:
    content = re.sub(old_pattern, new_pattern, content)
    with open('src/ai/signal_generator.py', 'w') as f:
        f.write(content)
    print("✅ Fixed check_entry() call")
else:
    print("✅ check_entry() already has df_1h parameter")

# Ensure DataFrames have proper datetime index
if 'df_4h = df_4h.set_index' not in content:
    # Add index setting after data fetch
    old = r'(df_4h = await binance_fetcher\.get_klines\(symbol=symbol, interval=\'4h\', limit=200\)\s*df_1h = await binance_fetcher\.get_klines\(symbol=symbol, interval=\'1h\', limit=200\))'
    new = r'\1\n\n                # Ensure timestamp is set as index for both dataframes\n                if \'timestamp\' in df_4h.columns:\n                    df_4h = df_4h.set_index(\'timestamp\')\n                if \'timestamp\' in df_1h.columns:\n                    df_1h = df_1h.set_index(\'timestamp\')'
    
    content = re.sub(old, new, content, count=1)
    with open('src/ai/signal_generator.py', 'w') as f:
        f.write(content)
    print("✅ Added DataFrame index fix")
PYTHON_SCRIPT
fi

# Fix 4: Update goldilock_strategy.py - fix negative index handling
echo "🔧 Fix 4: Updating goldilock_strategy.py..."
python3 << 'PYTHON_SCRIPT'
with open('src/strategies/goldilock_strategy.py', 'r') as f:
    content = f.read()

# Fix negative index handling
old_code = '''        # Calculate indicators on 4H timeframe
        df_4h = self.calculate_indicators(df_4h)
        
        # Get current time from 4H data
        if current_idx >= len(df_4h):
            return False, "invalid_index"
        
        current_time = df_4h.index[current_idx]'''

new_code = '''        # Calculate indicators on 4H timeframe
        df_4h = self.calculate_indicators(df_4h)
        
        # Handle negative index (e.g., -1 for latest bar)
        if current_idx < 0:
            current_idx = len(df_4h) + current_idx
        
        # Get current time from 4H data
        if current_idx >= len(df_4h) or current_idx < 0:
            return False, "invalid_index"
        
        current_time = df_4h.index[current_idx]'''

if 'if current_idx < 0:' not in content:
    content = content.replace(old_code, new_code)
    with open('src/strategies/goldilock_strategy.py', 'w') as f:
        f.write(content)
    print("✅ Fixed negative index handling")
else:
    print("✅ Negative index handling already fixed")
PYTHON_SCRIPT

# Create logs directory if it doesn't exist
mkdir -p logs

# Restart the bot with Goldilock strategy
echo ""
echo "🚀 Starting Goldilock Strategy Bot..."
nohup python3 -m src.ai.signal_generator > logs/vps_bot.log 2>&1 &
NEW_PID=$!

sleep 5

# Check if it's running
if ps -p $NEW_PID > /dev/null; then
    echo ""
    echo "✅ Bot started successfully!"
    echo "   PID: $NEW_PID"
    echo "   Log: /opt/springai/crypto-ai-trader/logs/vps_bot.log"
    echo ""
    echo "📊 Latest log output:"
    echo "-------------------"
    tail -30 logs/vps_bot.log
    echo ""
    echo "✅ All fixes applied! Bot is running with:"
    echo "   - 30-minute scan interval"
    echo "   - Fixed tradeable_coins error"
    echo "   - Goldilock strategy enabled"
    echo "   - Tracking: DOGEUSDT, SHIBUSDT, SOLUSDT"
else
    echo ""
    echo "❌ Failed to start bot. Check logs:"
    tail -50 logs/vps_bot.log
    exit 1
fi
