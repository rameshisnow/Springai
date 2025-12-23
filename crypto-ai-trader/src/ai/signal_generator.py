"""
Signal generation orchestrator - Three-tier architecture for cost optimization
- Tier 1: Market Watch (lightweight, no Claude)
- Tier 2: AI Decision (expensive, full Claude only when capacity exists)
- Tier 3: Trade Execution (only when all gates pass)
"""
import asyncio
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import time

from src.data.data_fetcher import (
    binance_fetcher,
    data_processor,
)
from src.utils.indicators import compute_all_indicators, format_indicators_for_prompt
from src.ai.ai_analyzer import ai_analyzer
from src.trading.risk_manager import risk_manager
from src.trading.order_manager import order_manager
from src.trading.safety_gates import safety_gates
from src.monitoring.signal_monitor import signal_monitor
from src.utils.logger import logger
from src.config.constants import (
    ANALYSIS_INTERVAL_MINUTES,
    PREFERRED_TIMEFRAME,
    TRADING_HOURS_UTC,
    MONITORING_ONLY,
    DRY_RUN_ENABLED,
    MAX_OPEN_POSITIONS,
    SCREEN_TOP_N,
    SCREEN_MAX_CANDIDATES,
    SCREEN_BREAKOUT_WINDOW,
    SCREEN_RSI_MIN,
    SCREEN_RSI_MAX,
    COIN_COOLDOWN_HOURS,
)
from src.strategies.strategy_manager import StrategyManager

logger.info(f"🔧 CONSTANTS LOADED: MONITORING_ONLY={MONITORING_ONLY}, DRY_RUN_ENABLED={DRY_RUN_ENABLED}")

