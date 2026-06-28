from sqlmodel import Session, SQLModel, create_engine, select

from app.db import create_db_and_tables, seed_anonymous_user
from app.models import User


EXPECTED_TABLES = {
    "users",
    "scenarios",
    "user_responses",
    "twin_contexts",
    "twin_strategies",
    "candle_cache",
    "backtest_runs",
    "backtest_trades",
    "feedbacks",
    "watchlists",
    "signal_events",
    "simulated_orders",
}


def test_model_metadata_contains_mvp_tables():
    assert EXPECTED_TABLES.issubset(set(SQLModel.metadata.tables.keys()))


def test_create_tables_and_seed_anonymous_user_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    create_db_and_tables(engine)

    with Session(engine) as session:
        first = seed_anonymous_user(session)
        second = seed_anonymous_user(session)
        users = session.exec(select(User)).all()

    assert first.id == second.id
    assert len(users) == 1
    assert users[0].nickname == "anonymous"


def test_required_constraints_are_named_in_metadata():
    strategy_table = SQLModel.metadata.tables["twin_strategies"]
    signal_table = SQLModel.metadata.tables["signal_events"]

    strategy_index_names = {index.name for index in strategy_table.indexes}
    signal_constraint_names = {
        constraint.name for constraint in signal_table.constraints if constraint.name
    }

    assert "uq_twin_strategy_version" in strategy_index_names
    assert "uq_active_strategy_per_user" in strategy_index_names
    assert "uq_signal_dedup_key" in signal_constraint_names
