from pathlib import Path

import pandas as pd

import dspace_reporting.reporting.datasets as datasets_module
from dspace_reporting.reporting.paths import (
    get_always_report_dir,
    get_month_figures_dir,
    get_month_report_dir,
    get_reports_root,
)
from dspace_reporting.reporting.datasets import (
    build_monthly_detail,
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
    build_repository_organization_snapshot_for_month,
    build_repository_snapshot_as_of_month,
    has_complete_monthly_overview_exports,
    missing_monthly_overview_exports,
)
from dspace_reporting.runners.build_reports import (
    item_href,
    normalize_handle,
    report_exists,
    resolve_logo_relative_path,
    resolve_navigation_months,
)


def test_report_paths_follow_monthly_layout():
    config = {"paths": {"reports_root": "reports"}}

    assert get_reports_root(Path("/project"), config) == Path("/project/reports")
    assert get_month_report_dir(Path("/project"), config, "2026-04") == Path(
        "/project/reports/monthly/2026-04"
    )
    assert get_month_figures_dir(Path("/project"), config, "2026-04") == Path(
        "/project/reports/monthly/2026-04/figures"
    )
    assert get_always_report_dir(Path("/project"), config, "2026-05") == Path(
        "/project/reports/always/2026-05"
    )


def test_item_href_prefers_handle_and_falls_back_to_dspace_item_url():
    assert normalize_handle("https://hdl.handle.net/20.500/test-1") == "20.500/test-1"
    assert normalize_handle("http://hdl.handle.net/20.500/test-2") == "20.500/test-2"
    assert item_href("abc", {"item_handle": "20.500/test-1"}) == (
        "https://hdl.handle.net/20.500/test-1"
    )
    assert item_href("abc", {}) == "https://dspace-clarin-it.ilc.cnr.it/items/abc"


def test_logo_is_published_inside_reports_tree(tmp_path):
    project_root = tmp_path
    source_logo = project_root / "assets" / "branding" / "logo.png"
    source_logo.parent.mkdir(parents=True)
    source_logo.write_bytes(b"logo")

    config = {
        "paths": {"reports_root": "reports"},
        "reporting": {"logo_path": "assets/branding/logo.png"},
    }
    report_dir = project_root / "reports" / "monthly" / "2026-04"
    report_dir.mkdir(parents=True)

    relative_path = resolve_logo_relative_path(project_root, config, report_dir)

    assert relative_path == "../../assets/branding/logo.png"
    assert (project_root / "reports" / "assets" / "branding" / "logo.png").read_bytes() == b"logo"


def test_monthly_overview_requires_all_input_exports(tmp_path):
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    required_paths = [
        tmp_path / "exports" / "db" / "monthly" / "2025-10" / "db_items_uploaded_in_month_details.csv",
        tmp_path / "exports" / "matomo" / "monthly" / "2025-10" / "matomo_visits_reference_month.csv",
        tmp_path / "exports" / "matomo" / "monthly" / "2025-10" / "matomo_pageviews_reference_month_action_details.csv",
        tmp_path / "exports" / "solr" / "monthly" / "2025-10" / "solr_views_downloads_ratio_by_item_reference_month.csv",
    ]
    for path in required_paths[:-1]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("col\n", encoding="utf-8")

    assert not has_complete_monthly_overview_exports(tmp_path, config, "2025-10")
    assert missing_monthly_overview_exports(tmp_path, config, "2025-10") == [
        ("solr", "solr_views_downloads_ratio_by_item_reference_month.csv")
    ]

    required_paths[-1].parent.mkdir(parents=True, exist_ok=True)
    required_paths[-1].write_text("col\n", encoding="utf-8")

    assert has_complete_monthly_overview_exports(tmp_path, config, "2025-10")
    assert missing_monthly_overview_exports(tmp_path, config, "2025-10") == []


def test_monthly_detail_keeps_empty_workflow_timeline_schema(monkeypatch, tmp_path):
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}

    def fake_load_metric_csv(project_root, config, source, scope, reference_month, filename):
        if filename == "db_items_modified_in_month_from_provenance.csv":
            return pd.DataFrame(columns=["item_id", "event_type", "event_line"])
        return pd.DataFrame()

    monkeypatch.setattr(datasets_module, "load_metric_csv", fake_load_metric_csv)

    detail = build_monthly_detail(tmp_path, config, "2025-07")

    assert detail["workflow_approval_timeline"].empty
    assert list(detail["workflow_approval_timeline"].columns) == [
        "item_id",
        "submitted_at",
        "first_approval_at",
        "second_approval_at",
        "final_approval_at",
        "made_available_at",
        "approval_steps_count",
        "submitted_to_first_approval_hours",
        "first_to_final_approval_hours",
        "submitted_to_available_hours",
    ]


