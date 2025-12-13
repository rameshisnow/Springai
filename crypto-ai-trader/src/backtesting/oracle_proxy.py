"""
Oracle Proxy - Simulates Claude's selection behavior for backtesting

NOT prediction - this is selection pressure simulation
Ranks coins by composite score and assigns confidence buckets
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass


@dataclass
class ProxySignal:
    """Simulated Oracle decision"""
    symbol: str
    proxy_confidence: int  # 0-100
    composite_score: float
    rank_percentile: float  # 0-100 (higher = better)
    indicators: Dict
    timestamp: str


class OracleProxy:
    """
    Simulates Oracle Mode selection for backtesting
    
    Methodology:
    1. Compute composite score from indicators
    2. Rank coins (only consider top percentiles)
    3. Assign confidence buckets based on rank
    4. Select top 1 coin (Oracle Mode behavior)
    
    This mimics Claude's role: filtering good setups from candidates
    """
    
    # Confidence buckets (match Claude's typical distribution)
    CONFIDENCE_BUCKETS = [
        (95, 100, 0.05),  # Top 5% → 95-100 confidence
        (85, 94, 0.10),   # Top 5-15% → 85-94 confidence
        (75, 84, 0.15),   # Top 15-30% → 75-84 confidence
        (65, 74, 0.20),   # Top 30-50% → 65-74 confidence
    ]
    
    def __init__(self):
        """Initialize Oracle Proxy with scoring weights"""
        # Composite score weights (tuned to match Oracle Mode priorities)
        self.weights = {
            'momentum': 0.30,      # Price momentum (1H, 4H)
            'volume_expansion': 0.25,  # Volume vs average
            'rsi_position': 0.20,  # RSI slope and position
            'volatility': 0.15,    # ATR relative to price
            'trend_alignment': 0.10,  # Price vs EMA200
        }
    
    def compute_composite_score(self, indicators: Dict) -> float:
        """
        Compute composite score for a coin
        
        Args:
            indicators: Dict with RSI, ATR, volume, price, etc.
        
        Returns:
            Composite score (0-100, higher = better setup)
        """
        scores = {}
        
        # 1. Momentum score (change in last 1H and 4H)
        change_1h = indicators.get('change_1h', 0)
        change_4h = indicators.get('change_4h', 0)
        # Positive momentum, not overextended
        if 0.5 < change_1h < 3.0 and 1.0 < change_4h < 8.0:
            momentum = min(100, (change_1h + change_4h) * 10)
        else:
            momentum = max(0, (change_1h + change_4h) * 5)
        scores['momentum'] = momentum
        
        # 2. Volume expansion score
        volume_24h = indicators.get('volume_24h_usd', 0)
        volume_avg = indicators.get('volume_avg_usd', volume_24h)
        if volume_avg > 0:
            volume_ratio = volume_24h / volume_avg
            # 1.5x to 3x average = good
            if 1.5 <= volume_ratio <= 3.0:
                volume_score = min(100, (volume_ratio - 1) * 40)
            else:
                volume_score = 50
        else:
            volume_score = 50
        scores['volume_expansion'] = volume_score
        
        # 3. RSI position score (sweet spot: 50-68)
        rsi = indicators.get('rsi', 50)
        if 50 <= rsi <= 68:
            rsi_score = 100 - abs(59 - rsi) * 5
        elif 45 <= rsi < 50:
            rsi_score = 70
        elif 68 < rsi <= 72:
            rsi_score = 60
        else:
            rsi_score = 30
        scores['rsi_position'] = rsi_score
        
        # 4. Volatility score (ATR relative to price)
        atr_percent = indicators.get('atr_percent', 0)
        # Sweet spot: 1.5-3% ATR
        if 1.5 <= atr_percent <= 3.0:
            vol_score = 100 - abs(2.25 - atr_percent) * 20
        elif 1.0 <= atr_percent < 1.5:
            vol_score = 70
        elif 3.0 < atr_percent <= 3.5:
            vol_score = 60
        else:
            vol_score = 30
        scores['volatility'] = vol_score
        
        # 5. Trend alignment (price vs EMA200)
        price = indicators.get('price', 0)
        ema200 = indicators.get('ema200', price)
        if ema200 > 0:
            distance = ((price - ema200) / ema200) * 100
            # 2-10% above EMA200 = good
            if 2 <= distance <= 10:
                trend_score = 100 - abs(6 - distance) * 5
            elif 0 <= distance < 2:
                trend_score = 70
            elif 10 < distance <= 15:
                trend_score = 60
            else:
                trend_score = 30
        else:
            trend_score = 50
        scores['trend_alignment'] = trend_score
        
        # Compute weighted composite
        composite = sum(
            scores[key] * self.weights[key]
            for key in self.weights
        )
        
        return min(100, max(0, composite))
    
    def rank_candidates(
        self,
        candidates: List[Dict]
    ) -> List[Tuple[str, float, int]]:
        """
        Rank candidate coins and assign confidence buckets
        
        Args:
            candidates: List of coins with indicators
        
        Returns:
            List of (symbol, score, confidence) sorted by score descending
        """
        if not candidates:
            return []
        
        # Compute scores
        scored = []
        for coin in candidates:
            score = self.compute_composite_score(coin['indicators'])
            scored.append((
                coin['symbol'],
                score,
                coin
            ))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Assign confidence buckets based on percentile rank
        total = len(scored)
        results = []
        
        for idx, (symbol, score, coin) in enumerate(scored):
            # Calculate percentile (0-100, higher = better)
            percentile = ((total - idx - 1) / total) * 100
            
            # Assign confidence bucket
            confidence = self._assign_confidence(percentile)
            
            results.append((symbol, score, confidence))
        
        return results
    
    def _assign_confidence(self, percentile: float) -> int:
        """
        Assign confidence based on percentile rank
        
        Args:
            percentile: 0-100, where 100 = best coin
        
        Returns:
            Confidence score (65-100 or 0 if rejected)
        """
        cumulative = 0
        for conf_min, conf_max, bucket_size in self.CONFIDENCE_BUCKETS:
            cumulative += bucket_size * 100
            if percentile >= (100 - cumulative):
                # Add some noise to simulate Claude variance
                noise = np.random.randint(-2, 3)
                confidence = np.random.randint(conf_min, conf_max + 1) + noise
                return max(conf_min, min(conf_max, confidence))
        
        # Below top 50% → rejected (confidence < 65)
        return np.random.randint(30, 65)
    
    def select_oracle_signal(
        self,
        candidates: List[Dict],
        min_confidence: int = 70
    ) -> Optional[ProxySignal]:
        """
        Simulate Oracle Mode: Select single best coin with sufficient confidence
        
        Args:
            candidates: List of eligible coins with indicators
            min_confidence: Minimum confidence to trade (default: 70)
        
        Returns:
            ProxySignal or None if no suitable setup
        """
        if not candidates:
            return None
        
        # Rank all candidates
        ranked = self.rank_candidates(candidates)
        
        if not ranked:
            return None
        
        # Oracle Mode: Select top 1 only
        symbol, score, confidence = ranked[0]
        
        # Check if meets minimum confidence
        if confidence < min_confidence:
            return None
        
        # Find original coin data
        coin_data = next(c for c in candidates if c['symbol'] == symbol)
        
        return ProxySignal(
            symbol=symbol,
            proxy_confidence=confidence,
            composite_score=score,
            rank_percentile=100.0,  # Top coin
            indicators=coin_data['indicators'],
            timestamp=coin_data.get('timestamp', ''),
        )


# Singleton instance
oracle_proxy = OracleProxy()
