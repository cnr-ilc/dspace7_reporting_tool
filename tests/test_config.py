from datetime import date

from dspace_reporting.config import get_run_months, normalize_config


def test_normalize_config_resolves_current_reference_month():
    config = {"run": {"mode": "single", "reference_month": "current"}}

    normalize_config(config, today=date(2026, 5, 12))

    assert config["run"]["reference_month"] == "2026-05"


def test_single_mode_current_reference_month_uses_launch_month():
    config = normalize_config(
        {"run": {"mode": "single", "reference_month": "today"}},
        today=date(2026, 5, 12),
    )

    assert get_run_months(config) == ["2026-05"]


def test_normalize_config_resolves_current_always_reference_month():
    config = {"run": {"always_reference_month": "current"}}

    normalize_config(config, today=date(2026, 5, 12))

    assert config["run"]["always_reference_month"] == "2026-05"
