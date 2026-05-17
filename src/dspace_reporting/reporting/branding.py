"""Branding helpers for generated reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any


SUPPORTED_LOGO_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg"}


def get_branding_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("reporting", {})


def resolve_logo_path(project_root: Path, config: dict[str, Any]) -> Path | None:
    logo_path = get_branding_config(config).get("logo_path")
    if not logo_path:
        return None

    path = project_root / str(logo_path)
    if path.suffix.lower() not in SUPPORTED_LOGO_SUFFIXES:
        raise ValueError(
            "Unsupported logo format. Use one of: "
            + ", ".join(sorted(SUPPORTED_LOGO_SUFFIXES))
        )
    return path