def test_repository_snapshot_as_of_month_uses_deposit_date_for_item_counts(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "db" / "always" / "2026-05"
    root.mkdir(parents=True)

    (root / "db_all_items_by_archive_status.csv").write_text(
        "\n".join(
            [
                "item_id,deposit_date,in_archive,publicly_reachable_candidate",
                "a,2026-01-10,True,True",
                "b,2026-02-20,True,False",
                "c,2026-03-05,True,True",
                "d,,False,False",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "db_total_communities.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_total_collections.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_all_users.csv").write_text("id\n1\n2\n", encoding="utf-8")
    (root / "db_total_groups.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_items_by_license.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_bitstreams_with_filename_extension.csv").write_text("id\n1\n2\n", encoding="utf-8")
    (root / "db_total_size_per_collection.csv").write_text("total_size_gb\n1.25\n", encoding="utf-8")
    (root / "db_items_without_handle_all_statuses.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_items_without_files.csv").write_text("id\n1\n", encoding="utf-8")
    solr_root = project_root / "exports" / "solr" / "always" / "2026-05"
    solr_root.mkdir(parents=True)
    (solr_root / "solr_total_oai_records.csv").write_text("id\n1\n2\n3\n", encoding="utf-8")

    snapshot = build_repository_snapshot_as_of_month(project_root, config, "2026-02")

    assert snapshot["snapshot_month"] == "2026-05"
    assert snapshot["as_of_month"] == "2026-02"
    assert snapshot["items_total"] == 2
    assert snapshot["items_archived"] == 2
    assert snapshot["items_publicly_reachable"] == 1
    assert snapshot["items_without_deposit_date"] == 1
    assert snapshot["oai_records_total"] == 3


def test_repository_organization_snapshot_summarizes_structure_and_groups(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "db" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "db_total_communities.csv").write_text(
        "community_id,community_name,collections_count\nc1,OPEN,2\nc2,EMPTY,0\n",
        encoding="utf-8",
    )
    (root / "db_total_collections.csv").write_text(
        "collection_id,collection_name,community_id,community_name\n"
        "a,A,c1,OPEN\nb,B,c1,OPEN\n",
        encoding="utf-8",
    )
    (root / "db_total_size_per_collection.csv").write_text(
        "collection_id,items_count,bitstreams_count,total_size_gb\n"
        "a,3,4,1.5\n",
        encoding="utf-8",
    )
    (root / "db_collection_groups.csv").write_text(
        "collection_name,submitter_group_names,submitter_group_members_count,"
        "workflow_group_names,workflow_group_members_count,"
        "administrator_group_names,administrator_group_members_count\n"
        "A,S1,2,W1,1,ADM1,1\nB,,0,,0,,0\n",
        encoding="utf-8",
    )

    snapshot = build_repository_organization_snapshot_for_month(
        project_root, config, "2026-05"
    )

    assert snapshot["communities_total"] == 2
    assert snapshot["collections_total"] == 2
    assert snapshot["communities_without_collections_total"] == 1
    assert snapshot["collections_without_items_total"] == 1
    assert snapshot["items_per_community"].to_dict("records") == [
        {"community_name": "OPEN", "items_count": 3.0},
        {"community_name": "EMPTY", "items_count": 0.0},
    ]
    assert snapshot["items_per_collection"].to_dict("records") == [
        {"collection_name": "A", "items_count": 3.0},
        {"collection_name": "B", "items_count": 0.0},
    ]


def test_oai_solr_exposure_snapshot_summarizes_technical_exports(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "solr" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "solr_available_cores.csv").write_text(
        "core_name,num_docs,deleted_docs,index_size\nstatistics,10,0,1 MB\n",
        encoding="utf-8",
    )
    (root / "solr_index_size_by_core.csv").write_text(
        "core_logical_name,index_size,index_size_bytes,num_docs,deleted_docs\nstatistics,1 MB,1048576,10,0\n",
        encoding="utf-8",
    )
    (root / "solr_record_count_by_core.csv").write_text(
        "core_logical_name,records_count\nstatistics,10\n",
        encoding="utf-8",
    )
    (root / "solr_statistics_distinct_event_types.csv").write_text(
        "statistics_type,events_count\nview,7\nsearch,3\n",
        encoding="utf-8",
    )
    (root / "solr_statistics_distinct_object_types.csv").write_text(
        "object_type,object_type_label,events_count\n2,item,7\n0,bitstream,3\n",
        encoding="utf-8",
    )
    (root / "solr_oai_sets_available_values.csv").write_text(
        "facet_field,field_value,records_count\nitem.public,true,9\n",
        encoding="utf-8",
    )
    (root / "solr_total_oai_records.csv").write_text(
        "item_id\n1\n2\n",
        encoding="utf-8",
    )
    (root / "solr_first_10_oai_datestamp.csv").write_text(
        "item_handle,oai_datestamp,title\nh1,2026-01-01,A\n",
        encoding="utf-8",
    )
    (root / "solr_last_10_oai_datestamp.csv").write_text(
        "item_handle,oai_datestamp,title\nh2,2026-02-01,B\n",
        encoding="utf-8",
    )
    (root / "solr_oai_records_missing_information.csv").write_text(
        "item_id\n1\n",
        encoding="utf-8",
    )
    (root / "solr_oai_records_deleted_items.csv").write_text(
        "item_id\n2\n",
        encoding="utf-8",
    )

    snapshot = build_oai_solr_exposure_snapshot_for_month(
        project_root, config, "2026-05"
    )

    assert snapshot["total_oai_records"] == 2
    assert snapshot["oai_records_missing_information"] == 1
    assert snapshot["oai_records_deleted_items"] == 1
    assert snapshot["index_size_by_core"]["index_size_bytes"].tolist() == [1048576]
    assert snapshot["record_count_by_core"]["records_count"].tolist() == [10]


def test_historical_usage_snapshot_summarizes_all_time_solr_usage(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    solr_root = project_root / "exports" / "solr" / "always" / "2026-05"
    db_root = project_root / "exports" / "db" / "always" / "2026-05"
    solr_root.mkdir(parents=True)
    db_root.mkdir(parents=True)
    (solr_root / "solr_total_item_views.csv").write_text("total_events\n11\n", encoding="utf-8")
    (solr_root / "solr_total_bitstream_downloads.csv").write_text("total_events\n7\n", encoding="utf-8")
    (solr_root / "solr_total_events.csv").write_text("total_events\n30\n", encoding="utf-8")
    (solr_root / "solr_non_bot_events.csv").write_text("total_events\n18\n", encoding="utf-8")
    (solr_root / "solr_most_viewed_items.csv").write_text(
        "item_id,views_count\n3,12\n1,10\n",
        encoding="utf-8",
    )
    (solr_root / "solr_most_downloaded_items.csv").write_text(
        "item_id,downloads_count\n1,7\n2,3\n",
        encoding="utf-8",
    )
    (solr_root / "solr_most_downloaded_bitstreams.csv").write_text(
        "bitstream_id,downloads_count,owning_item_id\nb1,7,1\n",
        encoding="utf-8",
    )
    (solr_root / "solr_views_by_collection.csv").write_text(
        "collection_id,views_count\nc1,8\n",
        encoding="utf-8",
    )
    (solr_root / "solr_downloads_by_collection.csv").write_text(
        "collection_id,downloads_count\nlegacy,7\n",
        encoding="utf-8",
    )
    (solr_root / "solr_views_by_community.csv").write_text(
        "community_id,views_count\nm1,9\n",
        encoding="utf-8",
    )
    (solr_root / "solr_downloads_by_community.csv").write_text(
        "community_id,community_name,downloads_count\nlegacy,Historical,7\n",
        encoding="utf-8",
    )
    (solr_root / "solr_views_downloads_ratio_by_item.csv").write_text(
        "item_id,views_count,downloads_count,bitstream_ids,views_downloads_ratio\n"
        "1,10,2,b1,5.0\n2,3,3,b2,1.0\n",
        encoding="utf-8",
    )
    (db_root / "db_total_collections.csv").write_text(
        "collection_id,collection_name\nc1,Current collection\n",
        encoding="utf-8",
    )
    (db_root / "db_total_communities.csv").write_text(
        "community_id,community_name\nm1,Current community\n",
        encoding="utf-8",
    )

    snapshot = build_historical_repository_usage_snapshot_for_month(
        project_root, config, "2026-05"
    )

    assert snapshot["total_item_views"] == 11
    assert snapshot["total_bitstream_downloads"] == 7
    assert snapshot["total_events"] == 30
    assert snapshot["non_bot_events"] == 18
    assert snapshot["most_viewed_items"]["item_id"].tolist() == [3, 1]
    assert snapshot["most_downloaded_items_with_bitstreams"]["item_id"].tolist() == [2, 1]
    assert snapshot["views_by_collection"]["collection_label"].tolist() == ["Current collection"]
    assert snapshot["downloads_by_community"]["community_label"].tolist() == ["Historical"]


def test_access_referrer_snapshot_keeps_solr_and_matomo_metrics_separate(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    solr_root = project_root / "exports" / "solr" / "always" / "2026-05"
    matomo_root = project_root / "exports" / "matomo" / "always" / "2026-05"
    solr_root.mkdir(parents=True)
    matomo_root.mkdir(parents=True)
    (solr_root / "solr_top_referrers_by_bot_status.csv").write_text(
        "referrer_normalized,bot_status,events_count\n"
        "direct_or_unknown,bot,4\ndirect_or_unknown,non_bot,2\nhttps://x,non_bot,3\n",
        encoding="utf-8",
    )
    (solr_root / "solr_accesses_from_search_engines.csv").write_text(
        "search_engine,events_count\ngoogle,5\nbing,2\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_direct_visits.csv").write_text(
        "visits_count\n10\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_visits_from_search_engines.csv").write_text(
        "search_engine,visits_count\nGoogle,7\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_visits_from_websites.csv").write_text(
        "website,visits_count\nexample.org,3\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_visits_from_social_networks.csv").write_text(
        "social_network,visits_count\nGitHub,1\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_campaign_visits.csv").write_text(
        "campaign,visits_count\ncampaign-a,2\n",
        encoding="utf-8",
    )
    (matomo_root / "matomo_top_referrer_websites.csv").write_text(
        "referrer_website,visits_count\nexample.org,3\n",
        encoding="utf-8",
    )

    snapshot = build_access_referrer_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["top_referrers"].to_dict("records") == [
        {"referrer_normalized": "direct_or_unknown", "events_count": 6},
        {"referrer_normalized": "https://x", "events_count": 3},
    ]
    assert snapshot["direct_visits"] == 10
    assert snapshot["search_engine_events"].to_dict("records") == [
        {"search_engine": "bing", "events_count": 2},
        {"search_engine": "google", "events_count": 5},
    ]


def test_event_quality_snapshot_summarizes_technical_signal_without_exposing_it(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "solr" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "solr_bot_events_by_type.csv").write_text(
        "statistics_type,object_type_label,events_count\nview,item,5\nsearch,,2\n",
        encoding="utf-8",
    )
    (root / "solr_internal_events_192_168_by_type.csv").write_text(
        "statistics_type,object_type_label,events_count\nview,item,3\nsearch,not_applicable,4\n",
        encoding="utf-8",
    )
    (root / "solr_internal_external_events_ratio_by_bot_status_and_type.csv").write_text(
        "network_scope,bot_status,statistics_type,events_count\n"
        "internal,bot,view,2\nexternal,bot,view,5\ninternal,non_bot,search,4\n",
        encoding="utf-8",
    )
    (root / "solr_most_frequent_bot_user_agents.csv").write_text(
        "user_agent,events_count\nbot-a,5\n",
        encoding="utf-8",
    )
    (root / "solr_most_frequent_user_agents_by_bot_status.csv").write_text(
        "user_agent,bot_status,events_count\nua-a,bot,5\n",
        encoding="utf-8",
    )
    (root / "solr_most_frequent_ips_dns.csv").write_text(
        "network_identifier,events_count\nhost-a,5\n",
        encoding="utf-8",
    )

    snapshot = build_event_quality_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["bot_events_total"] == 7
    assert snapshot["internal_events_total"] == 7
    assert set(snapshot["internal_external_ratio"]["event_bot_label"]) == {
        "view · bot",
        "search · non_bot",
    }


def test_internal_search_snapshot_keeps_details_available_but_surfaces_summary(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "solr" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "solr_total_searches_by_bot_status.csv").write_text(
        "bot_status,total_events\nbot,2\nnon_bot,5\n",
        encoding="utf-8",
    )
    (root / "solr_total_searches_details.csv").write_text(
        "search_query\nfoo\n",
        encoding="utf-8",
    )
    (root / "solr_most_searched_terms.csv").write_text(
        "searched_term,term_type,bot_status,events_count\n"
        "alpha,query,non_bot,4\nbeta,query,bot,9\n",
        encoding="utf-8",
    )

    snapshot = build_internal_search_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["total_searches"] == 7
    assert snapshot["most_searched_terms"]["searched_term"].tolist() == ["alpha"]


def test_matomo_web_traffic_snapshot_summarizes_browser_side_metrics(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "matomo" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "matomo_total_visits.csv").write_text("visits_count\n10\n", encoding="utf-8")
    (root / "matomo_unique_visitors_by_month.csv").write_text(
        "month,unique_visitors_count\n2026-04,3\n2026-05,4\n",
        encoding="utf-8",
    )
    (root / "matomo_total_actions.csv").write_text("actions_count\n20\n", encoding="utf-8")
    (root / "matomo_average_visit_duration.csv").write_text(
        "average_visit_duration_seconds\n30\n",
        encoding="utf-8",
    )
    (root / "matomo_bounce_count.csv").write_text("bounce_count\n6\n", encoding="utf-8")
    (root / "matomo_bounce_rate.csv").write_text("bounce_rate\n60%\n", encoding="utf-8")
    (root / "matomo_actions_per_visit.csv").write_text(
        "actions_per_visit\n2.0\n",
        encoding="utf-8",
    )
    (root / "matomo_max_actions_in_visit.csv").write_text(
        "max_actions_in_visit\n5\n",
        encoding="utf-8",
    )
    (root / "matomo_typology_of_page_views.csv").write_text(
        "page_typology,pageviews_count\nhome,7\nitem,3\n",
        encoding="utf-8",
    )
    (root / "matomo_top_visited_pages.csv").write_text(
        "page_title,pageviews_count,visits_count\n/home,7,5\n/item,3,2\n",
        encoding="utf-8",
    )

    snapshot = build_matomo_web_traffic_snapshot_for_month(
        project_root, config, "2026-05"
    )

    assert snapshot["total_visits"] == 10
    assert snapshot["total_actions"] == 20
    assert snapshot["average_visit_duration_seconds"] == 30
    assert snapshot["bounce_rate"] == "60%"


def test_access_geography_and_device_snapshots_summarize_matomo_exports(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "matomo" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "matomo_visits_by_country.csv").write_text(
        "country,visits_count\nItaly,5\nFrance,3\n",
        encoding="utf-8",
    )
    (root / "matomo_visits_by_city.csv").write_text(
        "city,country,visits_count\nRome,Italy,5\nParis,France,3\n",
        encoding="utf-8",
    )
    (root / "matomo_visits_by_continent.csv").write_text(
        "continent,visits_count\nEurope,8\n",
        encoding="utf-8",
    )
    (root / "matomo_visits_by_device_type.csv").write_text(
        "device_type,visits_count\nDesktop,7\nMobile,1\n",
        encoding="utf-8",
    )
    (root / "matomo_visits_by_browser.csv").write_text(
        "browser,visits_count\nChrome,6\nFirefox,2\n",
        encoding="utf-8",
    )
    (root / "matomo_visits_by_operating_system.csv").write_text(
        "operating_system,visits_count\nWindows,5\nLinux,3\n",
        encoding="utf-8",
    )

    geography = build_access_geography_snapshot_for_month(project_root, config, "2026-05")
    technology = build_device_technology_snapshot_for_month(project_root, config, "2026-05")

    assert geography["top_countries"]["country"].tolist() == ["Italy", "France"]
    assert geography["top_cities"]["city"].tolist() == ["Rome", "Paris"]
    assert technology["browsers"]["browser"].tolist() == ["Chrome", "Firefox"]


def test_user_group_workflow_snapshot_summarizes_operational_kpis(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "db" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "db_all_users.csv").write_text(
        "eperson_id,last_active\n1,2025-04-01\n2,2025-12-01\n3,\n",
        encoding="utf-8",
    )
    (root / "db_users_never_logged_in.csv").write_text("eperson_id\n3\n", encoding="utf-8")
    (root / "db_total_groups.csv").write_text("group_id\n1\n2\n", encoding="utf-8")
    (root / "db_empty_groups.csv").write_text("group_id\n2\n", encoding="utf-8")
    (root / "db_workspace_items_details.csv").write_text("id\n1\n2\n", encoding="utf-8")
    (root / "db_workflow_items_details.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_stalled_submissions_over_30_days.csv").write_text("id\n1\n", encoding="utf-8")
    (root / "db_workspace_items_per_user.csv").write_text(
        "submitter_email,workspace_items_count\nu@example.org,2\n",
        encoding="utf-8",
    )
    (root / "db_workspace_items_per_collection.csv").write_text(
        "collection_name,workspace_items_count\nC1,2\n",
        encoding="utf-8",
    )

    snapshot = build_user_group_workflow_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["snapshot_month"] == "2026-05"
    assert snapshot["total_users"] == 3
    assert snapshot["users_never_logged_in"] == 1
    assert snapshot["users_inactive_over_12_months"] == 1
    assert snapshot["total_groups"] == 2
    assert snapshot["empty_groups"] == 1
    assert snapshot["workspace_items"] == 2
    assert snapshot["workflow_items"] == 1
    assert snapshot["stalled_submissions_over_30_days"] == 1
    assert snapshot["workspace_items_per_user"].to_dict("records") == [
        {"submitter_email": "u@example.org", "workspace_items_count": 2},
    ]


def test_item_publication_snapshot_summarizes_status_and_anomalies(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    root = project_root / "exports" / "db" / "always" / "2026-05"
    root.mkdir(parents=True)
    (root / "db_all_items_by_archive_status.csv").write_text(
        "\n".join(
            [
                "item_id,title,handles,in_archive,withdrawn",
                "1,Alpha from DB,http://hdl.handle.net/20.500/db-1,True,False",
                "2,Beta from DB,http://hdl.handle.net/20.500/db-2,True,False",
                "3,Gamma from DB,http://hdl.handle.net/20.500/db-3,False,False",
                "4,Delta from DB,http://hdl.handle.net/20.500/db-4,False,True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "db_items_without_handle_all_statuses.csv").write_text("item_id\n1\n", encoding="utf-8")
    (root / "db_items_without_collection.csv").write_text("item_id\n1\n2\n", encoding="utf-8")
    (root / "db_items_anonymous_visibility.csv").write_text("item_id\n1\n", encoding="utf-8")
    (root / "db_embargoed_objects.csv").write_text("id\n", encoding="utf-8")
    (root / "db_items_without_files.csv").write_text("item_id\n1\n", encoding="utf-8")
    (root / "db_items_by_license.csv").write_text(
        "license_value,items_count,item_ids\n[no license],2,1; 2\nPUB,1,3\n",
        encoding="utf-8",
    )
    (root / "db_items_without_original_bundle.csv").write_text("item_id\n1\n", encoding="utf-8")
    (root / "db_items_invalid_license.csv").write_text(
        "item_id,item_name\n9,Gamma\n",
        encoding="utf-8",
    )
    (root / "db_items_with_multiple_licenses.csv").write_text(
        "item_id,item_name\n8,Delta\n",
        encoding="utf-8",
    )
    (root / "db_public_items_with_non_public_bitstreams.csv").write_text(
        "item_id,item_name\n7,Epsilon\n",
        encoding="utf-8",
    )
    solr_root = project_root / "exports" / "solr" / "always" / "2026-05"
    solr_root.mkdir(parents=True)
    (solr_root / "solr_total_oai_records.csv").write_text(
        "\n".join(
            [
                "item_id,title,item_handle",
                "1,Alpha,20.500/test-1",
                "2,Beta,20.500/test-2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = build_item_publication_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["items_total"] == 4
    assert snapshot["items_not_publicly_visible"] == 1
    assert snapshot["status_counts"] == {
        "public_items": 1,
        "not_publicly_visible_items": 1,
        "withdrawn_items": 1,
        "not_archived_items": 1,
    }
    assert snapshot["items_without_license"] == 2
    assert snapshot["anomalies"] == [
        {
            "indicator": "Item senza handle",
            "count": 1,
            "items": [{"item_id": "1", "title": "Alpha", "handle": "20.500/test-1"}],
        },
        {
            "indicator": "Item senza collection",
            "count": 2,
            "items": [
                {"item_id": "1", "title": "Alpha", "handle": "20.500/test-1"},
                {"item_id": "2", "title": "Beta", "handle": "20.500/test-2"},
            ],
        },
        {
            "indicator": "Item senza bitstream",
            "count": 1,
            "items": [{"item_id": "1", "title": "Alpha", "handle": "20.500/test-1"}],
        },
        {
            "indicator": "Item senza licenza",
            "count": 2,
            "items": [
                {"item_id": "1", "title": "Alpha", "handle": "20.500/test-1"},
                {"item_id": "2", "title": "Beta", "handle": "20.500/test-2"},
            ],
        },
        {
            "indicator": "Item senza bundle ORIGINAL",
            "count": 1,
            "items": [{"item_id": "1", "title": "Alpha", "handle": "20.500/test-1"}],
        },
    ]


def test_report_exists_detects_generated_report(tmp_path):
    report_dir = tmp_path / "reports" / "monthly" / "2026-04"
    report_dir.mkdir(parents=True)
    assert not report_exists(report_dir)

    (report_dir / "report.html").write_text("<html></html>", encoding="utf-8")
    assert report_exists(report_dir)


def test_navigation_months_include_only_existing_or_current_build_targets():
    assert resolve_navigation_months(
        {"2026-01", "2026-03"},
        ["2026-05"],
    ) == ["2026-01", "2026-03", "2026-05"]


def test_metadata_quality_snapshot_summarizes_kpis_and_chart_data(tmp_path):
    project_root = tmp_path
    config = {"paths": {"exports_root": "exports"}, "run": {"create_month_subfolders": True}}
    db_root = project_root / "exports" / "db" / "always" / "2026-05"
    solr_root = project_root / "exports" / "solr" / "always" / "2026-05"
    db_root.mkdir(parents=True)
    solr_root.mkdir(parents=True)

    (db_root / "db_items_missing_metadata.csv").write_text(
        "item_id,handle,missing_metadata_field\n1,h1,dc.title\n1,h1,dc.language.iso\n2,h2,dc.title\n",
        encoding="utf-8",
    )
    (db_root / "db_items_empty_metadata_values.csv").write_text(
        "item_id,metadata_value_id,metadata_field\n1,10,dc.title\n1,11,dc.description\n",
        encoding="utf-8",
    )
    (db_root / "db_metadata_count_per_item.csv").write_text(
        "item_id,metadata_count\n1,10\n2,20\n",
        encoding="utf-8",
    )
    (db_root / "db_items_by_license.csv").write_text(
        "license_value,items_count\n[no license],2\nPUB,1\n",
        encoding="utf-8",
    )
    (db_root / "db_licenses_per_collection.csv").write_text(
        "collection_name,community_name,items_count\nC1,Com1,2\nC1,Com1,1\nC2,Com2,4\n",
        encoding="utf-8",
    )
    (db_root / "db_licenses_per_resource_type.csv").write_text(
        "item_type,items_count\ncorpus,2\ntool,3\n",
        encoding="utf-8",
    )
    (solr_root / "solr_oai_records_missing_information.csv").write_text(
        "item_id,missing_fields\n1,mimetype; authors\n2,mimetype\n",
        encoding="utf-8",
    )
    (solr_root / "solr_oai_records_deleted_items.csv").write_text(
        "item_id\n1\n",
        encoding="utf-8",
    )

    snapshot = build_metadata_quality_snapshot_for_month(project_root, config, "2026-05")

    assert snapshot["items_missing_metadata"] == 2
    assert snapshot["items_empty_metadata_values"] == 1
    assert snapshot["average_metadata_values_per_item"] == 15.0
    assert snapshot["oai_records_missing_information"] == 2
    assert snapshot["oai_records_deleted_items"] == 1
    assert snapshot["items_without_license"] == 2
    assert snapshot["missing_metadata_detail"].to_dict(orient="records") == [
        {"item_id": 1, "handle": "h1", "missing_fields": "dc.language.iso; dc.title"},
        {"item_id": 2, "handle": "h2", "missing_fields": "dc.title"},
    ]
    assert snapshot["oai_missing_fields_counts"].to_dict(orient="records") == [
        {"missing_field": "mimetype", "records_count": 2},
        {"missing_field": "authors", "records_count": 1},
    ]
