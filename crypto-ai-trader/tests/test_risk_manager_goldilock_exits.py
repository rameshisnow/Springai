from datetime import datetime, timedelta


from src.trading.risk_manager import RiskManager, Position


def _make_manager_with_position(position: Position) -> RiskManager:
    rm = RiskManager(starting_capital=1000)
    rm.positions = {position.symbol: position}
    return rm


def test_goldilock_no_tp_before_min_hold() -> None:
    pos = Position(
        symbol="DOGEUSDT",
        entry_price=100.0,
        quantity=1.0,
        entry_time=datetime.now() - timedelta(days=3),
        stop_loss=92.0,
        take_profit_targets=[{"price": 115.0, "position_percent": 0.5, "hit": False}],
    )
    rm = _make_manager_with_position(pos)

    # Price is above TP1, but within min hold days => no TP should fire
    res = rm.update_position("DOGEUSDT", current_price=116.0)
    assert res.get("exit_signal") is None


def test_goldilock_stop_loss_tightens_after_day7() -> None:
    pos = Position(
        symbol="SHIBUSDT",
        entry_price=100.0,
        quantity=1.0,
        entry_time=datetime.now() - timedelta(days=10),
        stop_loss=92.0,  # initial 8% stop
    )
    rm = _make_manager_with_position(pos)

    # Trigger update to tighten SL to 97.0 (3% stop after min hold)
    res = rm.update_position("SHIBUSDT", current_price=100.0)
    assert res.get("exit_signal") is None
    assert pos.stop_loss >= 97.0


def test_goldilock_tp1_sets_tp1_hit_and_partial_exit() -> None:
    pos = Position(
        symbol="SOLUSDT",
        entry_price=100.0,
        quantity=10.0,
        entry_time=datetime.now() - timedelta(days=10),
        stop_loss=97.0,
    )
    rm = _make_manager_with_position(pos)

    res = rm.update_position("SOLUSDT", current_price=115.0)
    assert res.get("exit_signal") == "TAKE_PROFIT"
    assert res.get("take_profit_level") == 1
    assert abs(res.get("position_percent") - 0.5) < 1e-9
    assert pos.tp1_hit is True


def test_goldilock_trailing_only_after_tp1() -> None:
    pos = Position(
        symbol="DOGEUSDT",
        entry_price=100.0,
        quantity=10.0,
        entry_time=datetime.now() - timedelta(days=10),
        stop_loss=97.0,
    )
    rm = _make_manager_with_position(pos)

    # Build a high watermark without hitting TP1
    pos.update_highest_price(130.0)
    pos.tp1_hit = False
    # Keep price below TP1 (+15%) to avoid TP triggering
    res = rm.update_position("DOGEUSDT", current_price=110.0)
    assert res.get("exit_signal") is None

    # After TP1, trailing is enabled
    pos.tp1_hit = True
    pos.update_highest_price(130.0)
    # Use a pullback below TP1 so TP2 doesn't trigger; should hit trailing instead
    res2 = rm.update_position("DOGEUSDT", current_price=112.0)  # below 130*0.95=123.5
    assert res2.get("exit_signal") == "TRAILING_STOP"


def test_non_goldilock_symbol_behavior_unchanged_trailing() -> None:
    # For a symbol with no strategy mapping, RiskManager should keep the old trailing behavior.
    pos = Position(
        symbol="BTCUSDT",
        entry_price=100.0,
        quantity=1.0,
        entry_time=datetime.now() - timedelta(days=10),
        stop_loss=90.0,
        take_profit_targets=[{"price": 105.0, "percent": 5.0, "position_percent": 0.5, "hit": False}],
    )
    rm = _make_manager_with_position(pos)
    pos.update_highest_price(120.0)

    # With default trailing percent, price far below the high should trigger trailing stop.
    res = rm.update_position("BTCUSDT", current_price=1.0)
    assert res.get("exit_signal") in {"TRAILING_STOP", "STOP_LOSS"}
