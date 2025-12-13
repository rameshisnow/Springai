"""
Trade Analytics - Track all trades for performance analysis

This answers:
- What is my actual win rate?
- What is my expectancy?
- How does confidence correlate with outcomes?
- Where am I losing money?
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path


@dataclass
class Trade:
    """Complete trade record"""
    # Entry
    symbol: str
    entry_time: str
    entry_price: float
    quantity: float
    position_value: float
    
    # Risk parameters
    stop_loss: float
    take_profit_targets: List[Dict]
    risk_amount: float  # Dollar risk
    
    # AI context
    confidence: int
    rationale: str
    indicators_at_entry: Dict
    
    # Exit (populated when trade closes)
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "SL", "TP1", "TP2", "TIME", "MANUAL"
    
    # Outcomes (calculated at exit)
    pnl_dollars: Optional[float] = None
    pnl_percent: Optional[float] = None
    r_multiple: Optional[float] = None
    holding_hours: Optional[float] = None
    mae: Optional[float] = None  # Maximum Adverse Excursion
    mfe: Optional[float] = None  # Maximum Favorable Excursion
    
    # Metadata
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return {
            'symbol': self.symbol,
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'position_value': self.position_value,
            'stop_loss': self.stop_loss,
            'take_profit_targets': self.take_profit_targets,
            'risk_amount': self.risk_amount,
            'confidence': self.confidence,
            'rationale': self.rationale,
            'indicators_at_entry': self.indicators_at_entry,
            'exit_time': self.exit_time,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'pnl_dollars': self.pnl_dollars,
            'pnl_percent': self.pnl_percent,
            'r_multiple': self.r_multiple,
            'holding_hours': self.holding_hours,
            'mae': self.mae,
            'mfe': self.mfe,
            'notes': self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create Trade from dict"""
        return cls(**data)


class TradeJournal:
    """
    Persistent trade journal for analytics
    
    Records EVERY trade for analysis:
    - Win rate
    - Expectancy
    - Confidence calibration
    - Exit distribution
    """
    
    def __init__(self, data_file: str = "data/trade_journal.json"):
        self.data_file = Path(data_file)
        self.trades: List[Trade] = []
        self._load_from_file()
    
    def _load_from_file(self):
        """Load existing trades"""
        if not self.data_file.exists():
            return
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            self.trades = [Trade.from_dict(t) for t in data]
        
        except Exception as e:
            print(f"Error loading trade journal: {e}")
    
    def _save_to_file(self):
        """Persist trade journal"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = [t.to_dict() for t in self.trades]
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_trade_entry(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        position_value: float,
        stop_loss: float,
        take_profit_targets: List[Dict],
        confidence: int,
        rationale: str,
        indicators: Dict,
    ) -> Trade:
        """Record new trade entry"""
        # Calculate risk
        risk_per_share = entry_price - stop_loss
        risk_amount = risk_per_share * quantity
        
        trade = Trade(
            symbol=symbol,
            entry_time=datetime.now().isoformat(),
            entry_price=entry_price,
            quantity=quantity,
            position_value=position_value,
            stop_loss=stop_loss,
            take_profit_targets=take_profit_targets,
            risk_amount=risk_amount,
            confidence=confidence,
            rationale=rationale,
            indicators_at_entry=indicators,
        )
        
        self.trades.append(trade)
        self._save_to_file()
        
        return trade
    
    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
        mae: float,
        mfe: float,
        notes: str = ""
    ):
        """Record trade exit"""
        # Find open trade for this symbol
        trade = next((t for t in self.trades if t.symbol == symbol and t.exit_time is None), None)
        
        if not trade:
            print(f"Warning: No open trade found for {symbol}")
            return
        
        # Calculate outcomes
        trade.exit_time = datetime.now().isoformat()
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.mae = mae
        trade.mfe = mfe
        trade.notes = notes
        
        # P&L
        trade.pnl_dollars = (exit_price - trade.entry_price) * trade.quantity
        trade.pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        
        # R multiple (risk-adjusted return)
        if trade.risk_amount > 0:
            trade.r_multiple = trade.pnl_dollars / trade.risk_amount
        else:
            trade.r_multiple = 0
        
        # Holding time
        entry_dt = datetime.fromisoformat(trade.entry_time)
        exit_dt = datetime.fromisoformat(trade.exit_time)
        trade.holding_hours = (exit_dt - entry_dt).total_seconds() / 3600
        
        self._save_to_file()
        
        # Also add to confidence calibration
        from src.backtesting.confidence_calibration import confidence_calibration, TradeResult
        
        trade_result = TradeResult(
            timestamp=trade.entry_time,
            symbol=symbol,
            confidence=trade.confidence,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            stop_loss=trade.stop_loss,
            take_profit=[tp['price'] for tp in trade.take_profit_targets],
            exit_reason=exit_reason,
            r_multiple=trade.r_multiple,
            pnl_percent=trade.pnl_percent,
            holding_hours=trade.holding_hours,
            mae=mae,
            mfe=mfe,
            indicators=trade.indicators_at_entry,
            notes=notes,
        )
        
        confidence_calibration.add_trade_result(trade_result)
    
    def get_open_trades(self) -> List[Trade]:
        """Get all open trades"""
        return [t for t in self.trades if t.exit_time is None]
    
    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades"""
        return [t for t in self.trades if t.exit_time is not None]
    
    def get_stats(self) -> Dict:
        """Calculate performance statistics"""
        closed = self.get_closed_trades()
        
        if not closed:
            return {
                'total_trades': 0,
                'message': 'No closed trades yet'
            }
        
        # Win rate
        winners = [t for t in closed if t.pnl_dollars and t.pnl_dollars > 0]
        win_rate = (len(winners) / len(closed)) * 100
        
        # Expectancy
        avg_r = sum(t.r_multiple for t in closed if t.r_multiple) / len(closed)
        
        # P&L
        total_pnl = sum(t.pnl_dollars for t in closed if t.pnl_dollars)
        
        # Holding time
        avg_hold = sum(t.holding_hours for t in closed if t.holding_hours) / len(closed)
        
        return {
            'total_trades': len(closed),
            'win_rate': f"{win_rate:.1f}%",
            'expectancy': f"{avg_r:.2f}R",
            'total_pnl': f"${total_pnl:.2f}",
            'avg_holding_hours': f"{avg_hold:.1f}h",
        }


# Singleton instance
trade_journal = TradeJournal()
