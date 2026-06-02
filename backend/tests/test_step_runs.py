"""
[INPUT]: 依赖 app.feishu.repositories.step_runs.StepRunsRepo 的领域查询能力
[OUTPUT]: 对外提供 StepRunsRepo 的行为级测试用例——claim_step 与 find_by_pipeline
[POS]: tests 的 step_runs 门禁，验证业务键→record_id 解析与字段过滤行为
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.feishu.repositories.step_runs import StepRunsRepo


# ============================================================
# fixtures
# ============================================================

_APP_TOKEN = "bascn_test_token"
_TABLE_ID = "tbl_step_runs"


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_client: MagicMock) -> StepRunsRepo:
    with patch("app.feishu.table_map.FIELD_MAPS", {"step_runs": {
        "step_run_id": "step_run_id",
        "pipeline_run_id": "pipeline_run_id",
        "step_key": "step_key",
        "assigned_agent_id": "assigned_agent_id",
        "depends_on": "depends_on",
        "status": "status",
        "input_refs": "input_refs",
        "output_refs": "output_refs",
        "lease_owner": "lease_owner",
        "lease_until": "lease_until",
        "retry_count": "retry_count",
        "error_message": "error_message",
        "started_at": "started_at",
        "finished_at": "finished_at",
    }}):
        return StepRunsRepo(mock_client, _APP_TOKEN, _TABLE_ID)


# ============================================================
# claim_step
# ============================================================


class TestClaimStep:
    """claim_step resolves business key to record_id before updating."""

    def test_claim_step_resolves_business_key_to_record_id(
        self, repo: StepRunsRepo, mock_client: MagicMock
    ) -> None:
        """update() must receive the Feishu record_id, not the business step_run_id."""
        # --- arrange: find_by_business_key will list+filter and return a record
        list_response = {
            "data": {
                "items": [
                    {
                        "record_id": "rec-feishu-abc",
                        "fields": {
                            "step_run_id": "sr-42",
                            "pipeline_run_id": "pr-7",
                            "status": "pending",
                        },
                    }
                ],
                "has_more": False,
            }
        }
        update_response = {
            "data": {
                "record": {
                    "record_id": "rec-feishu-abc",
                    "fields": {
                        "step_run_id": "sr-42",
                        "lease_owner": "worker-1",
                        "status": "running",
                    },
                }
            }
        }
        mock_client.get.return_value = list_response
        mock_client.put.return_value = update_response

        # --- act
        result = repo.claim_step("sr-42", "worker-1")

        # --- assert: update PUT used record_id, not business key
        put_call = mock_client.put
        put_call.assert_called_once()
        put_path = put_call.call_args[0][0]
        assert "/rec-feishu-abc" in put_path, (
            f"Expected record_id in path, got: {put_path}"
        )
        assert "/sr-42" not in put_path, (
            "Business key must NOT appear in the update path"
        )

        # verify fields sent to PUT
        body = put_call.call_args.kwargs.get(
            "body", put_call.call_args[1].get("body", {})
        )
        assert body["fields"]["lease_owner"] == "worker-1"
        assert body["fields"]["status"] == "running"

    def test_claim_step_raises_on_missing(
        self, repo: StepRunsRepo, mock_client: MagicMock
    ) -> None:
        """When no record matches the business key, ValueError is raised."""
        mock_client.get.return_value = {
            "data": {"items": [], "has_more": False}
        }

        with pytest.raises(ValueError, match="Step run not found: sr-ghost"):
            repo.claim_step("sr-ghost", "worker-1")

        # update must never be called
        mock_client.put.assert_not_called()


# ============================================================
# find_by_pipeline
# ============================================================


class TestFindByPipeline:
    """find_by_pipeline delegates to list with _field_filter."""

    def test_find_by_pipeline_uses_field_filter(
        self, repo: StepRunsRepo, mock_client: MagicMock
    ) -> None:
        """The filter expression must use _field_filter format, not a raw f-string."""
        mock_client.get.return_value = {
            "data": {
                "items": [
                    {
                        "record_id": "rec-01",
                        "fields": {
                            "step_run_id": "sr-1",
                            "pipeline_run_id": "pr-7",
                        },
                    },
                    {
                        "record_id": "rec-02",
                        "fields": {
                            "step_run_id": "sr-2",
                            "pipeline_run_id": "pr-7",
                        },
                    },
                ],
                "has_more": False,
            }
        }

        results = repo.find_by_pipeline("pr-7")

        assert len(results) == 2

        # verify filter expression uses CurrentValue.[field] format
        call = mock_client.get.call_args
        params = call.kwargs.get("params", call[1].get("params", {}))
        filter_expr = params["filter"]
        assert filter_expr == 'CurrentValue.[pipeline_run_id] = "pr-7"'

    def test_find_by_pipeline_empty_result(
        self, repo: StepRunsRepo, mock_client: MagicMock
    ) -> None:
        """Returns empty list when no step runs match."""
        mock_client.get.return_value = {
            "data": {"items": [], "has_more": False}
        }

        results = repo.find_by_pipeline("pr-nonexistent")
        assert results == []
