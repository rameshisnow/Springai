"""
AI Analyzer - Uses Claude API to analyze coins and generate trading signals
"""
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from anthropic import Anthropic, APIError
from src.utils.logger import ai_logger
from src.config.settings import config
from src.config.constants import (
    AI_PROVIDER,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TEMPERATURE,
    MIN_CONFIDENCE_TO_TRADE,
    MIN_CONSENSUS_AGREEMENTS,
    VERBOSE_AI_RESPONSES,
)


class PromptTemplates:
    """Structured prompts for AI analysis"""
    
    @staticmethod
    def batch_oracle_prompt(coins_data: List[Dict[str, Any]]) -> str:
        """
        OPTIMIZED V2: Oracle prompt with pre-validated boolean filters
        Target: ≤200 tokens (down from 500) - 60% token reduction
        
        Coins arrive PRE-FILTERED by code:
        - EMA9 > EMA21 (bullish trend) ✅
        - RSI 55-70 (not overbought) ✅  
        - Breakout confirmed (20 or 50-bar) ✅
        - BTC outperformance ✅
        
        Claude's job: RANK best relative setup, assign edge category
        
        Args:
            coins_data: List of QUALIFIED coins with boolean filter flags
        
        Returns:
            Minimal prompt for ranking only
        """
        # Build ultra-compact qualified snapshot (≤150 tokens for 8 coins)
        qualified_snapshot = []
        for idx, coin in enumerate(coins_data[:8], 1):  # Max 8 candidates
            symbol = coin['symbol']
            price = coin['current_price']
            filters = coin.get('filters', {})  # Pre-calculated boolean flags
            
            # Format price
            price_str = f"${price:.4f}" if price < 1 else f"${price:.2f}"
            
            # Compact filter status display
            breakout_type = "50BAR" if filters.get('breakout_50bar') else "20BAR"
            volume_strength = "2x+" if filters.get('volume_spike_2x') else "1.5x"
            rsi_position = "EARLY" if filters.get('rsi_early_range') else "MID"
            
            snapshot = (
                f"{idx}. {symbol} {price_str} | "
                f"✅{breakout_type} ✅RSI_{rsi_position} ✅VOL_{volume_strength} ✅BTC_OK | "
                f"Score:{filters.get('composite_score', 0):.1f}"
            )
            qualified_snapshot.append(snapshot)
        
        snapshot_text = "\n".join(qualified_snapshot)
        
        return f"""You are a quantitative crypto trading oracle.

All coins below PASSED hard filters (code-validated):
- EMA trend: price > EMA9 > EMA21 ✅
- RSI range: 55-70 (not overbought) ✅
- Breakout: Above 20 or 50-bar high ✅
- BTC strength: Outperforming Bitcoin ✅

Qualified Candidates:
{snapshot_text}

Your Task:
Select the ONE coin with the STRONGEST relative edge for a 1-4 hour LONG trade.

Edge Classification:
STRONG = 50-bar breakout + EARLY RSI (55-65) + 2x+ volume spike + high composite score
MODERATE = 20-bar breakout + MID RSI (60-70) + 1.5x volume + acceptable score
WEAK = Passed filters but lacks conviction → return NO_TRADE

Rules:
- If no coin qualifies as STRONG or MODERATE → return NO_TRADE
- Prefer STRONG over MODERATE
- Consider composite score as tiebreaker

Output (JSON ONLY):
{{"action": "BUY" or "NO_TRADE", "symbol": "BTCUSDT" or null, "edge": "STRONG" or "MODERATE" or "WEAK", "reason": "max 15 words"}}

CRITICAL: Return valid JSON only, no explanations."""
    
    @staticmethod
    def technical_confirmation_prompt(symbol: str, price_data: str) -> str:
        """Prompt for technical analysis confirmation"""
        
        return f"""
Perform technical analysis on {symbol} using the following data:

{price_data}

Evaluate:
1. RSI (oversold/overbought)
2. MACD crossovers
3. Support/Resistance levels
4. Trend direction
5. Volume confirmation

RESPONSE FORMAT (STRICT JSON):
{{
    "symbol": "{symbol}",
    "technical_score": 0.75,
    "trend": "uptrend/downtrend/sideways",
    "signals": {{
        "rsi": "oversold/neutral/overbought",
        "macd": "bullish/bearish/neutral",
        "volume": "strong/normal/weak"
    }},
    "buy_recommendation": true/false,
    "entry_points": [0.95, 1.00],
    "stop_loss": 0.90,
    "take_profit_targets": [1.05, 1.10, 1.15]
}}

Respond ONLY with valid JSON.
"""
    
    @staticmethod
    def risk_assessment_prompt(symbol: str, market_data: str) -> str:
        """Prompt to assess trading risk"""
        
        return f"""
Assess the risk profile for trading {symbol}.

Market Data:
{market_data}

Evaluate:
1. Volatility levels
2. Liquidity (avoid low-volume coins)
3. Market concentration
4. Recent price action stability
5. Regulatory/news risks

RESPONSE FORMAT (STRICT JSON):
{{
    "symbol": "{symbol}",
    "risk_score": 0.3,
    "max_position_percent": 2.0,
    "suitable_for_trading": true,
    "risk_factors": ["factor1", "factor2"],
    "mitigation": ["strategy1", "strategy2"],
    "recommendation": "safe/medium_risk/high_risk"
}}

Respond ONLY with valid JSON.
"""
    
    @staticmethod
    def signal_generation_prompt(
        symbol: str,
        current_price: float,
        ohlcv_data: str,
        indicators: Dict[str, Any],
        sentiment_score: Optional[float] = None,
    ) -> str:
        """
        Prompt for structured signal generation with OHLCV + indicators
        
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            current_price: Current price
            ohlcv_data: Formatted OHLCV candles (last 5-10 candles)
            indicators: Dict with RSI, EMA, ATR, momentum, volume_spike
            sentiment_score: Optional social sentiment (-1 to 1)
        
        Returns:
            Prompt string for Claude
        """
        sentiment_text = ""
        if sentiment_score is not None:
            sentiment_text = f"Social Sentiment (Twitter/X): {sentiment_score:.2f} (-1=bearish, 0=neutral, +1=bullish)"
        
        return f"""
You are an expert crypto market analyst. Analyze the following coin and provide a trading recommendation.

Coin: {symbol}
Current Price: ${current_price:.6f}

OHLCV Data (last 5-10 candles, 1h or 4h):
{ohlcv_data}

Technical Indicators:
- RSI: {indicators.get('rsi', 'N/A')} (30=oversold, 70=overbought)
- EMA 20: ${indicators.get('ema_20', 'N/A')}
- EMA 50: ${indicators.get('ema_50', 'N/A')}
- EMA 200: ${indicators.get('ema_200', 'N/A')}
- ATR (Volatility): {indicators.get('atr', 'N/A')}
- Momentum (10-period): {indicators.get('momentum', 'N/A')}%
- Volume Spike: {indicators.get('volume_spike', 'N/A')}x average
- MACD: {indicators.get('macd', 'N/A')} (Signal: {indicators.get('macd_signal', 'N/A')})
- Trend: {indicators.get('trend', 'neutral')}
- Bollinger Position: {indicators.get('bb_position', 'neutral')}
{sentiment_text}

Instructions:
1. Provide a **signal**: BUY / SELL / HOLD
2. Provide a **confidence score**: 0–100 (only trade if >= 70)
3. Suggest **stop_loss** price (max -3% from entry)
4. Suggest **take_profit** prices (array of 1-3 targets)
5. Provide a **short rationale** (2-3 sentences explaining the technical setup)
6. Consider **short-term trades** (1–24 hours holding period)

RESPONSE FORMAT (STRICT JSON):
{{
  "signal": "BUY",
  "confidence": 78,
  "stop_loss": 0.92,
  "take_profit": [1.05, 1.10, 1.15],
  "rationale": "Price broke above EMA200 with strong momentum; RSI shows room to run; volume spike confirms interest."
}}

Respond ONLY with valid JSON, no additional text.
"""


