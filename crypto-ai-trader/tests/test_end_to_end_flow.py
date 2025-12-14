import asyncio
from unittest.mock import patch, MagicMock

import pytest

from src.ai.signal_generator import SignalOrchestrator
from src.trading.risk_manager import risk_manager
from src.trading.order_manager import order_manager
from src.config import constants


@pytest.mark.asyncio
async def test_happy_path_trade_opens_position(monkeypatch):
    """Full cycle: Claude says BUY, Binance accepts, position opens."""
    orchestrator = SignalOrchestrator()

    # Reset positions for a clean slate
    risk_manager.positions.clear()

    # Mock top coins list (just one coin)
    async def fake_get_top_n_coins_by_volume(n: int):
        return [{"symbol": "TEST"}]

    monkeypatch.setattr(
        "src.data.data_fetcher.data_processor.get_top_n_coins_by_volume",
        fake_get_top_n_coins_by_volume,
    )

    # Mock Tier-1 data collection + indicators
    async def fake_collect_market_data(self, top_coins):
        return [
            {
                "symbol": "TESTUSDT",
                "current_price": 10.0,
                "indicators": {"rsi": 60},
                "df": None,
            }
        ]

    monkeypatch.setattr(SignalOrchestrator, "_screen_primary_setups", fake_collect_market_data)

    # Mock Claude oracle to return a BUY
    class FakeAIAnalyzer:
        @staticmethod
        def generate_signals_batch_oracle(coins_data):
            return {
                "action": "BUY",
                "symbol": "TESTUSDT",
                "confidence": 80,
                "entry_reason": "Test BUY signal",
                "stop_loss": 9.7,
                "take_profit": [10.3, 10.5, 10.8],
            }

    monkeypatch.setattr("src.ai.ai_analyzer.ai_analyzer", FakeAIAnalyzer())

    # Mock Binance client
    fake_client = MagicMock()
    fake_client.get_account_balance.return_value = {"USDT": 100.0}
    fake_client.place_market_order.return_value = {"orderId": 123}

    monkeypatch.setattr(
        "src.trading.binance_client.binance_client",
        fake_client,
    )

    # Avoid real Telegram calls
    monkeypatch.setattr(
        "src.monitoring.notifications.notifier.send_trade_alert",
        lambda *a, **k: asyncio.Future(),
    )

    # Run one analysis cycle
    result = await orchestrator.run_analysis_cycle()

    # Assert cycle completed and a position was added
    assert result["status"] == "completed"
    assert any(sym.endswith("USDT") for sym in risk_manager.positions.keys())


@pytest.mark.asyncio
async def test_global_trading_pause_blocks_new_trades(monkeypatch):
    """When GLOBAL_TRADING_PAUSE is True, no new positions should open."""
    orchestrator = SignalOrchestrator()

    risk_manager.positions.clear()
    # Force pause
    monkeypatch.setattr("src.config.constants.GLOBAL_TRADING_PAUSE", True, raising=False)

    # Same mocks as happy path for top coins and Claude
    async def fake_get_top_n_coins_by_volume(n: int):
        return [{"symbol": "TEST"}]

    monkeypatch.setattr(
        "src.data.data_fetcher.data_processor.get_top_n_coins_by_volume",
        fake_get_top_n_coins_by_volume,
    )

    async def fake_collect_market_data(self, top_coins):
        return [
            {
                "symbol": "TESTUSDT",
                "current_price": 10.0,
                "indicators": {"rsi": 60},
                "df": None,
            }
        ]

    monkeypatch.setattr(SignalOrchestrator, "_screen_primary_setups", fake_collect_market_data)

    class FakeAIAnalyzer:
        @staticmethod
        def generate_signals_batch_oracle(coins_data):
            return {
                "action": "BUY",
                "symbol": "TESTUSDT",
                "confidence": 80,
                "entry_reason": "Test BUY signal",
                "stop_loss": 9.7,
                "take_profit": [10.3, 10.5, 10.8],
            }

    monkeypatch.setattr("src.ai.ai_analyzer.ai_analyzer", FakeAIAnalyzer())

    fake_client = MagicMock()
    fake_client.get_account_balance.return_value = {"USDT": 100.0}
    fake_client.place_market_order.return_value = {"orderId": 123}

    monkeypatch.setattr(
        "src.trading.binance_client.binance_client",
        fake_client,
    )

    monkeypatch.setattr(
        "src.monitoring.notifications.notifier.send_trade_alert",
        lambda *a, **k: asyncio.Future(),
    )

    result = await orchestrator.run_analysis_cycle()

    # No positions should be opened due to kill switch
    assert result["status"] == "completed" or result["status"] in {"no_candidates", "skipped"}
    assert risk_manager.positions == {}


@pytest.mark.asyncio
async def test_partial_take_profit_reduces_position(monkeypatch):
    """Simulate price hitting first TP and verify quantity reduction."""
    from src.monitoring.position_monitor import position_monitor

    # Seed a fake position directly in risk_manager
    risk_manager.positions.clear()

    class DummyPosition:
        def __init__(self):
            self.symbol = "TESTUSDT"
            self.entry_price = 10.0
            self.quantity = 10.0
            self.stop_loss = 9.7
            self.take_profit_targets = [
                {"price": 10.3, "position_percent": 0.5},
                {"price": 10.5, "position_percent": 0.5},
            ]

        def update_current_price(self, p):
            pass

    risk_manager.positions["TESTUSDT"] = DummyPosition()

    # Mock Binance price to be above first TP
    fake_client = MagicMock()
    fake_client.get_current_price.return_value = 10.31
    fake_client.place_market_order.return_value = {"orderId": 1}

    monkeypatch.setattr(
        "src.trading.binance_client.binance_client",
        fake_client,
    )

    # Wrap order_manager.close_position to observe calls but still update risk_manager
    original_close = order_manager.close_position

    def wrapped_close_position(symbol, reason="Manual", quantity_override=None, keep_open=False):
        return original_close(symbol, reason, quantity_override, keep_open)

    monkeypatch.setattr("src.trading.order_manager.order_manager.close_position", wrapped_close_position)

    # Run a single iteration of monitor_positions by shortening the sleep and breaking after one loop
    async def one_shot_monitor(self):
        self.running = True
        from src.trading.risk_manager import risk_manager as rm
        active_positions = rm.positions
        for symbol, position in active_positions.items():
            current_price = fake_client.get_current_price(symbol)
            position.update_current_price(current_price)
        self.running = False

    monkeypatch.setattr(
        "src.monitoring.position_monitor.PositionMonitor.monitor_positions",
        one_shot_monitor,
    )

    await position_monitor.monitor_positions()

    # After partial TP, quantity should be reduced (but not zero)
    remaining = risk_manager.positions["TESTUSDT"].quantity
    assert 0 < remaining < 10.0
