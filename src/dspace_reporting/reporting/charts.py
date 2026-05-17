"""Chart builders for static reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_no_data_chart(title: str, output_path: Path, message: str = "No data available for this month") -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
    axis.set_axis_off()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_monthly_overview_chart(history: pd.DataFrame, output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    figure, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    plots = (
        ("items_uploaded", "New items"),
        ("visits", "Visits"),
        ("item_views", "Item views"),
        ("downloads", "Downloads"),
    )

    for axis, (column, title) in zip(axes.ravel(), plots):
        axis.plot(history["reference_month"], history[column], marker="o")
        axis.set_title(title)
        axis.grid(alpha=0.25)
        axis.tick_params(axis="x", rotation=45)

    figure.suptitle("Monthly overview")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_top_collections_chart(
    uploads_by_collection: pd.DataFrame,
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if uploads_by_collection.empty or "total_items" not in uploads_by_collection.columns:
        save_no_data_chart("Top collections by new items", output_path)
        return

    data = uploads_by_collection.nlargest(10, "total_items").sort_values("total_items")
    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.barh(data["collection_name"], data["total_items"])
    axis.set_title("Top collections by new items")
    axis.set_xlabel("Items uploaded")
    axis.grid(axis="x", alpha=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_visits_by_country_chart(
    visits_by_country: pd.DataFrame,
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if visits_by_country.empty:
        save_no_data_chart("Top countries by visits", output_path)
        return

    if "visits_count" in visits_by_country.columns:
        value_column = "visits_count"
    elif "nb_visits" in visits_by_country.columns:
        value_column = "nb_visits"
    else:
        raise ValueError(
            "Could not find a visits count column in visits_by_country data."
        )
    label_column = visits_by_country.columns[0]
    data = visits_by_country.nlargest(10, value_column).sort_values(value_column)
    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.barh(data[label_column], data[value_column])
    axis.set_title("Top countries by visits")
    axis.set_xlabel("Visits")
    axis.grid(axis="x", alpha=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_page_typology_chart(
    page_typology: pd.DataFrame,
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if page_typology.empty or "pageviews_count" not in page_typology.columns:
        save_no_data_chart("Pageviews by DSpace section", output_path)
        return

    data = page_typology.sort_values("pageviews_count")
    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.barh(data["page_typology"], data["pageviews_count"])
    axis.set_title("Pageviews by DSpace section")
    axis.set_xlabel("Pageviews")
    axis.grid(axis="x", alpha=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_item_publication_status_chart(
    status_counts: dict[str, int],
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    labels = ["Pubblics", "Not pubblics", "Withdrawn", "Not archived"]
    values = [
        status_counts["public_items"],
        status_counts["not_publicly_visible_items"],
        status_counts["withdrawn_items"],
        status_counts["not_archived_items"],
    ]
    colors = ["#0f766e", "#f59e0b", "#dc2626", "#64748b"]

    figure, axis = plt.subplots(figsize=(8, 6), constrained_layout=True)
    axis.pie(
        values,
        labels=labels,
        autopct=lambda pct: f"{pct:.1f}%" if pct else "",
        startangle=90,
        colors=colors,
        wedgeprops={"width": 0.45, "edgecolor": "white"},
    )
    axis.set_title("Publication status of items")
    axis.text(
        0,
        0,
        f"{sum(values)}\nitems",
        ha="center",
        va="center",
        fontsize=16,
        fontweight="bold",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_horizontal_bar_chart(
    data: pd.DataFrame,
    *,
    label_column: str,
    value_column: str,
    title: str,
    xlabel: str,
    output_path: Path,
    limit: int | None = 15,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if data.empty or label_column not in data.columns or value_column not in data.columns:
        save_no_data_chart(title, output_path)
        return

    chart_data = data.copy()
    chart_data[label_column] = chart_data[label_column].fillna("[n.d.]").astype(str)
    chart_data = chart_data.sort_values(value_column, ascending=False)
    if limit is not None:
        chart_data = chart_data.head(limit)
    chart_data = chart_data.sort_values(value_column)

    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.barh(chart_data[label_column], chart_data[value_column], color="#0f766e")
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.grid(axis="x", alpha=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_bar_chart(
    data: pd.DataFrame,
    *,
    label_column: str,
    value_column: str,
    title: str,
    ylabel: str,
    output_path: Path,
    limit: int | None = 15,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if data.empty or label_column not in data.columns or value_column not in data.columns:
        save_no_data_chart(title, output_path)
        return

    chart_data = data.copy()
    chart_data[label_column] = chart_data[label_column].fillna("[n.d.]").astype(str)
    chart_data = chart_data.sort_values(value_column, ascending=False)
    if limit is not None:
        chart_data = chart_data.head(limit)

    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.bar(chart_data[label_column], chart_data[value_column], color="#0f766e")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.25)
    axis.tick_params(axis="x", rotation=30)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_stacked_bar_chart(
    data: pd.DataFrame,
    *,
    label_column: str,
    stack_column: str,
    value_column: str,
    title: str,
    ylabel: str,
    output_path: Path,
    limit: int | None = 10,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if (
        data.empty
        or label_column not in data.columns
        or stack_column not in data.columns
        or value_column not in data.columns
    ):
        save_no_data_chart(title, output_path)
        return

    grouped = (
        data.groupby([label_column, stack_column], dropna=False)[value_column]
        .sum()
        .unstack(fill_value=0)
    )
    totals = grouped.sum(axis=1).sort_values(ascending=False)
    if limit is not None:
        totals = totals.head(limit)
    grouped = grouped.loc[totals.index]

    figure, axis = plt.subplots(figsize=(11, 6), constrained_layout=True)
    bottom = None
    colors = ["#0f766e", "#f59e0b", "#64748b", "#dc2626"]
    for index, column in enumerate(grouped.columns):
        axis.bar(
            grouped.index.astype(str),
            grouped[column],
            bottom=bottom,
            label=str(column),
            color=colors[index % len(colors)],
        )
        bottom = grouped[column] if bottom is None else bottom + grouped[column]
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.25)
    axis.tick_params(axis="x", rotation=30)
    axis.legend()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def save_line_chart(
    data: pd.DataFrame,
    *,
    x_column: str,
    y_column: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "matplotlib is required to generate report figures. "
            "Install project dependencies before building reports."
        ) from exc

    if data.empty or x_column not in data.columns or y_column not in data.columns:
        save_no_data_chart(title, output_path)
        return

    figure, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    axis.plot(data[x_column], data[y_column], marker="o", color="#0f766e")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.25)
    axis.tick_params(axis="x", rotation=30)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
