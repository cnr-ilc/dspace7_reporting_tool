from pathlib import Path

import pytest

from dspace_reporting.export import (
    get_always_export_dir,
    get_month_export_dir,
    get_scoped_export_dir,
    get_source_export_root,
)


def test_source_export_root_uses_source_folder():
    config = {"paths": {"exports_root": "exports"}}

    assert get_source_export_root(Path("/project"), config, "solr") == Path(
        "/project/exports/solr"
    )


def test_scoped_export_dir_uses_source_scope_and_month():
    config = {
        "paths": {"exports_root": "exports"},
        "run": {"create_month_subfolders": True},
    }

    assert get_scoped_export_dir(Path("/project"), config, "db", "monthly", "2026-04") == Path(
        "/project/exports/db/monthly/2026-04"
    )
    assert get_scoped_export_dir(Path("/project"), config, "matomo", "always", "2026-04") == Path(
        "/project/exports/matomo/always/2026-04"
    )


def test_month_subfolder_can_be_disabled():
    config = {
        "paths": {"exports_root": "exports"},
        "run": {"create_month_subfolders": False},
    }

    assert get_month_export_dir(Path("/project"), config, "2026-04", source="db") == Path(
        "/project/exports/db/monthly"
    )
    assert get_always_export_dir(Path("/project"), config, "2026-04", source="db") == Path(
        "/project/exports/db/always"
    )


def test_invalid_scope_is_rejected():
    config = {"paths": {"exports_root": "exports"}}

    with pytest.raises(ValueError, match="Invalid export scope"):
        get_scoped_export_dir(Path("/project"), config, "db", "weekly", "2026-04")
