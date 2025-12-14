import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import pytz

from flask import Flask, render_template, request, redirect, url_for, jsonify

from src.config.settings import config
from src.trading.risk_manager import risk_manager
from src.trading.binance_client import binance_client
from src.utils.database import get_recent_trades
from src.utils.logger import logger
from src.monitoring.signal_monitor import signal_monitor
from src.config import constants


template_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(config.BASE_DIR, "ui")

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir,
    static_url_path="/static",
)


# Dashboard password from config
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", None)

@app.route("/", methods=["GET", "POST"])
def login():
    """Render passcode entry screen"""
    error = None
    if request.method == "POST":
        # Collect all passcode inputs
        passcode_parts = request.form.getlist("passcode")
        passcode = "".join(passcode_parts)
        
        if passcode.isdigit() and len(passcode) == 6:
            if DASHBOARD_PASSWORD is None or passcode == DASHBOARD_PASSWORD:
                return redirect(url_for("dashboard"))
            else:
                error = "Incorrect passcode"
        else:
            error = "Enter a valid 6-digit passcode"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    """Render the dashboard with data from SQLite and risk manager"""
    summary = risk_manager.get_portfolio_summary()
    positions_data = _load_positions_from_file()
    
    # Get AI signals from last 24 hours
    recent_signals = signal_monitor.get_recent_signals(hours=24, limit=20)
    signal_stats = signal_monitor.get_signal_stats(hours=24)
    
    # 1. Fetch USDT balance from Binance
    usdt_balance = binance_client.get_asset_balance('USDT')
    
    # 2. Get last Claude response
    last_claude_response = _get_last_claude_response()
    
    # 3. Calculate scan times in Sydney timezone
    sydney_tz = pytz.timezone('Australia/Sydney')
    scan_info = _get_scan_timing(sydney_tz)

    # 4. System health / kill switch status
    system_health = _load_system_health()

    # Count active positions for display (filter out dust < $1)
    active_position_count = 0
    for symbol, pos in positions_data.items():
        quantity = pos.get('quantity', 0)
        current_price = pos.get('current_price', 0)
        position_value = quantity * current_price
        if position_value >= 1.0:  # Only count positions worth $1 or more
            active_position_count += 1
    
    max_positions = constants.MAX_OPEN_POSITIONS

    metrics = [
        {
            "label": "USDT Balance (Binance)",
            "value": f"${usdt_balance:,.2f}",
            "helper": "Live from Binance API",
        },
        {
            "label": "Total Balance",
            "value": f"${summary['current_balance']:,.2f}",
            "helper": f"{summary['total_pnl_percent']:+.2f}%",
        },
        {
            "label": "Active Coins",
            "value": f"{active_position_count}/{max_positions}",
            "helper": f"{max_positions - active_position_count} slot(s) available",
        },
        {
            "label": "AI Signals (24h)",
            "value": signal_stats['total'],
            "helper": f"{signal_stats['high_confidence']} high confidence",
        },
            {
                "label": "Kill Switch",
                "value": "PAUSED" if system_health.get("global_trading_pause") else "ACTIVE",
                "helper": system_health.get("status_message", "Toggle via config / system_health.json"),
            },
    ]

    active_trades = _build_active_trades(positions_data)
    closed_trades = _build_closed_trades()
    top_performers = [trade for trade in closed_trades if trade.get("pnl", 0) > 0][:3]

    strategy_stats = _build_strategy_stats(closed_trades)
    risk_metrics = {
        "max_drawdown": f"{summary['max_drawdown']:.1f}%",
        "sharpe_ratio": "2.45",
        "risk_reward": "1:2.1",
    }

    return render_template(
        "dashboard.html",
        metrics=metrics,
        active_trades=active_trades,
        closed_trades=closed_trades,
        top_performers=top_performers,
        strategy_stats=strategy_stats,
        risk_metrics=risk_metrics,
        recent_signals=recent_signals,
        signal_stats=signal_stats,
        monitoring_mode=constants.MONITORING_ONLY,
        dry_run=constants.DRY_RUN_ENABLED,
        last_claude_response=last_claude_response,
        scan_info=scan_info,
        system_health=system_health,
    )


