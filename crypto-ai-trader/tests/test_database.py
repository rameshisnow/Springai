from pathlib import Path

from src.utils import database


def test_trade_record_round_trip(tmp_path: Path):
    db_path = tmp_path / "trades.db"
    database.configure_database(f"sqlite:///{db_path}")

    record_id = database.log_trade_entry(
        symbol="TESTUSDT",
        side="BUY",
        quantity=1.0,
        entry_price=10.0,
        stop_loss_price=9.7,
        take_profit_levels=[{"price": 10.5, "position_percent": 0.5}],
        confidence=0.85,
        metadata={"source": "test"},
    )
    assert record_id is not None

    updated = database.update_trade_exit(
        record_id=record_id,
        exit_price=10.8,
        pnl=0.8,
        pnl_percent=8.0,
        reason="round-trip test",
    )

    assert updated is not None
    assert updated.profit_loss == 0.8
    assert updated.metadata_payload.get("exit_reason") == "round-trip test"
