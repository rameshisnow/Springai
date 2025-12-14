"""
Constants and parameters for trading strategy
"""
from enum import Enum
from typing import Dict

# ==================== CAPITAL & POSITION SIZING ====================

# ✅ FIXED: Use DYNAMIC balance, not hardcoded capital
# This ensures position sizing matches actual available funds
USE_DYNAMIC_BALANCE = True  # Always use live Binance balance for position sizing
BALANCE_BUFFER_PERCENT = 0.90  # Use max 90% of free balance (10% buffer for fees/slippage)

# Legacy config (DO NOT USE - kept only for reference)
STARTING_CAPITAL_AUD = 1000  # NOT USED - always fetch from Binance
RISK_PER_TRADE_PERCENT = 5.0  # ✅ INCREASED to 5% to meet Binance minimum notional ($5+)
MAX_POSITION_SIZE_USD = None  # IGNORED - calculated dynamically from balance

# Kelly Criterion: f = (bp - q) / b
# b = profit ratio, p = win rate, q = loss rate
# Conservative Kelly = Kelly * 0.25
KELLY_CRITERION_FRACTION = 0.25

# ==================== POSITION MANAGEMENT ====================

MAX_OPEN_POSITIONS = 2  # ✅ REDUCED from 3 to 2 - Oracle Mode works best with 1-2
# Reason: High conviction + low frequency trades
# More positions = higher correlation risk + AI confidence degrades
MIN_POSITION_VALUE_USD = 5.0  # ✅ Minimum position value in USD (Binance spot min ~$5)
MIN_TRADING_VOLUME_USD = 5_000_000  # ✅ LOWERED from $10M to $5M to include mid-caps (gets ~50-80 coins)
MIN_MARKET_CAP_USD = 100_000_000  # Min $100M market cap
MIN_COIN_AGE_DAYS = 90  # Coin must exist for 90+ days

# ==================== SCREENING (PRE-CLAUDE) ====================

SCREEN_TOP_N = 200  # ✅ INCREASED from 100 to 200 - more coins evaluated
SCREEN_BREAKOUT_WINDOW = 50  # Lookback for breakout high (1H)
SCREEN_RSI_MIN = 55
SCREEN_RSI_MAX = 70
COIN_COOLDOWN_HOURS = 4  # Minimum hours before re-considering same coin

# ==================== ENTRY & EXIT RULES ====================

# Take Profit Levels (multiple exits)
TAKE_PROFIT_LEVELS = [
    {"percent": 3, "position_percent": 0.33},   # Exit 33% at +3%
    {"percent": 5, "position_percent": 0.33},   # Exit 33% at +5%
    {"percent": 8, "position_percent": 0.34},   # Exit 34% at +8%
]

# Stop Loss
STOP_LOSS_PERCENT = 3.0  # Hard stop at -3%
TRAILING_STOP_PERCENT = 2.0  # Trailing stop at 2% below highest price

# Timeframes & Analysis
# For intraday trades: 15-30 min (fast signals, more trades, higher risk)
# For swing trades: 60-240 min (slower signals, quality over quantity)
ANALYSIS_INTERVAL_MINUTES = 60  # Run AI analysis every 60 minutes (optimum for quality setups)
TRADING_TIMEFRAMES = ["1h", "4h"]  # Analyze on 1h and 4h charts
PREFERRED_TIMEFRAME = "1h"  # Primary trading timeframe (1h for intraday, 4h for swing)

# ==================== AI VALIDATION & FILTERING ====================

# Adaptive confidence thresholds (market-aware)
MIN_CONFIDENCE_TO_TRADE = 70  # ✅ Base: 70% in normal markets
MIN_CONFIDENCE_TRENDING = 65  # Lower threshold in strong trending markets
MIN_CONFIDENCE_SIDEWAYS = 75  # Higher threshold in choppy/sideways markets
MIN_CONFIDENCE_VOLATILE = 70  # Standard threshold in high volatility

# Position replacement (when positions are full)
ALLOW_POSITION_REPLACEMENT = False  # ⚠️ EXPERIMENTAL: Replace weak positions with strong signals
MIN_CONFIDENCE_FOR_REPLACEMENT = 80  # New signal must be ≥80% to replace
MAX_CONFIDENCE_TO_REPLACE = 50  # Only replace positions with ≤50% original confidence
REPLACEMENT_MIN_IMPROVEMENT = 15  # New signal must be +15% better than old

