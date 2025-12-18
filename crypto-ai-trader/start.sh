#!/bin/bash
# Local Startup Script for Goldilock Strategy Trading Bot

set -e  # Exit on error

echo "=================================================================="
echo "🚀 SpringAI Crypto Trading Bot - Goldilock Strategy"
echo "=================================================================="
echo ""

# Check Python version
echo "📋 Checking Python version..."
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt 2>&1 | grep -v "already satisfied" || true

echo ""
echo "=================================================================="
echo "⚙️  CONFIGURATION CHECK"
echo "=================================================================="

# Check for .env file
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo ""
    echo "Please create .env file with:"
    echo "  BINANCE_API_KEY=your_api_key"
    echo "  BINANCE_SECRET_KEY=your_secret_key"
    echo "  ANTHROPIC_API_KEY=your_claude_key"
    echo ""
    exit 1
else
    echo "✅ .env file found"
fi

# Check for required directories
echo ""
echo "📁 Checking directories..."
mkdir -p data
mkdir -p logs
echo "✅ Directories ready"

# Show current configuration
echo ""
echo "=================================================================="
echo "📊 GOLDILOCK STRATEGY CONFIGURATION"
echo "=================================================================="
echo "Tracked Coins: DOGE, SHIB, SOL"
echo "Position Size: 40% per trade"
echo "Max Positions: 2 (80% capital deployed)"
echo "Min Hold: 7 days (8% stop loss)"
echo "Regular Hold: 3% stop loss (day 7+)"
echo "TP1: +15% (close 50%, activate trailing)"
echo "TP2: +30% (close remaining 50%)"
echo "Trailing Stop: 5% from highest"
echo "Max Hold: 90 days (force exit)"
echo "Monthly Limit: 1 trade per coin"
echo ""

# Check current branch
echo "=================================================================="
echo "🔍 GIT STATUS"
echo "=================================================================="
BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "Current Branch: $BRANCH"

if [ "$BRANCH" != "goldilock" ]; then
    echo ""
    echo "⚠️  WARNING: Not on goldilock branch!"
    echo "Current branch: $BRANCH"
    echo ""
    read -p "Switch to goldilock branch? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git checkout goldilock || echo "Failed to switch branch"
    fi
fi

echo ""
echo "=================================================================="
echo "🎛️  STARTUP OPTIONS"
echo "=================================================================="
echo ""
echo "Choose startup mode:"
echo "1) DRY RUN (No real trades, testing only)"
echo "2) MONITORING (Track signals, no execution)"
echo "3) LIVE TRADING (Real trades with real money)"
echo "4) DASHBOARD ONLY (Web interface)"
echo "5) RUN TESTS (Validate Goldilock strategy)"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🧪 Starting in DRY RUN mode..."
        echo "   - Simulated trades only"
        echo "   - No real orders"
        echo "   - Safe for testing"
        echo ""
        export DRY_RUN_ENABLED=true
        export MONITORING_ONLY=false
        python3 main.py
        ;;
    2)
        echo ""
        echo "👁️  Starting in MONITORING mode..."
        echo "   - Signals tracked"
        echo "   - No order execution"
        echo "   - Dashboard updates"
        echo ""
        export DRY_RUN_ENABLED=false
        export MONITORING_ONLY=true
        python3 main.py
        ;;
    3)
        echo ""
        echo "⚠️  =================================="
        echo "⚠️  LIVE TRADING MODE"
        echo "⚠️  =================================="
        echo "   - Real trades with real money"
        echo "   - Actual orders on Binance"
        echo "   - 40% position sizing"
        echo ""
        read -p "Are you SURE you want to trade live? (type 'YES' to confirm): " confirm
        if [ "$confirm" = "YES" ]; then
            echo ""
            echo "🚀 Starting LIVE TRADING..."
            echo "   Current Balance: Check dashboard"
            echo "   Max Risk: 80% (2 positions @ 40% each)"
            echo ""
            export DRY_RUN_ENABLED=false
            export MONITORING_ONLY=false
            python3 main.py
        else
            echo "❌ Live trading cancelled"
            exit 0
        fi
        ;;
    4)
        echo ""
        echo "📊 Starting Dashboard..."
        echo "   Web interface: http://localhost:8080"
        echo "   Auto-refresh: 60 seconds"
        echo ""
        python3 -m src.web.server
        ;;
    5)
        echo ""
        echo "🧪 Running Goldilock Strategy Tests..."
        echo ""
        echo "Test 1: Exit Logic Validation"
        python3 test_goldilock_exits.py
        echo ""
        echo "Test 2: Integration Test"
        python3 test_goldilock_integration.py
        echo ""
        echo "✅ All tests complete!"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac
