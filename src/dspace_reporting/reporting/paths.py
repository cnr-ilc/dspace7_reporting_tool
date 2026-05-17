"""Path helpers for generated reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_reports_root(project_root: Path, config: dict[str, Any]) -> Path:
    return project_root / config.get("paths", {}).get("reports_root", "reports")


def get_month_report_dir(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> Path:
    return get_reports_root(project_root, config) / "monthly" / reference_month


def get_month_figures_dir(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> Path:
    return get_month_report_dir(project_root, config, reference_month) / "figures"


def get_always_report_dir(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> Path:
    return get_reports_root(project_root, config) / "always" / reference_month
