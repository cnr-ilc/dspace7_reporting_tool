"""Build static monthly reports from exported metric CSVs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import shutil

from dspace_reporting.config import get_run_months, load_config
from dspace_reporting.reporting.branding import resolve_logo_path
from dspace_reporting.reporting.charts import (
    save_bar_chart,
    save_horizontal_bar_chart,
    save_item_publication_status_chart,
    save_monthly_overview_chart,
    save_page_typology_chart,
    save_top_collections_chart,
    save_visits_by_country_chart,
    save_stacked_bar_chart,
    save_line_chart,
)
from dspace_reporting.reporting.datasets import (
    build_item_publication_snapshot_for_month,
    build_historical_repository_usage_snapshot_for_month,
    build_access_referrer_snapshot_for_month,
    build_event_quality_snapshot_for_month,
    build_internal_search_snapshot_for_month,
    build_matomo_web_traffic_snapshot_for_month,
    build_access_geography_snapshot_for_month,
    build_device_technology_snapshot_for_month,
    build_user_group_workflow_snapshot_for_month,
    build_metadata_quality_snapshot_for_month,
    build_oai_solr_exposure_snapshot_for_month,
    build_technical_integrity_snapshot_for_month,
    build_monthly_detail,
    build_latest_quality_snapshot,
    build_monthly_overview_history,
    build_quality_snapshot_for_month,
    build_repository_organization_snapshot_for_month,
    build_repository_snapshot_as_of_month,
    build_repository_snapshot_for_month,
    missing_monthly_overview_exports,
)
from dspace_reporting.reporting.loaders import available_months, load_metric_csv
from dspace_reporting.reporting.paths import (
    get_always_report_dir,
    get_month_figures_dir,
    get_month_report_dir,
)


def collapsible_sections_assets() -> str:
    """Return shared CSS and JS for collapsible report sections."""
    return """
    .report-section {
      margin-top: 2rem;
      border: 1px solid #dbe4ee;
      border-radius: 1rem;
      background: #ffffff;
      overflow: hidden;
    }
    .report-section[open] {
      box-shadow: 0 0.35rem 1rem rgba(15, 23, 42, 0.05);
    }
    .report-section-summary {
      list-style: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.25rem;
      padding: 1.25rem 1.75rem;
      background: #f8fafc;
    }
    .report-section-summary::-webkit-details-marker {
      display: none;
    }
    .report-section-summary::after {
      content: "+";
      color: #0f766e;
      font-size: 1.4rem;
      font-weight: 600;
      line-height: 1;
    }
    .report-section[open] > .report-section-summary::after {
      content: "−";
    }
    .report-section-summary h2 {
      margin: 0;
      font-size: 1.4rem;
    }
    .report-section-body {
      padding: 0 1.75rem 1.75rem;
    }
    .report-section-body > :first-child {
      margin-top: 1.25rem;
    }
    """


def collapsible_sections_script() -> str:
    """Return script that wraps each top-level h2 block in a native details element."""
    return """
  <script>
    document.addEventListener("DOMContentLoaded", () => {
      const shell = document.querySelector(".site-shell");
      if (!shell) return;

      [...shell.querySelectorAll(":scope > h2")].forEach((heading) => {
        const section = document.createElement("details");
        section.className = "report-section";
        section.open = true;

        const summary = document.createElement("summary");
        summary.className = "report-section-summary";
        summary.appendChild(heading.cloneNode(true));

        const body = document.createElement("div");
        body.className = "report-section-body";

        let node = heading.nextSibling;
        while (node && !(node.nodeType === Node.ELEMENT_NODE && node.tagName === "H2")) {
          const next = node.nextSibling;
          body.appendChild(node);
          node = next;
        }

        section.appendChild(summary);
        section.appendChild(body);
        heading.replaceWith(section);
      });
    });
  </script>
