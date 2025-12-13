"""
Notification system - Telegram alerts for trades, P&L, and system status
"""
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Warning: python-telegram-bot not installed. Telegram notifications disabled.")

from src.utils.logger import logger
from src.config.settings import config
from src.config.constants import (
    TELEGRAM_HOURLY_REPORT,
    TELEGRAM_TRADE_ALERTS,
    TELEGRAM_PNL_UPDATES,
    TELEGRAM_ERROR_ALERTS,
)


class TelegramNotifier:
    """Send notifications via Telegram"""
    
    def __init__(self):
        """Initialize Telegram bot"""
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.bot = None
        self.enabled = False
        
        if not TELEGRAM_AVAILABLE:
            logger.warning("Telegram library not available - install with: pip install python-telegram-bot")
            return
        
        if not self.token or not self.chat_id:
            logger.warning(f"Telegram credentials not configured - TOKEN: {'✅' if self.token else '❌'}, CHAT_ID: {'✅' if self.chat_id else '❌'}")
            return
        
        try:
            self.bot = Bot(token=self.token)
            self.enabled = True
            logger.info("✅ Telegram notifier initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram bot: {e}")
            self.enabled = False
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send Telegram message
        
        Args:
            message: Message text (supports HTML formatting)
            parse_mode: 'HTML' or 'Markdown'
        
        Returns:
            True if sent successfully
        """
        if not self.enabled or not TELEGRAM_AVAILABLE or not self.bot:
            logger.debug("Telegram disabled or not initialized - message not sent")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            logger.info("✅ Telegram message sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"❌ Telegram API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {type(e).__name__}: {e}")
            return False
    
    async def send_trade_alert(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profits: list = None,
        confidence: float = 0.0,
    ) -> bool:
        """Send trade entry alert"""
        if not TELEGRAM_TRADE_ALERTS or not self.enabled:
            return False
        
        tp_text = ""
        if take_profits:
            tp_text = "\n".join([
                f"  TP{i+1}: ${tp['price']:.8f} ({tp['percent']}%)"
                for i, tp in enumerate(take_profits[:3])
            ])
        
        message = f"""
🔔 <b>TRADE ALERT</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Quantity:</b> {quantity:.8f}
<b>Entry Price:</b> ${entry_price:.8f}
<b>Stop Loss:</b> ${stop_loss:.8f}
<b>Take Profits:</b>
{tp_text}
<b>Confidence:</b> {confidence:.1%}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_position_update(
        self,
        symbol: str,
        current_price: float,
        pnl: float,
        pnl_percent: float,
        reason: str = "",
    ) -> bool:
        """Send position P&L update"""
        if not TELEGRAM_PNL_UPDATES or not self.enabled:
            return False
        
        emoji = "📈" if pnl >= 0 else "📉"
        
        message = f"""
{emoji} <b>POSITION UPDATE</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Symbol:</b> {symbol}
<b>Current Price:</b> ${current_price:.8f}
<b>P&L:</b> ${pnl:.2f} ({pnl_percent:+.2f}%)
<b>Reason:</b> {reason}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_exit_alert(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        reason: str,
        exit_type: str = "MANUAL",
    ) -> bool:
        """Send position exit alert"""
        if not TELEGRAM_TRADE_ALERTS or not self.enabled:
            return False
        
        emoji = "✅" if pnl >= 0 else "❌"
        
        message = f"""
{emoji} <b>POSITION CLOSED</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Symbol:</b> {symbol}
<b>Exit Type:</b> {exit_type}
<b>Exit Price:</b> ${exit_price:.8f}
<b>P&L:</b> ${pnl:.2f} ({pnl_percent:+.2f}%)
<b>Reason:</b> {reason}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_hourly_report(self, portfolio_summary: Dict[str, Any]) -> bool:
        """Send hourly portfolio report"""
        if not TELEGRAM_HOURLY_REPORT or not self.enabled:
            return False
        
        balance = portfolio_summary.get('current_balance', 0)
        total_pnl = portfolio_summary.get('total_pnl', 0)
        total_pnl_percent = portfolio_summary.get('total_pnl_percent', 0)
        open_pos = portfolio_summary.get('open_positions', 0)
        closed_trades = portfolio_summary.get('closed_trades', 0)
        drawdown = portfolio_summary.get('current_drawdown', 0)
        circuit_breaker = portfolio_summary.get('circuit_breaker_active', False)
        
        emoji = "📊"
        status = "🔴 PAUSED" if circuit_breaker else "🟢 ACTIVE"
        
        message = f"""
{emoji} <b>HOURLY REPORT</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Status:</b> {status}
<b>Balance:</b> ${balance:.2f} AUD
<b>Total P&L:</b> ${total_pnl:+.2f} ({total_pnl_percent:+.2f}%)
<b>Drawdown:</b> {drawdown:.2f}%
<b>Open Positions:</b> {open_pos}
<b>Closed Trades:</b> {closed_trades}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_error_alert(
        self,
        error_title: str,
        error_message: str,
        severity: str = "WARNING",  # INFO, WARNING, CRITICAL
    ) -> bool:
        """Send error alert"""
        if not TELEGRAM_ERROR_ALERTS or not self.enabled:
            return False
        
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨",
        }
        emoji = emoji_map.get(severity, "❌")
        
        message = f"""
{emoji} <b>{severity}: {error_title}</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Details:</b> {error_message}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_system_health_alert(
        self,
        system_status: Dict[str, Any],
    ) -> bool:
        """Send system health status"""
        if not self.enabled:
            return False
        
        api_status = "✅" if system_status.get('api_connected') else "❌"
        db_status = "✅" if system_status.get('db_connected') else "❌"
        
        message = f"""
🏥 <b>SYSTEM HEALTH CHECK</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>API Status:</b> {api_status} {system_status.get('api_message', '')}
<b>Database:</b> {db_status} {system_status.get('db_message', '')}
<b>Uptime:</b> {system_status.get('uptime_hours', 0):.1f}h
<b>Memory Usage:</b> {system_status.get('memory_percent', 0):.1f}%
<b>CPU Usage:</b> {system_status.get('cpu_percent', 0):.1f}%
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)
    
    async def send_strategy_signal(
        self,
        coins: list,
        market_sentiment: str,
        analysis: str = "",
    ) -> bool:
        """Send AI analysis signal"""
        if not self.enabled:
            return False
        
        coins_text = "\n".join([
            f"  {i+1}. <b>{c.get('symbol')}</b> - Confidence: {c.get('confidence', 0):.1%}"
            for i, c in enumerate(coins[:5])
        ])
        
        sentiment_emoji = {
            "bullish": "🚀",
            "neutral": "➡️",
            "bearish": "📉",
        }
        emoji = sentiment_emoji.get(market_sentiment, "❓")
        
        message = f"""
{emoji} <b>AI ANALYSIS SIGNAL</b>
━━━━━━━━━━━━━━━━━━━━━━━
<b>Market Sentiment:</b> {market_sentiment.upper()}
<b>Top Coins:</b>
{coins_text}
<b>Analysis:</b> {analysis[:500]}...
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message)


# Singleton instance
notifier = TelegramNotifier()
