import json
from datetime import date

from dspace_reporting.runners.run_notebook_periods import (
    apply_output_mode,
    extract_export_filenames,
    extract_export_source,
    get_export_status,
    get_always_reference_month,
    has_scope_tags,
    MONTHLY_TAG,
    resolve_notebook_paths,
    resolve_requested_months,
    validate_exports_do_not_exist,
)
from dspace_reporting.config import config_for_reference_month


def test_get_always_reference_month_prefers_explicit_value():
    config = {
        "run": {
            "reference_month": "2026-04",
            "always_reference_month": "2026-05",
        }
    }

    assert get_always_reference_month(config) == "2026-05"


def test_get_always_reference_month_falls_back_to_reference_month():
    config = {"run": {"reference_month": "2026-04"}}

    assert get_always_reference_month(config) == "2026-04"


def test_get_always_reference_month_falls_back_to_current_month(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 11)

    monkeypatch.setattr(
        "dspace_reporting.config.date",
        FixedDate,
    )

    assert get_always_reference_month({"run": {}}) == "2026-05"


def test_get_always_reference_month_accepts_current_keyword(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 11)

    monkeypatch.setattr(
        "dspace_reporting.config.date",
        FixedDate,
    )

    assert (
        get_always_reference_month({"run": {"always_reference_month": "current"}})
        == "2026-05"
    )


def test_has_scope_tags_detects_monthly_or_always_tags(tmp_path):
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {"metadata": {"tags": []}},
                    {"metadata": {"tags": ["monthly"]}},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert has_scope_tags(notebook_path)


def test_resolve_notebook_paths_uses_existing_default_notebooks(tmp_path):
    notebooks_dir = tmp_path / "notebooks"
    notebooks_dir.mkdir()
    (notebooks_dir / "01_db_metrics.ipynb").write_text("{}", encoding="utf-8")
    (notebooks_dir / "02_solr_metrics.ipynb").write_text("{}", encoding="utf-8")
    (notebooks_dir / "03_matomo_metrics.ipynb").write_text("{}", encoding="utf-8")

    paths = resolve_notebook_paths(tmp_path, None)

    assert [path.name for path in paths] == [
        "01_db_metrics.ipynb",
        "02_solr_metrics.ipynb",
        "03_matomo_metrics.ipynb",
    ]


def test_resolve_notebook_paths_uses_explicit_notebook_args(tmp_path):
    paths = resolve_notebook_paths(tmp_path, ["notebooks/custom.ipynb"])

    assert paths == [tmp_path / "notebooks" / "custom.ipynb"]


def test_resolve_requested_months_prefers_explicit_cli_months():
    config = {"run": {"reference_month": "2026-04"}}

    assert resolve_requested_months(config, ["2026-05"]) == ["2026-05"]


def test_apply_output_mode_disables_exports_for_display_only():
    config = {"run": {}}

    apply_output_mode(config, display_only=True)

    assert config["run"]["export_outputs"] is False


def test_apply_output_mode_keeps_exports_enabled_by_default():
    config = {"run": {}}

    apply_output_mode(config, display_only=False)

    assert config["run"]["export_outputs"] is True


def test_extract_export_metadata_from_notebook(tmp_path):
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {"tags": []},
                        "source": ['EXPORT_SOURCE = "solr"\n'],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["monthly"]},
                        "source": [
                            'output_path = export_path("solr_monthly.csv")\n',
                        ],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["always"]},
                        "source": [
                            'output_path = export_path("solr_always.csv")\n',
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert extract_export_source(notebook_path) == "solr"
    assert extract_export_filenames(notebook_path, "monthly") == {"solr_monthly.csv"}
    assert extract_export_filenames(notebook_path, "always") == {"solr_always.csv"}


def test_validate_exports_do_not_exist_blocks_existing_exports(tmp_path):
    project_root = tmp_path
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {"tags": []},
                        "source": ['EXPORT_SOURCE = "db"\n'],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["monthly"]},
                        "source": ['output_path = export_path("metric.csv")\n'],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    existing_export = tmp_path / "exports" / "db" / "monthly" / "2026-04" / "metric.csv"
    existing_export.parent.mkdir(parents=True)
    existing_export.write_text("already here\n", encoding="utf-8")

    config = {
        "paths": {"exports_root": "exports"},
        "run": {
            "reference_month": "2026-04",
            "export_outputs": True,
            "overwrite_exports": False,
            "create_month_subfolders": True,
        },
    }

    assert not validate_exports_do_not_exist(
        project_root=project_root,
        base_config=config,
        notebook_path=notebook_path,
        months=["2026-04"],
        use_scope_tags=True,
        display_only=False,
    )


def test_validate_exports_do_not_exist_allows_overwrite(tmp_path):
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["monthly"]},
                        "source": ['output_path = export_path("metric.csv")\n'],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    config = {"run": {"export_outputs": True, "overwrite_exports": True}}

    assert validate_exports_do_not_exist(
        project_root=tmp_path,
        base_config=config,
        notebook_path=notebook_path,
        months=["2026-04"],
        use_scope_tags=True,
        display_only=False,
    )


def test_monthly_existing_exports_are_skipped_and_missing_months_run(tmp_path):
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {"tags": []},
                        "source": ['EXPORT_SOURCE = "db"\n'],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["monthly"]},
                        "source": ['output_path = export_path("metric.csv")\n'],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    for month in ["2025-09", "2025-10", "2025-12"]:
        existing_export = tmp_path / "exports" / "db" / "monthly" / month / "metric.csv"
        existing_export.parent.mkdir(parents=True)
        existing_export.write_text("already here\n", encoding="utf-8")

    config = {
        "paths": {"exports_root": "exports"},
        "run": {"create_month_subfolders": True},
    }
    source = extract_export_source(notebook_path)
    runnable_months = []
    skipped_months = []

    for month in ["2025-09", "2025-10", "2025-11", "2025-12"]:
        status, _, _ = get_export_status(
            project_root=tmp_path,
            config=config_for_reference_month(config, month),
            notebook_path=notebook_path,
            source=source,
            scope=MONTHLY_TAG,
            reference_month=month,
        )
        if status == "complete":
            skipped_months.append(month)
        elif status == "missing":
            runnable_months.append(month)

    assert skipped_months == ["2025-09", "2025-10", "2025-12"]
    assert runnable_months == ["2025-11"]


def test_partial_month_exports_are_rejected(tmp_path):
    notebook_path = tmp_path / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "metadata": {"tags": []},
                        "source": ['EXPORT_SOURCE = "db"\n'],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {"tags": ["monthly"]},
                        "source": [
                            'export_path("metric_a.csv")\n',
                            'export_path("metric_b.csv")\n',
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    existing_export = tmp_path / "exports" / "db" / "monthly" / "2025-11" / "metric_a.csv"
    existing_export.parent.mkdir(parents=True)
    existing_export.write_text("already here\n", encoding="utf-8")

    config = {
        "paths": {"exports_root": "exports"},
        "run": {"create_month_subfolders": True},
    }

    status, existing_exports, missing_exports = get_export_status(
        project_root=tmp_path,
        config=config_for_reference_month(config, "2025-11"),
        notebook_path=notebook_path,
        source=extract_export_source(notebook_path),
        scope=MONTHLY_TAG,
        reference_month="2025-11",
    )

    assert status == "partial"
    assert len(existing_exports) == 1
    assert len(missing_exports) == 1
