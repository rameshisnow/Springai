"""
Portfolio tracker - Real-time portfolio monitoring and analytics
"""
from typing import Dict, List, Any
from datetime import datetime
from src.utils.logger import logger
from src.trading.binance_client import binance_client
from src.trading.risk_manager import risk_manager
from src.trading.order_manager import order_manager


class PortfolioTracker:
    """Track and analyze portfolio performance"""
    
    def __init__(self):
        """Initialize portfolio tracker"""
        self.start_time = datetime.now()
        self.peak_balance = risk_manager.starting_capital
    
    def get_current_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio snapshot"""
        
        # Get account balance
        balances = binance_client.get_account_balance()
        
        # Get active trades
        active_trades = order_manager.get_active_trades()
        
        # Calculate total value
        total_balance = risk_manager.current_balance
        
        # Open P&L
        open_pnl = 0.0
        for symbol, trade in active_trades.items():
            current_price = binance_client.get_current_price(symbol)
            if current_price > 0:
                pnl, _ = risk_manager.positions[symbol].get_current_pnl(current_price)
                open_pnl += pnl
        
        # Closed P&L
        closed_pnl = sum(t.pnl for t in order_manager.closed_trades)
        
        # Total P&L
        total_pnl = open_pnl + closed_pnl
        total_pnl_percent = (total_pnl / risk_manager.starting_capital) * 100 if risk_manager.starting_capital > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "account_balance": risk_manager.current_balance,
            "portfolio_value": total_balance,
            "starting_capital": risk_manager.starting_capital,
            "open_pnl": open_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "active_positions": len(active_trades),
            "closed_trades": len(order_manager.closed_trades),
            "balances": balances,
            "risk_metrics": risk_manager.get_portfolio_summary(),
        }
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """Get trading statistics"""
        
        closed_trades = order_manager.closed_trades
        
        if not closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
            }
        
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = sum(abs(t.pnl) for t in losing_trades)
        
        win_rate = (len(winning_trades) / len(closed_trades)) * 100 if closed_trades else 0
        
        avg_win = (total_wins / len(winning_trades)) if winning_trades else 0
        avg_loss = (total_losses / len(losing_trades)) if losing_trades else 0
        
        profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
        
        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "profit_factor": profit_factor,
            "best_trade": max((t.pnl for t in closed_trades), default=0),
            "worst_trade": min((t.pnl for t in closed_trades), default=0),
        }
    
    def get_asset_allocation(self) -> Dict[str, float]:
        """Get current asset allocation"""
        
        allocation = {}
        total_value = risk_manager.current_balance
        
        active_trades = order_manager.get_active_trades()
        
        for symbol, trade in active_trades.items():
            current_price = binance_client.get_current_price(symbol)
            if current_price > 0:
                position_value = trade.quantity * current_price
                allocation[symbol] = (position_value / total_value) * 100
        
        # Cash allocation
        cash_allocated = sum(t.quantity * t.entry_price for t in active_trades.values())
        allocation['CASH'] = ((total_value - cash_allocated) / total_value) * 100
        
        return allocation
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Calculate advanced performance metrics"""
        
        closed_trades = order_manager.closed_trades
        
        if len(closed_trades) < 2:
            return {
                "sharpe_ratio": 0.0,
                "calmar_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
            }
        
        # Returns
        returns = [t.pnl_percent for t in closed_trades]
        
        # Sharpe Ratio (assuming risk-free rate = 0)
        import statistics
        mean_return = statistics.mean(returns)
        stdev = statistics.stdev(returns) if len(returns) > 1 else 0
        sharpe_ratio = (mean_return / stdev * (252 ** 0.5)) if stdev > 0 else 0  # Annualized
        
        # Max consecutive wins/losses
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in closed_trades:
            if trade.pnl > 0:
                current_wins += 1
                max_wins = max(max_wins, current_wins)
                current_losses = 0
            else:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
                current_wins = 0
        
        # Calmar Ratio
        total_return = (risk_manager.current_balance - risk_manager.starting_capital) / risk_manager.starting_capital
        max_drawdown = risk_manager.max_drawdown / 100
        calmar_ratio = (total_return / max_drawdown) if max_drawdown > 0 else 0
        
        return {
            "sharpe_ratio": sharpe_ratio,
            "calmar_ratio": calmar_ratio,
            "max_consecutive_wins": max_wins,
            "max_consecutive_losses": max_losses,
            "total_return_percent": (total_return * 100),
        }
    
    def get_uptime(self) -> str:
        """Get bot uptime"""
        delta = datetime.now() - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        days = delta.days
        
        return f"{days}d {hours}h {minutes}m"
    
    def print_portfolio_summary(self):
        """Print formatted portfolio summary"""
        
        portfolio = self.get_current_portfolio()
        stats = self.get_trade_statistics()
        metrics = self.get_performance_metrics()
        allocation = self.get_asset_allocation()
        
        print("\n" + "=" * 60)
        print("📊 PORTFOLIO SUMMARY")
        print("=" * 60)
        
        print(f"\n💰 BALANCE & P&L:")
        print(f"   Starting Capital: ${portfolio['starting_capital']:.2f} AUD")
        print(f"   Current Balance:  ${portfolio['account_balance']:.2f} AUD")
        print(f"   Total P&L:        ${portfolio['total_pnl']:+.2f} ({portfolio['total_pnl_percent']:+.2f}%)")
        print(f"   Open P&L:         ${portfolio['open_pnl']:+.2f}")
        
        print(f"\n📈 TRADING STATISTICS:")
        print(f"   Total Trades:     {stats['total_trades']}")
        print(f"   Winning Trades:   {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
        print(f"   Losing Trades:    {stats['losing_trades']}")
        print(f"   Avg Win:          ${stats['avg_win']:+.2f}")
        print(f"   Avg Loss:         ${stats['avg_loss']:+.2f}")
        print(f"   Profit Factor:    {stats['profit_factor']:.2f}x")
        
        print(f"\n⚠️  RISK METRICS:")
        risk_summary = portfolio['risk_metrics']
        print(f"   Current Drawdown: {risk_summary['current_drawdown']:.2f}%")
        print(f"   Max Drawdown:     {risk_summary['max_drawdown']:.2f}%")
        print(f"   Open Positions:   {risk_summary['open_positions']}")
        print(f"   Consecutive Loss: {risk_summary['consecutive_losses']}")
        
        print(f"\n📊 PERFORMANCE METRICS:")
        print(f"   Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
        print(f"   Calmar Ratio:     {metrics['calmar_ratio']:.2f}")
        print(f"   Uptime:           {self.get_uptime()}")
        
        print(f"\n🎯 ASSET ALLOCATION:")
        for asset, percent in sorted(allocation.items(), key=lambda x: x[1], reverse=True):
            print(f"   {asset:8s}: {percent:6.2f}%")
        
        print("\n" + "=" * 60 + "\n")


# Singleton instance
portfolio_tracker = PortfolioTracker()
