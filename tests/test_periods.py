from datetime import date

from dspace_reporting.periods import resolve_months


def test_year_start_runs_from_january_to_previous_month():
    assert resolve_months("2026", None, today=date(2026, 5, 11)) == [
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]


def test_explicit_month_range_is_inclusive():
    assert resolve_months("2025-11", "2026-02", today=date(2026, 5, 11)) == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


def test_current_month_is_excluded_when_end_is_omitted():
    assert resolve_months("2026-04", None, today=date(2026, 5, 11)) == ["2026-04"]


def test_future_start_defaults_to_current_year():
    assert resolve_months("2027", None, today=date(2026, 5, 11)) == [
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]

