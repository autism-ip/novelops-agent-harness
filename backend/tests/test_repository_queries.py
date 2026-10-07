"""Every configured Feishu table resolves a domain query to its own Bitable table.

The HTTP client is replaced at the transport boundary; repository selection,
filter construction and response mapping remain production code.
"""
from unittest.mock import MagicMock

import pytest

from app.feishu.repositories.factory import create_repositories
from app.feishu.table_map import FIELD_MAPS, TABLE_NAMES, TableMapConfig


@pytest.fixture
def repository_set(monkeypatch):
    for name in TABLE_NAMES:
        monkeypatch.setenv(f"FEISHU_TABLE_ID_{name.upper()}", f"tbl_{name}")
    client = MagicMock()
    repos = create_repositories(client, TableMapConfig(app_token="test-base"))
    return client, repos


def test_factory_binds_all_domain_repositories_to_configured_tables(repository_set):
    client, repos = repository_set
    assert set(repos) == set(TABLE_NAMES) == set(FIELD_MAPS)
    for name, repo in repos.items():
        assert repo._base_path() == f"/bitable/v1/apps/test-base/tables/tbl_{name}/records"
        assert repo._field_map == FIELD_MAPS[name]
        assert repo._client is client


@pytest.mark.parametrize("table,method,args,fields,expected_filter", [
    ("agents", "find_by_role", ("writer",), {"agent_role": "writer"}, 'CurrentValue.[agent_role] = "writer"'),
    ("agent_states", "find_by_agent", ("AG-1",), {"agent_id": "AG-1"}, 'CurrentValue.[agent_id] = "AG-1"'),
    ("agent_states", "find_by_status", ("ready",), {"status": "ready"}, 'CurrentValue.[status] = "ready"'),
    ("agent_runs", "find_by_agent", ("AG-1",), {"agent_id": "AG-1"}, 'CurrentValue.[agent_id] = "AG-1"'),
    ("agent_runs", "find_by_pipeline", ("PR-1",), {"pipeline_run_id": "PR-1"}, 'CurrentValue.[pipeline_run_id] = "PR-1"'),
    ("pipeline_runs", "find_by_status", ("pending",), {"status": "pending"}, 'CurrentValue.[status] = "pending"'),
    ("pipeline_runs", "find_by_type", ("research",), {"pipeline_type": "research"}, 'CurrentValue.[pipeline_type] = "research"'),
    ("hotspots", "find_by_status", ("new",), {"status": "new"}, 'CurrentValue.[status] = "new"'),
    ("hotspots", "find_by_dedupe_hash", ("sha-1",), {"dedupe_hash": "sha-1"}, 'CurrentValue.[dedupe_hash] = "sha-1"'),
    ("hotspot_analyses", "find_by_hotspot", ("HS-1",), {"hotspot_id": "HS-1"}, 'CurrentValue.[hotspot_id] = "HS-1"'),
    ("title_candidates", "find_by_analysis", ("AN-1",), {"analysis_id": "AN-1"}, 'CurrentValue.[analysis_id] = "AN-1"'),
    ("cover_plans", "find_by_title", ("TI-1",), {"title_id": "TI-1"}, 'CurrentValue.[title_id] = "TI-1"'),
    ("books", "find_by_status", ("draft",), {"status": "draft"}, 'CurrentValue.[status] = "draft"'),
    ("chapter_briefs", "find_by_book", ("BK-1",), {"book_id": "BK-1"}, 'CurrentValue.[book_id] = "BK-1"'),
    ("chapter_versions", "find_by_chapter", ("BK-1", 3), {"book_id": "BK-1", "chapter_no": 3},
     'CurrentValue.[book_id] = "BK-1" && CurrentValue.[chapter_no] = 3'),
    ("review_reports", "find_by_target", ("chapter", "BK-1/3"), {"target_type": "chapter", "target_id": "BK-1/3"},
     'CurrentValue.[target_type] = "chapter" && CurrentValue.[target_id] = "BK-1/3"'),
    ("revision_tasks", "find_by_status", ("open",), {"status": "open"}, 'CurrentValue.[status] = "open"'),
    ("agent_team_snapshots", "find_by_chapter", ("BK-1", 3), {"book_id": "BK-1", "chapter_no": 3},
     'CurrentValue.[book_id] = "BK-1" && CurrentValue.[chapter_no] = 3'),
    ("approval_events", "find_by_target", ("chapter", "BK-1/3"), {"target_type": "chapter", "target_id": "BK-1/3"},
     'CurrentValue.[target_type] = "chapter" && CurrentValue.[target_id] = "BK-1/3"'),
])
def test_domain_query_reads_only_matching_table_and_fields(
    repository_set, table, method, args, fields, expected_filter
):
    client, repos = repository_set
    client.get.return_value = {"data": {"items": [
        {"record_id": "rec-matched", "fields": fields}], "has_more": False}}
    result = getattr(repos[table], method)(*args)
    assert result == [{**fields, "record_id": "rec-matched"}]
    client.get.assert_called_once()
    path = client.get.call_args.args[0]
    assert path == f"/bitable/v1/apps/test-base/tables/tbl_{table}/records"
    assert client.get.call_args.kwargs["params"]["filter"] == expected_filter