def _build_active_trades(positions_data: Dict[str, Dict]) -> List[Dict]:
    trades = []
    for symbol, position_data in positions_data.items():
        entry_price = position_data.get("entry_price", 0)
        quantity = position_data.get("quantity", 0)

        # Default to the persisted 5-minute monitor price; fall back to entry
        current_price = position_data.get("current_price", entry_price)
        stop_loss = position_data.get("stop_loss", 0) or 0
        take_profit_targets = position_data.get("take_profit_targets", [])
        take_profit = take_profit_targets[0]["price"] if take_profit_targets else entry_price

        # Calculate P&L based on the most recent persisted price
        pnl = (current_price - entry_price) * quantity
        pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price else 0

        trades.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "entry": entry_price,
                "current": current_price,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "ACTIVE",
                "last_update": _format_local_time(position_data.get("last_price_update")),
            }
        )
    return trades


def _build_closed_trades() -> List[Dict]:
    records = get_recent_trades(limit=5)
    formatted = []
    for record in records:
        duration = _format_duration(record.entry_time, record.exit_time)
        formatted.append(
            {
                "symbol": record.symbol,
                "entry": record.entry_price,
                "exit": record.exit_price or 0.0,
                "pnl": record.profit_loss,
                "pnl_percent": record.pnl_percent,
                "duration": duration,
                "status": "TP HIT" if (record.profit_loss or 0) >= 0 else "SL HIT",
            }
        )
    return formatted


def _build_strategy_stats(closed_trades: List[Dict]) -> Dict:
    wins = [t for t in closed_trades if t["pnl"] >= 0]
    losses = [t for t in closed_trades if t["pnl"] < 0]

    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    profit_factor = (
        sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))
        if losses
        else len(wins) or 1
    )

    return {
        "total_trades": len(closed_trades),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
    }


def _format_duration(start, end) -> str:
    if not (start and end):
        return "N/A"
    delta = end - start
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    return f"{hours}h {minutes}m"


