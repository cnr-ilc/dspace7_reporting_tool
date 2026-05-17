"""Execute reporting notebooks for configured monthly and always metrics."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from dspace_reporting.config import (
    CONFIG_ENV_VAR,
    config_for_reference_month,
    current_month_label,
    get_run_months,
    load_config,
    resolve_month_keyword,
    save_config,
)
from dspace_reporting.export import get_scoped_export_dir


MONTHLY_TAG = "monthly"
ALWAYS_TAG = "always"
EXPORT_PATH_RE = re.compile(r"""export_path\(\s*["']([^"']+\.csv)["']\s*\)""")
EXPORT_SOURCE_RE = re.compile(r"""EXPORT_SOURCE\s*=\s*["']([^"']+)["']""")
DEFAULT_NOTEBOOKS = (
    "notebooks/01_db_metrics.ipynb",
    "notebooks/02_solr_metrics.ipynb",
    "notebooks/03_matomo_metrics.ipynb",
)


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/settings.local.yaml",
        help="Path to the base YAML configuration.",
    )
    parser.add_argument(
        "--notebook",
        nargs="*",
        default=None,
        help=(
            "Notebook(s) to execute for each reference month. "
            "If omitted, all known reporting notebooks present in notebooks/ are used."
        ),
    )
    parser.add_argument(
        "--month",
        nargs="*",
        default=None,
        help=(
            "Optional reference month(s) to execute, for example --month 2026-05. "
            "If omitted, months are resolved from the run configuration."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the months that would be executed without running the notebook.",
    )
    parser.add_argument(
        "--display-only",
        action="store_true",
        help="Execute the notebook and show outputs without writing CSV exports.",
    )
    return parser.parse_args()


def resolve_notebook_paths(project_root: Path, notebook_args: list[str] | None) -> list[Path]:
    if notebook_args is not None:
        return [project_root / notebook for notebook in notebook_args]

    return [
        project_root / notebook
        for notebook in DEFAULT_NOTEBOOKS
        if (project_root / notebook).exists()
    ]


def resolve_requested_months(config: dict, month_args: list[str] | None) -> list[str]:
    """Return explicit CLI months when provided, otherwise use config resolution."""
    return month_args if month_args else get_run_months(config)


def get_always_reference_month(config: dict) -> str:
    run_config = config.get("run", {})
    configured_month = run_config.get("always_reference_month") or run_config.get(
        "reference_month"
    )
    if configured_month:
        return str(resolve_month_keyword(configured_month))
    return current_month_label()


def has_scope_tags(notebook_path: Path) -> bool:
    with notebook_path.open("r", encoding="utf-8") as handle:
        notebook = json.load(handle)

    for cell in notebook.get("cells", []):
        tags = set(cell.get("metadata", {}).get("tags", []))
        if MONTHLY_TAG in tags or ALWAYS_TAG in tags:
            return True
    return False


def get_notebook_cells(notebook_path: Path) -> list[dict]:
    with notebook_path.open("r", encoding="utf-8") as handle:
        notebook = json.load(handle)
    return notebook.get("cells", [])


def extract_export_source(notebook_path: Path, default: str = "db") -> str:
    for cell in get_notebook_cells(notebook_path):
        source = normalize_notebook_text(cell.get("source"))
        match = EXPORT_SOURCE_RE.search(source)
        if match:
            return match.group(1)
    return default


def extract_export_filenames(notebook_path: Path, scope: str | None = None) -> set[str]:
    filenames: set[str] = set()
    for cell in get_notebook_cells(notebook_path):
        tags = set(cell.get("metadata", {}).get("tags", []))
        if scope and scope not in tags:
            continue
        source = normalize_notebook_text(cell.get("source"))
        filenames.update(EXPORT_PATH_RE.findall(source))
    return filenames


def get_expected_export_paths(
    project_root: Path,
    config: dict,
    notebook_path: Path,
    source: str,
    scope: str | None,
    reference_month: str,
) -> list[Path]:
    lookup_scope = scope or MONTHLY_TAG
    export_dir = get_scoped_export_dir(
        project_root=project_root,
        config=config,
        source=source,
        scope=lookup_scope,
        reference_month=reference_month,
    )
    return sorted(
        export_dir / filename
        for filename in extract_export_filenames(notebook_path, scope)
    )


def find_existing_exports(
    project_root: Path,
    config: dict,
    notebook_path: Path,
    source: str,
    scope: str | None,
    reference_month: str,
) -> list[Path]:
    return sorted(
        path
        for path in get_expected_export_paths(
            project_root, config, notebook_path, source, scope, reference_month
        )
        if path.exists()
    )


def get_export_status(
    project_root: Path,
    config: dict,
    notebook_path: Path,
    source: str,
    scope: str | None = None,
    reference_month: str = "",
) -> tuple[str, list[Path], list[Path]]:
    expected_exports = get_expected_export_paths(
        project_root, config, notebook_path, source, scope, reference_month
    )
    existing_exports = sorted(path for path in expected_exports if path.exists())
    missing_exports = sorted(path for path in expected_exports if not path.exists())

    if not existing_exports:
        return "missing", existing_exports, missing_exports
    if not missing_exports:
        return "complete", existing_exports, missing_exports
    return "partial", existing_exports, missing_exports


def format_export_context(scope: str | None, reference_month: str | None) -> str:
    context = ""
    if scope and reference_month:
        context = f" for {scope} {reference_month}"
    return context


def print_existing_exports_error(
    existing_exports: list[Path],
    scope: str | None = None,
    reference_month: str | None = None,
) -> None:
    context = format_export_context(scope, reference_month)
    print(
        f"Existing CSV exports found{context} and overwrite_exports=false. "
        "The notebook was not executed.",
        file=sys.stderr,
    )
    for path in existing_exports[:20]:
        print(f"  - {path}", file=sys.stderr)
    if len(existing_exports) > 20:
        print(f"  ... and {len(existing_exports) - 20} more", file=sys.stderr)
    print(
        "Set run.overwrite_exports=true or remove/move the existing exports "
        "before rerunning.",
        file=sys.stderr,
    )


def print_partial_exports_error(
    existing_exports: list[Path],
    missing_exports: list[Path],
    scope: str | None,
    reference_month: str,
) -> None:
    context = format_export_context(scope, reference_month)
    print(
        f"Partial CSV exports found{context} and overwrite_exports=false. "
        "The notebook was not executed.",
        file=sys.stderr,
    )
    print("Existing exports:", file=sys.stderr)
    for path in existing_exports[:20]:
        print(f"  - {path}", file=sys.stderr)
    if len(existing_exports) > 20:
        print(f"  ... and {len(existing_exports) - 20} more", file=sys.stderr)
    print("Missing exports:", file=sys.stderr)
    for path in missing_exports[:20]:
        print(f"  - {path}", file=sys.stderr)
    if len(missing_exports) > 20:
        print(f"  ... and {len(missing_exports) - 20} more", file=sys.stderr)
    print(
        "Remove/move the existing partial exports or set "
        "run.overwrite_exports=true before rerunning.",
        file=sys.stderr,
    )


def print_complete_exports_skip(
    existing_exports: list[Path],
    source: str,
    scope: str | None,
    reference_month: str,
) -> None:
    context = format_export_context(scope, reference_month)
    print(
        f"Skipping {source} exports{context}: all {len(existing_exports)} expected CSV exports "
        "already exist."
    )


def print_missing_exports_generation(
    missing_exports: list[Path],
    source: str,
    scope: str | None,
    reference_month: str,
) -> None:
    context = format_export_context(scope, reference_month)
    print(
        f"Generating {source} exports{context}: "
        f"{len(missing_exports)} expected CSV exports are missing."
    )
    if missing_exports:
        print(f"Export directory: {missing_exports[0].parent}")


def should_check_existing_exports(config: dict, display_only: bool) -> bool:
    run_config = config.get("run", {})
    if display_only or not run_config.get("export_outputs", True):
        return False
    return not run_config.get("overwrite_exports", False)


def validate_exports_do_not_exist(
    project_root: Path,
    base_config: dict,
    notebook_path: Path,
    months: list[str],
    use_scope_tags: bool,
    display_only: bool,
) -> bool:
    if not should_check_existing_exports(base_config, display_only):
        return True

    source = extract_export_source(notebook_path)
    existing_exports: list[Path] = []

    if use_scope_tags:
        for reference_month in months:
            month_config = config_for_reference_month(base_config, reference_month)
            existing_exports.extend(
                find_existing_exports(
                    project_root,
                    month_config,
                    notebook_path,
                    source,
                    MONTHLY_TAG,
                    reference_month,
                )
            )

        always_reference_month = get_always_reference_month(base_config)
        always_config = config_for_reference_month(base_config, always_reference_month)
        existing_exports.extend(
            find_existing_exports(
                project_root,
                always_config,
                notebook_path,
                source,
                ALWAYS_TAG,
                always_reference_month,
            )
        )
    else:
        for reference_month in months:
            month_config = config_for_reference_month(base_config, reference_month)
            existing_exports.extend(
                find_existing_exports(
                    project_root,
                    month_config,
                    notebook_path,
                    source,
                    None,
                    reference_month,
                )
            )

    if existing_exports:
        print_existing_exports_error(existing_exports)
        return False
    return True


def should_execute_period(
    project_root: Path,
    config: dict,
    notebook_path: Path,
    source: str,
    scope: str | None,
    reference_month: str,
    check_existing_exports: bool,
) -> bool:
    if not check_existing_exports:
        return True

    status, existing_exports, missing_exports = get_export_status(
        project_root=project_root,
        config=config,
        notebook_path=notebook_path,
        source=source,
        scope=scope,
        reference_month=reference_month,
    )
    if status == "missing":
        print_missing_exports_generation(
            missing_exports,
            source,
            scope,
            reference_month,
        )
        return True
    if status == "complete":
        print_complete_exports_skip(existing_exports, source, scope, reference_month)
        return False

    print_partial_exports_error(
        existing_exports,
        missing_exports,
        scope,
        reference_month,
    )
    raise RuntimeError("Partial CSV exports found")


def apply_output_mode(config: dict, display_only: bool) -> dict:
    run_config = config.setdefault("run", {})
    run_config["export_outputs"] = not display_only
    return config


def normalize_notebook_text(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "".join(value)
    return value


def markdown_heading(source: str) -> tuple[int, str] | None:
    for line in source.splitlines():
        text = line.strip()
        if not text.startswith("#"):
            continue
        marker = text.split(maxsplit=1)[0]
        level = len(marker)
        title = text[level:].strip().replace("**", "").strip()
        if title:
            return level, title
    return None


def html_to_text(value: str | list[str]) -> str:
    parser = HTMLTextExtractor()
    parser.feed(normalize_notebook_text(value))
    return parser.get_text()


def output_to_text(output: dict) -> str:
    output_type = output.get("output_type")
    if output_type == "stream":
        return normalize_notebook_text(output.get("text")).rstrip()
    if output_type == "error":
        traceback = normalize_notebook_text(output.get("traceback"))
        if traceback:
            return traceback.rstrip()
        return f"{output.get('ename', 'Error')}: {output.get('evalue', '')}".rstrip()

    data = output.get("data", {})
    if "text/plain" in data:
        return normalize_notebook_text(data["text/plain"]).rstrip()
    if "text/markdown" in data:
        return normalize_notebook_text(data["text/markdown"]).rstrip()
    if "text/html" in data:
        return html_to_text(data["text/html"]).rstrip()
    return ""


def clean_display_output(text: str) -> str:
    skipped_prefixes = (
        "Display-only mode, export skipped:",
        "File saved to:",
        "File saved in:",
        "File salvato in:",
        "File saved:",
    )
    lines = [
        line
        for line in text.splitlines()
        if not line.strip().startswith(skipped_prefixes)
    ]
    return "\n".join(lines).strip()


def print_display_only_outputs(notebook_path: Path, label: str) -> None:
    with notebook_path.open("r", encoding="utf-8") as handle:
        notebook = json.load(handle)

    print()
    print("=" * 80)
    print(f"Display output: {label}")
    print("=" * 80)

    heading_stack: list[tuple[int, str]] = []
    printed_any = False

    for cell in notebook.get("cells", []):
        cell_type = cell.get("cell_type")
        source = normalize_notebook_text(cell.get("source"))

        if cell_type == "markdown":
            heading = markdown_heading(source)
            if heading:
                level, title = heading
                heading_stack = [
                    existing
                    for existing in heading_stack
                    if existing[0] < level
                ]
                heading_stack.append((level, title))
            continue

        tags = set(cell.get("metadata", {}).get("tags", []))
        if not ({MONTHLY_TAG, ALWAYS_TAG} & tags):
            continue

        outputs = []
        for output in cell.get("outputs", []):
            text = clean_display_output(output_to_text(output))
            if text:
                outputs.append(text)
        if not outputs:
            continue

        if heading_stack:
            print()
            for _, heading in heading_stack:
                print(f"## {heading}")
        else:
            print()

        print("\n\n".join(outputs))
        printed_any = True

    if not printed_any:
        print("No displayable cell outputs were produced.")
    print()


def execute_notebook(
    notebook_path: Path,
    env: dict[str, str],
    output_dir: Path,
    label: str,
    remove_tags: list[str] | None = None,
    display_outputs: bool = False,
) -> int:
    src_path = notebook_path.parent.parent / "src"
    if src_path.exists():
        pythonpath_parts = [str(src_path)]
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    command = [
        sys.executable,
        "-m",
        "dspace_reporting.runners.nbconvert",
        "--to",
        "notebook",
        "--execute",
        "--output-dir",
        str(output_dir),
        "--output",
        f"{notebook_path.stem}.{label}.ipynb",
    ]

    if remove_tags:
        command.append("--TagRemovePreprocessor.enabled=True")
        for tag in remove_tags:
            command.append(f"--TagRemovePreprocessor.remove_cell_tags={tag}")

    command.append(str(notebook_path.name))

    result = subprocess.run(
        command,
        cwd=str(notebook_path.parent),
        env=env,
        check=False,
    )
    if result.returncode == 0 and display_outputs:
        output_notebook_path = output_dir / f"{notebook_path.stem}.{label}.ipynb"
        print_display_only_outputs(output_notebook_path, label)
    return result.returncode


def process_notebook(
    *,
    project_root: Path,
    base_config: dict,
    months: list[str],
    notebook_path: Path,
    display_only: bool,
    dry_run: bool,
) -> int:
    if not notebook_path.exists():
        print(f"Notebook not found: {notebook_path}", file=sys.stderr)
        return 2

    use_scope_tags = has_scope_tags(notebook_path)
    export_source = extract_export_source(notebook_path)

    print()
    print(f"Notebook: {notebook_path}")
    print(f"Export source: {export_source}")

    if use_scope_tags:
        print(
            "Always metrics reference month: "
            + get_always_reference_month(base_config)
        )
    if dry_run:
        return 0

    check_existing_exports = should_check_existing_exports(base_config, display_only)

    with TemporaryDirectory(prefix="dspace-reporting-") as temp_dir:
        temp_root = Path(temp_dir)
        for reference_month in months:
            month_config = config_for_reference_month(base_config, reference_month)
            try:
                execute_period = should_execute_period(
                    project_root=project_root,
                    config=month_config,
                    notebook_path=notebook_path,
                    source=export_source,
                    scope=MONTHLY_TAG if use_scope_tags else None,
                    reference_month=reference_month,
                    check_existing_exports=check_existing_exports,
                )
            except RuntimeError:
                return 3
            if not execute_period:
                continue

            apply_output_mode(month_config, display_only)
            month_config.setdefault("run", {})["metrics_scope"] = MONTHLY_TAG
            temp_config_path = temp_root / f"settings.{reference_month}.yaml"
            save_config(month_config, temp_config_path)

            env = os.environ.copy()
            env[CONFIG_ENV_VAR] = str(temp_config_path)

            print(
                f"Executing {export_source} monthly metrics in {notebook_path} "
                f"for {reference_month}"
            )
            returncode = execute_notebook(
                notebook_path=notebook_path,
                env=env,
                output_dir=temp_root,
                label=f"monthly.{reference_month}",
                remove_tags=[ALWAYS_TAG] if use_scope_tags else None,
                display_outputs=display_only,
            )
            if returncode != 0:
                return returncode

        if use_scope_tags:
            always_reference_month = get_always_reference_month(base_config)
            always_config = config_for_reference_month(
                base_config, always_reference_month
            )
            try:
                execute_period = should_execute_period(
                    project_root=project_root,
                    config=always_config,
                    notebook_path=notebook_path,
                    source=export_source,
                    scope=ALWAYS_TAG,
                    reference_month=always_reference_month,
                    check_existing_exports=check_existing_exports,
                )
            except RuntimeError:
                return 3
            if not execute_period:
                return 0

            apply_output_mode(always_config, display_only)
            always_config.setdefault("run", {})["metrics_scope"] = ALWAYS_TAG
            temp_config_path = temp_root / f"settings.always.{always_reference_month}.yaml"
            save_config(always_config, temp_config_path)

            env = os.environ.copy()
            env[CONFIG_ENV_VAR] = str(temp_config_path)

            print(
                f"Executing {export_source} always metrics in {notebook_path} "
                f"for {always_reference_month}"
            )
            returncode = execute_notebook(
                notebook_path=notebook_path,
                env=env,
                output_dir=temp_root,
                label=f"always.{always_reference_month}",
                remove_tags=[MONTHLY_TAG],
                display_outputs=display_only,
            )
            if returncode != 0:
                return returncode

    return 0


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()
    base_config = load_config(args.config)
    months = resolve_requested_months(base_config, args.month)
    notebook_paths = resolve_notebook_paths(project_root, args.notebook)

    if not notebook_paths:
        print("No reporting notebooks found.", file=sys.stderr)
        return 2

    missing_notebooks = [path for path in notebook_paths if not path.exists()]
    if missing_notebooks:
        for path in missing_notebooks:
            print(f"Notebook not found: {path}", file=sys.stderr)
        return 2

    if not months:
        print("No complete months to process.")
        return 0

    print("Months to process: " + ", ".join(months))
    if args.display_only:
        print("Display-only mode: CSV exports will not be written.")

    returncodes: list[int] = []
    for notebook_path in notebook_paths:
        returncodes.append(
            process_notebook(
                project_root=project_root,
                base_config=base_config,
                months=months,
                notebook_path=notebook_path,
                display_only=args.display_only,
                dry_run=args.dry_run,
            )
        )

    for returncode in returncodes:
        if returncode != 0:
            return returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
