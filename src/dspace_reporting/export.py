"""Export path helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


VALID_EXPORT_SCOPES = {"monthly", "always"}


def get_exports_root(project_root: Path, config: dict[str, Any]) -> Path:
    return project_root / config.get("paths", {}).get("exports_root", "exports")


def get_source_export_root(
    project_root: Path,
    config: dict[str, Any],
    source: str,
) -> Path:
    return get_exports_root(project_root, config) / source


def get_scoped_export_dir(
    project_root: Path,
    config: dict[str, Any],
    source: str,
    scope: str,
    reference_month: str,
) -> Path:
    if scope not in VALID_EXPORT_SCOPES:
        raise ValueError(
            f"Invalid export scope {scope!r}. Use one of: "
            + ", ".join(sorted(VALID_EXPORT_SCOPES))
        )

    export_root = get_source_export_root(project_root, config, source) / scope
    create_month_subfolders = config.get("run", {}).get("create_month_subfolders", True)
    if create_month_subfolders:
        return export_root / reference_month
    return export_root


def get_month_export_dir(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
    source: str = "db",
) -> Path:
    return get_scoped_export_dir(project_root, config, source, "monthly", reference_month)


def get_always_export_dir(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
    source: str = "db",
) -> Path:
    return get_scoped_export_dir(project_root, config, source, "always", reference_month)


def get_snapshot_export_dir(
    project_root: Path,
    config: dict[str, Any],
    snapshot_date: str,
    source: str = "db",
) -> Path:
    return get_source_export_root(project_root, config, source) / "snapshots" / snapshot_date