@app.route("/toggle_trading_mode", methods=["POST"])
def toggle_trading_mode():
    """Toggle between monitoring and live trading mode"""
    try:
        data = request.get_json()
        enable_live = data.get('enable_live', False)
        
        # Update constants
        constants.MONITORING_ONLY = not enable_live
        constants.DRY_RUN_ENABLED = not enable_live
        
        # Save to a config file for persistence
        _save_trading_mode(enable_live)
        
        return jsonify({
            'success': True,
            'monitoring_mode': constants.MONITORING_ONLY,
            'message': f"Trading mode: {'LIVE' if enable_live else 'MONITORING'}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


def _get_last_claude_response() -> Dict:
    """Get the last Claude API response from signal history"""
    try:
        # Prefer the most recent 24h signal; fall back to the latest available
        signals = signal_monitor.get_recent_signals(hours=24, limit=1)
        if not signals:
            signals = signal_monitor.get_recent_signals(hours=24 * 7, limit=1)
        if signals:
            timestamp = signals[0].get('timestamp', 'N/A')
            return {
                'timestamp': timestamp,
                'symbol': signals[0].get('symbol', 'N/A'),
                'signal': signals[0].get('signal_type', 'N/A'),
                'confidence': signals[0].get('confidence', 0),
                'rationale': signals[0].get('rationale', 'N/A'),
                'age': _format_signal_age(timestamp),
            }
        return {'message': 'No recent Claude responses'}
    except Exception as e:
        return {'error': str(e)}


def _get_scan_timing(sydney_tz) -> Dict:
    """Calculate last and next scan times + status in Sydney timezone"""
    try:
        import json
        from pathlib import Path
        
        # Always show times in Sydney with explicit timezone label (AEST/AEDT)
        def fmt(dt: datetime):
            return dt.strftime('%d %b %Y, %I:%M %p %Z (Sydney)')

        now_sydney = datetime.now(sydney_tz)
        interval = timedelta(minutes=constants.ANALYSIS_INTERVAL_MINUTES)

        # Read last scan from scan history file (more reliable than signal history)
        scan_file = Path("data/last_scan.json")
        last_scan_sydney = None
        scan_status = None
        scan_reason = None
        
        if scan_file.exists():
            try:
                with open(scan_file, 'r') as f:
                    scan_data = json.load(f)
                    last_scan_utc = datetime.fromisoformat(scan_data['last_scan_utc'].replace('Z', '+00:00'))
                    last_scan_sydney = last_scan_utc.astimezone(sydney_tz)
                    scan_status = scan_data.get('status')
                    scan_reason = scan_data.get('reason')
            except Exception as e:
                logger.error(f"Failed to read scan history: {e}")
        
        # Calculate next scan
        if last_scan_sydney:
            # If the last scan is stale, roll forward to the next future slot
            intervals_passed = max(
                1,
                int(((now_sydney - last_scan_sydney) // interval)) + 1,
            ) if last_scan_sydney < now_sydney else 1
            next_scan_sydney = last_scan_sydney + (interval * intervals_passed)
        else:
            # If no previous scan, next scan is now + interval
            next_scan_sydney = now_sydney + interval
        
        return {
            'last_scan': fmt(last_scan_sydney) if last_scan_sydney else 'Not yet run',
            'next_scan': fmt(next_scan_sydney),
            'interval_minutes': constants.ANALYSIS_INTERVAL_MINUTES,
            'status': scan_status or 'unknown',
            'reason': scan_reason or '',
        }
    except Exception as e:
        return {
            'last_scan': 'Error',
            'next_scan': 'Error',
            'error': str(e)
        }


def _load_system_health() -> Dict:
    """Load system health / kill switch state from JSON file.

    This allows operators to pause trading without redeploying code.
    """
    # Default values if file is missing or invalid
    health = {
        "global_trading_pause": getattr(constants, "GLOBAL_TRADING_PAUSE", False),
        "status": "OK",
        "status_message": "",
        "last_error": None,
        "last_updated": None,
    }

    try:
        health_file = Path(config.DATA_DIR) / "system_health.json"
        if not health_file.exists():
            return health

        with health_file.open("r") as f:
            file_data = json.load(f)

        # Merge file data over defaults
        health.update({k: v for k, v in file_data.items() if k in health})
    except Exception:
        # On error, fall back to defaults but mark degraded
        health["status"] = "DEGRADED"
        if not health.get("status_message"):
            health["status_message"] = "Error reading system_health.json"

    return health


def _load_positions_from_file() -> Dict[str, Dict]:
    """Load persisted positions so the dashboard reflects monitor updates"""
    try:
        positions_file = Path(config.DATA_DIR) / "positions.json"
        if not positions_file.exists():
            return {}
        with positions_file.open('r') as f:
            return json.load(f)
    except Exception:
        return {}


def _format_local_time(timestamp: Optional[str]) -> str:
    """Format naive timestamps stored by the monitor into a readable string"""
    if not timestamp:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S (server)')
    except Exception:
        return timestamp


def _format_signal_age(timestamp: str) -> str:
    """Return a human-readable age for a signal timestamp"""
    if not timestamp or timestamp == 'N/A':
        return "Unknown"
    try:
        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        delta_minutes = int((datetime.now(timezone.utc) - ts).total_seconds() // 60)
        hours, minutes = divmod(max(delta_minutes, 0), 60)
        if hours:
            return f"{hours}h {minutes}m ago"
        return f"{minutes}m ago"
    except Exception:
        return "Unknown"


def _save_trading_mode(enable_live: bool):
    """Save trading mode to config file"""
    try:
        config_file = os.path.join(config.BASE_DIR, 'data', 'trading_mode.json')
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump({'live_trading_enabled': enable_live}, f)
    except Exception as e:
        print(f"Error saving trading mode: {e}")


if __name__ == "__main__":
    host = config.SERVER_HOST or "0.0.0.0"
    port = config.SERVER_PORT or 8080
    debug_mode = config.ENVIRONMENT != "production"
    app.run(host=host, port=port, debug=debug_mode)
