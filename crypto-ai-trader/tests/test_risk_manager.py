from src.trading.risk_manager import RiskManager


def test_calculate_position_size_is_positive():
    manager = RiskManager(starting_capital=1000)
    size = manager.calculate_position_size(current_balance=1000, entry_price=10, stop_loss_price=9)
    assert size > 0
    assert size <= 1000


def test_validate_trade_rejects_bad_stop_loss():
    manager = RiskManager(starting_capital=1000)
    valid, message = manager.validate_trade(
        symbol="TESTUSDT",
        quantity=0.1,
        entry_price=10,
        stop_loss_price=12,
    )
    assert not valid
    assert "stop loss" in message.lower()
