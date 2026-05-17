"""Configuration loading and normalization."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
import os

import yaml

from .periods import resolve_months


DEFAULT_CONFIG_PATH = Path("config/settings.local.yaml")
CONFIG_ENV_VAR = "DSPACE_REPORTING_CONFIG"
CURRENT_MONTH_KEYWORDS = {"current", "today"}


def current_month_label(today: date | None = None) -> str:
    value = today or date.today()
    return value.strftime("%Y-%m")


def resolve_month_keyword(value: Any, today: date | None = None) -> Any:
    if isinstance(value, str) and value.strip().lower() in CURRENT_MONTH_KEYWORDS:
        return current_month_label(today)
    return value


def normalize_config(config: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    run_config = config.setdefault("run", {})
    for key in ("reference_month", "always_reference_month"):
        if key in run_config:
            run_config[key] = resolve_month_keyword(run_config[key], today)
    return config


def load_config(config_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = Path(config_path or os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    return normalize_config(config)


def save_config(config: dict[str, Any], config_path: str | os.PathLike[str]) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False, allow_unicode=False)


def get_run_months(config: dict[str, Any]) -> list[str]:
    run_config = config.get("run", {})
    if run_config.get("mode") in (None, "single") and run_config.get("reference_month"):
        return [run_config["reference_month"]]

    start = run_config.get("start")
    end = run_config.get("end")
    if start is None and run_config.get("reference_month"):
        start = run_config["reference_month"]

    return resolve_months(
        start=start,
        end=end,
        future_start_policy=run_config.get("future_start_policy", "current_year"),
    )


def config_for_reference_month(
    base_config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    config = deepcopy(base_config)
    run_config = config.setdefault("run", {})
    run_config["mode"] = "single"
    run_config["reference_month"] = reference_month
    return config