MIN_CONSENSUS_AGREEMENTS = 2  # Require 2 out of 3 prompt variations to agree
HALLUCINATION_CHECK_ENABLED = True  # Cross-validate data

# ==================== SAFETY CIRCUITS & LIMITS ====================

MAX_RISK_PER_DAY_PERCENT = 4.0  # ✅ Max 4% daily loss before circuit breaker activates
# If hit: no more trades for 24 hours
MAX_TRADES_PER_24H = 4  # ✅ Max 4 trades per day to prevent over-trading
# If exceeded: NO_TRADE mode for 12 hours
REENTRY_COOLDOWN_MINUTES = 90  # ✅ Wait 90min before re-entering same coin after close
# Prevents revenge-trading loops
MAX_HOLD_HOURS = 4  # ✅ Exit position after 4 hours max (Oracle signals decay fast)
ATR_VOLATILITY_CUTOFF = 0.035  # ✅ Avoid trades if ATR > 3.5% (volatile = traps)

# ==================== POSITION LIFECYCLE ====================

AUTO_KILL_TRADES = False  # ✅ NEVER auto-close live positions for new signals
# Only close on: stop-loss, take-profit, time exit, or volatility breaker

# Position health monitoring (for replacement logic)
POSITION_STALE_CANDLES = 8  # Position is "stale" after 8 candles with no movement
POSITION_WEAK_SL_DISTANCE_PERCENT = 1.5  # Position is "weak" if price within 1.5% of SL
POSITION_WEAK_CONFIDENCE_THRESHOLD = 50  # Position is "weak" if original confidence ≤50%

# Response parsing thresholds
BULLISH_THRESHOLD = 0.70  # Confidence >= 70% = buy signal
NEUTRAL_THRESHOLD = 0.30  # 30-70% = wait

# ==================== CIRCUIT BREAKERS & SAFETY ====================

# Daily Loss Limits
DAILY_MAX_LOSS_AUD = 100  # Stop trading if lost $100 in a day
DAILY_MAX_LOSS_PERCENT = 10  # Stop if down 10%
MAX_CONSECUTIVE_LOSSES = 3  # Stop after 3 losses in a row
COOLDOWN_AFTER_LOSS_MINUTES = 120  # Wait 2 hours after loss

# Portfolio Limits
MAX_DRAWDOWN_PERCENT = 15  # Stop all trading if down 15%
CIRCUIT_BREAKER_RECOVERY_HOURS = 24  # Wait 24 hours to resume

# Position Limits
MAX_POSITION_EXPOSURE_PERCENT = 6  # Max 6% of capital in one position
LEVERAGE_MULTIPLIER = 1  # No leverage (1x)

# ==================== MARKET CONDITIONS ====================

# Only trade during high volatility periods
MIN_VOLATILITY_PERCENT = 2.0  # Min 2% price movement in lookback window
VOLATILITY_LOOKBACK_HOURS = 24

# Volume conditions
MIN_RELATIVE_VOLUME = 1.5  # Volume should be 1.5x average
VOLUME_LOOKBACK_BARS = 20

# Liquidity check
SLIPPAGE_TOLERANCE_PERCENT = 0.15  # Max 0.15% slippage
LIQUIDITY_CHECK_ENABLED = True

# ==================== TIMING & SCHEDULING ====================

# Crypto trades 24/7 - no trading hours restriction
MARKET_OPEN_HOUR = 0   # Crypto is 24/7
MARKET_CLOSE_HOUR = 23  # Crypto is 24/7
TRADING_HOURS_UTC = list(range(0, 24))  # Active 24/7

# Avoid trading around major events (Black Swan protection)
HIGH_IMPACT_EVENT_AVOIDANCE_MINUTES = 60
VOLATILITY_CRUSH_AVOIDANCE_ENABLED = True

# ==================== NOTIFICATION SETTINGS ====================

TELEGRAM_HOURLY_REPORT = True  # Send hourly status
TELEGRAM_TRADE_ALERTS = True  # Notify on every trade
TELEGRAM_PNL_UPDATES = True  # Notify on P&L changes
TELEGRAM_ERROR_ALERTS = True  # Notify on errors

# ==================== BINANCE TRADING PARAMS ====================

# Order types
ORDER_TYPE = "MARKET"  # Use market orders for speed
LIMIT_ORDER_TIMEOUT_MINUTES = 5  # Cancel limit orders after 5 min

