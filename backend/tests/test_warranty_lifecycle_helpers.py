from datetime import datetime, timezone

import pytest

from app.modules.warranty.service import add_months


def test_add_months_preserves_time_and_timezone():
    value = datetime(2026, 10, 20, 15, 30, 45, tzinfo=timezone.utc)
    assert add_months(value, 6) == datetime(2027, 4, 20, 15, 30, 45, tzinfo=timezone.utc)


def test_add_months_clamps_end_of_month():
    value = datetime(2027, 1, 31, 9, 0, tzinfo=timezone.utc)
    assert add_months(value, 1) == datetime(2027, 2, 28, 9, 0, tzinfo=timezone.utc)


def test_add_months_handles_leap_year():
    value = datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc)
    assert add_months(value, 12) == datetime(2029, 2, 28, 12, 0, tzinfo=timezone.utc)


def test_add_months_rejects_negative_duration():
    with pytest.raises(ValueError):
        add_months(datetime.now(timezone.utc), -1)