"""


def tabbed_sections_assets() -> str:
    """Return CSS for a horizontally scrollable section tab bar."""
    return """
    .report-tabs {
      display: flex;
      gap: 0.75rem;
      overflow-x: auto;
      padding: 0.25rem 0 1rem;
      margin: 1.75rem 0 1rem;
      scrollbar-width: thin;
    }
    .report-tabs .nav-link {
      white-space: nowrap;
      border-radius: 999px;
      color: #0f766e;
      background: #ecfeff;
      border: 1px solid #ccfbf1;
    }
    .report-tabs .nav-link.active {
      color: #ffffff;
      background: #0f766e;
      border-color: #0f766e;
    }
    """


def tabbed_sections_script() -> str:
    """Return script that exposes report sections through scrollable tabs."""
    return """
  <script>
    document.addEventListener("DOMContentLoaded", () => {
      const shell = document.querySelector(".site-shell");
      const sections = [...shell.querySelectorAll(":scope > .report-section")];
      const tabsHost = shell.querySelector("[data-report-tabs]");
      if (!tabsHost || sections.length === 0) return;

      const tabs = document.createElement("nav");
      tabs.className = "report-tabs nav";
      tabs.setAttribute("aria-label", "Sezioni del report");

      sections.forEach((section, index) => {
        const heading = section.querySelector("h2");
        const button = document.createElement("button");
        const sectionId = `report-section-${index + 1}`;
        section.id = sectionId;
        button.type = "button";
        button.className = "nav-link";
        button.textContent = heading ? heading.textContent : `Section ${index + 1}`;
        button.setAttribute("aria-controls", sectionId);
        button.addEventListener("click", () => {
          sections.forEach((candidate, candidateIndex) => {
            const isActive = candidateIndex === index;
            candidate.hidden = !isActive;
            candidate.open = true;
            tabs.children[candidateIndex].classList.toggle("active", isActive);
            tabs.children[candidateIndex].setAttribute("aria-selected", String(isActive));
          });
        });
        tabs.appendChild(button);
      });

      tabsHost.appendChild(tabs);
      tabs.children[0].click();
    });
  </script>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/settings.local.yaml",
        help="Path to the YAML configuration.",
    )
    parser.add_argument(
        "--month",
        nargs="*",
        default=None,
        help=(
            "Optional reference month(s) to build. "
            "If omitted, months are resolved from the run configuration."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the months that would be reported without generating files.",
    )
    parser.add_argument(
        "--overwrite-reports",
        action="store_true",
        help="Regenerate reports even if report.html already exists.",
    )
    return parser.parse_args()


def render_report_html(
    *,
    reference_month: str,
    institution_name: str,
    institution_subtitle: str,
    latest_row: dict[str, object],
    logo_relative_path: str | None,
    home_href: str,
    quality_snapshot: dict[str, object],
    repository_snapshot: dict[str, object],
    repository_organization_snapshot: dict[str, object],
    monthly_oai_snapshot: dict[str, object],
    user_group_workflow_snapshot: dict[str, object],
    detail: dict[str, object],
    previous_month: str | None,
    next_month: str | None,
) -> str:
    logo_html = (
        f'<a href="{home_href}" aria-label="Torna alla home"><img class="logo" src="{logo_relative_path}" alt="{institution_name} logo"></a>'
        if logo_relative_path
        else ""
    )
    previous_link = (
        f'<a class="btn btn-outline-primary" href="../{previous_month}/report.html">&larr; {previous_month}</a>'
        if previous_month
        else '<span class="btn btn-outline-secondary disabled" aria-disabled="true">&larr; Precedente</span>'
    )
    next_link = (
        f'<a class="btn btn-outline-primary" href="../{next_month}/report.html">{next_month} &rarr;</a>'
        if next_month
        else '<span class="btn btn-outline-secondary disabled" aria-disabled="true">Successivo &rarr;</span>'
    )
    def table_html(df, columns, limit=10):
        if any(column not in df.columns for column in columns):
            return "<p>No data available for the selected month.</p>"
        subset = df.loc[:, columns].head(limit).copy()
        return (
            '<div class="detail-table-wrap">'
            + subset.to_html(
                index=False,
                classes="table table-striped table-hover align-middle mb-0",
                border=0,
                escape=False,
            )
            + "</div>"
        )

    acquisition_rows = [
        ("Direct", detail["direct_visits_count"]),
        ("Search engines", detail["search_engines_visits_count"]),
        ("Websites", detail["websites_visits_count"]),
        ("Social network", detail["social_networks_visits_count"]),
        ("Campaigns", detail["campaign_visits_count"]),
    ]
    acquisition_html = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in acquisition_rows
    )
    average_visit_duration_minutes = round(detail["average_visit_duration_seconds"] / 60, 1)
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{institution_name} - Report {reference_month}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ color: #1f2937; background: #f8fafc; }}
    main {{ max-width: 1200px; }}
    .site-shell {{ background: white; }}
    .brand-accent {{ border-bottom: 3px solid #0f766e; }}
    .brand-link {{ color: inherit; text-decoration: none; }}
    .logo {{ max-width: min(240px, 100%); max-height: 90px; object-fit: contain; }}
    h2 {{ color: #0f766e; margin-top: 2.75rem; margin-bottom: 1rem; }}
    h3 {{ margin-top: 2rem; margin-bottom: 1rem; }}
    .subtitle {{ color: #475569; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1.25rem; }}
    .kpi {{ background: #f1f5f9; border: 0; }}
    .kpi .card-body {{ padding: 1.25rem 1.35rem; }}
    .kpi strong {{ display: block; font-size: 1.6rem; }}
    .kpi small {{ display: block; color: #64748b; }}
    figure {{ margin-top: 1.5rem; margin-bottom: 2rem; }}
    figure img {{ max-width: 100%; border: 1px solid #e2e8f0; border-radius: 0.75rem; }}
    figcaption {{ color: #475569; font-size: 0.95rem; margin-top: 8px; }}
    p {{ line-height: 1.6; }}
    .detail-table-wrap {{ max-height: 360px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 0.75rem; margin-top: 0.75rem; margin-bottom: 2rem; }}
    .detail-table-wrap thead th {{ position: sticky; top: 0; background: #f8fafc; z-index: 1; }}
    .two-col {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 2rem; margin-top: 1rem; margin-bottom: 1.5rem; }}
    h3 {{ margin-top: 1.75rem; margin-bottom: 1rem; }}
    {collapsible_sections_assets()}
    {tabbed_sections_assets()}
    @media (max-width: 640px) {{
      .kpis {{ grid-template-columns: 1fr; }}
      .two-col {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main class="container px-3 px-md-4 py-4 py-md-5">
<div class="site-shell shadow-sm rounded-4 p-4 p-md-5">
  <header class="brand-accent d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 pb-4">
    <div>
      <h1><a class="brand-link" href="{home_href}">{institution_name}</a></h1>
      <div class="subtitle">{institution_subtitle} - {reference_month}</div>
    </div>
    {logo_html}
  </header>
  <nav class="d-flex flex-column flex-sm-row justify-content-between align-items-stretch align-items-sm-center gap-2 my-4">
    <div>{previous_link}</div>
    <div><a class="btn btn-primary" href="../../index.html">Report archive</a></div>
    <div>{next_link}</div>
  </nav>
  <div data-report-tabs></div>

  <h2>Monthly summary</h2>
  <p>
    This section provides the opening snapshot for the reference month,
    combining Matomo web traffic, Solr internal searches, content usage and
    repository growth.
  </p>

  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Visits in the reference month</span><strong>{latest_row['visits']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Pageviews in the reference month</span><strong>{latest_row['pageviews']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Actions in the reference month</span><strong>{detail['total_actions_count']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average visit duration</span><strong>{detail['average_visit_duration_seconds']} s</strong><small>{average_visit_duration_minutes} min</small></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bounce rate</span><strong>{detail['bounce_rate']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Actions per visit</span><strong>{detail['actions_per_visit_value']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total searches in the reference month</span><strong>{detail['total_searches_count']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items uploaded in the reference month</span><strong>{latest_row['items_uploaded']}</strong></div></div>
  </div>
  <div class="two-col">
    <div>
      <h3>Top items in the reference month</h3>
      {table_html(detail["top_viewed_items"], ["resource", "views_count"], 5)}
    </div>
    <div>
      <h3>Top downloaded items in the reference month</h3>
      {table_html(detail["top_downloaded_items"], ["resource", "downloads_count"], 5)}
    </div>
  </div>

  <h2>Monthly trend</h2>
  <p>
    The chart shows how the main metrics evolve up to the reference month.
    It helps distinguish the month-specific value from a structural change
    over time.
  </p>
  <figure>
    <img src="figures/monthly_overview.png" alt="Monthly trend of the main metrics">
    <figcaption>New items, visits, item views and downloads by month.</figcaption>
  </figure>

  <h2>Deposit activity in the reference month</h2>
  <p>
    This section describes newly deposited content during the month and the related
    editorial activity, using PostgreSQL metrics dedicated to uploaded items.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average file size for uploaded items</span><strong>{round(float(detail["average_file_size"]["avg_file_size_mb"].iloc[0]), 2)} MB</strong></div></div>
  </div>
  <h3>Uploaded items with bitstream count, size and MIME type</h3>
  {table_html(detail["uploaded_items_with_bitstreams"], ["resource", "bitstreams_count", "total_size_mb", "mime_types"], 20)}
  <div class="two-col">
    <figure>
      <img src="figures/uploads_by_submitter.png" alt="Items uploaded by submitter">
      <figcaption>Items uploaded in the reference month per submitter.</figcaption>
    </figure>
    <figure>
      <img src="figures/uploads_by_collection.png" alt="Items uploaded by collection">
      <figcaption>Items uploaded in the reference month per collection.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/uploads_by_language.png" alt="Items uploaded by language">
      <figcaption>Language distribution of items uploaded in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/most_active_collections.png" alt="Most active collections in the reference month">
      <figcaption>Most active collections in the reference month, considering new items and modifications.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <div>
      <h3>Items uploaded by type and author</h3>
      {table_html(detail["uploaded_items_details"], ["resource", "item_types", "authors"], 20)}
    </div>
    <div>
      <h3>Timeline approvazione workflow</h3>
      {table_html(detail["workflow_approval_timeline"], ["resource", "submitted_at", "first_approval_at", "second_approval_at", "final_approval_at", "made_available_at", "approval_steps_count", "submitted_to_first_approval_hours", "first_to_final_approval_hours", "submitted_to_available_hours"], 20)}
    </div>
  </div>

  <h2>Repository-side usage in the reference month</h2>
  <p>
    This section measures repository-side use of DSpace objects during the
    reference month, mainly through Solr metrics on items, bitstreams,
    collections, communities, licenses and formats.
  </p>
  <div class="two-col">
    <div>
      <h3>Top items in the reference month</h3>
      {table_html(detail["top_viewed_items"], ["resource", "views_count"], 10)}
    </div>
    <div>
      <h3>Top downloaded items in the reference month</h3>
      {table_html(detail["top_downloaded_items"], ["resource", "downloads_count"], 10)}
    </div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_views_by_collection.png" alt="Views by collection in the reference month">
      <figcaption>Views by collection in the reference month. Labels reflect the IDs available in the monthly Solr export.</figcaption>
    </figure>
    <div>
      <h3>Downloads by collection in the reference month</h3>
      <p>No dedicated monthly export for downloads by collection is currently available.</p>
    </div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_views_by_community.png" alt="Views by community in the reference month">
      <figcaption>Views by community in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_downloads_by_community.png" alt="Downloads by community in the reference month">
      <figcaption>Downloads by community in the reference month.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_downloads_by_license.png" alt="Downloads by license in the reference month">
      <figcaption>Downloads by license in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_downloads_by_resource_type.png" alt="Downloads by resource type in the reference month">
      <figcaption>Downloads by resource type in the reference month.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/monthly_downloads_by_mimetype.png" alt="Downloads by MIME type in the reference month">
    <figcaption>Downloads by MIME type in the reference month.</figcaption>
  </figure>
  <h3>View/download ratio by item</h3>
  {table_html(detail["view_download_ratio"], ["resource", "views_count", "downloads_count", "views_downloads_ratio"], 10)}

  <h2>Internal searches in the reference month</h2>
  <p>
    This section describes what users searched for in the repository during the
    reference month, distinguishing text queries from filters/facets used by users.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total searches in the reference month</span><strong>{detail["total_searches_count"]}</strong></div></div>
  </div>
  <figure>
    <img src="figures/monthly_most_searched_terms.png" alt="Most searched terms in the reference month">
    <figcaption>Most frequent queries and facets in the reference month.</figcaption>
  </figure>
  <h3>Top 20 searched terms</h3>
  {table_html(detail["most_searched_terms"], ["searched_term", "term_type", "bot_status", "events_count"], 20)}
  <details class="mt-3">
    <summary>Search details in the reference month</summary>
    {table_html(detail["search_details"], ["search_date", "search_query_text", "search_filters", "search_page", "referrer", "bot_status"], 50)}
  </details>

  <h2>Accesses, referrers and acquisition in the reference month</h2>
  <p>
    In this section, <strong>Solr</strong> describes referrers for repository-side events,
    while <strong>Matomo</strong> describes the origin of browser-tracked web visits.
  </p>
  <h3>Referrer repository-side (Solr)</h3>
  {table_html(detail["top_referrers"], ["referrer_normalized", "events_count"], 10)}
  <figure>
    <img src="figures/monthly_solr_search_engine_events.png" alt="Solr accesses from search engines in the reference month">
    <figcaption>Repository-side accesses from search engines in the reference month. The current monthly export is available only for non-bot events.</figcaption>
  </figure>
  <div class="two-col">
    <div>
      <h3>User agent per bot status</h3>
      {table_html(detail["user_agents_by_bot_status"], ["user_agent", "bot_status", "events_count"], 10)}
    </div>
  </div>
  <h3>Web acquisition (Matomo)</h3>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Direct visits in the reference month</span><strong>{detail["direct_visits_count"]}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_matomo_visits_from_search_engines.png" alt="Matomo visits from search engines in the reference month">
      <figcaption>Web visits from search engines in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_matomo_visits_from_websites.png" alt="Matomo visits from websites in the reference month">
      <figcaption>Web visits from external websites in the reference month.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <div>
      <h3>Visits from social networks</h3>
      {table_html(detail["social_networks"], ["social_network", "visits_count"], 10)}
    </div>
    <div>
      <h3>Campaign visits</h3>
      {table_html(detail["campaigns"], ["campaign", "visits_count"], 10)}
    </div>
  </div>
  <div class="two-col">
    <div>
      <h3>Referrer websites</h3>
      {table_html(detail["websites"], ["website", "visits_count"], 10)}
    </div>
    <div>
      <h3>Top referrer websites</h3>
      {table_html(detail["top_referrer_websites"], ["referrer_website", "visits_count"], 10)}
    </div>
  </div>

  <h2>Bots, internal traffic and event quality in the reference month</h2>
  <p>
    This technical section helps interpret the quality of the monthly signal,
    highlighting the weight of bots, internal traffic and other components that may
    make observed usage harder to interpret.
  </p>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_bot_events_by_type.png" alt="Bot events in the reference month by event and object type">
      <figcaption>Bot events in the reference month by event and object type.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_internal_events_by_type.png" alt="Internal events in the reference month by event and object type">
      <figcaption>Internal 192.168.X.X events in the reference month by event and object type.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/monthly_internal_external_ratio.png" alt="Internal/external ratio in the reference month">
    <figcaption>Ratio among internal, external and unclassified events by bot status and event type.</figcaption>
  </figure>
  <div class="two-col">
    <details>
      <summary>Most frequent bot user agents</summary>
      {table_html(detail["bot_user_agents"], ["user_agent", "events_count"], 10)}
    </details>
    <details>
      <summary>User agent per bot status</summary>
      {table_html(detail["user_agents_by_bot_status"], ["user_agent", "bot_status", "events_count"], 10)}
    </details>
  </div>

  <h2>Matomo web traffic in the reference month</h2>
  <p>
    This section describes browser-tracked web traffic in the reference month.
    Matomo statistics represent browser-tracked traffic and may be affected by
    ad blockers or anti-tracking protections.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Visits in the reference month</span><strong>{latest_row['visits']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Pageviews in the reference month</span><strong>{latest_row['pageviews']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Actions in the reference month</span><strong>{detail['total_actions_count']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average visit duration</span><strong>{detail['average_visit_duration_seconds']} s</strong><small>{average_visit_duration_minutes} min</small></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bounce rate</span><strong>{detail['bounce_rate']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Actions per visit</span><strong>{detail['actions_per_visit_value']}</strong></div></div>
  </div>
  <div class="two-col">
    <div>
      <h3>Top visited pages</h3>
      {table_html(detail["top_visited_pages"], ["page_title", "pageviews_count", "visits_count"], 10)}
    </div>
    <figure>
      <img src="figures/page_typology.png" alt="Typology of page views in the reference month">
      <figcaption>Page views in the reference month grouped by DSpace page type.</figcaption>
    </figure>
  </div>

  <h2>Access geography in the reference month</h2>
  <p>
    The geographic distribution of visits shows where Matomo-recorded web traffic
    came from during the reference month.
  </p>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_visits_by_continent.png" alt="Visits by continent in the reference month">
      <figcaption>Visits by continent in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_visits_by_country.png" alt="Visits by country in the reference month">
      <figcaption>Top 20 countries by visits in the reference month.</figcaption>
    </figure>
  </div>
  <h3>Top cities in the reference month</h3>
  {table_html(detail["visits_by_city"], ["city", "visits_count"], 20)}

  <h2>Devices and technology in the reference month</h2>
  <p>
    This section provides a concise technical profile of web traffic
    recorded during the month.
  </p>
  <div class="two-col">
    <figure>
      <img src="figures/monthly_visits_by_device_type.png" alt="Visits by device type in the reference month">
      <figcaption>Visits by device type in the reference month.</figcaption>
    </figure>
    <figure>
      <img src="figures/monthly_visits_by_browser.png" alt="Visits by browser in the reference month">
      <figcaption>Visits by browser in the reference month.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/monthly_visits_by_operating_system.png" alt="Visits by operating system in the reference month">
    <figcaption>Visits by operating system in the reference month.</figcaption>
  </figure>

  <h2>OAI and indexing in the reference month</h2>
  <p>
    The main monthly measure here is the number of OAI records created or updated
    during the reference month. Extreme datestamps and problematic records are instead
    state indicators drawn from the latest technical snapshot
    ({monthly_oai_snapshot.get('snapshot_month', 'n.d.')}).
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>OAI records updated in the reference month</span><strong>{detail["monthly_oai_records_count"]}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>OAI records with missing information</span><strong>{monthly_oai_snapshot.get('oai_records_missing_information', 'n.d.')}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>OAI records of deleted items</span><strong>{monthly_oai_snapshot.get('oai_records_deleted_items', 'n.d.')}</strong></div></div>
  </div>
  <div class="two-col">
    <div>
      <h3>First 10 OAI datestamps</h3>
      {table_html(monthly_oai_snapshot["first_10_oai_datestamp"], ["item_handle", "oai_datestamp", "title"], 10)}
    </div>
    <div>
      <h3>Last 10 OAI datestamps</h3>
      {table_html(monthly_oai_snapshot["last_10_oai_datestamp"], ["item_handle", "oai_datestamp", "title"], 10)}
    </div>
  </div>

  <h2>Users and workflow in the reference month</h2>
  <p>
    Active users are measured in the reference month. Workspace, workflow
    and stalled submissions instead describe the current operational state of the
    available snapshot ({user_group_workflow_snapshot.get('snapshot_month', 'n.d.')}).
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Active users in the reference month</span><strong>{detail["active_users_count"]}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Workspace items</span><strong>{user_group_workflow_snapshot.get('workspace_items', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Workflow items</span><strong>{user_group_workflow_snapshot.get('workflow_items', 'n.d.')}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Submissions stalled &gt; 30 days</span><strong>{user_group_workflow_snapshot.get('stalled_submissions_over_30_days', 'n.d.')}</strong></div></div>
  </div>
  <div class="two-col">
    <div>
      <h3>Workspace items per user</h3>
      {table_html(user_group_workflow_snapshot["workspace_items_per_user"], ["submitter_email", "workspace_items_count"], 20)}
    </div>
    <div>
      <h3>Workflow items per collection</h3>
      <p>No dedicated export for workflow items by collection is currently available.</p>
    </div>
  </div>
  <div class="two-col">
    <div>
      <h3>Workflow approval timeline for uploaded items</h3>
      {table_html(detail["workflow_approval_timeline"], ["resource", "submitted_at", "first_approval_at", "second_approval_at", "final_approval_at", "made_available_at", "submitted_to_available_hours"], 20)}
    </div>
    <div>
      <h3>Active users in the reference month</h3>
      {table_html(detail["active_users_in_month"], ["email", "last_active"], 20)}
    </div>
  </div>

  <h2>Repository profile</h2>
  <p>
    Item metrics in this section are reconstructed up to the reference month
    ({repository_snapshot.get('as_of_month', reference_month)}) using deposit dates.
    Other state metrics come from the latest available snapshot
    ({repository_snapshot.get('snapshot_month', 'n.d.')}).
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Community</span><strong>{repository_snapshot.get('communities_total', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Collection</span><strong>{repository_snapshot.get('collections_total', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Collections without items</span><strong>{repository_organization_snapshot.get('collections_without_items_total', 'n.d.')}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/items_per_collection.png" alt="Item per collection">
      <figcaption>Item distribution by collection in the available snapshot.</figcaption>
    </figure>
    <figure>
      <img src="figures/size_per_collection.png" alt="Total size by collection">
      <figcaption>Total file size by collection in the available snapshot.</figcaption>
    </figure>
  </div>

  <h2>Editorial production</h2>
  <p>
    This analysis highlights which collections contributed most
    to repository growth during the reference month.
  </p>
  <figure>
    <img src="figures/top_collections.png" alt="Top collections by new items">
    <figcaption>Top collections by number of new items uploaded in the reference month.</figcaption>
  </figure>

  <h2>Content usage</h2>
  <p>
    This section describes which contents received the most attention
    and which formats or types were downloaded most during the month.
  </p>
  <div class="two-col">
    <div>
      <h3>Most viewed items</h3>
      {table_html(detail["top_viewed_items"], ["resource", "views_count"], 10)}
    </div>
    <div>
      <h3>Most downloaded items</h3>
      {table_html(detail["top_downloaded_items"], ["resource", "downloads_count"], 10)}
    </div>
  </div>
  <div class="two-col">
    <div>
      <h3>Downloads by type</h3>
      {table_html(detail["downloads_by_resource_type"], ["resource_type", "downloads_count"], 10)}
    </div>
    <div>
      <h3>Downloads by MIME type</h3>
      {table_html(detail["downloads_by_mimetype"], ["mimetype", "downloads_count"], 10)}
    </div>
  </div>

  <h2>Audience and origin</h2>
  <p>
    The geographic distribution of visits helps describe the repository's reach
    and the audience reached during the month.
  </p>
  <figure>
    <img src="figures/top_countries.png" alt="Top countries by visits">
    <figcaption>Top countries of origin for visits in the reference month.</figcaption>
  </figure>

  <h2>Traffic acquisition</h2>
  <p>
    The distribution of visits by channel shows how users reach the repository
    and helps distinguish direct traffic, search-engine discovery and external referrals.
  </p>
  <table class="data-table">
    <thead><tr><th>Channel</th><th>Visits</th></tr></thead>
    <tbody>{acquisition_html}</tbody>
  </table>
  <div class="two-col">
    <div>
      <h3>Search engines</h3>
      {table_html(detail["search_engines"], ["search_engine", "visits_count"], 10)}
    </div>
    <div>
      <h3>Referrer websites</h3>
      {table_html(detail["websites"], ["website", "visits_count"], 10)}
    </div>
  </div>

  <h2>Use of site sections</h2>
  <p>
    The distribution of page views by page type helps show
    whether the audience concentrates mainly on the homepage, item pages,
    search or other repository sections.
  </p>
  <figure>
    <img src="figures/page_typology.png" alt="Pageviews by DSpace section">
    <figcaption>Monthly page views grouped by DSpace page type.</figcaption>
  </figure>

  <h2>Quality and compliance</h2>
  <p>
    The following metrics are repository-state indicators rather than monthly measures:
    they capture the latest snapshot available when the report was generated ({quality_snapshot.get('snapshot_month', 'n.d.') }).
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items with missing metadata</span><strong>{quality_snapshot.get('items_missing_metadata', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items without files</span><strong>{quality_snapshot.get('items_without_files', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Invalid licenses</span><strong>{quality_snapshot.get('items_invalid_license', 'n.d.')}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Submissions stalled &gt; 30 days</span><strong>{quality_snapshot.get('stalled_submissions_over_30_days', 'n.d.')}</strong></div></div>
  </div>

  <h2>Methodological note</h2>
  <p>
    The report combines PostgreSQL, Solr and Matomo metrics. Monthly metrics
    are calculated over the complete reference month; Solr usage measures
    exclude bot events where required by the current queries.
  </p>
</div>
</main>
{collapsible_sections_script()}
{tabbed_sections_script()}
</body>
</html>
"""


def report_exists(report_dir: Path) -> bool:
    return (report_dir / "report.html").exists()


def resolve_logo_relative_path(
    project_root: Path,
    config: dict,
    from_dir: Path,
) -> str | None:
    logo_path = resolve_logo_path(project_root, config)
    if logo_path is None:
        return None
    reports_root = project_root / config.get("paths", {}).get("reports_root", "reports")
    published_logo_path = reports_root / "assets" / "branding" / logo_path.name
    if not logo_path.exists():
        if published_logo_path.exists():
            return os.path.relpath(published_logo_path, start=from_dir).replace("\\", "/")
        print(f"Configured logo not found, continuing without logo: {logo_path}")
        return None

    published_logo_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(logo_path, published_logo_path)
    return os.path.relpath(published_logo_path, start=from_dir).replace("\\", "/")


def safe_sum(df, column: str) -> int:
    if column not in df.columns:
        return 0
    return int(df[column].sum())


def normalize_handle(handle: object) -> str | None:
    if handle is None:
        return None
    normalized = (
        str(handle)
        .strip()
        .removeprefix("http://hdl.handle.net/")
        .removeprefix("https://hdl.handle.net/")
    )
    if normalized.lower() in {"", "nan", "none"}:
        return None
    return normalized or None


def item_href(item_id: object, item: dict[str, str] | None = None) -> str:
    item = item or {}
    handle = normalize_handle(item.get("handle") or item.get("item_handle"))
    if handle:
        return f"https://hdl.handle.net/{handle}"
    return f"https://dspace-clarin-it.ilc.cnr.it/items/{item_id}"


def add_item_resource_column(df, item_lookup: dict[str, dict[str, str]]):
    if "item_id" not in df.columns:
        return df
    enriched = df.copy()

    def render_resource(item_id: object) -> str:
        key = str(item_id)
        item = item_lookup.get(key, {})
        title = escape(item.get("title") or key)
        href = escape(item_href(key, item))
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{title}</a>'

    enriched["resource"] = enriched["item_id"].map(render_resource)
    return enriched


def resolve_navigation_months(
    existing_report_months: set[str],
    target_report_months: list[str],
) -> list[str]:
    """Return only months that will have report pages after the current build."""
    return sorted(existing_report_months | set(target_report_months))


def render_reports_index_html(
    institution_name: str,
    institution_subtitle: str,
    archive_title: str,
    monthly_report_months: list[str],
    always_report_months: list[str],
    logo_relative_path: str | None,
    home_href: str,
) -> str:
    monthly_years: dict[str, list[str]] = {}
    for month in sorted(monthly_report_months, reverse=True):
        year = month.split("-", 1)[0]
        monthly_years.setdefault(year, []).append(month)

    if len(monthly_years) > 1:
        monthly_rows = "\n".join(
            (
                f'<div class="mb-3">'
                f'<div class="fw-bold mb-2">{year}</div>'
                f'<div class="list-group list-group-flush">'
                + "\n".join(
                    f'<a class="monthly-report-link list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="monthly/{month}/report.html"><span>{month}</span><span aria-hidden="true">&rarr;</span></a>'
                    for month in months
                )
                + "</div></div>"
            )
            for year, months in monthly_years.items()
        )
    else:
        monthly_rows = "\n".join(
            f'<a class="monthly-report-link list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="monthly/{month}/report.html"><span>{month}</span><span aria-hidden="true">&rarr;</span></a>'
            for month in sorted(monthly_report_months, reverse=True)
        )
    always_rows = "\n".join(
        f'<a class="monthly-report-link list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="always/{month}/report.html"><span>{month}</span><span aria-hidden="true">&rarr;</span></a>'
        for month in sorted(always_report_months, reverse=True)
    )
    logo_html = (
        f'<a href="{home_href}" aria-label="Torna alla home"><img class="logo" src="{logo_relative_path}" alt="{institution_name} logo"></a>'
        if logo_relative_path
        else ""
    )
    return f"""<!doctype html>
<html lang="it">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{archive_title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      body {{ color: #1f2937; background: #f8fafc; }}
      main {{ max-width: 900px; }}
      .site-shell {{ background: white; min-height: calc(100vh - 3rem); }}
      .brand-accent {{ border-bottom: 3px solid #0f766e; }}
      .brand-link {{ color: inherit; text-decoration: none; }}
      .logo {{ max-width: min(240px, 100%); max-height: 90px; object-fit: contain; }}
      h1 {{ color: #0f766e; }}
      .monthly-report-link {{
        transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
      }}
      .monthly-report-link:hover {{
        background-color: #e6fffb;
        color: #0f766e;
        transform: translateX(4px);
      }}
    </style>
</head>
<body>
<main class="container px-3 py-4 py-md-5">
<div class="site-shell shadow-sm rounded-4 p-3 p-md-5">
  <header class="brand-accent d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 pb-4 mb-4">
    <div>
      <h1><a class="brand-link" href="{home_href}">{institution_name}</a></h1>
      <p>{institution_subtitle}</p>
    </div>
    {logo_html}
  </header>
  <h2>{archive_title}</h2>
  <div class="row g-4">
    <section class="col-12 col-md-6">
      <div class="card border-0 shadow-sm h-100">
        <div class="card-body">
          <h3 class="h5 card-title"> Monthly Reports</h3>
            {monthly_rows}
        </div>
      </div>
    </section>
    <section class="col-12 col-md-6">
      <div class="card border-0 shadow-sm h-100">
        <div class="card-body">
          <h3 class="h5 card-title">Overall Status Report</h3>
          <div class="list-group list-group-flush">{always_rows}</div>
        </div>
      </div>
    </section>
  </div>
</div>
</main>
</body>
</html>
"""


def render_always_report_html(
    *,
    reference_month: str,
    institution_name: str,
    institution_subtitle: str,
    logo_relative_path: str | None,
    home_href: str,
    repository_snapshot: dict[str, object],
    repository_organization_snapshot: dict[str, object],
    item_publication_snapshot: dict[str, object],
    metadata_quality_snapshot: dict[str, object],
    oai_solr_exposure_snapshot: dict[str, object],
    historical_usage_snapshot: dict[str, object],
    access_referrer_snapshot: dict[str, object],
    event_quality_snapshot: dict[str, object],
    internal_search_snapshot: dict[str, object],
    matomo_web_traffic_snapshot: dict[str, object],
    access_geography_snapshot: dict[str, object],
    device_technology_snapshot: dict[str, object],
    user_group_workflow_snapshot: dict[str, object],
    technical_integrity_snapshot: dict[str, object],
    quality_snapshot: dict[str, object],
) -> str:
    logo_html = (
        f'<a href="{home_href}" aria-label="Torna alla home"><img class="logo" src="{logo_relative_path}" alt="{institution_name} logo"></a>'
        if logo_relative_path
        else ""
    )
    anomaly_items_html = []
    for index, row in enumerate(item_publication_snapshot["anomalies"], start=1):
        list_items = []
        for item in row["items"]:
            title = escape(str(item["title"]))
            item_id = escape(str(item["item_id"]))
            item_id_html = (
                f'<a href="https://dspace-clarin-it.ilc.cnr.it/items/{item_id}" '
                f'target="_blank" rel="noopener noreferrer">{item_id}</a>'
            )
            handle = item["handle"]
            if handle:
                handle_links = []
                for raw_handle in str(handle).split(";"):
                    normalized_handle = (
                        raw_handle.strip()
                        .removeprefix("http://hdl.handle.net/")
                        .removeprefix("https://hdl.handle.net/")
                    )
                    if not normalized_handle:
                        continue
                    escaped_handle = escape(normalized_handle)
                    handle_links.append(
                        f'<a href="https://hdl.handle.net/{escaped_handle}" target="_blank" '
                        f'rel="noopener noreferrer">{escaped_handle}</a>'
                    )
                resource_html = "<br>".join(handle_links) if handle_links else '<span class="text-muted">missing handle</span>'
            else:
                resource_html = '<span class="text-muted">missing handle</span>'
            list_items.append(
                f"<li><span>{title}</span><small>{item_id_html}</small><span>{resource_html}</span></li>"
            )
        anomaly_items_html.append(
            f"""
    <div class="accordion-item">
      <h4 class="accordion-header" id="heading-anomaly-{index}">
        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-anomaly-{index}" aria-expanded="false" aria-controls="collapse-anomaly-{index}">
          {escape(str(row['indicator']))} <span class="badge text-bg-warning ms-2">{row['count']}</span>
        </button>
      </h4>
      <div id="collapse-anomaly-{index}" class="accordion-collapse collapse" aria-labelledby="heading-anomaly-{index}" data-bs-parent="#anomaliesAccordion">
        <div class="accordion-body">
          <ul class="anomaly-list">{''.join(list_items)}</ul>
        </div>
      </div>
    </div>
"""
        )
    anomalies_html = (
        f"""
  <h3>Issues</h3>
  <div class="accordion mb-4" id="anomaliesAccordion">
    {''.join(anomaly_items_html)}
  </div>
"""
        if item_publication_snapshot["anomalies"]
        else ""
    )
    item_lookup = {
        str(row["item_id"]): {
            "title": str(row.get("title", "") or row["item_id"]),
            "item_handle": str(row.get("item_handle", "") or ""),
        }
        for _, row in oai_solr_exposure_snapshot["item_catalog"].iterrows()
    }

    def linked_item_id(item_id: object) -> str:
        key = str(item_id)
        item = item_lookup.get(key, {})
        title = escape(item.get("title", key))
        href = escape(item_href(key, item))
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{title}</a>'

    def linked_handle(handle: object) -> str:
        normalized_handle = (
            str(handle)
            .removeprefix("http://hdl.handle.net/")
            .removeprefix("https://hdl.handle.net/")
        )
        escaped_handle = escape(normalized_handle)
        return (
            f'<a href="https://hdl.handle.net/{escaped_handle}" '
            f'target="_blank" rel="noopener noreferrer">{escaped_handle}</a>'
        )

    def detail_table_html(df, columns, row_renderer=None):
        if df.empty:
            return '<p class="text-muted">Nessuna anomalia rilevata.</p>'
        header_html = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
        body_rows = []
        for _, row in df.iterrows():
            cells = []
            for column, _ in columns:
                value = row.get(column, "")
                rendered = (
                    row_renderer(column, value)
                    if row_renderer is not None
                    else escape("" if value is None else str(value))
                )
                cells.append(f"<td>{rendered}</td>")
            body_rows.append(f"<tr>{''.join(cells)}</tr>")
        return f"""
        <div class="detail-table-wrap">
          <table class="table table-striped table-hover align-middle mb-0">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{''.join(body_rows)}</tbody>
          </table>
        </div>
        """

    render_value = lambda column, value: linked_item_id(value) if column == "item_id" else escape("" if value is None else str(value))
    missing_metadata_table = detail_table_html(
        metadata_quality_snapshot["missing_metadata_detail"],
        [("item_id", "Resource"), ("handle", "Handle"), ("missing_fields", "Missing fields")],
        lambda column, value: linked_item_id(value)
        if column == "item_id"
        else linked_handle(value)
        if column == "handle" and str(value) not in {"", "nan", "None"}
        else escape("" if value is None else str(value)),
    )
    empty_metadata_table = detail_table_html(
        metadata_quality_snapshot["empty_metadata_values_detail"],
        [("item_id", "Resource"), ("metadata_field", "Metadata field"), ("metadata_value_id", "Metadata value ID")],
        render_value,
    )
    problematic_bitstreams_table = detail_table_html(
        technical_integrity_snapshot["problematic_bitstreams"],
        [
            ("problem", "Problema"),
            ("bitstream_id", "Bitstream ID"),
            ("item_id", "Resource"),
            ("filename", "Filename"),
            ("bundle_name", "Bundle"),
            ("bitstream_visibility_problem", "Detail"),
        ],
        lambda column, value: linked_item_id(value)
        if column == "item_id" and str(value) not in {"", "nan", "None"}
        else escape("" if value is None else str(value)),
    )
    submitter_groups_table = detail_table_html(
        repository_organization_snapshot["submitter_groups_per_collection"],
        [
            ("collection_name", "Collection"),
            ("group_names", "Submitter groups"),
            ("group_members_count", "Members"),
        ],
    )
    workflow_groups_table = detail_table_html(
        repository_organization_snapshot["workflow_groups_per_collection"],
        [
            ("collection_name", "Collection"),
            ("group_names", "Workflow groups"),
            ("group_members_count", "Members"),
        ],
    )
    administrator_groups_table = detail_table_html(
        repository_organization_snapshot["administrator_groups_per_collection"],
        [
            ("collection_name", "Collection"),
            ("group_names", "Admin groups"),
            ("group_members_count", "Members"),
        ],
    )
    available_cores_table = detail_table_html(
        oai_solr_exposure_snapshot["available_cores"],
        [
            ("core_name", "Core"),
            ("num_docs", "Documents"),
            ("deleted_docs", "Deleted documents"),
            ("index_size", "Index size"),
        ],
    )
    index_size_by_core_table = detail_table_html(
        oai_solr_exposure_snapshot["index_size_by_core"],
        [
            ("core_logical_name", "Core"),
            ("index_size", "Index size"),
            ("num_docs", "Documents"),
            ("deleted_docs", "Deleted documents"),
        ],
    )
    record_count_by_core_table = detail_table_html(
        oai_solr_exposure_snapshot["record_count_by_core"],
        [("core_logical_name", "Core"), ("records_count", "Record")],
    )
    distinct_event_types_table = detail_table_html(
        oai_solr_exposure_snapshot["distinct_event_types"],
        [("statistics_type", "Event type"), ("events_count", "Events")],
    )
    distinct_object_types_table = detail_table_html(
        oai_solr_exposure_snapshot["distinct_object_types"],
        [
            ("object_type_label", "Object type"),
            ("object_type", "Code"),
            ("events_count", "Events"),
        ],
    )
    oai_sets_available_values_table = detail_table_html(
        oai_solr_exposure_snapshot["oai_sets_available_values"],
        [
            ("facet_field", "Field"),
            ("field_value", "Value"),
            ("records_count", "Record"),
        ],
    )
    first_10_oai_datestamp_table = detail_table_html(
        oai_solr_exposure_snapshot["first_10_oai_datestamp"],
        [
            ("item_handle", "Handle"),
            ("oai_datestamp", "Datestamp OAI"),
            ("title", "Titolo"),
        ],
    )
    last_10_oai_datestamp_table = detail_table_html(
        oai_solr_exposure_snapshot["last_10_oai_datestamp"],
        [
            ("item_handle", "Handle"),
            ("oai_datestamp", "Datestamp OAI"),
            ("title", "Titolo"),
        ],
    )
    most_viewed_items_table = detail_table_html(
        historical_usage_snapshot["most_viewed_items"],
        [
            ("item_id", "Resource"),
            ("views_count", "Views"),
            ("downloads_count", "Download"),
        ],
        render_value,
    )
    most_downloaded_items_table = detail_table_html(
        historical_usage_snapshot["most_downloaded_items"],
        [("item_id", "Resource"), ("downloads_count", "Download")],
        render_value,
    )
    most_downloaded_items_with_bitstreams_table = detail_table_html(
        historical_usage_snapshot["most_downloaded_items_with_bitstreams"],
        [
            ("item_id", "Resource"),
            ("downloads_count", "Download"),
            ("bitstream_ids", "Bitstream IDs"),
        ],
        render_value,
    )
    view_download_ratio_table = detail_table_html(
        historical_usage_snapshot["view_download_ratio_top_10"],
        [
            ("item_id", "Resource"),
            ("views_count", "Views"),
            ("downloads_count", "Download"),
            ("views_downloads_ratio", "Views/download ratio"),
        ],
        render_value,
    )
    top_referrers_table = detail_table_html(
        access_referrer_snapshot["top_referrers"],
        [("referrer_normalized", "Referrer"), ("events_count", "Events")],
    )
    websites_table = detail_table_html(
        access_referrer_snapshot["visits_from_websites"],
        [("website", "Website"), ("visits_count", "Visits")],
    )
    social_networks_table = detail_table_html(
        access_referrer_snapshot["visits_from_social_networks"],
        [("social_network", "Social network"), ("visits_count", "Visits")],
    )
    campaigns_table = detail_table_html(
        access_referrer_snapshot["campaign_visits"],
        [("campaign", "Campaign"), ("visits_count", "Visits")],
    )
    top_referrer_websites_table = detail_table_html(
        access_referrer_snapshot["top_referrer_websites"],
        [("referrer_website", "Website"), ("visits_count", "Visits")],
    )
    most_searched_terms_table = detail_table_html(
        internal_search_snapshot["most_searched_terms"],
        [
            ("searched_term", "Termine"),
            ("term_type", "Tipo"),
            ("events_count", "Searches"),
        ],
    )
    top_visited_pages_table = detail_table_html(
        matomo_web_traffic_snapshot["top_visited_pages"],
        [
            ("page_title", "Pagina"),
            ("pageviews_count", "Pageviews"),
            ("visits_count", "Visits"),
        ],
    )
    top_cities_table = detail_table_html(
        access_geography_snapshot["top_cities"],
        [
            ("city", "Città"),
            ("country", "Country"),
            ("visits_count", "Visits"),
        ],
    )
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{institution_name} - Repository status {reference_month}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ color: #1f2937; background: #f8fafc; }}
    main {{ max-width: 1200px; }}
    .site-shell {{ background: white; }}
    .brand-accent {{ border-bottom: 3px solid #0f766e; }}
    .brand-link {{ color: inherit; text-decoration: none; }}
    .logo {{ max-width: min(240px, 100%); max-height: 90px; object-fit: contain; }}
    h2 {{ color: #0f766e; margin-top: 2.75rem; margin-bottom: 1rem; }}
    h3 {{ margin-top: 2rem; margin-bottom: 1rem; }}
    .subtitle {{ color: #475569; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1.25rem; }}
    .kpi {{ background: #f1f5f9; border: 0; }}
    .kpi .card-body {{ padding: 1.25rem 1.35rem; }}
    .kpi-warning {{ background: #fff7ed; border-left: 4px solid #f59e0b; }}
    .kpi strong {{ display: block; font-size: 1.6rem; }}
    figure img {{ max-width: 100%; border: 1px solid #e2e8f0; border-radius: 0.75rem; }}
    figure {{ margin-top: 1.5rem; margin-bottom: 2rem; }}
    figcaption {{ color: #475569; font-size: 0.95rem; margin-top: 8px; }}
    .anomaly-list {{ list-style: none; margin: 0; padding: 0; max-height: 320px; overflow-y: auto; }}
    .anomaly-list li {{ display: grid; grid-template-columns: minmax(220px, 1fr) auto auto; gap: 16px; align-items: center; padding: 10px 0; border-bottom: 1px solid #e2e8f0; }}
    .anomaly-list li:last-child {{ border-bottom: 0; }}
    .anomaly-list small {{ color: #64748b; }}
    .detail-table-wrap {{ max-height: 360px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 0.75rem; margin-top: 0.75rem; margin-bottom: 2rem; }}
    .detail-table-wrap thead th {{ position: sticky; top: 0; background: #f8fafc; z-index: 1; }}
    .two-col {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 2rem; margin-top: 1rem; margin-bottom: 1.5rem; }}
    p {{ line-height: 1.6; }}
    h3 {{ margin-top: 1.75rem; margin-bottom: 1rem; }}
    .section-lead {{ margin-bottom: 1.5rem; }}
    {collapsible_sections_assets()}
    {tabbed_sections_assets()}
    @media (max-width: 640px) {{
      .kpis {{ grid-template-columns: 1fr; }}
      .anomaly-list li {{ grid-template-columns: 1fr; gap: 4px; }}
      .two-col {{ grid-template-columns: 1fr; }}
    }}
    a {{ color: #0f766e; text-decoration: none; }}
  </style>
</head>
<body>
<main class="container px-3 px-md-4 py-4 py-md-5">
<div class="site-shell shadow-sm rounded-4 p-4 p-md-5">
  <header class="brand-accent d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 pb-4">
    <div>
      <h1><a class="brand-link" href="{home_href}">{institution_name}</a></h1>
      <div class="subtitle">{institution_subtitle} - overall condition {reference_month}</div>
    </div>
    {logo_html}
  </header>
  <p class="my-4"><a class="btn btn-primary" href="../../index.html">&larr; Report archive</a></p>
  <div data-report-tabs></div>
  <h2>Overall repository profile</h2>
  <p>This report compiles the `always` metrics, i.e. the overall status indicators calculated at the time of the snapshot.</p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total items</span><strong>{repository_snapshot['items_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Archived items</span><strong>{repository_snapshot['items_archived']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Public items</span><strong>{repository_snapshot['items_publicly_reachable']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total bitstreams</span><strong>{repository_snapshot['bitstreams_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total file size</span><strong>{repository_snapshot['files_total_size_gb']} GB</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items with handle</span><strong>{repository_snapshot['items_with_handle']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items with bitstreams</span><strong>{repository_snapshot['items_with_files']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Community</span><strong>{repository_snapshot['communities_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Collection</span><strong>{repository_snapshot['collections_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Users</span><strong>{repository_snapshot['users_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Groups</span><strong>{repository_snapshot['groups_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>OAI records</span><strong>{repository_snapshot['oai_records_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Distinct licenses</span><strong>{repository_snapshot['licenses_total']}</strong></div></div>
  </div>
  <h2>Repository organization</h2>
  <p class="section-lead">
    This section describes the organizational structure of the repository: communities,
    collections, item distribution and collection-level administrative configuration.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total communities</span><strong>{repository_organization_snapshot['communities_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total collections</span><strong>{repository_organization_snapshot['collections_total']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Communities without collections</span><strong>{repository_organization_snapshot['communities_without_collections_total']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Collections without items</span><strong>{repository_organization_snapshot['collections_without_items_total']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/items_per_community.png" alt="Item per community">
      <figcaption>Item distribution by community.</figcaption>
    </figure>
    <figure>
      <img src="figures/items_per_collection.png" alt="Item per collection">
      <figcaption>Item distribution by collection.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/organization_size_per_collection.png" alt="Total size by collection">
    <figcaption>Total file size by collection.</figcaption>
  </figure>
  <h3>Collection administration</h3>
  <p>
    The following tables are deliberately more technical and are kept separate from the
    main summary: they are intended to verify the operational structure of the groups by collection.
  </p>
  <h4>Submitter groups per collection</h4>
  {submitter_groups_table}
  <h4 class="mt-4">Workflow groups per collection</h4>
  {workflow_groups_table}
  <h4 class="mt-4">Administrator groups per collection</h4>
  {administrator_groups_table}
  <h2>Item status and publication</h2>
  <p>
    This section distinguishes the overall consistency of items from the signals
    operativi che incidono sulla pubblicazione e sulla loro corretta esposizione.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total items</span><strong>{item_publication_snapshot['items_total']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Items without handle</span><strong>{item_publication_snapshot['items_without_handle']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Items without collection</span><strong>{item_publication_snapshot['items_without_collection']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items not publicly visible</span><strong>{item_publication_snapshot['items_not_publicly_visible']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Objects under embargo</span><strong>{item_publication_snapshot['objects_under_embargo']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items without bitstreams</span><strong>{item_publication_snapshot['items_without_bitstreams']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items without license</span><strong>{item_publication_snapshot['items_without_license']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Items without ORIGINAL bundle</span><strong>{item_publication_snapshot['items_without_original_bundle']}</strong></div></div>
  </div>
  <figure>
    <img src="figures/item_publication_status.png" alt="Item distribution by publication status">
    <figcaption>Public items, not publicly visible items, withdrawn items and not archived items.</figcaption>
  </figure>
  {anomalies_html}
  <h2>Metadata quality</h2>
  <p>
    This section assesses the comprehensiveness of the repository’s metadata: it highlights
    records with missing or empty metadata, the quality of the OAI exposure, and the
    distribution of licences across different organisational contexts.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items with missing metadata</span><strong>{metadata_quality_snapshot['items_missing_metadata']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items with empty metadata values</span><strong>{metadata_quality_snapshot['items_empty_metadata_values']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average metadata values per item</span><strong>{metadata_quality_snapshot['average_metadata_values_per_item']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>OAI records with missing information</span><strong>{metadata_quality_snapshot['oai_records_missing_information']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>OAI records of deleted items</span><strong>{metadata_quality_snapshot['oai_records_deleted_items']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items without license</span><strong>{metadata_quality_snapshot['items_without_license']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/oai_missing_fields.png" alt="OAI records by missing field">
      <figcaption>OAI records with missing information, distribuiti per Field.</figcaption>
    </figure>
    <figure>
      <img src="figures/licenses_per_resource_type.png" alt="Licenses by resource type">
      <figcaption>License assignments by resource type.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/licenses_per_collection.png" alt="Licenses by collection">
      <figcaption>Top collections by number of license assignments.</figcaption>
    </figure>
    <figure>
      <img src="figures/licenses_per_community.png" alt="Licenses by community">
      <figcaption>License assignments by community.</figcaption>
    </figure>
  </div>
  <h3>Items with missing metadata</h3>
  {missing_metadata_table}
  <h3 class="mt-4">Items with empty metadata values</h3>
  {empty_metadata_table}
  <h2>OAI exposure and Solr indexing</h2>
  <p>
    This section monitors technical exposure and indexing levels:
    Solr core consistency, record distribution, values exposed through OAI
    and anomaly signals in published records.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total OAI records</span><strong>{oai_solr_exposure_snapshot['total_oai_records']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>OAI records with missing information</span><strong>{oai_solr_exposure_snapshot['oai_records_missing_information']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>OAI records of deleted items</span><strong>{oai_solr_exposure_snapshot['oai_records_deleted_items']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/solr_index_size_by_core.png" alt="Index size per core Solr">
      <figcaption>Index size by Solr core.</figcaption>
    </figure>
    <figure>
      <img src="figures/solr_record_count_by_core.png" alt="Record count by Solr core">
      <figcaption>Number of indexed records by Solr core.</figcaption>
    </figure>
  </div>
  <h3>Available Solr cores</h3>
  {available_cores_table}
  <div class="two-col">
    <div>
      <h3>Index size by core</h3>
      {index_size_by_core_table}
    </div>
    <div>
      <h3>Record count by Solr core</h3>
      {record_count_by_core_table}
    </div>
  </div>
  <div class="two-col">
    <div>
      <h3>Distinct event types in the statistics core</h3>
      {distinct_event_types_table}
    </div>
    <div>
      <h3>Distinct object types in the statistics core</h3>
      {distinct_object_types_table}
    </div>
  </div>
  <h3>OAI sets and available values</h3>
  {oai_sets_available_values_table}
  <div class="two-col">
    <div>
      <h3>First 10 OAI datestamp</h3>
      {first_10_oai_datestamp_table}
    </div>
    <div>
      <h3>Last 10 OAI datestamp</h3>
      {last_10_oai_datestamp_table}
    </div>
  </div>
  <h2>Historical repository usage</h2>
  <p>
    This section describes the cumulative usage of the <strong>all-time repository on the Solr side </strong>:
    It uses events stored in the <code>statistics</code> core and therefore measures the activity 
    observed by the repository over time, not Matomo’s monthly web traffic.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total item views</span><strong>{historical_usage_snapshot['total_item_views']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total bitstream downloads</span><strong>{historical_usage_snapshot['total_bitstream_downloads']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total events</span><strong>{historical_usage_snapshot['total_events']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Non-bot events</span><strong>{historical_usage_snapshot['non_bot_events']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/historical_views_by_collection.png" alt="Views storiche per collection">
      <figcaption>Cumulative views by collection according to Solr.</figcaption>
    </figure>
    <figure>
      <img src="figures/historical_downloads_by_collection.png" alt="Download storici per collection">
      <figcaption>Cumulative downloads by collection according to Solr.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/historical_views_by_community.png" alt="Views storiche per community">
      <figcaption>Cumulative views by community according to Solr.</figcaption>
    </figure>
    <figure>
      <img src="figures/historical_downloads_by_community.png" alt="Download storici per community">
      <figcaption>Cumulative downloads by community according to Solr.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <div>
      <h3>Most viewed items</h3>
      {most_viewed_items_table}
    </div>
    <div>
      <h3>Most downloaded items</h3>
      {most_downloaded_items_table}
    </div>
  </div>
  <h3>Most downloaded items with bitstream IDs</h3>
  {most_downloaded_items_with_bitstreams_table}
  <h3>View/download ratio by item</h3>
  {view_download_ratio_table}
  <h2>Accesses, referrers and origin</h2>
  <p>
    This section keeps two complementary layers distinct:
    <strong>Solr</strong> describes referrers observed on repository-side events;
    <strong>Matomo</strong> describes browser-side web visits.
  </p>
  <h3>Referrer repository-side (Solr)</h3>
  <div class="two-col">
    <div>
      <h4>Top referrers</h4>
      {top_referrers_table}
    </div>
    <figure>
      <img src="figures/solr_top_referrers_by_bot_status.png" alt="Top referrer Solr per bot status">
      <figcaption>Top referrers observed on Solr events, split by bot status.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/solr_accesses_from_search_engines.png" alt="Solr accesses from search engines">
    <figcaption>Repository-side accesses from search engines according to Solr; the current export exposes only non-bot events.</figcaption>
  </figure>
  <h3>Browser-side web visits (Matomo)</h3>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Direct visits</span><strong>{access_referrer_snapshot['direct_visits']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/matomo_visits_from_search_engines.png" alt="Matomo visits from search engines">
      <figcaption>Web visits from search engines.</figcaption>
    </figure>
    <figure>
      <img src="figures/matomo_visits_from_websites.png" alt="Matomo visits from websites">
      <figcaption>Web visits from external websites.</figcaption>
    </figure>
  </div>
  <div class="two-col">
    <div>
      <h4>Visits from websites</h4>
      {websites_table}
    </div>
    <div>
      <h4>Top referrer websites</h4>
      {top_referrer_websites_table}
    </div>
  </div>
  <div class="two-col">
    <div>
      <h4>Visits from social networks</h4>
      {social_networks_table}
    </div>
    <div>
      <h4>Campaign visits</h4>
      {campaigns_table}
    </div>
  </div>
  <h2>Bots, internal traffic and event quality</h2>
  <p>
    This is a technical quality control section. The main view
    displays only the key metrics needed to assess the quality of events:
    bot traffic, internal traffic and the ratio of internal to external traffic.
    User agent, IP and DNS are deliberately excluded from the main page.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bot events</span><strong>{event_quality_snapshot['bot_events_total']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Internal events</span><strong>{event_quality_snapshot['internal_events_total']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/bot_events_by_event_and_object_type.png" alt="Bot events by event and object type">
      <figcaption>Bot events by event and object type.</figcaption>
    </figure>
    <figure>
      <img src="figures/internal_events_by_event_and_object_type.png" alt="Internal events by event and object type">
      <figcaption>Events from the 192.168.X.X network by event and object type.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/internal_external_events_ratio.png" alt="Internal and external events ratio">
    <figcaption>Ratio between internal and external events by bot status and event type.</figcaption>
  </figure>
  <h2>Internal search</h2>
  <p>
    This section summarises the usage of the repository-side internal search.
    Event-by-event details are not included on the main page.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total searches</span><strong>{internal_search_snapshot['total_searches']}</strong></div></div>
  </div>
  <figure>
    <img src="figures/most_searched_terms.png" alt="Termini più cercati">
    <figcaption>Top 20 searched terms lato repository, esclusi i bot.</figcaption>
  </figure>
  <h3>Most searched terms</h3>
  {most_searched_terms_table}
  <h2>Matomo web traffic</h2>
  <p>
    This section describes browser-tracked web traffic from Matomo.
    Matomo statistics may underestimate actual traffic in the presence of ad blockers,
    anti-tracking protections or disabled JavaScript.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total visits</span><strong>{matomo_web_traffic_snapshot['total_visits']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total actions</span><strong>{matomo_web_traffic_snapshot['total_actions']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average visit duration</span><strong>{matomo_web_traffic_snapshot['average_visit_duration_seconds']} s</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bounce count</span><strong>{matomo_web_traffic_snapshot['bounce_count']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bounce rate</span><strong>{matomo_web_traffic_snapshot['bounce_rate']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Actions per visit</span><strong>{matomo_web_traffic_snapshot['actions_per_visit']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Max actions in a visit</span><strong>{matomo_web_traffic_snapshot['max_actions_in_visit']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/matomo_unique_visitors_by_month.png" alt="Matomo unique visitors by month">
      <figcaption>Monthly unique visitors detected by Matomo.</figcaption>
    </figure>
    <figure>
      <img src="figures/matomo_page_typology.png" alt="Pageview typology">
      <figcaption>Pageviews grouped by page type.</figcaption>
    </figure>
  </div>
  <h3>Top visited pages</h3>
  {top_visited_pages_table}
  <h2>Access geography</h2>
  <p>
    This section summarizes the geographic distribution of Matomo web visits.
  </p>
  <div class="two-col">
    <figure>
      <img src="figures/matomo_visits_by_continent.png" alt="Visits by continent">
      <figcaption>Web visits by continent.</figcaption>
    </figure>
    <figure>
      <img src="figures/matomo_top_countries.png" alt="Top countries by visits">
      <figcaption>Top countries by number of visits.</figcaption>
    </figure>
  </div>
  <h3>Top cities</h3>
  {top_cities_table}
  <h2>Devices and technology</h2>
  <p>
    This section provides secondary technical context on browser-side web visits.
  </p>
  <div class="two-col">
    <figure>
      <img src="figures/matomo_visits_by_device_type.png" alt="Visits by device type">
      <figcaption>Visits by device type.</figcaption>
    </figure>
    <figure>
      <img src="figures/matomo_visits_by_browser.png" alt="Visits by browser">
      <figcaption>Visits by browser.</figcaption>
    </figure>
  </div>
  <figure>
    <img src="figures/matomo_visits_by_operating_system.png" alt="Visits by operating system">
    <figcaption>Visits by operating system.</figcaption>
  </figure>
  <h2>Users, groups and workflow</h2>
  <p>
    This section gathers the main operational indicators related to users,
    groups and submission queues.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total users</span><strong>{user_group_workflow_snapshot['total_users']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Users never logged in</span><strong>{user_group_workflow_snapshot['users_never_logged_in']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Users inactive &gt; 12 months</span><strong>{user_group_workflow_snapshot['users_inactive_over_12_months']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Total groups</span><strong>{user_group_workflow_snapshot['total_groups']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Empty groups</span><strong>{user_group_workflow_snapshot['empty_groups']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Workspace items</span><strong>{user_group_workflow_snapshot['workspace_items']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Workflow items</span><strong>{user_group_workflow_snapshot['workflow_items']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Submissions stalled &gt; 30 days</span><strong>{user_group_workflow_snapshot['stalled_submissions_over_30_days']}</strong></div></div>
  </div>
  <h2>Files, bitstreams and technical integrity</h2>
  <p>
    This section measures the technical consistency of content: file availability,
    completeness of technical metadata and possible discrepancies between
    item visibility and visibility of linked bitstreams.
  </p>
  <div class="kpis my-4">
    <div class="kpi card shadow-sm"><div class="card-body"><span>Items without bitstreams</span><strong>{technical_integrity_snapshot['items_without_bitstreams']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Bitstreams with MIME type</span><strong>{technical_integrity_snapshot['bitstreams_with_mimetype']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Average bitstreams per item</span><strong>{technical_integrity_snapshot['average_bitstreams_per_item']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Bitstreams without checksum</span><strong>{technical_integrity_snapshot['bitstreams_without_checksum']}</strong></div></div>
    <div class="kpi card shadow-sm"><div class="card-body"><span>Non-public bitstreams</span><strong>{technical_integrity_snapshot['non_public_bitstreams']}</strong></div></div>
    <div class="kpi kpi-warning card shadow-sm"><div class="card-body"><span>Public items with non-public bitstreams</span><strong>{technical_integrity_snapshot['public_items_with_non_public_bitstreams']}</strong></div></div>
  </div>
  <div class="two-col">
    <figure>
      <img src="figures/total_size_per_collection.png" alt="Total size by collection">
      <figcaption>Total file size by collection.</figcaption>
    </figure>
    <figure>
      <img src="figures/downloads_by_mimetype.png" alt="Downloads by MIME type">
      <figcaption>Bitstream downloads by MIME type.</figcaption>
    </figure>
    <figure>
      <img src="figures/downloads_by_resource_type.png" alt="Downloads by resource type">
      <figcaption>Bitstream downloads by resource type.</figcaption>
    </figure>
  </div>
  <h3>Problematic bitstreams</h3>
  {problematic_bitstreams_table}
  <p class="mt-3">
    The table lists bitstreams with at least one technical issue:
    missing checksum, lack of public accessibility or membership in a public item
    that contains non-public bitstreams. Rows are kept by issue category, so the
    same bitstream may appear more than once if it falls under multiple conditions
    that need checking.
  </p>
</div>
</main>
{collapsible_sections_script()}
{tabbed_sections_script()}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()
    config = load_config(args.config)
    temp_root = project_root / config.get("paths", {}).get("temp_root", "data/temp")
    mpl_config_dir = temp_root / "matplotlib"
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    history = build_monthly_overview_history(project_root, config)

    if history.empty:
        print("No complete monthly history found across db, solr and matomo exports.")
        return 1

    configured_months = args.month or get_run_months(config)
    available_history_months = set(history["reference_month"].astype(str))
    report_months = [month for month in configured_months if month in available_history_months]
    unavailable_months = [month for month in configured_months if month not in available_history_months]

    if unavailable_months:
        print(
            "Skipping months without complete monthly exports across db, solr and matomo: "
            + ", ".join(unavailable_months)
        )
        for month in unavailable_months:
            missing_exports = missing_monthly_overview_exports(
                project_root, config, month
            )
            if missing_exports:
                missing_labels = ", ".join(
                    f"{source}/{filename}" for source, filename in missing_exports
                )
                print(f"  - {month}: missing {missing_labels}")

    if not report_months:
        print("No reportable months found.")
        return 1

    print("Months to report: " + ", ".join(report_months))
    if args.dry_run:
        return 0

    run_config = config.get("run", {})
    reporting_config = config.get("reporting", {})
    overwrite_reports = (
        args.overwrite_reports
        or run_config.get("overwrite_reports", False)
        or reporting_config.get("overwrite_reports", False)
    )
    institution_name = reporting_config.get("institution_name", "DSpace")
    institution_subtitle = reporting_config.get(
        "institution_subtitle", "Monthly institutional report"
    )
    archive_title = reporting_config.get(
        "archive_title", "Archivio dei report mensili"
    )
    quality_snapshot = build_latest_quality_snapshot(project_root, config)
    for reference_month in report_months:
        month_rows = history[history["reference_month"] == reference_month]
        history_until_reference_month = history[
            history["reference_month"] <= reference_month
        ]
        repository_snapshot = build_repository_snapshot_as_of_month(
            project_root,
            config,
            reference_month,
        )
        repository_organization_snapshot = build_repository_organization_snapshot_for_month(
            project_root,
            config,
            repository_snapshot["snapshot_month"],
        )
        monthly_oai_snapshot = build_oai_solr_exposure_snapshot_for_month(
            project_root,
            config,
            repository_snapshot["snapshot_month"],
        )
        user_group_workflow_snapshot = build_user_group_workflow_snapshot_for_month(
            project_root,
            config,
            repository_snapshot["snapshot_month"],
        )
        item_catalog = load_metric_csv(
            project_root,
            config,
            "solr",
            "always",
            repository_snapshot["snapshot_month"],
            "solr_total_oai_records.csv",
        )
        report_dir = get_month_report_dir(project_root, config, reference_month)
        if report_exists(report_dir) and not overwrite_reports:
            print(f"Skipping report for {reference_month}: report already exists.")
            continue

        figures_dir = get_month_figures_dir(project_root, config, reference_month)
        report_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)

        detail = build_monthly_detail(project_root, config, reference_month)
        enriched_detail = {
            **detail,
            "direct_visits_count": int(len(load_metric_csv(
                project_root,
                config,
                "matomo",
                "monthly",
                reference_month,
                "matomo_direct_visits_reference_month_details.csv",
            ))),
            "search_engines_visits_count": safe_sum(detail["search_engines"], "visits_count"),
            "websites_visits_count": safe_sum(detail["websites"], "visits_count"),
            "social_networks_visits_count": safe_sum(detail["social_networks"], "visits_count"),
            "campaign_visits_count": safe_sum(detail["campaigns"], "visits_count"),
            "total_actions_count": safe_sum(detail["actions_per_visit"], "actions_count"),
            "average_visit_duration_seconds": int(
                detail["average_visit_duration"]["average_visit_duration_seconds"].iloc[0]
            ),
            "bounce_rate": str(detail["bounce_rate"]["bounce_rate"].iloc[0]),
            "actions_per_visit_value": float(
                detail["actions_per_visit"]["actions_per_visit"].iloc[0]
            ),
            "total_searches_count": safe_sum(
                detail["total_searches_by_bot_status"],
                "total_events",
            ),
            "monthly_oai_records_count": int(len(detail["monthly_oai_records"])),
            "active_users_count": int(len(detail["active_users_in_month"])),
        }
        item_lookup = {
            str(row["item_id"]): {
                "title": str(row.get("title", "")),
                "item_handle": str(row.get("item_handle", "") or ""),
            }
            for _, row in item_catalog.iterrows()
        }
        for key in [
            "top_viewed_items",
            "top_downloaded_items",
            "view_download_ratio",
            "uploaded_items_with_bitstreams",
            "uploaded_items_details",
            "workflow_approval_timeline",
        ]:
            enriched_detail[key] = add_item_resource_column(enriched_detail[key], item_lookup)
        uploaded_item_ids = set(enriched_detail["uploaded_items_details"]["item_id"].astype(str))
        enriched_detail["workflow_approval_timeline"] = enriched_detail[
            "workflow_approval_timeline"
        ][enriched_detail["workflow_approval_timeline"]["item_id"].astype(str).isin(uploaded_item_ids)]
        save_monthly_overview_chart(
            history_until_reference_month,
            figures_dir / "monthly_overview.png",
        )
        save_top_collections_chart(
            detail["uploads_by_collection"], figures_dir / "top_collections.png"
        )
        save_bar_chart(
            detail["uploads_by_submitter"],
            label_column="submitter_email",
            value_column="total_items",
            title="Items uploaded by submitter",
            ylabel="Item",
            output_path=figures_dir / "uploads_by_submitter.png",
            limit=None,
        )
        save_bar_chart(
            detail["uploads_by_collection"],
            label_column="collection_name",
            value_column="total_items",
            title="Items uploaded by collection",
            ylabel="Item",
            output_path=figures_dir / "uploads_by_collection.png",
            limit=None,
        )
        save_bar_chart(
            detail["uploads_by_language"],
            label_column="language",
            value_column="total_items",
            title="Items uploaded by language",
            ylabel="Item",
            output_path=figures_dir / "uploads_by_language.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["active_collections"],
            label_column="collection_name",
            value_column="total_activity_score",
            title="Most active collections in the reference month",
            xlabel="Punteggio attività",
            output_path=figures_dir / "most_active_collections.png",
        )
        save_visits_by_country_chart(
            detail["visits_by_country"], figures_dir / "top_countries.png"
        )
        save_horizontal_bar_chart(
            detail["visits_by_continent"],
            label_column="continent",
            value_column="visits_count",
            title="Visits by continent in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_visits_by_continent.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["visits_by_country"],
            label_column="country",
            value_column="visits_count",
            title="Visits by country in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_visits_by_country.png",
            limit=20,
        )
        save_page_typology_chart(
            detail["page_typology"], figures_dir / "page_typology.png"
        )
        nonzero_device_types = detail["visits_by_device_type"][
            detail["visits_by_device_type"]["visits_count"] > 0
        ]
        save_horizontal_bar_chart(
            nonzero_device_types,
            label_column="device_type",
            value_column="visits_count",
            title="Visits by device type in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_visits_by_device_type.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["visits_by_browser"],
            label_column="browser",
            value_column="visits_count",
            title="Visits by browser in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_visits_by_browser.png",
        )
        save_horizontal_bar_chart(
            detail["visits_by_operating_system"],
            label_column="operating_system",
            value_column="visits_count",
            title="Visits by operating system in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_visits_by_operating_system.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["views_by_collection"],
            label_column="collection_id",
            value_column="views_count",
            title="Views by collection in the reference month",
            xlabel="Views",
            output_path=figures_dir / "monthly_views_by_collection.png",
        )
        save_bar_chart(
            detail["views_by_community"],
            label_column="community_name",
            value_column="views_count",
            title="Views by community in the reference month",
            ylabel="Views",
            output_path=figures_dir / "monthly_views_by_community.png",
            limit=None,
        )
        save_bar_chart(
            detail["downloads_by_community"],
            label_column="community_name",
            value_column="downloads_count",
            title="Downloads by community in the reference month",
            ylabel="Download",
            output_path=figures_dir / "monthly_downloads_by_community.png",
            limit=None,
        )
        save_bar_chart(
            detail["downloads_by_license"],
            label_column="license_label",
            value_column="downloads_count",
            title="Downloads by license in the reference month",
            ylabel="Download",
            output_path=figures_dir / "monthly_downloads_by_license.png",
            limit=None,
        )
        save_bar_chart(
            detail["downloads_by_resource_type"],
            label_column="resource_type",
            value_column="downloads_count",
            title="Downloads by resource type in the reference month",
            ylabel="Download",
            output_path=figures_dir / "monthly_downloads_by_resource_type.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["downloads_by_mimetype"],
            label_column="mimetype",
            value_column="downloads_count",
            title="Downloads by MIME type in the reference month",
            xlabel="Download",
            output_path=figures_dir / "monthly_downloads_by_mimetype.png",
        )
        save_horizontal_bar_chart(
            detail["most_searched_terms"],
            label_column="searched_term",
            value_column="events_count",
            title="Most searched terms in the reference month",
            xlabel="Searches",
            output_path=figures_dir / "monthly_most_searched_terms.png",
            limit=20,
        )
        save_bar_chart(
            detail["search_engine_events"],
            label_column="search_engine",
            value_column="events_count",
            title="Solr accesses from search engines in the reference month",
            ylabel="Events",
            output_path=figures_dir / "monthly_solr_search_engine_events.png",
            limit=None,
        )
        save_bar_chart(
            detail["search_engines"],
            label_column="search_engine",
            value_column="visits_count",
            title="Matomo visits from search engines in the reference month",
            ylabel="Visits",
            output_path=figures_dir / "monthly_matomo_visits_from_search_engines.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            detail["websites"],
            label_column="website",
            value_column="visits_count",
            title="Matomo visits from websites in the reference month",
            xlabel="Visits",
            output_path=figures_dir / "monthly_matomo_visits_from_websites.png",
        )
        save_stacked_bar_chart(
            detail["bot_events_by_type"],
            label_column="statistics_type",
            stack_column="object_type_label",
            value_column="events_count",
            title="Bot events in the reference month by event and object type",
            ylabel="Events",
            output_path=figures_dir / "monthly_bot_events_by_type.png",
            limit=None,
        )
        save_stacked_bar_chart(
            detail["internal_events_by_type"],
            label_column="statistics_type",
            stack_column="object_type_label",
            value_column="events_count",
            title="Internal events in the reference month by event and object type",
            ylabel="Events",
            output_path=figures_dir / "monthly_internal_events_by_type.png",
            limit=None,
        )
        ratio_frame = detail["internal_external_ratio"].copy()
        ratio_frame["event_bot_label"] = (
            ratio_frame["statistics_type"].astype(str)
            + " · "
            + ratio_frame["bot_status"].astype(str)
        )
        save_stacked_bar_chart(
            ratio_frame,
            label_column="event_bot_label",
            stack_column="network_scope",
            value_column="events_count",
            title="Internal/external ratio in the reference month",
            ylabel="Events",
            output_path=figures_dir / "monthly_internal_external_ratio.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            repository_organization_snapshot["items_per_collection"],
            label_column="collection_name",
            value_column="items_count",
            title="Item per collection",
            xlabel="Item",
            output_path=figures_dir / "items_per_collection.png",
        )
        save_horizontal_bar_chart(
            repository_organization_snapshot["total_size_per_collection"],
            label_column="collection_name",
            value_column="total_size_gb",
            title="Total size by collection",
            xlabel="GB",
            output_path=figures_dir / "size_per_collection.png",
        )

        logo_relative_path = resolve_logo_relative_path(
            project_root, config, report_dir
        )
        latest_row = month_rows.iloc[0].to_dict()
        existing_report_months = {
            path.name
            for path in get_month_report_dir(project_root, config, reference_month).parents[1]
            .joinpath("monthly")
            .iterdir()
            if path.is_dir() and report_exists(path)
        }
        navigation_months = resolve_navigation_months(existing_report_months, report_months)
        month_index = navigation_months.index(reference_month)
        previous_month = navigation_months[month_index - 1] if month_index > 0 else None
        next_month = (
            navigation_months[month_index + 1]
            if month_index + 1 < len(navigation_months)
            else None
        )
        (report_dir / "report.html").write_text(
            render_report_html(
                reference_month=reference_month,
                institution_name=institution_name,
                  institution_subtitle=institution_subtitle,
                  latest_row=latest_row,
                  logo_relative_path=logo_relative_path,
                  home_href="../../index.html",
                  quality_snapshot=quality_snapshot,
                repository_snapshot=repository_snapshot,
                repository_organization_snapshot=repository_organization_snapshot,
                monthly_oai_snapshot=monthly_oai_snapshot,
                user_group_workflow_snapshot=user_group_workflow_snapshot,
                detail=enriched_detail,
                previous_month=previous_month,
                next_month=next_month,
            ),
            encoding="utf-8",
        )
        manifest = {
            "reference_month": reference_month,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "institution_name": institution_name,
            "institution_subtitle": institution_subtitle,
            "logo": logo_relative_path,
            "outputs": [
                "report.html",
                "figures/monthly_overview.png",
                "figures/top_collections.png",
                "figures/uploads_by_submitter.png",
                "figures/uploads_by_collection.png",
                "figures/uploads_by_language.png",
                "figures/most_active_collections.png",
                "figures/top_countries.png",
                "figures/monthly_visits_by_continent.png",
                "figures/monthly_visits_by_country.png",
                "figures/page_typology.png",
                "figures/monthly_visits_by_device_type.png",
                "figures/monthly_visits_by_browser.png",
                "figures/monthly_visits_by_operating_system.png",
                "figures/monthly_views_by_collection.png",
                "figures/monthly_views_by_community.png",
                "figures/monthly_downloads_by_community.png",
                "figures/monthly_downloads_by_license.png",
                "figures/monthly_downloads_by_resource_type.png",
                "figures/monthly_downloads_by_mimetype.png",
                "figures/monthly_most_searched_terms.png",
                "figures/monthly_solr_search_engine_events.png",
                "figures/monthly_matomo_visits_from_search_engines.png",
                "figures/monthly_matomo_visits_from_websites.png",
                "figures/monthly_bot_events_by_type.png",
                "figures/monthly_internal_events_by_type.png",
                "figures/monthly_internal_external_ratio.png",
                "figures/items_per_collection.png",
                "figures/size_per_collection.png",
            ],
        }
        (report_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        print(f"Report written to: {report_dir}")

    always_months = sorted(
        set(available_months(project_root, config, "db", scope="always"))
        & set(available_months(project_root, config, "solr", scope="always"))
        & set(available_months(project_root, config, "matomo", scope="always"))
    )
    for reference_month in always_months:
        always_report_dir = get_always_report_dir(project_root, config, reference_month)
        if report_exists(always_report_dir) and not overwrite_reports:
            print(f"Skipping always report for {reference_month}: report already exists.")
            continue
        always_report_dir.mkdir(parents=True, exist_ok=True)
        logo_relative_path = resolve_logo_relative_path(
            project_root, config, always_report_dir
        )
        always_repository_snapshot = build_repository_snapshot_for_month(
            project_root, config, reference_month
        )
        always_repository_organization_snapshot = build_repository_organization_snapshot_for_month(
            project_root, config, reference_month
        )
        always_quality_snapshot = build_quality_snapshot_for_month(
            project_root, config, reference_month
        )
        always_item_publication_snapshot = build_item_publication_snapshot_for_month(
            project_root, config, reference_month
        )
        always_metadata_quality_snapshot = build_metadata_quality_snapshot_for_month(
            project_root, config, reference_month
        )
        always_oai_solr_exposure_snapshot = build_oai_solr_exposure_snapshot_for_month(
            project_root, config, reference_month
        )
        always_historical_usage_snapshot = build_historical_repository_usage_snapshot_for_month(
            project_root, config, reference_month
        )
        always_access_referrer_snapshot = build_access_referrer_snapshot_for_month(
            project_root, config, reference_month
        )
        always_event_quality_snapshot = build_event_quality_snapshot_for_month(
            project_root, config, reference_month
        )
        always_internal_search_snapshot = build_internal_search_snapshot_for_month(
            project_root, config, reference_month
        )
        always_matomo_web_traffic_snapshot = build_matomo_web_traffic_snapshot_for_month(
            project_root, config, reference_month
        )
        always_access_geography_snapshot = build_access_geography_snapshot_for_month(
            project_root, config, reference_month
        )
        always_device_technology_snapshot = build_device_technology_snapshot_for_month(
            project_root, config, reference_month
        )
        always_user_group_workflow_snapshot = build_user_group_workflow_snapshot_for_month(
            project_root, config, reference_month
        )
        always_technical_integrity_snapshot = build_technical_integrity_snapshot_for_month(
            project_root, config, reference_month
        )
        always_figures_dir = always_report_dir / "figures"
        save_item_publication_status_chart(
            always_item_publication_snapshot["status_counts"],
            always_figures_dir / "item_publication_status.png",
        )
        save_bar_chart(
            always_repository_organization_snapshot["items_per_community"],
            label_column="community_name",
            value_column="items_count",
            title="Item per community",
            ylabel="Item",
            output_path=always_figures_dir / "items_per_community.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_repository_organization_snapshot["items_per_collection"],
            label_column="collection_name",
            value_column="items_count",
            title="Item per collection",
            xlabel="Item",
            output_path=always_figures_dir / "items_per_collection.png",
        )
        save_horizontal_bar_chart(
            always_repository_organization_snapshot["total_size_per_collection"],
            label_column="collection_name",
            value_column="total_size_gb",
            title="Total size by collection",
            xlabel="GB",
            output_path=always_figures_dir / "organization_size_per_collection.png",
        )
        save_horizontal_bar_chart(
            always_oai_solr_exposure_snapshot["index_size_by_core"],
            label_column="core_logical_name",
            value_column="index_size_bytes",
            title="Index size per core Solr",
            xlabel="Byte",
            output_path=always_figures_dir / "solr_index_size_by_core.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_oai_solr_exposure_snapshot["record_count_by_core"],
            label_column="core_logical_name",
            value_column="records_count",
            title="Record per core Solr",
            xlabel="Record",
            output_path=always_figures_dir / "solr_record_count_by_core.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_historical_usage_snapshot["views_by_collection"],
            label_column="collection_label",
            value_column="views_count",
            title="Views storiche per collection",
            xlabel="Views",
            output_path=always_figures_dir / "historical_views_by_collection.png",
        )
        save_horizontal_bar_chart(
            always_historical_usage_snapshot["downloads_by_collection"],
            label_column="collection_label",
            value_column="downloads_count",
            title="Download storici per collection",
            xlabel="Download",
            output_path=always_figures_dir / "historical_downloads_by_collection.png",
        )
        save_bar_chart(
            always_historical_usage_snapshot["views_by_community"],
            label_column="community_label",
            value_column="views_count",
            title="Views storiche per community",
            ylabel="Views",
            output_path=always_figures_dir / "historical_views_by_community.png",
            limit=None,
        )
        save_bar_chart(
            always_historical_usage_snapshot["downloads_by_community"],
            label_column="community_label",
            value_column="downloads_count",
            title="Download storici per community",
            ylabel="Download",
            output_path=always_figures_dir / "historical_downloads_by_community.png",
            limit=None,
        )
        save_stacked_bar_chart(
            always_access_referrer_snapshot["top_referrers_by_bot_status"],
            label_column="referrer_normalized",
            stack_column="bot_status",
            value_column="events_count",
            title="Top referrer Solr per bot status",
            ylabel="Events",
            output_path=always_figures_dir / "solr_top_referrers_by_bot_status.png",
        )
        save_bar_chart(
            always_access_referrer_snapshot["search_engine_events"],
            label_column="search_engine",
            value_column="events_count",
            title="Solr accesses from search engines",
            ylabel="Events",
            output_path=always_figures_dir / "solr_accesses_from_search_engines.png",
            limit=None,
        )
        save_bar_chart(
            always_access_referrer_snapshot["visits_from_search_engines"],
            label_column="search_engine",
            value_column="visits_count",
            title="Matomo visits from search engines",
            ylabel="Visits",
            output_path=always_figures_dir / "matomo_visits_from_search_engines.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_access_referrer_snapshot["visits_from_websites"],
            label_column="website",
            value_column="visits_count",
            title="Matomo visits from websites",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_visits_from_websites.png",
        )
        save_stacked_bar_chart(
            always_event_quality_snapshot["bot_events_by_type"],
            label_column="statistics_type",
            stack_column="object_type_label",
            value_column="events_count",
            title="Bot events by event and object type",
            ylabel="Events",
            output_path=always_figures_dir / "bot_events_by_event_and_object_type.png",
            limit=None,
        )
        save_stacked_bar_chart(
            always_event_quality_snapshot["internal_events_by_type"],
            label_column="statistics_type",
            stack_column="object_type_label",
            value_column="events_count",
            title="Internal events by event and object type",
            ylabel="Events",
            output_path=always_figures_dir / "internal_events_by_event_and_object_type.png",
            limit=None,
        )
        save_stacked_bar_chart(
            always_event_quality_snapshot["internal_external_ratio"],
            label_column="event_bot_label",
            stack_column="network_scope",
            value_column="events_count",
            title="Internal and external events ratio",
            ylabel="Events",
            output_path=always_figures_dir / "internal_external_events_ratio.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_internal_search_snapshot["most_searched_terms"],
            label_column="searched_term",
            value_column="events_count",
            title="Termini più cercati",
            xlabel="Searches",
            output_path=always_figures_dir / "most_searched_terms.png",
            limit=20,
        )
        save_line_chart(
            always_matomo_web_traffic_snapshot["unique_visitors_by_month"],
            x_column="month",
            y_column="unique_visitors_count",
            title="Matomo unique visitors by month",
            ylabel="Unique visitors",
            output_path=always_figures_dir / "matomo_unique_visitors_by_month.png",
        )
        save_horizontal_bar_chart(
            always_matomo_web_traffic_snapshot["page_typology"],
            label_column="page_typology",
            value_column="pageviews_count",
            title="Pageview typology",
            xlabel="Pageviews",
            output_path=always_figures_dir / "matomo_page_typology.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_access_geography_snapshot["continents"],
            label_column="continent",
            value_column="visits_count",
            title="Visits by continent",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_visits_by_continent.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_access_geography_snapshot["top_countries"],
            label_column="country",
            value_column="visits_count",
            title="Top countries by visits",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_top_countries.png",
        )
        save_horizontal_bar_chart(
            always_device_technology_snapshot["device_types"],
            label_column="device_type",
            value_column="visits_count",
            title="Visits by device type",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_visits_by_device_type.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_device_technology_snapshot["browsers"],
            label_column="browser",
            value_column="visits_count",
            title="Visits by browser",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_visits_by_browser.png",
        )
        save_horizontal_bar_chart(
            always_device_technology_snapshot["operating_systems"],
            label_column="operating_system",
            value_column="visits_count",
            title="Visits by operating system",
            xlabel="Visits",
            output_path=always_figures_dir / "matomo_visits_by_operating_system.png",
        )
        save_horizontal_bar_chart(
            always_metadata_quality_snapshot["oai_missing_fields_counts"],
            label_column="missing_field",
            value_column="records_count",
            title="OAI records by missing field",
            xlabel="OAI records",
            output_path=always_figures_dir / "oai_missing_fields.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_metadata_quality_snapshot["licenses_per_collection"],
            label_column="collection_name",
            value_column="license_assignments_count",
            title="Licenses by collection",
            xlabel="License assignments",
            output_path=always_figures_dir / "licenses_per_collection.png",
        )
        save_horizontal_bar_chart(
            always_metadata_quality_snapshot["licenses_per_community"],
            label_column="community_name",
            value_column="license_assignments_count",
            title="Licenses by community",
            xlabel="License assignments",
            output_path=always_figures_dir / "licenses_per_community.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_metadata_quality_snapshot["licenses_per_resource_type"],
            label_column="item_type",
            value_column="license_assignments_count",
            title="Licenses by resource type",
            xlabel="License assignments",
            output_path=always_figures_dir / "licenses_per_resource_type.png",
            limit=None,
        )
        save_horizontal_bar_chart(
            always_technical_integrity_snapshot["total_size_per_collection"],
            label_column="collection_name",
            value_column="total_size_gb",
            title="Total size by collection",
            xlabel="GB",
            output_path=always_figures_dir / "total_size_per_collection.png",
        )
        save_horizontal_bar_chart(
            always_technical_integrity_snapshot["downloads_by_mimetype"],
            label_column="mimetype",
            value_column="downloads_count",
            title="Downloads by MIME type",
            xlabel="Download",
            output_path=always_figures_dir / "downloads_by_mimetype.png",
        )
        save_horizontal_bar_chart(
            always_technical_integrity_snapshot["downloads_by_resource_type"],
            label_column="resource_type",
            value_column="downloads_count",
            title="Downloads by resource type",
            xlabel="Download",
            output_path=always_figures_dir / "downloads_by_resource_type.png",
            limit=None,
        )
        (always_report_dir / "report.html").write_text(
            render_always_report_html(
                reference_month=reference_month,
                  institution_name=institution_name,
                  institution_subtitle=institution_subtitle,
                  logo_relative_path=logo_relative_path,
                  home_href="../../index.html",
                  repository_snapshot=always_repository_snapshot,
                  repository_organization_snapshot=always_repository_organization_snapshot,
                  item_publication_snapshot=always_item_publication_snapshot,
                  metadata_quality_snapshot=always_metadata_quality_snapshot,
                  oai_solr_exposure_snapshot=always_oai_solr_exposure_snapshot,
                  historical_usage_snapshot=always_historical_usage_snapshot,
                  access_referrer_snapshot=always_access_referrer_snapshot,
                  event_quality_snapshot=always_event_quality_snapshot,
                  internal_search_snapshot=always_internal_search_snapshot,
                  matomo_web_traffic_snapshot=always_matomo_web_traffic_snapshot,
                  access_geography_snapshot=always_access_geography_snapshot,
                  device_technology_snapshot=always_device_technology_snapshot,
                  user_group_workflow_snapshot=always_user_group_workflow_snapshot,
                  technical_integrity_snapshot=always_technical_integrity_snapshot,
                quality_snapshot=always_quality_snapshot,
            ),
            encoding="utf-8",
        )
        print(f"Always report written to: {always_report_dir}")

    reports_root = get_month_report_dir(project_root, config, report_months[0]).parents[1]
    generated_monthly_months = sorted(
        path.name
        for path in (reports_root / "monthly").iterdir()
        if path.is_dir() and (path / "report.html").exists()
    )
    generated_always_months = sorted(
        path.name
        for path in (reports_root / "always").iterdir()
        if path.is_dir() and (path / "report.html").exists()
    ) if (reports_root / "always").exists() else []
    (reports_root / "index.html").write_text(
        render_reports_index_html(
            institution_name=institution_name,
            institution_subtitle=institution_subtitle,
            archive_title=archive_title,
            monthly_report_months=generated_monthly_months,
            always_report_months=generated_always_months,
              logo_relative_path=resolve_logo_relative_path(
                  project_root, config, reports_root
              ),
              home_href="index.html",
        ),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