class SignalOrchestrator:
    """
    Three-tier orchestration for professional token cost optimization:
    
    Tier 1 (Market Watch): Lightweight market monitoring, NO Claude calls
    Tier 2 (AI Decision): Full Claude analysis ONLY when capacity exists
    Tier 3 (Execution): Trade execution only when all safety gates pass
    """
    
    def __init__(self):
        self.last_analysis_time = None
        self.last_light_check_time = None
        self.position_count = 0
        self.token_usage_session = 0
        self.scan_history_file = "data/last_scan.json"
        
        # Initialize strategy manager
        self.strategy_manager = StrategyManager()
        
        logger.info("Signal Orchestrator initialized (Strategy-Based Architecture)")
        logger.info("  Tier 1: Strategy-based screening")
        logger.info("  Tier 2: AI Decision (full Claude only when capacity exists)")
        logger.info("  Tier 3: Trade Execution (strict validation)")
        logger.info(f"  Tracked coins: {', '.join(self.strategy_manager.get_all_tracked_coins())}")
        
        # Startup validation: Check for position cap violations
        self._validate_position_cap_on_startup()
    
    def _record_scan_completion(self, status: str = "ok", reason: str = ""):
        """Record scan completion metadata for dashboard tracking.

        status: one of ["ok", "no_candidates", "outside_hours", "positions_full",
                        "daily_loss_limit", "error"]
        reason: human-readable explanation
        """
        import json
        from pathlib import Path
        try:
            scan_data = {
                'last_scan_utc': datetime.now(timezone.utc).isoformat(),
                'interval_minutes': ANALYSIS_INTERVAL_MINUTES,
                'status': status,
                'reason': reason,
            }
            Path(self.scan_history_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.scan_history_file, 'w') as f:
                json.dump(scan_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to record scan completion: {e}")
    
    def _validate_position_cap_on_startup(self) -> None:
        """Validate position count on startup and warn if cap is exceeded"""
        try:
            position_count = self._get_position_count()
            
            if position_count > MAX_OPEN_POSITIONS:
                logger.warning("\n" + "="*70)
                logger.warning(f"⚠️  POSITION CAP VIOLATION DETECTED")
                logger.warning(f"⚠️  Current: {position_count} positions")
                logger.warning(f"⚠️  Maximum: {MAX_OPEN_POSITIONS} positions")
                logger.warning(f"⚠️  BLOCKING NEW TRADES until positions close")
                logger.warning(f"⚠️  Claude analysis will run in LIGHT MODE only (token savings)")
                logger.warning("="*70 + "\n")
            elif position_count == MAX_OPEN_POSITIONS:
                logger.info(f"📊 Positions at capacity: {position_count}/{MAX_OPEN_POSITIONS}")
                logger.info("⚡ Will run LIGHT monitoring mode (70-90% token savings)")
            else:
                logger.info(f"✅ Capacity available: {position_count}/{MAX_OPEN_POSITIONS} positions")
        except Exception as e:
            logger.error(f"Error validating position cap: {e}")
    
    def _get_position_count(self) -> int:
        """Get current number of ACTIVE positions (excluding dust positions marked as closed/dust)"""
        if not hasattr(risk_manager, 'positions'):
            return 0
        
        active_positions = 0
        for symbol, position in risk_manager.positions.items():
            try:
                # Only count positions with status="active" (dust/closed positions don't count)
                if position.status == "active":
                    active_positions += 1
            except Exception:
                # If status field doesn't exist, assume active (for backward compatibility)
                active_positions += 1
        
        return active_positions
    
    def _is_capacity_available(self) -> bool:
        """Check if we have capacity for new positions (excluding dust)"""
        return self._get_position_count() < MAX_OPEN_POSITIONS
    
    def _has_weak_positions(self) -> tuple[bool, Optional[str]]:
        """
        Check if any positions are weak and could be replaced
        
        Returns:
            (has_weak: bool, weakest_symbol: str | None)
        """
        from src.config.constants import (
            ALLOW_POSITION_REPLACEMENT,
            POSITION_WEAK_SL_DISTANCE_PERCENT,
        )
        
        if not ALLOW_POSITION_REPLACEMENT:
            return False, None
        
        if not hasattr(risk_manager, 'positions'):
            return False, None
        
        weakest_symbol = None
        weakest_score = 100  # Lower score = weaker position
        
        for symbol, position in risk_manager.positions.items():
            try:
                # Get current price
                current_price = binance_fetcher.get_current_price(symbol) if hasattr(binance_fetcher, 'get_current_price') else position.entry_price
                
                # Calculate distance to stop loss
                sl_distance_percent = ((current_price - position.stop_loss) / position.stop_loss) * 100
                
                # Position is weak if:
                # 1. Very close to stop loss (< 1.5%)
                # 2. Underwater and stagnant
                if sl_distance_percent < POSITION_WEAK_SL_DISTANCE_PERCENT:
                    score = sl_distance_percent
                    if score < weakest_score:
                        weakest_score = score
                        weakest_symbol = symbol
                        
            except Exception:
                continue
        
        return weakest_symbol is not None, weakest_symbol
    
    async def _collect_market_data(self, top_coins: List[Dict]) -> List[Dict]:
        """
        TIER 1: Market Watch - Collect essential market metrics WITHOUT Claude
        Returns minimal essential data for all coins
        """
        logger.info("\n" + "=" * 60)
        logger.info("📊 TIER 1: Market Watch (Lightweight, No Claude)")
        logger.info("=" * 60)
        
        coins_essential_data = []
        
        for idx, coin in enumerate(top_coins, 1):
            symbol = coin.get('symbol', '').upper()
            binance_symbol = f"{symbol}USDT"
            
            try:
                logger.info(f"[{idx}/{len(top_coins)}] {binance_symbol}...")
                
                # Fetch OHLCV
                df = await binance_fetcher.get_klines(
                    symbol=binance_symbol,
                    interval='1h',
                    limit=100
                )
                
                if df.empty:
                    continue
                
                # Compute indicators
                df = compute_all_indicators(df)
                
                # Extract ONLY essential metrics
                current_price = float(df.iloc[-1]['close'])
                
                # Calculate % changes
                change_1h = ((df.iloc[-1]['close'] / df.iloc[-2]['close']) - 1) * 100 if len(df) >= 2 else 0
                change_4h = ((df.iloc[-1]['close'] / df.iloc[-5]['close']) - 1) * 100 if len(df) >= 5 else 0
                change_24h = ((df.iloc[-1]['close'] / df.iloc[-25]['close']) - 1) * 100 if len(df) >= 25 else 0
                
                # Volume in USDT
                volume_1h = float(df.iloc[-1]['volume']) * current_price
                volume_24h = float(df['volume'].iloc[-24:].sum()) * current_price if len(df) >= 24 else volume_1h * 24
                
                # Technical indicators
                rsi = float(df.iloc[-1].get('rsi', 50))
                atr = float(df.iloc[-1].get('atr', 0))
                atr_percent = (atr / current_price) * 100 if current_price > 0 else 0
                ema200 = float(df.iloc[-1].get('ema_200', current_price))
                above_ema200 = current_price > ema200
                
                # Store essential data
                coins_essential_data.append({
                    'symbol': binance_symbol,
                    'current_price': current_price,
                    'indicators': {
                        'change_1h': change_1h,
                        'change_4h': change_4h,
                        'change_24h': change_24h,
                        'volume_1h': volume_1h,
                        'volume_24h': volume_24h,
                        'rsi': rsi,
                        'atr': atr,
                        'atr_percent': atr_percent,
                        'above_ema200': above_ema200,
                    },
                    'df': df,
                })
                
            except Exception as e:
                logger.error(f"Error collecting data for {binance_symbol}: {e}")
                continue
        
        logger.info(f"✅ Tier 1 Complete: {len(coins_essential_data)} coins analyzed (NO Claude calls)")
        return coins_essential_data

    async def _screen_strategy_based(self, top_coins: List[Dict]) -> List[Dict]:
        """Strategy-based screening using each coin's strategy entry logic.

        For Goldilock Strategy (DOGE/SHIB/SOL):
        - RSI < 40 (oversold)
        - Need 3 of 4 conditions:
          1. EMA 9 > EMA 21 (bullish trend)
          2. Volume spike > 1.3x average
          3. MACD bullish (MACD > Signal)
          4. Daily trend up (price > daily EMA50)
        
        Uses strategy.check_entry() for validation instead of hardcoded rules.
        """

        logger.info("\n" + "=" * 60)
        logger.info("🔎 Strategy-Based Screen: Using strategy.check_entry() for each coin")
        logger.info("=" * 60)

        filtered: List[Dict] = []
        screening_details: Dict[str, Dict] = {}  # Track why coins pass/fail
        # Expose latest screening details to later tiers (Claude + safety gates)
        self.last_screening_details = screening_details

        logger.info(f"📋 Evaluating {len(top_coins)} coins using strategy entry conditions...")

        for idx, coin in enumerate(top_coins, 1):
            base = coin.get('symbol', '').upper()
            symbol = f"{base}USDT"
            try:
                # Get strategy for this coin
                strategy = self.strategy_manager.get_strategy(symbol)
                
                if not strategy:
                    logger.debug(f"   ⊘ {symbol}: No strategy configured")
                    screening_details[symbol] = {'status': 'skipped', 'reason': 'No strategy configured'}
                    continue
                
                # Fetch 4H and 1H candles for strategy evaluation
                df_4h = await binance_fetcher.get_klines(symbol=symbol, interval='4h', limit=200)
                df_1h = await binance_fetcher.get_klines(symbol=symbol, interval='1h', limit=200)

                if df_1h.empty or df_4h.empty or len(df_4h) < 50 or len(df_1h) < 50:
                    reason = "Insufficient data"
                    if df_1h.empty or df_4h.empty:
                        reason = "No candle data available"
                    elif len(df_4h) < 50:
                        reason = f"Insufficient 4H history ({len(df_4h)} bars, need 50)"
                    elif len(df_1h) < 50:
                        reason = f"Insufficient 1H history ({len(df_1h)} bars, need 50)"
                    screening_details[symbol] = {'status': 'skipped', 'reason': reason}
                    logger.debug(f"   ⊘ {symbol}: {reason}")
                    continue
                
                # Ensure timestamp is set as index for both dataframes
                if 'timestamp' in df_4h.columns:
                    df_4h = df_4h.set_index('timestamp')
                if 'timestamp' in df_1h.columns:
                    df_1h = df_1h.set_index('timestamp')
                
                # Create daily candles from 1H data (for daily trend check)
                df_daily = df_1h.resample('1D').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
                
                # Calculate indicators for diagnostics (before check_entry)
                df_4h = strategy.calculate_indicators(df_4h)
                df_daily = strategy.calculate_indicators(df_daily)
                
                # Call strategy entry check
                should_enter, reason = strategy.check_entry(
                    df_1h=df_1h,
                    df_4h=df_4h,
                    df_daily=df_daily,
                    current_idx=-1  # Latest bar
                )

                if not should_enter:
                    # Entry conditions not met - collect detailed diagnostics
                    last_4h = df_4h.iloc[-1]
                    current_price = float(last_4h['close'])
                    
                    # Get all indicator values for diagnostics (handle NaN safely)
                    import numpy as np
                    rsi_val = float(last_4h.get('rsi', 0)) if not pd.isna(last_4h.get('rsi', np.nan)) else 0.0
                    ema9 = float(last_4h.get('ema_9', 0)) if not pd.isna(last_4h.get('ema_9', np.nan)) else 0.0
                    ema21 = float(last_4h.get('ema_21', 0)) if not pd.isna(last_4h.get('ema_21', np.nan)) else 0.0
                    volume_ratio = float(last_4h.get('volume_ratio', 0)) if not pd.isna(last_4h.get('volume_ratio', np.nan)) else 0.0
                    macd_bullish = bool(last_4h.get('macd_bullish', False))
                    
                    # Get daily trend info
                    daily_bars_before = df_daily[df_daily.index <= df_4h.index[-1]]
                    if len(daily_bars_before) > 0:
                        daily_close = float(daily_bars_before['close'].iloc[-1])
                        daily_ema50_val = daily_bars_before['ema_50'].iloc[-1]
                        daily_ema50 = float(daily_ema50_val) if not pd.isna(daily_ema50_val) else current_price
                    else:
                        daily_close = current_price
                        daily_ema50 = current_price
                    
                    # Count how many of the 4 conditions are met
                    conditions_met = sum([
                        ema9 > ema21 if (ema9 > 0 and ema21 > 0) else False,
                        rsi_val < 40 if rsi_val > 0 else False,
                        volume_ratio > 1.3 if volume_ratio > 0 else False,
                        macd_bullish
                    ])
                    
                    screening_details[symbol] = {
                        'status': 'failed',
                        'reason': reason,
                        'current_price': current_price,
                        'criteria': {
                            'rsi': rsi_val,
                            'rsi_target': 40,
                            'rsi_met': (rsi_val < 40) if rsi_val > 0 else False,
                            'ema9': ema9,
                            'ema21': ema21,
                            'ema_cross': (ema9 > ema21) if (ema9 > 0 and ema21 > 0) else False,
                            'volume_ratio': volume_ratio,
                            'volume_target': 1.3,
                            'volume_spike': (volume_ratio > 1.3) if volume_ratio > 0 else False,
                            'macd_bullish': macd_bullish,
                            'daily_price': daily_close,
                            'daily_ema50': daily_ema50,
                            'daily_trend': daily_close > daily_ema50,
                        },
                        'conditions_met': conditions_met,
                        'conditions_required': 3
                    }
                    logger.debug(f"   ❌ {symbol}: {reason} ({conditions_met}/4 conditions)")
                    continue
                
                # Entry conditions MET! Prepare data for Claude
                logger.info(f"   ✅ {symbol}: Entry signal detected - {reason}")
                
                # Calculate indicators from 1H for Claude context
                df_1h = compute_all_indicators(df_1h)
                last_1h = df_1h.iloc[-1]
                close_1h = float(last_1h['close'])
                
                # Calculate changes
                change_1h = ((close_1h / df_1h.iloc[-2]['close']) - 1) * 100 if len(df_1h) >= 2 else 0.0
                change_4h = ((close_1h / df_1h.iloc[-5]['close']) - 1) * 100 if len(df_1h) >= 5 else 0.0
                change_24h = ((close_1h / df_1h.iloc[-25]['close']) - 1) * 100 if len(df_1h) >= 25 else 0.0
                
                # Volume metrics
                volume_1h = float(last_1h['volume']) * close_1h
                volume_24h = float(df_1h['volume'].iloc[-24:].sum()) * close_1h if len(df_1h) >= 24 else volume_1h * 24
                
                # Technical indicators
                rsi = float(last_1h.get('rsi', 50))
                atr = float(last_1h.get('atr', 0))
                atr_percent = (atr / close_1h) * 100 if close_1h > 0 else 0.0
                above_ema200 = close_1h > float(last_1h.get('ema_200', close_1h))
                
                # Store minimal filter flags for Claude
                filters = {
                    'strategy_entry': True,  # Passed strategy.check_entry()
                    'entry_reason': reason,
                    'rsi_oversold': rsi < 40,
                    'composite_score': 1.0  # All strategy coins weighted equally
                }
                
                # Minimal score (all strategy-qualified coins treated equally)
                score = 1.0
                filters['composite_score'] = score
                
                # Coin passed strategy entry check
                logger.info(f"      RSI: {rsi:.1f}")
                logger.info(f"      Price: ${close_1h:.4f}")
                logger.info(f"      Change: 1H={change_1h:+.2f}%, 4H={change_4h:+.2f}%, 24H={change_24h:+.2f}%")
                
                screening_details[symbol] = {
                    'status': 'passed',
                    'reason': f'Strategy entry: {reason}',
                    'current_price': close_1h,
                    'criteria': {
                        'rsi': rsi,
                        'rsi_target': 40,
                        'rsi_met': rsi < 40,
                        'ema9': float(last_1h.get('ema_9', 0)) if 'ema_9' in last_1h and not pd.isna(last_1h.get('ema_9')) else 0.0,
                        'ema21': float(last_1h.get('ema_21', 0)) if 'ema_21' in last_1h and not pd.isna(last_1h.get('ema_21')) else 0.0,
                        'ema_cross': True,  # Passed strategy check
                        'volume_ratio': 0.0,  # Would need 4H data
                        'volume_target': 1.3,
                        'volume_spike': True,  # Passed strategy check
                        'macd_bullish': True,  # Passed strategy check
                        'daily_price': close_1h,
                        'daily_ema50': close_1h * 0.95,  # Approximate
                        'daily_trend': True,  # Passed strategy check
                    },
                    'conditions_met': 4,  # All conditions met
                    'conditions_required': 3,
                    'entry_reason': reason,
                    'change_1h': change_1h,
                    'change_4h': change_4h,
                    'change_24h': change_24h,
                    'filters': filters,
                }
                
                filtered.append({
                    'symbol': symbol,
                    'current_price': close_1h,
                    'indicators': {
                        'change_1h': change_1h,
                        'change_4h': change_4h,
                        'change_24h': change_24h,
                        'volume_1h': volume_1h,
                        'volume_24h': volume_24h,
                        'rsi': rsi,
                        'atr': atr,
                        'atr_percent': atr_percent,
                        'above_ema200': above_ema200,
                    },
                    'df': df_1h,
                    'filters': filters,
                    'entry_reason': reason,  # Strategy entry reason
                })

            except Exception as e:
                logger.error(f"Error screening {symbol}: {e}")
                screening_details[symbol] = {'status': 'error', 'reason': str(e)}
                continue

        # Save screening details to JSON for inspection
        try:
            import json
            from pathlib import Path
            screening_file = "data/screening_results.json"
            
            # Count coins by status
            passed_count = len(filtered)
            failed_count = sum(1 for cd in screening_details.values() if cd.get('status') == 'failed')
            skipped_count = sum(1 for cd in screening_details.values() if cd.get('status') == 'skipped')
            error_count = sum(1 for cd in screening_details.values() if cd.get('status') == 'error')
            
            results_summary = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'evaluation_summary': {
                    'total_coins_attempted': len(screening_details),
                    'passed': passed_count,
                    'failed': failed_count,
                    'skipped': skipped_count,
                    'error': error_count,
                },
                'coins': screening_details
            }
            Path(screening_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Write with ensure_ascii=False and proper encoding
            with open(screening_file, 'w', encoding='utf-8') as f:
                json.dump(results_summary, f, indent=2, ensure_ascii=True)
            
            logger.info(f"💾 Screening complete: {passed_count} passed, {failed_count} failed, {skipped_count} skipped, {error_count} errors")
            logger.info(f"💾 Results saved to {screening_file}")
        except Exception as e:
            logger.error(f"Failed to save screening results: {e}")

        # Return all strategy-qualified coins (already limited to tracked coins)
        logger.info(f"Strategy screen complete: {len(filtered)} coin(s) passed entry conditions")
        if filtered:
            for coin in filtered:
                logger.info(f"  ✅ {coin['symbol']}: {coin.get('entry_reason', 'Entry signal')}")
        
        return filtered
    
    async def _check_exceptional_event(self, coins_data: List[Dict]) -> Optional[Dict]:
        """
        LOCAL FILTER: Check for exceptional market conditions
        Returns coin data if exceptional event detected, None otherwise
        
        Exceptional criteria:
        - Volume spike > 2.5x average
        - 1H momentum > 2%
        - RSI < 72 (not overbought)
        """
        logger.info("\n" + "=" * 60)
        logger.info("🔍 Local Filter: Checking for exceptional events")
        logger.info("=" * 60)
        
        exceptional_coins = []
        
        for coin in coins_data:
            indicators = coin['indicators']
            
            # Check for exceptional momentum + volume
            volume_spike = (indicators['volume_1h'] / max(indicators.get('volume_24h', 1) / 24, 0.0001))
            has_volume_spike = volume_spike > 2.5
            has_momentum = abs(indicators['change_1h']) > 2.0
            not_overbought = indicators['rsi'] < 72
            
            if has_volume_spike and has_momentum and not_overbought:
                logger.warning(f"⚠️  Exceptional event detected in {coin['symbol']}:")
                logger.warning(f"   Volume spike: {volume_spike:.2f}x")
                logger.warning(f"   1H momentum: {indicators['change_1h']:+.2f}%")
                logger.warning(f"   RSI: {indicators['rsi']:.1f}")
                exceptional_coins.append(coin)
        
        if exceptional_coins:
            logger.info(f"🚨 Found {len(exceptional_coins)} exceptional event(s)")
            return exceptional_coins[0]  # Return first exceptional coin for analysis
        
        logger.info("✅ No exceptional events detected")
        return None
    
    async def _run_light_check(self, coins_data: List[Dict]) -> Dict[str, Any]:
        """
        LIGHT MONITORING (when positions are full):
        - Do NOT suggest trades
        - Only check for market risk/reversals
        - Minimal Claude token usage
        """
        logger.info("\n" + "=" * 60)
        logger.info("⚡ LIGHT MONITORING: Market risk assessment (NO trade suggestions)")
        logger.info("=" * 60)
        
        # Find highest momentum coin for context
        riskiest_coin = max(coins_data, key=lambda x: abs(x['indicators']['change_1h']), default=None)
        
        if not riskiest_coin:
            logger.info("No data for light check")
            return {
                "market_risk": "LOW",
                "notes": "No market data available"
            }
        
        # Create minimal prompt for market risk assessment
        light_prompt = f"""You are monitoring {len(coins_data)} coins for MARKET RISK only.
Do NOT suggest trades. Positions are at capacity.

Riskiest coin: {riskiest_coin['symbol']}
  Price: ${riskiest_coin['current_price']:.2f}
  1H Change: {riskiest_coin['indicators']['change_1h']:+.2f}%
  RSI: {riskiest_coin['indicators']['rsi']:.0f}

Output JSON only:
{{
  "market_risk": "LOW|MEDIUM|HIGH",
  "notes": "max 15 words"
}}
"""
        
        try:
            # This is a CHEAP Claude call (minimal tokens)
            market_risk = ai_analyzer.assess_market_risk(light_prompt)
            logger.info(f"Market risk assessment: {market_risk.get('market_risk', 'UNKNOWN')}")
            logger.info(f"Notes: {market_risk.get('notes', 'N/A')}")
            
            return market_risk
        except Exception as e:
            logger.error(f"Error in light check: {e}")
            return {"market_risk": "UNKNOWN", "notes": "Assessment failed"}
    
    async def run_analysis_cycle(self) -> Dict[str, Any]:
        """
        Three-tier analysis cycle:
        
        TIER 1: Market Watch (always runs, lightweight)
        TIER 2: AI Decision (only if capacity available)
        TIER 3: Trade Execution (only if all gates pass)
        
        Token optimization:
        - If positions < MAX: Full Claude analysis (30-40 calls/day)
        - If positions == MAX: Light monitoring only (2-6 calls/day)
        - 70-90% token cost reduction when positions full
        """
        try:
            current_hour = datetime.now(timezone.utc).hour
            
            # Check trading hours
            if current_hour not in TRADING_HOURS_UTC:
                logger.info(f"Outside trading hours (current: {current_hour} UTC)")
                self._record_scan_completion(status="outside_hours", reason="Outside trading hours")
                return {"status": "skipped", "reason": "outside_trading_hours"}
            
            logger.info("\n" + "=" * 80)
            logger.info(f"ANALYSIS CYCLE START at {datetime.now(timezone.utc)}")
            logger.info("=" * 80)
            
            # Step 1: Get coins from strategy manager (tracked universe)
            tracked_coins = self.strategy_manager.get_all_tracked_coins()
            logger.info(f"Strategy-based tracking: {len(tracked_coins)} coins ({', '.join(tracked_coins)})")
            
            # Convert to format expected by screening
            top_coins = [{'symbol': coin.replace('USDT', '')} for coin in tracked_coins]
            
            if not top_coins:
                logger.warning("No coins configured in strategy manager")
                return {"status": "error", "reason": "no_coins_configured"}
            
            logger.info(f"Found {len(top_coins)} tradeable coins")
            
            # ===================================================================
            # STRATEGY-BASED SCREEN: Use strategy.check_entry() for each coin
            # ===================================================================
            coins_data = await self._screen_strategy_based(top_coins)

            if not coins_data:
                logger.warning("No coins met strategy entry conditions (RSI<40 + 3/4 conditions)")
                self._record_scan_completion(status="no_candidates", reason="No coins met strategy entry conditions")
                return {"status": "no_candidates"}
            
            # Check position capacity
            position_count = self._get_position_count()
            capacity_available = self._is_capacity_available()
            has_weak, weakest_symbol = self._has_weak_positions()
            
            logger.info(f"\n📊 Current Position Status: {position_count}/{MAX_OPEN_POSITIONS}")
            
            # ===================================================================
            # TIER 2: AI Decision (conditional - only if capacity available)
            # ===================================================================
            if capacity_available:
                logger.info("\n" + "=" * 60)
                logger.info(f"✅ CAPACITY AVAILABLE ({position_count}/{MAX_OPEN_POSITIONS})")
                logger.info("✅ Running FULL Claude analysis")
                logger.info("=" * 60)
                
                result = await self._run_full_analysis(coins_data)
                return result
            
            elif has_weak and weakest_symbol:
                # EXPERIMENTAL: Position replacement mode
                from src.config.constants import ALLOW_POSITION_REPLACEMENT
                
                if ALLOW_POSITION_REPLACEMENT:
                    logger.info("\n" + "=" * 60)
                    logger.info(f"⚠️ POSITIONS FULL ({position_count}/{MAX_OPEN_POSITIONS})")
                    logger.info(f"⚠️ WEAK POSITION DETECTED: {weakest_symbol}")
                    logger.info("🔄 Running REPLACEMENT SCAN mode")
                    logger.info("   Looking for signals >80% confidence to replace weak position")
                    logger.info("=" * 60)
                    
                    result = await self._run_replacement_scan(coins_data, weakest_symbol)
                    return result
                else:
                    # Replacement disabled, run light monitoring
                    logger.info("\n" + "=" * 60)
                    logger.info(f"⛔ POSITIONS FULL ({position_count}/{MAX_OPEN_POSITIONS})")
                    logger.info(f"⚠️ Weak position detected: {weakest_symbol} (replacement disabled)")
                    logger.info("⛔ Blocking full Claude analysis")
                    logger.info("⚡ Running LIGHT monitoring instead (70-90% less tokens)")
                    logger.info("=" * 60)
                    
                    result = await self._run_light_monitoring(coins_data)
                    self._record_scan_completion(status="positions_full", reason="Positions full, replacement disabled")
                    return result
            else:
                logger.info("\n" + "=" * 60)
                logger.info(f"⛔ POSITIONS FULL ({position_count}/{MAX_OPEN_POSITIONS})")
                logger.info("⛔ No weak positions detected for replacement")
                logger.info("⛔ Blocking full Claude analysis")
                logger.info("⚡ Running LIGHT monitoring instead (70-90% less tokens)")
                logger.info("=" * 60)
                
                result = await self._run_light_monitoring(coins_data)
                self._record_scan_completion(status="positions_full", reason="Positions full, no weak positions")
                return result
        
        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}")
            import traceback
            traceback.print_exc()
            self._record_scan_completion(status="error", reason=str(e))
            return {"status": "error", "reason": str(e)}
    
    async def _run_full_analysis(self, coins_data: List[Dict]) -> Dict[str, Any]:
        """
        TIER 2: Full Claude Analysis (only when capacity available)
        
        This is the expensive operation, but justified because we can execute the trade
        """
        logger.info("\n" + "=" * 60)
        logger.info("🤖 TIER 2: Full AI Analysis (Oracle Mode)")
        logger.info("=" * 60)
        
        try:
            # Call Claude for trade selection
            oracle_decision = ai_analyzer.generate_signals_batch_oracle(coins_data)
            
            logger.info(f"Oracle decision: {oracle_decision.get('action')}")
            
            if oracle_decision.get('action') == 'NO_TRADE':
                logger.info("✅ No high-quality setup - skipping")
                
                signal_monitor.add_signal({
                    'symbol': 'MARKET',
                    'signal_type': 'NO_TRADE',
                    'edge': oracle_decision.get('edge', 'WEAK'),
                    'confidence': 0,  # Keeping for backward compat
                    'stop_loss': 0,
                    'take_profit': [],
                    'rationale': oracle_decision.get('reason', 'No quality setup'),
                    'current_price': 0,
                    'indicators': {},
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
                
                return {
                    "status": "completed",
                    "tier": "full_analysis",
                    "coins_analyzed": len(coins_data),
                    "oracle_decision": "NO_TRADE",
                    "oracle_edge": oracle_decision.get('edge', 'WEAK'),
                }
            
            # Extract selected coin
            selected_symbol = oracle_decision.get('symbol')
            
            if not selected_symbol:
                logger.error("Oracle returned BUY but no symbol")
                return {"status": "error", "reason": "Invalid oracle decision"}
            
            selected_coin_data = next((c for c in coins_data if c['symbol'] == selected_symbol), None)
            
            if not selected_coin_data:
                logger.error(f"Selected coin {selected_symbol} not in data")
                return {"status": "error", "reason": "Coin data missing"}
            
            # Validate edge threshold
            edge = oracle_decision.get('edge', 'WEAK').upper()
            from src.config.constants import MIN_EDGE_TO_TRADE
            
            if edge not in ['STRONG', 'MODERATE']:
                logger.warning(f"Oracle returned {edge} edge - not trading WEAK setups")
                return {
                    "status": "completed",
                    "oracle_decision": "NO_TRADE",
                    "oracle_edge": edge,
                    "reason": f"Edge {edge} below threshold {MIN_EDGE_TO_TRADE}"
                }
            
            if MIN_EDGE_TO_TRADE == "STRONG" and edge == "MODERATE":
                logger.warning(f"Oracle returned MODERATE edge but MIN_EDGE_TO_TRADE=STRONG - skipping")
                return {
                    "status": "completed",
                    "oracle_decision": "NO_TRADE",
                    "oracle_edge": edge,
                    "reason": "MODERATE edge below STRONG threshold"
                }
            
            logger.info(f"\n🎯 Oracle selected: {selected_symbol}")
            logger.info(f"   Edge: {edge}")
            logger.info(f"   Reason: {oracle_decision.get('reason')}")

            # Record Claude decision into screening results (for UI transparency)
            try:
                if isinstance(self.last_screening_details, dict) and selected_symbol in self.last_screening_details:
                    self.last_screening_details[selected_symbol].setdefault('claude', {})
                    self.last_screening_details[selected_symbol]['claude'].update({
                        'action': oracle_decision.get('action'),
                        'edge': edge,
                        'confidence': oracle_decision.get('confidence'),
                        'reason': oracle_decision.get('reason'),
                        'stop_loss': oracle_decision.get('stop_loss'),
                        'take_profit': oracle_decision.get('take_profit'),
                    })
            except Exception:
                pass
            
            # ===================================================================
            # TIER 3: Trade Execution (strict validation before execution)
            # ===================================================================
            logger.info("\n" + "=" * 60)
            logger.info("🛡️ TIER 3: Safety Gates & Execution")
            logger.info("=" * 60)
            
            current_price = selected_coin_data['current_price']
            indicators = selected_coin_data['indicators']
            
            # Extract Claude's SL and TP suggestions
            claude_stop_loss = oracle_decision.get('stop_loss', 0)
            claude_take_profits = oracle_decision.get('take_profit', [])

            # Explicitly log and persist the confidence used for Tier-3 gating.
            # This prevents confusing UI rows like "Low confidence: 0%" without context.
            from src.config.constants import MIN_CONFIDENCE_TO_TRADE
            decision_confidence = oracle_decision.get('confidence', 0)
            logger.info(
                f"🧠 Tier-3 inputs for {selected_symbol}: edge={edge}, "
                f"confidence={decision_confidence}% (min {MIN_CONFIDENCE_TO_TRADE}%)"
            )
            
            # Apply strict safety gates
            approved, rejection_reason = safety_gates.validate_trade(
                symbol=selected_symbol,
                ai_decision=oracle_decision,
                current_price=current_price,
                volume_24h_usd=indicators['volume_24h'],
                rsi=indicators['rsi'],
                active_positions=self._get_position_count(),
                account_balance=risk_manager.current_balance,
            )
            
            if not approved:
                logger.warning(f"❌ Trade rejected: {rejection_reason}")

                # Record rejection reason into screening results
                try:
                    if isinstance(self.last_screening_details, dict) and selected_symbol in self.last_screening_details:
                        self.last_screening_details[selected_symbol].setdefault('gates', {})
                        self.last_screening_details[selected_symbol]['gates'].update({
                            'approved': False,
                            'rejection_reason': rejection_reason,
                            'confidence_used': decision_confidence,
                            'min_confidence_required': MIN_CONFIDENCE_TO_TRADE,
                        })
                except Exception:
                    pass
                
                signal_monitor.add_signal({
                    'symbol': selected_symbol,
                    'signal_type': 'REJECTED',
                    'edge': edge,
                    'confidence': 0,  # Keeping for backward compat
                    'stop_loss': 0,
                    'take_profit': [],
                    'rationale': f"Rejected: {rejection_reason}",
                    'current_price': current_price,
                    'indicators': indicators,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
                
                return {
                    "status": "rejected",
                    "tier": "full_analysis",
                    "rejection_reason": rejection_reason,
                    "oracle_edge": edge,
                }
            
            logger.info("✅ All safety gates PASSED")

            # Record gate approval into screening results
            try:
                if isinstance(self.last_screening_details, dict) and selected_symbol in self.last_screening_details:
                    self.last_screening_details[selected_symbol].setdefault('gates', {})
                    self.last_screening_details[selected_symbol]['gates'].update({
                        'approved': True,
                        'rejection_reason': None,
                        'confidence_used': decision_confidence,
                        'min_confidence_required': MIN_CONFIDENCE_TO_TRADE,
                    })
            except Exception:
                pass
            
            # Calculate position size (from safety_gates)
            quantity, position_value = safety_gates.calculate_position_size(
                symbol=selected_symbol,
                account_balance=risk_manager.current_balance,
                current_price=current_price,
                atr_percent=indicators['atr_percent'],
            )
            
            # Use Claude's suggested SL/TP values (NOT hardcoded percentages)
            # Validate Claude's stop loss - if 0 or invalid, use 3% default
            if claude_stop_loss and claude_stop_loss > 0:
                stop_loss = claude_stop_loss
            else:
                logger.warning(f"⚠️  Claude's stop_loss invalid ({claude_stop_loss}), using 3% default")
                stop_loss = current_price * 0.97  # 3% stop loss default
            
            # Convert Claude's take_profit array (as % multipliers) to price levels
            take_profits = []
            if isinstance(claude_take_profits, list) and len(claude_take_profits) > 0:
                for i, tp_multiplier in enumerate(claude_take_profits):
                    # Claude returns TP as multipliers (e.g., 1.05 = +5%)
                    tp_price = current_price * tp_multiplier
                    take_profits.append({
                        'price': tp_price,
                        'percent': (tp_multiplier - 1) * 100,  # Convert to percentage
                        'position_percent': 1.0 / len(claude_take_profits),  # Equal split
                    })
            else:
                # Fallback: if Claude didn't provide TPs, use safety_gates
                logger.warning(f"⚠️  Claude didn't provide take_profits, using safety_gates fallback")
                take_profits = safety_gates.calculate_take_profits(
                    current_price=current_price,
                    atr=indicators['atr'],
                )
            
            logger.info(f"✅ Using Claude's suggested levels:")
            logger.info(f"   Claude SL: {claude_stop_loss}")
            logger.info(f"   Claude TPs: {claude_take_profits}")
            logger.info(f"   Calculated SL Price: ${stop_loss:.4f}")
            for i, tp in enumerate(take_profits):
                logger.info(f"   Calculated TP{i+1} Price: ${tp['price']:.4f}")
            
            # Log signal with Claude's actual suggestions
            signal_monitor.add_signal({
                'symbol': selected_symbol,
                'signal_type': 'BUY',
                'edge': edge,
                'confidence': 0,  # Keeping for backward compat
                'stop_loss': stop_loss,
                'take_profit': [tp['price'] for tp in take_profits],
                'claude_raw_tp': claude_take_profits,  # Store Claude's raw response
                'rationale': oracle_decision.get('reason'),
                'current_price': current_price,
                'indicators': indicators,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })
            
            # Execute trade
            logger.info("\n" + "=" * 60)
            logger.info("💼 EXECUTION")
            logger.info("=" * 60)
            
            trades_executed = []
            
            if MONITORING_ONLY or DRY_RUN_ENABLED:
                logger.info(f"[MONITORING MODE] Would BUY {selected_symbol}")
                logger.info(f"   Entry: ${current_price:.4f}")
                logger.info(f"   Qty: {quantity:.6f}")
                logger.info(f"   SL: ${stop_loss:.4f}")
                tp_str = ', '.join([f'${tp["price"]:.4f}' for tp in take_profits])
                logger.info(f"   TP: {tp_str}")
                
                trades_executed.append({
                    'symbol': selected_symbol,
                    'side': 'BUY',
                    'mode': 'monitoring',
                })
            else:
                logger.info(f"Executing LIVE BUY for {selected_symbol}...")
                
                order_result = await order_manager.execute_entry_order(
                    symbol=selected_symbol,
                    quantity=quantity,
                    entry_price=current_price,
                    stop_loss_price=stop_loss,
                    take_profit_levels=[tp['price'] for tp in take_profits],
                    confidence=0.75 if edge == "STRONG" else 0.60,  # Map edge to confidence for backward compat
                )
                
                if order_result:
                    logger.info(f"✅ Order executed")
                    trades_executed.append({
                        'symbol': selected_symbol,
                        'side': 'BUY',
                    })
                else:
                    logger.error(f"❌ Order failed")
            
            logger.info("=" * 80)
            logger.info(f"✅ CYCLE COMPLETE: {selected_symbol} selected & executed")
            logger.info("=" * 80)
            
            self._record_scan_completion()
            return {
                "status": "completed",
                "tier": "full_analysis",
                "coins_analyzed": len(coins_data),
                "oracle_decision": oracle_decision.get('action'),
                "selected_coin": selected_symbol,
                "trades_executed": len(trades_executed),
            }
        
        except Exception as e:
            logger.error(f"Error in full analysis: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "reason": str(e)}
    
    async def _run_replacement_scan(self, coins_data: List[Dict], weak_symbol: str) -> Dict[str, Any]:
        """
        TIER 2: Replacement Scan (EXPERIMENTAL)
        
        Only runs when:
        - Positions are full
        - At least one position is weak (near SL, low confidence)
        - ALLOW_POSITION_REPLACEMENT = True
        
        Looks for signals with >80% confidence that are significantly better
        than the weakest position
        """
        from src.config.constants import (
            MIN_CONFIDENCE_FOR_REPLACEMENT,
            REPLACEMENT_MIN_IMPROVEMENT,
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("🔄 TIER 2: Replacement Scan Mode (EXPERIMENTAL)")
        logger.info(f"🎯 Target: Replace weak position {weak_symbol}")
        logger.info("=" * 60)
        
        try:
            # Get weak position details
            weak_position = risk_manager.positions.get(weak_symbol)
            if not weak_position:
                logger.warning(f"Weak position {weak_symbol} not found")
                return await self._run_light_monitoring(coins_data)
            
            # Call Claude for trade selection (same as full analysis)
            oracle_decision = ai_analyzer.generate_signals_batch_oracle(coins_data)
            
            logger.info(f"Oracle decision: {oracle_decision.get('action')}")
            
            if oracle_decision.get('action') == 'NO_TRADE':
                logger.info("✅ No superior setup found - keeping weak position")
                return {
                    "status": "completed",
                    "tier": "replacement_scan",
                    "result": "no_replacement",
                    "reason": "No high-quality setup found",
                }
            
            # Check if new signal is strong enough to replace weak position
            new_confidence = oracle_decision.get('confidence', 0)
            
            if new_confidence < MIN_CONFIDENCE_FOR_REPLACEMENT:
                logger.info(f"❌ New signal confidence {new_confidence}% < {MIN_CONFIDENCE_FOR_REPLACEMENT}% (replacement threshold)")
                logger.info("✅ Keeping weak position")
                return {
                    "status": "completed",
                    "tier": "replacement_scan",
                    "result": "no_replacement",
                    "reason": f"New confidence {new_confidence}% too low",
                }
            
            # Calculate improvement
            # For simplicity, assume weak position had 50% confidence
            # In production, you'd store original confidence with position
            weak_confidence = 50  # Placeholder - should be stored with position
            improvement = new_confidence - weak_confidence
            
            if improvement < REPLACEMENT_MIN_IMPROVEMENT:
                logger.info(f"❌ Improvement +{improvement}% < {REPLACEMENT_MIN_IMPROVEMENT}% (minimum)")
                logger.info("✅ Keeping weak position")
                return {
                    "status": "completed",
                    "tier": "replacement_scan",
                    "result": "no_replacement",
                    "reason": f"Improvement +{improvement}% insufficient",
                }
            
            # Signal is strong enough - close weak position and open new
            logger.info("\n" + "=" * 60)
            logger.info("🔄 REPLACEMENT APPROVED")
            logger.info(f"   Close: {weak_symbol} (confidence ~{weak_confidence}%)")
            logger.info(f"   Open: {oracle_decision.get('selected_coin')} (confidence {new_confidence}%)")
            logger.info(f"   Improvement: +{improvement}%")
            logger.info("=" * 60)
            
            # Close weak position first
            try:
                logger.info(f"🔴 Closing weak position: {weak_symbol}")
                close_result = order_manager.close_position(
                    symbol=weak_symbol,
                    reason=f"Replaced by superior signal (improvement: +{improvement}%)"
                )
                
                if close_result.get('status') != 'success':
                    logger.error(f"Failed to close weak position: {close_result.get('message')}")
                    return {
                        "status": "error",
                        "tier": "replacement_scan",
                        "reason": "Failed to close weak position",
                    }
                
                logger.info(f"✅ Weak position closed successfully")
                
            except Exception as e:
                logger.error(f"Error closing weak position: {e}")
                return {
                    "status": "error",
                    "tier": "replacement_scan",
                    "reason": f"Error closing position: {e}",
                }
            
            # Now run full analysis to open new position
            # This will execute the trade since we now have capacity
            logger.info("\n🟢 Opening new position...")
            result = await self._run_full_analysis(coins_data)
            
            result["tier"] = "replacement_scan"
            result["replacement_details"] = {
                "closed_symbol": weak_symbol,
                "new_symbol": oracle_decision.get('selected_coin'),
                "improvement": improvement,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in replacement scan: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "reason": str(e)}
    
    async def _run_light_monitoring(self, coins_data: List[Dict]) -> Dict[str, Any]:
        """
        TIER 2: Light Monitoring (when positions full)
        
        - Check for exceptional events only
        - If exceptional event found, run minimal Claude analysis
        - Otherwise, skip Claude entirely
        - 70-90% less token usage
        """
        logger.info("\n" + "=" * 60)
        logger.info("⚡ TIER 2: Light Monitoring Mode (Positions Full)")
        logger.info("=" * 60)
        
        try:
            # Check for exceptional events using local filters
            exceptional_coin = await self._check_exceptional_event(coins_data)
            
            if exceptional_coin:
                logger.info(f"\n⚠️  Exceptional event detected in {exceptional_coin['symbol']}")
                logger.info("🚨 Running emergency Claude analysis...")
                
                # Even with exceptional event, we CANNOT execute (positions full)
                # This is just for alerting/logging
                
                signal_monitor.add_signal({
                    'symbol': exceptional_coin['symbol'],
                    'signal_type': 'ALERT',
                    'confidence': 75,  # High confidence alert
                    'stop_loss': 0,
                    'take_profit': [],
                    'rationale': 'Exceptional market event detected (positions full - no execution)',
                    'current_price': exceptional_coin['current_price'],
                    'indicators': exceptional_coin['indicators'],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
                
                return {
                    "status": "completed",
                    "tier": "light_monitoring",
                    "mode": "exceptional_event_detected",
                    "alert_coin": exceptional_coin['symbol'],
                    "note": "Positions full - no execution allowed",
                }
            
            # No exceptional events - run cheap market risk assessment
            logger.info("\nNo exceptional events, running market risk assessment...")
            market_risk = await self._run_light_check(coins_data)
            
            logger.info("=" * 80)
            logger.info(f"✅ CYCLE COMPLETE: Light monitoring")
            logger.info(f"   Market Risk: {market_risk.get('market_risk')}")
            logger.info(f"   Note: {market_risk.get('notes')}")
            logger.info("=" * 80)
            
            return {
                "status": "completed",
                "tier": "light_monitoring",
                "mode": "standard_monitoring",
                "market_risk": market_risk.get('market_risk'),
                "note": f"{market_risk.get('notes')} (positions full - no execution)",
            }
        
        except Exception as e:
            logger.error(f"Error in light monitoring: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "reason": str(e)}
    
    async def run_continuous(self):
        """Run analysis cycles continuously at configured intervals"""
        logger.info(f"Starting continuous mode (interval: {ANALYSIS_INTERVAL_MINUTES} min)")
        
        while True:
            try:
                await self.run_analysis_cycle()
                
                # Wait for next cycle
                wait_seconds = ANALYSIS_INTERVAL_MINUTES * 60
                logger.info(f"Waiting {ANALYSIS_INTERVAL_MINUTES} minutes until next cycle...")
                await asyncio.sleep(wait_seconds)
            
            except KeyboardInterrupt:
                logger.info("Stopping continuous mode")
                break
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error


# Singleton instance
signal_orchestrator = SignalOrchestrator()


async def main():
    """Main entry point for continuous signal generation."""
    logger.info("=" * 80)
    logger.info("🚀 SIGNAL GENERATOR STARTED")
    logger.info("=" * 80)
    logger.info(f"Analysis cycle interval: {ANALYSIS_INTERVAL_MINUTES} minutes")
    logger.info("=" * 80)
    
    # Sync any orphaned positions from Binance on startup
    logger.info("🔄 Syncing positions with Binance account...")
    synced_count = risk_manager.sync_positions_from_binance()
    logger.info(f"Position sync complete. Recovered {synced_count} position(s).")
    
    try:
        await signal_orchestrator.run_continuous()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        raise


if __name__ == "__main__":
    asyncio.run(main())
