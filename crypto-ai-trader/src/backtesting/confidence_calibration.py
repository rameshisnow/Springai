"""
Confidence Calibration Tracker

Answers the critical question:
"When Claude says X% confidence, what is the actual expectancy?"

This is the MOST IMPORTANT validation for Oracle Mode.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class TradeResult:
    """Individual trade outcome"""
    timestamp: str
    symbol: str
    confidence: int  # Claude's stated confidence
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: List[float]
    
    # Outcomes
    exit_reason: str  # "SL", "TP1", "TP2", "TIME", "MANUAL"
    r_multiple: float  # Risk-adjusted return
    pnl_percent: float
    holding_hours: float
    
    # Risk metrics
    mae: float  # Maximum Adverse Excursion (worst drawdown)
    mfe: float  # Maximum Favorable Excursion (best peak)
    
    # Metadata
    indicators: Dict = field(default_factory=dict)
    notes: str = ""


@dataclass
class ConfidenceBucket:
    """Statistics for a confidence range"""
    confidence_range: str  # "85-100", "75-84", etc.
    trades: List[TradeResult] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return len(self.trades)
    
    @property
    def win_rate(self) -> float:
        """Percentage of trades with positive PnL"""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl_percent > 0)
        return (wins / len(self.trades)) * 100
    
    @property
    def avg_r_multiple(self) -> float:
        """Average R multiple (expectancy)"""
        if not self.trades:
            return 0.0
        return sum(t.r_multiple for t in self.trades) / len(self.trades)
    
    @property
    def expectancy(self) -> float:
        """Expected value per trade"""
        return self.avg_r_multiple
    
    @property
    def avg_holding_hours(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.holding_hours for t in self.trades) / len(self.trades)


class ConfidenceCalibration:
    """
    Track and analyze Claude's confidence vs actual outcomes
    
    Healthy system: Higher confidence → higher expectancy
    Broken system: No correlation or inverse correlation
    """
    
    BUCKETS = [
        "85-100",  # Very high confidence
        "75-84",   # High confidence
        "65-74",   # Medium confidence
        "55-64",   # Low confidence (should reject)
    ]
    
    def __init__(self, data_file: str = "data/confidence_calibration.json"):
        self.data_file = Path(data_file)
        self.buckets: Dict[str, ConfidenceBucket] = {
            bucket: ConfidenceBucket(confidence_range=bucket)
            for bucket in self.BUCKETS
        }
        self._load_from_file()
    
    def _load_from_file(self):
        """Load existing calibration data"""
        if not self.data_file.exists():
            return
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            for bucket_name, trades_data in data.items():
                if bucket_name in self.buckets:
                    for trade_dict in trades_data:
                        trade = TradeResult(**trade_dict)
                        self.buckets[bucket_name].trades.append(trade)
        
        except Exception as e:
            print(f"Error loading calibration data: {e}")
    
    def _save_to_file(self):
        """Persist calibration data"""
        data = {}
        for bucket_name, bucket in self.buckets.items():
            data[bucket_name] = [
                {
                    'timestamp': t.timestamp,
                    'symbol': t.symbol,
                    'confidence': t.confidence,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'stop_loss': t.stop_loss,
                    'take_profit': t.take_profit,
                    'exit_reason': t.exit_reason,
                    'r_multiple': t.r_multiple,
                    'pnl_percent': t.pnl_percent,
                    'holding_hours': t.holding_hours,
                    'mae': t.mae,
                    'mfe': t.mfe,
                    'indicators': t.indicators,
                    'notes': t.notes,
                }
                for t in bucket.trades
            ]
        
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _get_bucket_name(self, confidence: int) -> str:
        """Determine which bucket a confidence score belongs to"""
        if confidence >= 85:
            return "85-100"
        elif confidence >= 75:
            return "75-84"
        elif confidence >= 65:
            return "65-74"
        else:
            return "55-64"
    
    def add_trade_result(self, trade: TradeResult):
        """Add a completed trade to calibration data"""
        bucket_name = self._get_bucket_name(trade.confidence)
        self.buckets[bucket_name].trades.append(trade)
        self._save_to_file()
    
    def get_summary(self) -> Dict:
        """Get calibration summary across all buckets"""
        summary = {}
        
        for bucket_name, bucket in self.buckets.items():
            if bucket.count > 0:
                summary[bucket_name] = {
                    'trades': bucket.count,
                    'win_rate': f"{bucket.win_rate:.1f}%",
                    'avg_r': f"{bucket.avg_r_multiple:.2f}R",
                    'expectancy': f"{bucket.expectancy:.2f}R",
                    'avg_holding_hours': f"{bucket.avg_holding_hours:.1f}h",
                }
        
        return summary
    
    def is_calibrated(self, min_trades_per_bucket: int = 10) -> bool:
        """
        Check if we have enough data to trust the calibration
        
        Args:
            min_trades_per_bucket: Minimum trades needed per bucket
        
        Returns:
            True if calibrated, False if need more data
        """
        # Need at least 10 trades in top 2 buckets
        top_buckets = ["85-100", "75-84"]
        for bucket_name in top_buckets:
            if self.buckets[bucket_name].count < min_trades_per_bucket:
                return False
        return True
    
    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if confidence calibration is healthy
        
        Healthy = higher confidence → higher expectancy (monotonic)
        
        Returns:
            (is_healthy: bool, reason: str)
        """
        if not self.is_calibrated(min_trades_per_bucket=10):
            return False, "Not enough trades to assess (need 10+ per bucket)"
        
        # Get expectancies in descending confidence order
        expectancies = []
        for bucket_name in ["85-100", "75-84", "65-74"]:
            bucket = self.buckets[bucket_name]
            if bucket.count >= 5:  # Need at least 5 trades
                expectancies.append(bucket.expectancy)
        
        if len(expectancies) < 2:
            return False, "Not enough buckets with data"
        
        # Check if mostly monotonic (allow 1 violation)
        violations = 0
        for i in range(len(expectancies) - 1):
            if expectancies[i] < expectancies[i + 1]:
                violations += 1
        
        if violations > 1:
            return False, f"Non-monotonic: higher confidence not producing better results"
        
        # Check if top bucket is positive
        top_bucket = self.buckets["85-100"]
        if top_bucket.count >= 5 and top_bucket.expectancy <= 0:
            return False, f"Top confidence bucket has negative expectancy ({top_bucket.expectancy:.2f}R)"
        
        return True, "Confidence calibration is healthy"
    
    def get_recommended_threshold(self) -> int:
        """
        Recommend minimum confidence threshold based on calibration
        
        Returns:
            Recommended MIN_CONFIDENCE_TO_TRADE value
        """
        if not self.is_calibrated():
            return 70  # Default
        
        # Find lowest bucket with positive expectancy
        for bucket_name in ["65-74", "75-84", "85-100"]:
            bucket = self.buckets[bucket_name]
            if bucket.count >= 10 and bucket.expectancy >= 0.3:
                # Parse bucket minimum
                return int(bucket_name.split('-')[0])
        
        # If nothing positive, recommend high threshold
        return 80
    
    def print_report(self):
        """Print detailed calibration report"""
        print("\n" + "="*70)
        print("CONFIDENCE CALIBRATION REPORT")
        print("="*70)
        
        total_trades = sum(b.count for b in self.buckets.values())
        print(f"\nTotal Trades Tracked: {total_trades}")
        
        if total_trades == 0:
            print("\n⚠️  No trades recorded yet - calibration unavailable")
            return
        
        print("\n" + "-"*70)
        print(f"{'Confidence':<15} {'Trades':<8} {'Win Rate':<12} {'Avg R':<10} {'Expectancy':<12}")
        print("-"*70)
        
        for bucket_name in self.BUCKETS:
            bucket = self.buckets[bucket_name]
            if bucket.count > 0:
                print(
                    f"{bucket_name:<15} "
                    f"{bucket.count:<8} "
                    f"{bucket.win_rate:>6.1f}%     "
                    f"{bucket.avg_r_multiple:>6.2f}R   "
                    f"{bucket.expectancy:>6.2f}R"
                )
        
        print("-"*70)
        
        # Assessment
        is_healthy, reason = self.is_healthy()
        
        if not self.is_calibrated():
            print("\n⚠️  STATUS: NOT CALIBRATED")
            print(f"   Need 10+ trades in top buckets to assess")
        elif is_healthy:
            print("\n✅ STATUS: HEALTHY")
            print(f"   {reason}")
            rec_threshold = self.get_recommended_threshold()
            print(f"   Recommended MIN_CONFIDENCE_TO_TRADE: {rec_threshold}")
        else:
            print("\n❌ STATUS: UNHEALTHY")
            print(f"   {reason}")
            print(f"   Consider: Stop trading, review strategy, or collect more data")
        
        print("\n" + "="*70 + "\n")


# Singleton instance
confidence_calibration = ConfidenceCalibration()