class AIAnalyzer:
    """Analyze coins using Claude API and generate trading signals"""
    
    def __init__(self):
        """Initialize Claude client"""
        self.client = Anthropic(api_key=config.CLAUDE_API_KEY)
        self.conversation_history = []
        self.model = CLAUDE_MODEL
        self.temperature = CLAUDE_TEMPERATURE
        self.max_tokens = CLAUDE_MAX_TOKENS
        
        ai_logger.info(f"Initialized AI Analyzer with model: {self.model}")
    
    def analyze_pump_candidates(self, coins_data: List[Dict[str, Any]], hours: int = 24) -> Dict[str, Any]:
        """
        Analyze coins to identify pump candidates
        
        Args:
            coins_data: List of coin market data
            hours: Time horizon for pump prediction
        
        Returns:
            Analysis result with top 3 coins
        """
        try:
            prompt = PromptTemplates.coin_pump_analysis_prompt(coins_data, hours)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text
            
            if VERBOSE_AI_RESPONSES:
                ai_logger.debug(f"Raw Claude response: {response_text}")
            
            # Parse JSON response
            analysis = self._parse_json_response(response_text)
            
            if not analysis:
                ai_logger.error("Failed to parse AI response as JSON")
                return self._empty_analysis()
            
            # Validate confidence scores
            if 'selected_coins' in analysis:
                for coin in analysis['selected_coins']:
                    if coin.get('confidence', 0) < MIN_CONFIDENCE_TO_TRADE:
                        ai_logger.warning(
                            f"Low confidence for {coin.get('symbol')}: "
                            f"{coin.get('confidence'):.2f} < {MIN_CONFIDENCE_TO_TRADE}"
                        )
            
            ai_logger.info(f"Analysis complete: {len(analysis.get('selected_coins', []))} coins identified")
            return analysis
        
        except APIError as e:
            ai_logger.error(f"Claude API error: {e}")
            return self._empty_analysis()
        except Exception as e:
            ai_logger.error(f"Error in pump candidate analysis: {e}")
            return self._empty_analysis()
    
    def validate_with_consensus(
        self,
        coins_data: List[Dict[str, Any]],
        num_variations: int = 3,
    ) -> Dict[str, Any]:
        """
        Run analysis multiple times with different prompt variations
        and only return coins with consensus agreement
        
        Args:
            coins_data: List of coin data
            num_variations: Number of analysis runs
        
        Returns:
            Consensus-based analysis results
        """
        all_results = []
        
        for i in range(num_variations):
            ai_logger.info(f"Running consensus analysis {i+1}/{num_variations}")
            result = self.analyze_pump_candidates(coins_data)
            all_results.append(result)
        
        # Extract agreed-upon coins
        consensus_coins = self._extract_consensus(all_results)
        
        if len(consensus_coins) < MIN_CONSENSUS_AGREEMENTS:
            ai_logger.warning(
                f"Insufficient consensus: {len(consensus_coins)} < {MIN_CONSENSUS_AGREEMENTS}"
            )
        
        return {
            "consensus_coins": consensus_coins,
            "agreement_strength": len(consensus_coins) / num_variations,
            "all_analyses": all_results,
        }
    
    def technical_confirmation(self, symbol: str, klines_data: str) -> Dict[str, Any]:
        """Get technical confirmation for a coin"""
        try:
            prompt = PromptTemplates.technical_confirmation_prompt(symbol, klines_data)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text
            return self._parse_json_response(response_text) or {}
        
        except Exception as e:
            ai_logger.error(f"Error in technical confirmation for {symbol}: {e}")
            return {}
    
    def assess_risk(self, symbol: str, market_data: str) -> Dict[str, Any]:
        """Get risk assessment for a coin"""
        try:
            prompt = PromptTemplates.risk_assessment_prompt(symbol, market_data)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text
            return self._parse_json_response(response_text) or {}
        
        except Exception as e:
            ai_logger.error(f"Error in risk assessment for {symbol}: {e}")
            return {}
    
    def generate_signal(
        self,
        symbol: str,
        current_price: float,
        ohlcv_data: str,
        indicators: Dict[str, Any],
        sentiment_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate trading signal with OHLCV + indicator analysis
        
        Args:
            symbol: Trading pair
            current_price: Current price
            ohlcv_data: Formatted candle data string
            indicators: Technical indicators dict
            sentiment_score: Optional sentiment (-1 to 1)
        
        Returns:
            Signal dict with BUY/SELL/HOLD, confidence, stop_loss, take_profit, rationale
        """
        try:
            prompt = PromptTemplates.signal_generation_prompt(
                symbol, current_price, ohlcv_data, indicators, sentiment_score
            )
            
            if VERBOSE_AI_RESPONSES:
                ai_logger.debug(f"Signal generation prompt for {symbol}:\n{prompt[:500]}...")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text
            
            if VERBOSE_AI_RESPONSES:
                ai_logger.debug(f"Raw Claude signal response: {response_text}")
            
            signal = self._parse_json_response(response_text)
            
            if not signal:
                ai_logger.error(f"Failed to parse signal for {symbol}")
                return self._empty_signal(symbol)
            
            # Validate confidence threshold
            confidence = signal.get('confidence', 0)
            if confidence < MIN_CONFIDENCE_TO_TRADE:
                ai_logger.info(
                    f"Low confidence signal for {symbol}: {confidence}% < {MIN_CONFIDENCE_TO_TRADE}%"
                )
            
            ai_logger.info(
                f"Signal for {symbol}: {signal.get('signal')} "
                f"@ {confidence}% confidence"
            )
            
            return signal
        
        except APIError as e:
            ai_logger.error(f"Claude API error for {symbol}: {e}")
            return self._empty_signal(symbol)
        except Exception as e:
            ai_logger.error(f"Error generating signal for {symbol}: {e}")
            return self._empty_signal(symbol)
    
    def generate_signals_batch_oracle(
        self,
        coins_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        OPTIMIZED V2: Oracle-style batch analysis with edge categories
        Target: ≤300 tokens total (down from 500)
        
        Args:
            coins_data: List of PRE-QUALIFIED coins with boolean filter flags
        
        Returns:
            Single trade recommendation with edge category or NO_TRADE
        """
        try:
            prompt = PromptTemplates.batch_oracle_prompt(coins_data)
            
            # Log token estimate
            estimated_tokens = len(prompt) // 4
            ai_logger.info(f"Oracle prompt: ~{estimated_tokens} tokens")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,  # Reduced from 200 (simpler response)
                temperature=0.3,  # Lower = more consistent
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Log actual token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            ai_logger.info(f"✅ Token usage: {input_tokens} input + {output_tokens} output = {total_tokens} total")
            
            response_text = response.content[0].text
            
            # Parse JSON response
            decision = self._parse_json_response(response_text)
            
            if not decision:
                ai_logger.error("Failed to parse oracle response")
                return self._empty_oracle_decision()
            
            # Validate decision structure
            if decision.get('action') not in ['BUY', 'NO_TRADE']:
                ai_logger.warning(f"Invalid action: {decision.get('action')}")
                return self._empty_oracle_decision()
            
            # Validate edge category
            edge = decision.get('edge', '').upper()
            if edge and edge not in ['STRONG', 'MODERATE', 'WEAK']:
                ai_logger.warning(f"Invalid edge category: {edge}, defaulting to WEAK")
                decision['edge'] = 'WEAK'
            
            ai_logger.info(f"✅ Oracle decision: {decision.get('action')} "
                          f"({decision.get('symbol', 'N/A')} @ {decision.get('edge', 'UNKNOWN')} edge)")
            
            return decision
        
        except APIError as e:
            ai_logger.error(f"Claude API error in oracle analysis: {e}")
            return self._empty_oracle_decision()
        except Exception as e:
            ai_logger.error(f"Error in oracle analysis: {e}")
            return self._empty_oracle_decision()
    
    def assess_market_risk(self, prompt: str) -> Dict[str, Any]:
        """
        LIGHTWEIGHT: Market risk assessment only (≤50 tokens request, ~30 tokens response)
        Used when positions are FULL and system is in monitoring-only mode
        
        Tier 2 Light Assessment - minimal Claude expenditure to assess current market conditions
        without performing full pump analysis or signal generation
        
        Args:
            prompt: Market-only assessment prompt (lightweight market data + risk question)
        
        Returns:
            Dict with 'market_risk' (LOW/MEDIUM/HIGH) and 'notes' (max 15 words)
            Example: {"market_risk": "MEDIUM", "notes": "BTC selling pressure, altcoins resilient"}
        """
        try:
            estimated_tokens = len(prompt) // 4
            ai_logger.info(f"🔍 Light market assessment: ~{estimated_tokens} tokens")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,  # Very minimal response
                temperature=0.2,  # Very conservative
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Log token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            ai_logger.info(f"⚡ Light assessment tokens: {input_tokens} input + {output_tokens} output = {total_tokens} total")
            
            response_text = response.content[0].text
            
            # Parse JSON response
            assessment = self._parse_json_response(response_text)
            
            if not assessment:
                ai_logger.warning("Failed to parse market risk assessment, using neutral default")
                return self._empty_market_risk_assessment()
            
            # Validate assessment structure
            market_risk = assessment.get('market_risk', '').upper()
            if market_risk not in ['LOW', 'MEDIUM', 'HIGH']:
                ai_logger.warning(f"Invalid market_risk value: {market_risk}, using MEDIUM")
                return self._empty_market_risk_assessment()
            
            # Truncate notes to max 15 words
            notes = assessment.get('notes', '')
            notes_words = notes.split()[:15]
            notes = ' '.join(notes_words)
            
            assessment['notes'] = notes
            ai_logger.info(f"📊 Market risk: {market_risk} | Notes: {notes}")
            
            return assessment
        
        except APIError as e:
            ai_logger.error(f"Claude API error in market risk assessment: {e}")
            return self._empty_market_risk_assessment()
        except Exception as e:
            ai_logger.error(f"Error in market risk assessment: {e}")
            return self._empty_market_risk_assessment()
    
    @staticmethod
    def _empty_oracle_decision() -> Dict[str, Any]:
        """Return safe NO_TRADE decision"""
        return {
            "action": "NO_TRADE",
            "symbol": None,
            "edge": "WEAK",
            "reason": "Analysis failed"
        }
    
    @staticmethod
    def _empty_market_risk_assessment() -> Dict[str, Any]:
        """Return safe MEDIUM risk assessment as default"""
        return {
            "market_risk": "MEDIUM",
            "notes": "Assessment unavailable, using neutral default"
        }
    
    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse JSON from Claude response
        Handles cases where JSON is embedded in other text
        """
        try:
            # Try direct parse first
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        try:
            # Extract JSON from text (look for {...})
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group()
                return json.loads(json_str)
        except Exception as e:
            ai_logger.debug(f"Failed to extract JSON: {e}")
        
        return None
    
    def _extract_consensus(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract coins that appear in multiple analyses"""
        coin_counts = {}
        
        for result in all_results:
            for coin in result.get('selected_coins', []):
                symbol = coin.get('symbol', '').upper()
                if symbol not in coin_counts:
                    coin_counts[symbol] = []
                coin_counts[symbol].append(coin)
        
        # Return coins mentioned in at least 2 analyses
        consensus = []
        for symbol, coins in coin_counts.items():
            if len(coins) >= MIN_CONSENSUS_AGREEMENTS:
                # Average the data
                avg_confidence = sum(c.get('confidence', 0) for c in coins) / len(coins)
                coins[0]['consensus_strength'] = len(coins) / len(all_results)
                coins[0]['confidence'] = avg_confidence
                consensus.append(coins[0])
        
        return sorted(consensus, key=lambda x: x.get('confidence', 0), reverse=True)
    
    @staticmethod
    def _empty_analysis() -> Dict[str, Any]:
        """Return empty analysis structure"""
        return {
            "analysis": "Analysis failed",
            "selected_coins": [],
            "market_sentiment": "neutral",
            "important_notes": "Could not complete analysis",
        }
    
    @staticmethod
    def _empty_signal(symbol: str) -> Dict[str, Any]:
        """Return empty signal structure"""
        return {
            "signal": "HOLD",
            "confidence": 0,
            "stop_loss": 0,
            "take_profit": [],
            "rationale": f"Could not generate signal for {symbol}",
        }


# Singleton instance
ai_analyzer = AIAnalyzer()
