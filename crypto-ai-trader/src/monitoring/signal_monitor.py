"""
Simple signal monitoring dashboard - store AI signals for display
"""
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from pathlib import Path


class SignalMonitor:
    """Store and retrieve AI trading signals for dashboard display"""
    
    def __init__(self, storage_file: str = "data/signal_history.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.storage_file.exists():
            self._save_signals([])
    
    def add_signal(self, signal: Dict[str, Any]):
        """
        Add a new signal to history
        
        Args:
            signal: Signal dict with keys: symbol, signal_type, confidence, 
                    stop_loss, take_profit, rationale, timestamp, indicators
        """
        signals = self._load_signals()
        
        # Add timestamp if not present
        if 'timestamp' not in signal:
            signal['timestamp'] = datetime.now().isoformat()
        
        # Add unique ID
        signal['id'] = f"{signal['symbol']}_{int(datetime.now().timestamp())}"
        
        signals.append(signal)
        
        # Keep only last 100 signals
        if len(signals) > 100:
            signals = signals[-100:]
        
        self._save_signals(signals)
    
    def get_recent_signals(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get signals from last N hours"""
        signals = self._load_signals()
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent = []
        for s in signals:
            try:
                ts = datetime.fromisoformat(s['timestamp'])
                # Make timestamp timezone-aware if it isn't
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts > cutoff:
                    recent.append(s)
            except (KeyError, ValueError):
                continue
        
        # Sort by timestamp descending
        recent.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return recent[:limit]
    
    def get_signal_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics about recent signals (supports both edge and confidence)"""
        signals = self.get_recent_signals(hours=hours)
        
        if not signals:
            return {
                'total': 0,
                'buy': 0,
                'sell': 0,
                'hold': 0,
                'avg_confidence': 0,
                'high_confidence': 0,
                'strong_edge': 0,
                'moderate_edge': 0,
                'weak_edge': 0,
            }
        
        buy_count = sum(1 for s in signals if s.get('signal_type') == 'BUY')
        sell_count = sum(1 for s in signals if s.get('signal_type') == 'SELL')
        hold_count = sum(1 for s in signals if s.get('signal_type') == 'HOLD')
        
        # Legacy: confidence-based stats
        confidences = [s.get('confidence', 0) for s in signals]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        high_conf = sum(1 for c in confidences if c >= 70)
        
        # New: edge-based stats
        strong_edge = sum(1 for s in signals if s.get('edge', '').upper() == 'STRONG')
        moderate_edge = sum(1 for s in signals if s.get('edge', '').upper() == 'MODERATE')
        weak_edge = sum(1 for s in signals if s.get('edge', '').upper() == 'WEAK')
        
        return {
            'total': len(signals),
            'buy': buy_count,
            'sell': sell_count,
            'hold': hold_count,
            'avg_confidence': round(avg_conf, 1),
            'high_confidence': high_conf,
            # New edge metrics
            'strong_edge': strong_edge,
            'moderate_edge': moderate_edge,
            'weak_edge': weak_edge,
        }
    
    def clear_old_signals(self, days: int = 7):
        """Remove signals older than N days"""
        signals = self._load_signals()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = [
            s for s in signals
            if datetime.fromisoformat(s['timestamp']) > cutoff
        ]
        
        self._save_signals(filtered)
    
    def _load_signals(self) -> List[Dict[str, Any]]:
        """Load signals from JSON file"""
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _save_signals(self, signals: List[Dict[str, Any]]):
        """Save signals to JSON file"""
        with open(self.storage_file, 'w') as f:
            json.dump(signals, f, indent=2)


# Singleton instance
signal_monitor = SignalMonitor()
