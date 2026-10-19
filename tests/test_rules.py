from datetime import UTC, date, datetime, time

from app.rules import has_minimum_notice, is_future, is_within_max_days_ahead


def test_future_rule_uses_bogota_time() -> None:
    now = datetime(2026, 1, 1, 15, 0, tzinfo=UTC)

    assert is_future(date(2026, 1, 1), time(10, 1), now)
    assert not is_future(date(2026, 1, 1), time(10, 0), now)


def test_maximum_days_ahead_rule() -> None:
    now = datetime(2026, 1, 1, 15, 0, tzinfo=UTC)

    assert is_within_max_days_ahead(date(2026, 1, 11), max_days=10, now=now)
    assert not is_within_max_days_ahead(date(2026, 1, 12), max_days=10, now=now)


def test_minimum_notice_rule_includes_exact_boundary() -> None:
    now = datetime(2026, 1, 1, 15, 0, tzinfo=UTC)

    assert has_minimum_notice(date(2026, 1, 2), time(10, 0), minimum_hours=24, now=now)
    assert not has_minimum_notice(date(2026, 1, 2), time(9, 59), minimum_hours=24, now=now)