# Commission
BINANCE_MAKER_FEE = 0.001  # 0.1% maker fee
BINANCE_TAKER_FEE = 0.001  # 0.1% taker fee (simplified)
TOTAL_TRADING_COST_PERCENT = BINANCE_TAKER_FEE * 2  # Entry + exit

# Trading pairs
QUOTE_ASSET = "USDT"  # Trade in USDT pairs
STABLECOIN_PAIRS = ["USDT", "BUSD", "USDC"]

# Exclude certain coins
EXCLUDED_COINS = [
    "USDT", "BUSD", "USDC", "DAI",  # Stablecoins
    "BNB",  # Exchange token (optional)
    "LUNC", "LUNA", "FTT",  # Already delisted/collapsed
]

EXCLUDE_MONITORING_COINS = True  # Don't trade in-development coins

# ==================== AI MODEL CONFIGURATION ====================

class AIProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    HYBRID = "hybrid"  # Use both for consensus

AI_PROVIDER = AIProvider.CLAUDE.value

# Claude Model (using available model on this API tier)
CLAUDE_MODEL = "claude-3-5-haiku-20241022"  # Claude 3.5 Haiku (newest, faster, similar cost)
# Other options require higher API tiers:
# "claude-3-haiku-20240307" (older Haiku version)
# "claude-3-sonnet-20240229" (88% accuracy - requires higher tier)
# "claude-3-5-sonnet-20240620" (better but requires higher tier)
CLAUDE_MAX_TOKENS = 500  # Increased for better analysis depth
CLAUDE_TEMPERATURE = 0.3  # Lower temp for consistent, deterministic analysis

# OpenAI Model (backup)
OPENAI_MODEL = "gpt-4-turbo"
OPENAI_MAX_TOKENS = 1500
OPENAI_TEMPERATURE = 0.3

# ==================== BACKTESTING ====================

BACKTEST_START_DATE = "2023-01-01"
BACKTEST_END_DATE = "2025-01-01"
BACKTEST_LOOKBACK_MONTHS = 24  # 2 years of historical data

# Success criteria
BACKTEST_MIN_WIN_RATE = 0.60  # 60% win rate
BACKTEST_MIN_PROFIT_FACTOR = 1.5  # Profit factor >= 1.5
BACKTEST_MAX_DRAWDOWN = 0.20  # Max 20% drawdown
BACKTEST_MIN_SHARPE_RATIO = 1.5

# ==================== LOGGING & DATA ====================

LOG_TRADES = True
LOG_PRICE_UPDATES = False  # Too verbose if True
LOG_AI_DECISIONS = True
LOG_RISK_CHECKS = True

KEEP_TRADE_HISTORY = True  # Store in DB for analysis
TRADE_HISTORY_RETENTION_DAYS = 365

# ==================== ADVANCED FEATURES ====================

# Sentiment Analysis (optional enhancement)
USE_SENTIMENT_ANALYSIS = False
SENTIMENT_WEIGHT = 0.2  # 20% weight in decision

# Technical Indicator Confirmation
USE_TECHNICAL_CONFIRMATION = True
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_SIGNAL_CROSSOVER_REQUIRED = True

# On-chain Metrics (requires paid API)
USE_ONCHAIN_METRICS = False
WHALE_MOVEMENT_THRESHOLD_USD = 1_000_000

# ==================== SYSTEM HEALTH ====================

# Global kill switch – when True, no new trades are opened.
# Existing positions can still be monitored/closed by SL/TP.
GLOBAL_TRADING_PAUSE = False

HEARTBEAT_INTERVAL_SECONDS = 300  # Check system health every 5 min
API_TIMEOUT_SECONDS = 30
RECONNECT_ATTEMPTS = 5
RECONNECT_WAIT_SECONDS = 10

# Database
AUTO_BACKUP_ENABLED = True
AUTO_BACKUP_INTERVAL_HOURS = 24

# ==================== DEBUGGING ====================

DEBUG_MODE = False
DRY_RUN_ENABLED = False  # Live mode: Execute actual orders on Binance
MONITORING_ONLY = False  # Live trading: Execute real trades when signals trigger
VERBOSE_AI_RESPONSES = False  # Print full LLM responses

# API Call Optimization
CACHE_MARKET_DATA_SECONDS = 60  # Cache market data for 60 seconds
BATCH_API_CALLS = True  # Fetch multiple coins in parallel
MAX_CONCURRENT_API_CALLS = 5  # Limit parallel requests
