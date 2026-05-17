"""Load exported metric CSVs for report generation and dashboards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from dspace_reporting.export import get_scoped_export_dir, get_source_export_root


def available_months(
    project_root: Path,
    config: dict[str, Any],
    source: str,
    scope: str = "monthly",
) -> list[str]:
    root = get_source_export_root(project_root, config, source) / scope
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def metric_path(
    project_root: Path,
    config: dict[str, Any],
    source: str,
    scope: str,
    reference_month: str,
    filename: str,
) -> Path:
    return (
        get_scoped_export_dir(
            project_root=project_root,
            config=config,
            source=source,
            scope=scope,
            reference_month=reference_month,
        )
        / filename
    )


def load_metric_csv(
    project_root: Path,
    config: dict[str, Any],
    source: str,
    scope: str,
    reference_month: str,
    filename: str,
) -> pd.DataFrame:
    path = metric_path(
        project_root=project_root,
        config=config,
        source=source,
        scope=scope,
        reference_month=reference_month,
        filename=filename,
    )
    return pd.read_csv(path)
