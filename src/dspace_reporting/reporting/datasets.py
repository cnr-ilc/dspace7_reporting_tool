"""Reusable analytical datasets shared by reports and future dashboards."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd

from .loaders import available_months, load_metric_csv, metric_path


MONTHLY_OVERVIEW_REQUIRED_EXPORTS = (
    ("db", "db_items_uploaded_in_month_details.csv"),
    ("matomo", "matomo_visits_reference_month.csv"),
    ("matomo", "matomo_pageviews_reference_month_action_details.csv"),
    ("solr", "solr_views_downloads_ratio_by_item_reference_month.csv"),
)


def has_complete_monthly_overview_exports(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> bool:
    return all(
        metric_path(
            project_root=project_root,
            config=config,
            source=source,
            scope="monthly",
            reference_month=reference_month,
            filename=filename,
        ).exists()
        for source, filename in MONTHLY_OVERVIEW_REQUIRED_EXPORTS
    )


def missing_monthly_overview_exports(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> list[tuple[str, str]]:
    return [
        (source, filename)
        for source, filename in MONTHLY_OVERVIEW_REQUIRED_EXPORTS
        if not metric_path(
            project_root=project_root,
            config=config,
            source=source,
            scope="monthly",
            reference_month=reference_month,
            filename=filename,
        ).exists()
    ]


def build_monthly_overview_history(
    project_root: Path,
    config: dict[str, Any],
) -> pd.DataFrame:
    months = sorted(
        set(available_months(project_root, config, "db"))
        & set(available_months(project_root, config, "solr"))
        & set(available_months(project_root, config, "matomo"))
    )

    rows: list[dict[str, Any]] = []
    for month in months:
        if not has_complete_monthly_overview_exports(project_root, config, month):
            continue
        uploaded_items = load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            month,
            "db_items_uploaded_in_month_details.csv",
        )
        visits = load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            month,
            "matomo_visits_reference_month.csv",
        )
        pageviews = load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            month,
            "matomo_pageviews_reference_month_action_details.csv",
        )
        item_usage = load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            month,
            "solr_views_downloads_ratio_by_item_reference_month.csv",
        )

        rows.append(
            {
                "reference_month": month,
                "items_uploaded": int(len(uploaded_items)),
                "visits": int(len(visits)),
                "pageviews": int(len(pageviews)),
                "item_views": int(item_usage["views_count"].sum()),
                "downloads": int(item_usage["downloads_count"].sum()),
            }
        )

    return pd.DataFrame(rows)


def build_monthly_detail(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, pd.DataFrame]:
    modified_events = load_metric_csv(
        project_root,
        config,
        "db",
        "monthly",
        reference_month,
        "db_items_modified_in_month_from_provenance.csv",
    )
    modified_events["event_timestamp"] = pd.to_datetime(
        modified_events["event_line"].astype(str).str.extract(
            r"on ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+)Z",
            expand=False,
        ),
        errors="coerce",
        utc=True,
    )
    workflow_rows: list[dict[str, Any]] = []
    for item_id, group in modified_events.groupby("item_id"):
        submitted = group[group["event_type"].eq("submitted")]["event_timestamp"].min()
        approvals = (
            group[group["event_type"].eq("workflow_approval")]
            .sort_values("event_timestamp")
            .loc[:, ["event_timestamp", "event_line"]]
        )
        available = group[group["event_type"].eq("made_available")]["event_timestamp"].min()
        approval_times = approvals["event_timestamp"].tolist()
        workflow_rows.append(
            {
                "item_id": item_id,
                "submitted_at": submitted,
                "first_approval_at": approval_times[0] if len(approval_times) > 0 else pd.NaT,
                "second_approval_at": approval_times[1] if len(approval_times) > 1 else pd.NaT,
                "final_approval_at": approval_times[-1] if approval_times else pd.NaT,
                "made_available_at": available,
                "approval_steps_count": len(approval_times),
                "submitted_to_first_approval_hours": round(
                    (approval_times[0] - submitted).total_seconds() / 3600, 2
                )
                if len(approval_times) > 0 and pd.notna(submitted)
                else None,
                "first_to_final_approval_hours": round(
                    (approval_times[-1] - approval_times[0]).total_seconds() / 3600, 2
                )
                if len(approval_times) > 1
                else None,
                "submitted_to_available_hours": round(
                    (available - submitted).total_seconds() / 3600, 2
                )
                if pd.notna(submitted) and pd.notna(available)
                else None,
            }
        )
    workflow_timeline = pd.DataFrame(workflow_rows)

    return {
        "uploads_by_collection": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_items_uploaded_in_month_by_collection.csv",
        ),
        "uploaded_items_with_bitstreams": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_items_uploaded_in_month_with_bitstreams.csv",
        ),
        "uploads_by_submitter": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_items_uploaded_in_month_by_submitter.csv",
        ),
        "uploads_by_language": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_items_uploaded_in_month_by_language.csv",
        ),
        "uploaded_items_details": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_items_uploaded_in_month_details.csv",
        ),
        "average_file_size": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_avg_file_size_month.csv",
        ),
        "active_collections": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_active_collections_combined_in_month.csv",
        ),
        "modified_events": modified_events,
        "workflow_approval_timeline": workflow_timeline,
        "views_by_collection": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_views_by_collection_reference_month.csv",
        ),
        "views_by_community": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_views_by_current_community_reference_month.csv",
        ),
        "downloads_by_community": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_downloads_by_community_reference_month.csv",
        ),
        "downloads_by_license": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_downloads_by_license_reference_month.csv",
        ),
        "view_download_ratio": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_views_downloads_ratio_by_item_reference_month.csv",
        ),
        "visits_by_country": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_country_reference_month.csv",
        ),
        "visits_by_city": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_city_reference_month.csv",
        ),
        "visits_by_continent": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_continent_reference_month.csv",
        ),
        "page_typology": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_typology_of_page_views_reference_month.csv",
        ),
        "visits_by_device_type": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_device_type_reference_month.csv",
        ),
        "visits_by_browser": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_browser_reference_month.csv",
        ),
        "visits_by_operating_system": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_by_operating_system_reference_month.csv",
        ),
        "average_visit_duration": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_average_visit_duration_reference_month.csv",
        ),
        "bounce_rate": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_bounce_rate_reference_month.csv",
        ),
        "actions_per_visit": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_actions_per_visit_reference_month.csv",
        ),
        "top_viewed_items": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_top_items_reference_month.csv",
        ),
        "top_downloaded_items": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_top_downloaded_items_reference_month.csv",
        ),
        "downloads_by_resource_type": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_downloads_by_resource_type_reference_month.csv",
        ),
        "downloads_by_mimetype": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_downloads_by_mimetype_reference_month.csv",
        ),
        "search_engines": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_from_search_engines_reference_month.csv",
        ),
        "websites": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_from_websites_reference_month.csv",
        ),
        "social_networks": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_visits_from_social_networks_reference_month.csv",
        ),
        "campaigns": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_campaign_visits_reference_month.csv",
        ),
        "total_searches_by_bot_status": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_total_searches_reference_month_by_bot_status.csv",
        ),
        "search_details": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_total_searches_details_reference_month.csv",
        ),
        "most_searched_terms": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_most_searched_terms_reference_month.csv",
        ),
        "top_referrers": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_top_referrers_reference_month.csv",
        ),
        "search_engine_events": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_accesses_from_search_engines_reference_month.csv",
        ),
        "user_agents_by_bot_status": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_most_frequent_user_agents_reference_month_by_bot_status.csv",
        ),
        "ips_dns": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_most_frequent_ips_dns_reference_month.csv",
        ),
        "top_referrer_websites": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_top_referrer_websites_reference_month.csv",
        ),
        "bot_events_by_type": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_bot_events_reference_month_by_type.csv",
        ),
        "bot_user_agents": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_most_frequent_bot_user_agents_reference_month.csv",
        ),
        "internal_events_by_type": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_internal_events_192_168_reference_month_by_type.csv",
        ),
        "internal_external_ratio": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_internal_external_events_ratio_reference_month_by_bot_status_and_type.csv",
        ),
        "top_visited_pages": load_metric_csv(
            project_root,
            config,
            "matomo",
            "monthly",
            reference_month,
            "matomo_top_visited_pages_reference_month.csv",
        ),
        "monthly_oai_records": load_metric_csv(
            project_root,
            config,
            "solr",
            "monthly",
            reference_month,
            "solr_total_oai_records_reference_month.csv",
        ),
        "active_users_in_month": load_metric_csv(
            project_root,
            config,
            "db",
            "monthly",
            reference_month,
            "db_active_users_in_month_last_active.csv",
        ),
    }


def build_latest_quality_snapshot(
    project_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    months = available_months(project_root, config, "db", scope="always")
    if not months:
        return {}

    snapshot_month = months[-1]
    missing_metadata = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_missing_metadata.csv",
    )
    items_without_files = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_without_files.csv",
    )
    invalid_licenses = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_invalid_license.csv",
    )
    stalled_submissions = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_stalled_submissions_over_30_days.csv",
    )
    return {
        "snapshot_month": snapshot_month,
        "items_missing_metadata": int(len(missing_metadata)),
        "items_without_files": int(len(items_without_files)),
        "items_invalid_license": int(len(invalid_licenses)),
        "stalled_submissions_over_30_days": int(len(stalled_submissions)),
    }


def build_latest_repository_snapshot(
    project_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    months = available_months(project_root, config, "db", scope="always")
    if not months:
        return {}

    snapshot_month = months[-1]
    items = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_all_items_by_archive_status.csv",
    )
    communities = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_total_communities.csv",
    )
    collections = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_total_collections.csv",
    )
    users = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_all_users.csv",
    )
    groups = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_total_groups.csv",
    )
    licenses = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_by_license.csv",
    )
    bitstreams = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_bitstreams_with_filename_extension.csv",
    )
    collection_sizes = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_total_size_per_collection.csv",
    )
    items_without_handle = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_without_handle_all_statuses.csv",
    )
    items_without_files = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_items_without_files.csv",
    )
    oai_records = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        snapshot_month,
        "solr_total_oai_records.csv",
    )

    return {
        "snapshot_month": snapshot_month,
        "items_total": int(len(items)),
        "items_archived": int(items["in_archive"].sum()),
        "items_publicly_reachable": int(
            items["publicly_reachable_candidate"].sum()
        ),
        "communities_total": int(len(communities)),
        "collections_total": int(len(collections)),
        "users_total": int(len(users)),
        "groups_total": int(len(groups)),
        "licenses_total": int(len(licenses)),
        "bitstreams_total": int(len(bitstreams)),
        "files_total_size_gb": round(float(collection_sizes["total_size_gb"].sum()), 2),
        "items_with_handle": int(len(items) - len(items_without_handle)),
        "items_with_files": int(items["in_archive"].sum() - len(items_without_files)),
        "oai_records_total": int(len(oai_records)),
    }


def build_repository_snapshot_as_of_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    latest_snapshot = build_latest_repository_snapshot(project_root, config)
    if not latest_snapshot:
        return {}

    snapshot_month = latest_snapshot["snapshot_month"]
    items = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        snapshot_month,
        "db_all_items_by_archive_status.csv",
    )
    if "deposit_date" not in items.columns:
        raise ValueError(
            "db_all_items_by_archive_status.csv is missing deposit_date. "
            "Regenerate DB always exports before building monthly reports."
        )

    month_end = pd.Period(reference_month, freq="M").end_time.normalize()
    deposit_dates = pd.to_datetime(items["deposit_date"], errors="coerce")
    items_as_of = items[deposit_dates.notna() & (deposit_dates <= month_end)]

    return {
        **latest_snapshot,
        "as_of_month": reference_month,
        "items_total": int(len(items_as_of)),
        "items_archived": int(items_as_of["in_archive"].sum()),
        "items_publicly_reachable": int(
            items_as_of["publicly_reachable_candidate"].sum()
        ),
        "items_without_deposit_date": int(deposit_dates.isna().sum()),
    }


def build_repository_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    items = load_metric_csv(project_root, config, "db", "always", reference_month, "db_all_items_by_archive_status.csv")
    communities = load_metric_csv(project_root, config, "db", "always", reference_month, "db_total_communities.csv")
    collections = load_metric_csv(project_root, config, "db", "always", reference_month, "db_total_collections.csv")
    users = load_metric_csv(project_root, config, "db", "always", reference_month, "db_all_users.csv")
    groups = load_metric_csv(project_root, config, "db", "always", reference_month, "db_total_groups.csv")
    licenses = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_by_license.csv")
    bitstreams = load_metric_csv(project_root, config, "db", "always", reference_month, "db_bitstreams_with_filename_extension.csv")
    collection_sizes = load_metric_csv(project_root, config, "db", "always", reference_month, "db_total_size_per_collection.csv")
    items_without_handle = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_handle_all_statuses.csv")
    items_without_files = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_files.csv")
    oai_records = load_metric_csv(project_root, config, "solr", "always", reference_month, "solr_total_oai_records.csv")
    return {
        "snapshot_month": reference_month,
        "items_total": int(len(items)),
        "items_archived": int(items["in_archive"].sum()),
        "items_publicly_reachable": int(items["publicly_reachable_candidate"].sum()),
        "communities_total": int(len(communities)),
        "collections_total": int(len(collections)),
        "users_total": int(len(users)),
        "groups_total": int(len(groups)),
        "licenses_total": int(len(licenses)),
        "bitstreams_total": int(len(bitstreams)),
        "files_total_size_gb": round(float(collection_sizes["total_size_gb"].sum()), 2),
        "items_with_handle": int(len(items) - len(items_without_handle)),
        "items_with_files": int(items["in_archive"].sum() - len(items_without_files)),
        "oai_records_total": int(len(oai_records)),
    }


def build_repository_organization_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    communities = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_communities.csv"
    )
    collections = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_collections.csv"
    )
    collection_sizes = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_size_per_collection.csv"
    )
    collection_groups = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_collection_groups.csv"
    )

    collection_inventory = collections.loc[
        :, ["collection_id", "collection_name", "community_id", "community_name"]
    ].merge(
        collection_sizes.loc[
            :,
            [
                "collection_id",
                "items_count",
                "bitstreams_count",
                "total_size_gb",
            ],
        ],
        on="collection_id",
        how="left",
    )
    for column in ["items_count", "bitstreams_count", "total_size_gb"]:
        collection_inventory[column] = pd.to_numeric(
            collection_inventory[column], errors="coerce"
        ).fillna(0)

    communities["collections_count"] = pd.to_numeric(
        communities["collections_count"], errors="coerce"
    ).fillna(0)

    community_item_totals = (
        collection_inventory.groupby("community_name", dropna=False)["items_count"]
        .sum()
        .reset_index()
    )
    items_per_community = communities.loc[:, ["community_name"]].merge(
        community_item_totals,
        on="community_name",
        how="left",
    )
    items_per_community["items_count"] = items_per_community["items_count"].fillna(0)
    communities_without_collections = communities[
        communities["collections_count"].fillna(0).eq(0)
    ].copy()
    collections_without_items = collection_inventory[
        collection_inventory["items_count"].eq(0)
    ].copy()

    def technical_group_table(prefix: str) -> pd.DataFrame:
        return collection_groups.loc[
            :,
            [
                "collection_name",
                f"{prefix}_group_names",
                f"{prefix}_group_members_count",
            ],
        ].rename(
            columns={
                f"{prefix}_group_names": "group_names",
                f"{prefix}_group_members_count": "group_members_count",
            }
        )

    return {
        "snapshot_month": reference_month,
        "communities_total": int(len(communities)),
        "collections_total": int(len(collections)),
        "communities_without_collections_total": int(len(communities_without_collections)),
        "collections_without_items_total": int(len(collections_without_items)),
        "items_per_community": items_per_community,
        "items_per_collection": collection_inventory.loc[
            :, ["collection_name", "items_count"]
        ],
        "total_size_per_collection": collection_inventory.loc[
            :, ["collection_name", "total_size_gb"]
        ],
        "submitter_groups_per_collection": technical_group_table("submitter"),
        "workflow_groups_per_collection": technical_group_table("workflow"),
        "administrator_groups_per_collection": technical_group_table("administrator"),
    }


def build_item_publication_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    items = load_metric_csv(project_root, config, "db", "always", reference_month, "db_all_items_by_archive_status.csv")
    items_without_handle = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_handle_all_statuses.csv")
    items_without_collection = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_collection.csv")
    items_not_publicly_visible = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_anonymous_visibility.csv")
    embargoed_objects = load_metric_csv(project_root, config, "db", "always", reference_month, "db_embargoed_objects.csv")
    items_without_bitstreams = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_files.csv")
    items_by_license = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_by_license.csv")
    items_without_original_bundle = load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_original_bundle.csv")
    oai_records = load_metric_csv(project_root, config, "solr", "always", reference_month, "solr_total_oai_records.csv")
    item_name_sources = [
        items_not_publicly_visible.loc[:, ["item_id", "item_name"]]
        if "item_name" in items_not_publicly_visible.columns
        else pd.DataFrame(columns=["item_id", "item_name"]),
        load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_invalid_license.csv").loc[:, ["item_id", "item_name"]],
        load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_with_multiple_licenses.csv").loc[:, ["item_id", "item_name"]],
        load_metric_csv(project_root, config, "db", "always", reference_month, "db_public_items_with_non_public_bitstreams.csv").loc[:, ["item_id", "item_name"]],
    ]

    archived_non_withdrawn_items = int((items["in_archive"] & ~items["withdrawn"]).sum())
    not_publicly_visible_items = int(len(items_not_publicly_visible))
    public_items = archived_non_withdrawn_items - not_publicly_visible_items
    withdrawn_items = int(items["withdrawn"].sum())
    not_archived_items = int((~items["in_archive"] & ~items["withdrawn"]).sum())
    items_without_license = int(
        items_by_license.loc[
            items_by_license["license_value"].fillna("").eq("[no license]"),
            "items_count",
        ].sum()
    )

    item_lookup = (
        oai_records.loc[:, ["item_id", "title", "item_handle"]]
        .assign(item_id=lambda df: df["item_id"].astype(str))
        .drop_duplicates(subset=["item_id"])
        .set_index("item_id")
    )
    fallback_title_lookup = (
        pd.concat(
            [
                items.loc[:, ["item_id", "title"]].rename(columns={"title": "item_name"})
                if "title" in items.columns
                else pd.DataFrame(columns=["item_id", "item_name"]),
                *item_name_sources,
            ],
            ignore_index=True,
        )
        .dropna(subset=["item_id"])
        .assign(item_id=lambda df: df["item_id"].astype(str))
        .drop_duplicates(subset=["item_id"])
        .set_index("item_id")["item_name"]
        .to_dict()
    )
    fallback_handle_lookup = (
        items.loc[:, ["item_id", "handles"]]
        .dropna(subset=["item_id"])
        .assign(item_id=lambda df: df["item_id"].astype(str))
        .drop_duplicates(subset=["item_id"])
        .set_index("item_id")["handles"]
        .to_dict()
        if "handles" in items.columns
        else {}
    )

    def build_detail_rows(item_ids: list[str]) -> list[dict[str, str | None]]:
        rows: list[dict[str, str | None]] = []
        for item_id in item_ids:
            item_id = str(item_id)
            if item_id in item_lookup.index:
                row = item_lookup.loc[item_id]
                title = str(row["title"]) if pd.notna(row["title"]) else None
                handle = str(row["item_handle"]) if pd.notna(row["item_handle"]) else None
            else:
                title = None
                handle = None
            if not title:
                title = fallback_title_lookup.get(item_id) or "[no title]"
            if not handle:
                raw_handle = fallback_handle_lookup.get(item_id)
                if pd.notna(raw_handle) and raw_handle:
                    handle = str(raw_handle).removeprefix("http://hdl.handle.net/").removeprefix(
                        "https://hdl.handle.net/"
                    )
            rows.append({"item_id": item_id, "title": title, "handle": handle})
        return rows

    no_license_item_ids = []
    no_license_rows = items_by_license[
        items_by_license["license_value"].fillna("").eq("[no license]")
    ]
    if not no_license_rows.empty and "item_ids" in no_license_rows.columns:
        for raw_ids in no_license_rows["item_ids"].dropna():
            no_license_item_ids.extend(
                [value.strip() for value in str(raw_ids).split(";") if value.strip()]
            )

    anomaly_rows = [
        ("Items without handle", list(items_without_handle["item_id"])),
        ("Items without collection", list(items_without_collection["item_id"])),
        ("Items without bitstreams", list(items_without_bitstreams["item_id"])),
        ("Items without license", no_license_item_ids),
        ("Items without ORIGINAL bundle", list(items_without_original_bundle["item_id"])),
    ]

    return {
        "items_total": int(len(items)),
        "items_without_handle": int(len(items_without_handle)),
        "items_without_collection": int(len(items_without_collection)),
        "items_not_publicly_visible": not_publicly_visible_items,
        "objects_under_embargo": int(len(embargoed_objects)),
        "items_without_bitstreams": int(len(items_without_bitstreams)),
        "items_without_license": items_without_license,
        "items_without_original_bundle": int(len(items_without_original_bundle)),
        "status_counts": {
            "public_items": public_items,
            "not_publicly_visible_items": not_publicly_visible_items,
            "withdrawn_items": withdrawn_items,
            "not_archived_items": not_archived_items,
        },
        "anomalies": [
            {
                "indicator": label,
                "count": int(len(item_ids)),
                "items": build_detail_rows(item_ids),
            }
            for label, item_ids in anomaly_rows
            if item_ids
        ],
    }


def build_quality_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    return {
        "snapshot_month": reference_month,
        "items_missing_metadata": int(len(load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_missing_metadata.csv"))),
        "items_without_files": int(len(load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_without_files.csv"))),
        "items_invalid_license": int(len(load_metric_csv(project_root, config, "db", "always", reference_month, "db_items_invalid_license.csv"))),
        "stalled_submissions_over_30_days": int(len(load_metric_csv(project_root, config, "db", "always", reference_month, "db_stalled_submissions_over_30_days.csv"))),
    }


def build_metadata_quality_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    missing_metadata = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_items_missing_metadata.csv"
    )
    empty_metadata_values = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_items_empty_metadata_values.csv"
    )
    metadata_count_per_item = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_metadata_count_per_item.csv"
    )
    items_by_license = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_items_by_license.csv"
    )
    licenses_per_collection = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_licenses_per_collection.csv"
    )
    licenses_per_resource_type = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_licenses_per_resource_type.csv"
    )
    oai_missing_information = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_oai_records_missing_information.csv"
    )
    oai_deleted_items = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_oai_records_deleted_items.csv"
    )

    missing_metadata_detail = (
        missing_metadata.groupby(["item_id", "handle"], dropna=False)["missing_metadata_field"]
        .agg(lambda values: "; ".join(sorted({str(value) for value in values if pd.notna(value)})))
        .reset_index()
        .rename(columns={"missing_metadata_field": "missing_fields"})
    )
    oai_missing_fields_counts = (
        oai_missing_information["missing_fields"]
        .fillna("")
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )
    oai_missing_fields_counts = (
        oai_missing_fields_counts[oai_missing_fields_counts.ne("")]
        .value_counts()
        .rename_axis("missing_field")
        .reset_index(name="records_count")
    )

    licenses_per_collection_summary = (
        licenses_per_collection.groupby("collection_name", dropna=False)["items_count"]
        .sum()
        .reset_index()
        .rename(columns={"items_count": "license_assignments_count"})
    )
    licenses_per_community_summary = (
        licenses_per_collection.groupby("community_name", dropna=False)["items_count"]
        .sum()
        .reset_index()
        .rename(columns={"items_count": "license_assignments_count"})
    )
    licenses_per_resource_type_summary = (
        licenses_per_resource_type.groupby("item_type", dropna=False)["items_count"]
        .sum()
        .reset_index()
        .rename(columns={"items_count": "license_assignments_count"})
    )
    items_without_license = int(
        items_by_license.loc[
            items_by_license["license_value"].fillna("").eq("[no license]"),
            "items_count",
        ].sum()
    )

    return {
        "items_missing_metadata": int(missing_metadata["item_id"].nunique()),
        "items_empty_metadata_values": int(empty_metadata_values["item_id"].nunique()),
        "average_metadata_values_per_item": round(float(metadata_count_per_item["metadata_count"].mean()), 2),
        "oai_records_missing_information": int(len(oai_missing_information)),
        "oai_records_deleted_items": int(len(oai_deleted_items)),
        "items_without_license": items_without_license,
        "missing_metadata_detail": missing_metadata_detail,
        "empty_metadata_values_detail": empty_metadata_values,
        "oai_missing_fields_counts": oai_missing_fields_counts,
        "licenses_per_collection": licenses_per_collection_summary,
        "licenses_per_community": licenses_per_community_summary,
        "licenses_per_resource_type": licenses_per_resource_type_summary,
    }


def build_oai_solr_exposure_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    available_cores = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_available_cores.csv"
    )
    index_size_by_core = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_index_size_by_core.csv"
    )
    record_count_by_core = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_record_count_by_core.csv"
    )
    distinct_event_types = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_statistics_distinct_event_types.csv",
    )
    distinct_object_types = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_statistics_distinct_object_types.csv",
    )
    oai_sets_available_values = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_oai_sets_available_values.csv",
    )
    total_oai_records = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_total_oai_records.csv"
    )
    first_10_oai_datestamp = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_first_10_oai_datestamp.csv",
    )
    last_10_oai_datestamp = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_last_10_oai_datestamp.csv",
    )
    missing_information = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_oai_records_missing_information.csv",
    )
    deleted_items = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_oai_records_deleted_items.csv",
    )

    for frame, column in [
        (index_size_by_core, "index_size_bytes"),
        (record_count_by_core, "records_count"),
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    return {
        "snapshot_month": reference_month,
        "available_cores": available_cores,
        "index_size_by_core": index_size_by_core,
        "record_count_by_core": record_count_by_core,
        "distinct_event_types": distinct_event_types,
        "distinct_object_types": distinct_object_types,
        "oai_sets_available_values": oai_sets_available_values,
        "item_catalog": total_oai_records,
        "total_oai_records": int(len(total_oai_records)),
        "first_10_oai_datestamp": first_10_oai_datestamp,
        "last_10_oai_datestamp": last_10_oai_datestamp,
        "oai_records_missing_information": int(len(missing_information)),
        "oai_records_deleted_items": int(len(deleted_items)),
    }


def build_historical_repository_usage_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    total_item_views = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_total_item_views.csv"
    )
    total_bitstream_downloads = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_total_bitstream_downloads.csv",
    )
    total_events = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_total_events.csv"
    )
    non_bot_events = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_non_bot_events.csv"
    )
    most_viewed_items = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_most_viewed_items.csv"
    )
    most_downloaded_items = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_most_downloaded_items.csv"
    )
    most_downloaded_bitstreams = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_most_downloaded_bitstreams.csv",
    )
    views_by_collection = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_views_by_collection.csv"
    )
    downloads_by_collection = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_downloads_by_collection.csv",
    )
    views_by_community = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_views_by_community.csv"
    )
    downloads_by_community = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_downloads_by_community.csv",
    )
    views_downloads_ratio_by_item = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_views_downloads_ratio_by_item.csv",
    )
    current_collections = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_collections.csv"
    )
    current_communities = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_communities.csv"
    )

    numeric_frames = [
        (most_viewed_items, "views_count"),
        (most_downloaded_items, "downloads_count"),
        (most_downloaded_bitstreams, "downloads_count"),
        (views_by_collection, "views_count"),
        (downloads_by_collection, "downloads_count"),
        (views_by_community, "views_count"),
        (downloads_by_community, "downloads_count"),
        (views_downloads_ratio_by_item, "views_count"),
        (views_downloads_ratio_by_item, "downloads_count"),
        (views_downloads_ratio_by_item, "views_downloads_ratio"),
    ]
    for frame, column in numeric_frames:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    collection_name_lookup = (
        current_collections.loc[:, ["collection_id", "collection_name"]]
        .drop_duplicates(subset=["collection_id"])
        .set_index("collection_id")["collection_name"]
        .to_dict()
    )
    community_name_lookup = (
        current_communities.loc[:, ["community_id", "community_name"]]
        .drop_duplicates(subset=["community_id"])
        .set_index("community_id")["community_name"]
        .to_dict()
    )

    views_by_collection = views_by_collection.assign(
        collection_label=lambda df: df["collection_id"].map(collection_name_lookup).fillna(df["collection_id"])
    )
    downloads_by_collection = downloads_by_collection.assign(
        collection_label=lambda df: df["collection_id"].fillna("[no collection]")
    )
    views_by_community = views_by_community.assign(
        community_label=lambda df: df["community_id"].map(community_name_lookup).fillna(df["community_id"])
    )
    downloads_by_community = downloads_by_community.assign(
        community_label=lambda df: df["community_name"].fillna(df["community_id"]).fillna("[no community]")
    )

    view_download_ratio_top_10 = views_downloads_ratio_by_item.nlargest(
        10, "views_downloads_ratio"
    ).copy()

    return {
        "snapshot_month": reference_month,
        "total_item_views": int(total_item_views["total_events"].iloc[0]),
        "total_bitstream_downloads": int(total_bitstream_downloads["total_events"].iloc[0]),
        "total_events": int(total_events["total_events"].iloc[0]),
        "non_bot_events": int(non_bot_events["total_events"].iloc[0]),
        "most_viewed_items": most_viewed_items.nlargest(10, "views_count"),
        "most_downloaded_items": most_downloaded_items.nlargest(10, "downloads_count"),
        "most_downloaded_items_with_bitstreams": views_downloads_ratio_by_item.nlargest(
            10, "downloads_count"
        ).copy(),
        "most_downloaded_bitstreams": most_downloaded_bitstreams.nlargest(10, "downloads_count"),
        "views_by_collection": views_by_collection,
        "downloads_by_collection": downloads_by_collection,
        "views_by_community": views_by_community,
        "downloads_by_community": downloads_by_community,
        "view_download_ratio_top_10": view_download_ratio_top_10,
    }


def build_access_referrer_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    solr_top_referrers_by_bot_status = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_top_referrers_by_bot_status.csv",
    )
    solr_accesses_from_search_engines = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_accesses_from_search_engines.csv",
    )
    matomo_direct_visits = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_direct_visits.csv"
    )
    matomo_visits_from_search_engines = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_visits_from_search_engines.csv",
    )
    matomo_visits_from_websites = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_visits_from_websites.csv",
    )
    matomo_visits_from_social_networks = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_visits_from_social_networks.csv",
    )
    matomo_campaign_visits = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_campaign_visits.csv"
    )
    matomo_top_referrer_websites = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_top_referrer_websites.csv",
    )

    for frame, column in [
        (solr_top_referrers_by_bot_status, "events_count"),
        (solr_accesses_from_search_engines, "events_count"),
        (matomo_visits_from_search_engines, "visits_count"),
        (matomo_visits_from_websites, "visits_count"),
        (matomo_visits_from_social_networks, "visits_count"),
        (matomo_campaign_visits, "visits_count"),
        (matomo_top_referrer_websites, "visits_count"),
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    top_referrers = (
        solr_top_referrers_by_bot_status.groupby("referrer_normalized", dropna=False)[
            "events_count"
        ]
        .sum()
        .reset_index()
        .sort_values("events_count", ascending=False)
        .head(10)
    )
    search_engine_events = (
        solr_accesses_from_search_engines.groupby("search_engine", dropna=False)[
            "events_count"
        ]
        .sum()
        .reset_index()
    )

    return {
        "snapshot_month": reference_month,
        "top_referrers": top_referrers,
        "top_referrers_by_bot_status": solr_top_referrers_by_bot_status,
        "search_engine_events": search_engine_events,
        "direct_visits": int(matomo_direct_visits["visits_count"].iloc[0]),
        "visits_from_search_engines": matomo_visits_from_search_engines,
        "visits_from_websites": matomo_visits_from_websites,
        "visits_from_social_networks": matomo_visits_from_social_networks,
        "campaign_visits": matomo_campaign_visits,
        "top_referrer_websites": matomo_top_referrer_websites.head(10),
    }


def build_event_quality_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    bot_events_by_type = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_bot_events_by_type.csv"
    )
    internal_events_by_type = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_internal_events_192_168_by_type.csv",
    )
    internal_external_ratio = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_internal_external_events_ratio_by_bot_status_and_type.csv",
    )
    most_frequent_bot_user_agents = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_most_frequent_bot_user_agents.csv",
    )
    most_frequent_user_agents_by_bot_status = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_most_frequent_user_agents_by_bot_status.csv",
    )
    most_frequent_ips_dns = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_most_frequent_ips_dns.csv",
    )

    for frame in [
        bot_events_by_type,
        internal_events_by_type,
        internal_external_ratio,
        most_frequent_bot_user_agents,
        most_frequent_user_agents_by_bot_status,
        most_frequent_ips_dns,
    ]:
        if "events_count" in frame.columns:
            frame["events_count"] = pd.to_numeric(
                frame["events_count"], errors="coerce"
            ).fillna(0)

    bot_events_by_event = (
        bot_events_by_type.groupby("statistics_type", dropna=False)["events_count"]
        .sum()
        .reset_index()
    )
    internal_events_by_event = (
        internal_events_by_type.groupby("statistics_type", dropna=False)["events_count"]
        .sum()
        .reset_index()
    )
    ratio_summary = (
        internal_external_ratio.groupby(
            ["network_scope", "bot_status", "statistics_type"], dropna=False
        )["events_count"]
        .sum()
        .reset_index()
    )
    ratio_summary["event_bot_label"] = (
        ratio_summary["statistics_type"].astype(str)
        + " · "
        + ratio_summary["bot_status"].astype(str)
    )

    return {
        "snapshot_month": reference_month,
        "bot_events_by_type": bot_events_by_type,
        "internal_events_by_type": internal_events_by_type,
        "internal_external_ratio": ratio_summary,
        "most_frequent_bot_user_agents": most_frequent_bot_user_agents,
        "most_frequent_user_agents_by_bot_status": most_frequent_user_agents_by_bot_status,
        "most_frequent_ips_dns": most_frequent_ips_dns,
        "bot_events_total": int(bot_events_by_event["events_count"].sum()),
        "internal_events_total": int(internal_events_by_event["events_count"].sum()),
    }


def build_internal_search_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    total_searches_by_bot_status = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_total_searches_by_bot_status.csv",
    )
    search_details = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_total_searches_details.csv",
    )
    most_searched_terms = load_metric_csv(
        project_root,
        config,
        "solr",
        "always",
        reference_month,
        "solr_most_searched_terms.csv",
    )
    total_searches_by_bot_status["total_events"] = pd.to_numeric(
        total_searches_by_bot_status["total_events"], errors="coerce"
    ).fillna(0)
    most_searched_terms["events_count"] = pd.to_numeric(
        most_searched_terms["events_count"], errors="coerce"
    ).fillna(0)
    non_bot_terms = most_searched_terms[
        most_searched_terms["bot_status"].fillna("").eq("non_bot")
    ]
    return {
        "snapshot_month": reference_month,
        "total_searches": int(total_searches_by_bot_status["total_events"].sum()),
        "search_details": search_details,
        "most_searched_terms": non_bot_terms.nlargest(20, "events_count"),
    }


def build_matomo_web_traffic_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    total_visits = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_total_visits.csv"
    )
    unique_visitors_by_month = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_unique_visitors_by_month.csv",
    )
    total_actions = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_total_actions.csv"
    )
    average_visit_duration = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_average_visit_duration.csv",
    )
    bounce_count = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_bounce_count.csv"
    )
    bounce_rate = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_bounce_rate.csv"
    )
    actions_per_visit = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_actions_per_visit.csv"
    )
    max_actions_in_visit = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_max_actions_in_visit.csv",
    )
    page_typology = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_typology_of_page_views.csv",
    )
    top_visited_pages = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_top_visited_pages.csv",
    )
    for frame, column in [
        (unique_visitors_by_month, "unique_visitors_count"),
        (page_typology, "pageviews_count"),
        (top_visited_pages, "pageviews_count"),
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    return {
        "snapshot_month": reference_month,
        "total_visits": int(total_visits["visits_count"].iloc[0]),
        "unique_visitors_by_month": unique_visitors_by_month,
        "total_actions": int(total_actions["actions_count"].iloc[0]),
        "average_visit_duration_seconds": int(
            average_visit_duration["average_visit_duration_seconds"].iloc[0]
        ),
        "bounce_count": int(bounce_count["bounce_count"].iloc[0]),
        "bounce_rate": str(bounce_rate["bounce_rate"].iloc[0]),
        "actions_per_visit": float(actions_per_visit["actions_per_visit"].iloc[0]),
        "max_actions_in_visit": int(max_actions_in_visit["max_actions_in_visit"].iloc[0]),
        "page_typology": page_typology,
        "top_visited_pages": top_visited_pages.nlargest(10, "pageviews_count"),
    }


def build_access_geography_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    countries = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_visits_by_country.csv"
    )
    cities = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_visits_by_city.csv"
    )
    continents = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_visits_by_continent.csv"
    )
    for frame in [countries, cities, continents]:
        frame["visits_count"] = pd.to_numeric(frame["visits_count"], errors="coerce").fillna(0)
    return {
        "snapshot_month": reference_month,
        "top_countries": countries.nlargest(10, "visits_count"),
        "top_cities": cities.nlargest(20, "visits_count"),
        "continents": continents,
    }


def build_device_technology_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    device_types = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_visits_by_device_type.csv",
    )
    browsers = load_metric_csv(
        project_root, config, "matomo", "always", reference_month, "matomo_visits_by_browser.csv"
    )
    operating_systems = load_metric_csv(
        project_root,
        config,
        "matomo",
        "always",
        reference_month,
        "matomo_visits_by_operating_system.csv",
    )
    for frame in [device_types, browsers, operating_systems]:
        frame["visits_count"] = pd.to_numeric(frame["visits_count"], errors="coerce").fillna(0)
    return {
        "snapshot_month": reference_month,
        "device_types": device_types,
        "browsers": browsers,
        "operating_systems": operating_systems,
    }


def build_user_group_workflow_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    users = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_all_users.csv"
    )
    users_never_logged_in = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_users_never_logged_in.csv",
    )
    groups = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_groups.csv"
    )
    empty_groups = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_empty_groups.csv"
    )
    workspace_items = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_workspace_items_details.csv",
    )
    workflow_items = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_workflow_items_details.csv",
    )
    stalled_submissions = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_stalled_submissions_over_30_days.csv",
    )
    workspace_items_per_user = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_workspace_items_per_user.csv",
    )
    workspace_items_per_collection = load_metric_csv(
        project_root,
        config,
        "db",
        "always",
        reference_month,
        "db_workspace_items_per_collection.csv",
    )

    last_active = pd.to_datetime(users["last_active"], errors="coerce")
    month_end = pd.Period(reference_month, freq="M").end_time.normalize()
    inactivity_cutoff = month_end - pd.DateOffset(months=12)
    inactive_over_12_months = users[
        last_active.notna() & (last_active < inactivity_cutoff)
    ]

    return {
        "snapshot_month": reference_month,
        "total_users": int(len(users)),
        "users_never_logged_in": int(len(users_never_logged_in)),
        "users_inactive_over_12_months": int(len(inactive_over_12_months)),
        "total_groups": int(len(groups)),
        "empty_groups": int(len(empty_groups)),
        "workspace_items": int(len(workspace_items)),
        "workflow_items": int(len(workflow_items)),
        "stalled_submissions_over_30_days": int(len(stalled_submissions)),
        "workspace_items_per_user": workspace_items_per_user,
        "workspace_items_per_collection": workspace_items_per_collection,
    }


def build_technical_integrity_snapshot_for_month(
    project_root: Path,
    config: dict[str, Any],
    reference_month: str,
) -> dict[str, Any]:
    items_without_bitstreams = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_items_without_files.csv"
    )
    bitstreams = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_bitstreams_with_filename_extension.csv"
    )
    bitstreams_per_item = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_bitstreams_per_item_all_statuses.csv"
    )
    bitstreams_without_checksum = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_bitstreams_without_checksum.csv"
    )
    non_public_bitstreams = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_non_public_bitstreams.csv"
    )
    public_items_with_non_public_bitstreams = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_public_items_with_non_public_bitstreams.csv"
    )
    total_size_per_collection = load_metric_csv(
        project_root, config, "db", "always", reference_month, "db_total_size_per_collection.csv"
    )
    downloads_by_mimetype = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_downloads_by_mimetype.csv"
    )
    downloads_by_resource_type = load_metric_csv(
        project_root, config, "solr", "always", reference_month, "solr_downloads_by_resource_type.csv"
    )

    problematic_frames = []
    if not bitstreams_without_checksum.empty:
        problematic_frames.append(
            bitstreams_without_checksum.assign(problem="Missing checksum")
        )
    if not non_public_bitstreams.empty:
        problematic_frames.append(
            non_public_bitstreams.assign(problem="Non-public bitstream")
        )
    if not public_items_with_non_public_bitstreams.empty:
        problematic_frames.append(
            public_items_with_non_public_bitstreams.assign(
                problem="Public item with non-public bitstream"
            )
        )
    problematic_bitstreams = (
        pd.concat(problematic_frames, ignore_index=True, sort=False)
        if problematic_frames
        else pd.DataFrame()
    )

    return {
        "items_without_bitstreams": int(len(items_without_bitstreams)),
        "bitstreams_with_mimetype": int(bitstreams["mimetype"].notna().sum()),
        "average_bitstreams_per_item": round(float(bitstreams_per_item["bitstreams_count"].mean()), 2),
        "bitstreams_without_checksum": int(len(bitstreams_without_checksum)),
        "non_public_bitstreams": int(len(non_public_bitstreams)),
        "public_items_with_non_public_bitstreams": int(
            public_items_with_non_public_bitstreams["item_id"].nunique()
        ),
        "bitstreams_per_item": bitstreams_per_item,
        "problematic_bitstreams": problematic_bitstreams,
        "total_size_per_collection": total_size_per_collection,
        "downloads_by_mimetype": downloads_by_mimetype,
        "downloads_by_resource_type": downloads_by_resource_type,
    }
