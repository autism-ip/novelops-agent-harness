"""
[INPUT]: FastAPI TestClient、PipelineEngine/Feishu repository fixtures。
[OUTPUT]: 流水线端点契约与不可信业务键过滤安全回归。
[POS]: API HTTP 层的行为门禁。
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes.pipelines import get_engine
from app.config import Settings
from app.main import create_app


# ============================================================
# fixtures
# ============================================================


@pytest.fixture()
def settings(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-key")
    monkeypatch.setenv("FEISHU_APP_ID", "test-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    return Settings()


@pytest.fixture()
def mock_engine() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_pipeline_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_step_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def client(
    settings: Settings,
    mock_engine: MagicMock,
    mock_pipeline_repo: MagicMock,
    mock_step_repo: MagicMock,
):
    app = create_app(settings)
    app.dependency_overrides[get_engine] = lambda: mock_engine
    with patch("app.api.routes.pipelines._build_pipeline_repo", return_value=mock_pipeline_repo), \
         patch("app.api.routes.pipelines._build_step_repo", return_value=mock_step_repo):
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(settings: Settings) -> dict[str, str]:
    return {"x-api-key": settings.BACKEND_API_KEY}


# ============================================================
# POST /api/pipelines
# ============================================================


class TestCreatePipeline:
    def test_returns_201_with_pipeline_run_id(
        self, client: TestClient, mock_engine: MagicMock, auth_headers: dict
    ):
        mock_engine.create_pipeline.return_value = {
            "pipeline_run_id": "PR-abc123",
            "status": "pending",
        }

        resp = client.post("/api/pipelines", json={
            "pipeline_type": "douyin_to_novel",
            "steps": [
                {"step_key": "extract", "assigned_agent_id": "agent-a"},
                {"step_key": "analyze", "assigned_agent_id": "agent-b", "depends_on": ["extract"]},
            ],
        }, headers=auth_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["pipeline_run_id"] == "PR-abc123"
        assert data["status"] == "pending"

    def test_passes_step_defs_to_engine(
        self, client: TestClient, mock_engine: MagicMock, auth_headers: dict
    ):
        mock_engine.create_pipeline.return_value = {
            "pipeline_run_id": "PR-001",
            "status": "pending",
        }

        client.post("/api/pipelines", json={
            "pipeline_type": "t",
            "steps": [
                {"step_key": "s1", "assigned_agent_id": "a1"},
            ],
            "source_hotspot_id": "HS-1",
            "book_id": "BK-1",
        }, headers=auth_headers)

        call_kwargs = mock_engine.create_pipeline.call_args[1]
        assert call_kwargs["pipeline_type"] == "t"
        assert call_kwargs["source_hotspot_id"] == "HS-1"
        assert call_kwargs["book_id"] == "BK-1"
        assert len(call_kwargs["step_defs"]) == 1
        assert call_kwargs["step_defs"][0].step_key == "s1"


# ============================================================
# GET /api/pipelines/{pipeline_run_id}
# ============================================================


class TestGetPipeline:
    def test_returns_200_with_pipeline_and_steps(
        self, client: TestClient, mock_pipeline_repo: MagicMock, mock_step_repo: MagicMock, auth_headers: dict
    ):
        mock_pipeline_repo.find_by_business_key.return_value = {
            "pipeline_run_id": "PR-001", "status": "running",
        }
        mock_step_repo.find_by_pipeline.return_value = [
            {"step_run_id": "SR-001", "step_key": "s1", "status": "success"},
        ]

        resp = client.get("/api/pipelines/PR-001", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_run_id"] == "PR-001"
        assert len(data["step_runs"]) == 1
        mock_pipeline_repo.find_by_business_key.assert_called_once_with(pipeline_run_id="PR-001")

    def test_returns_404_when_not_found(
        self, client: TestClient, mock_pipeline_repo: MagicMock, auth_headers: dict
    ):
        mock_pipeline_repo.find_by_business_key.return_value = None

        resp = client.get("/api/pipelines/PR-nonexistent", headers=auth_headers)

        assert resp.status_code == 404


# ============================================================
# GET /api/pipelines/{pipeline_run_id}/steps
# ============================================================


class TestListStepRuns:
    def test_returns_step_list(
        self, client: TestClient, mock_step_repo: MagicMock, auth_headers: dict
    ):
        mock_step_repo.find_by_pipeline.return_value = [
            {"step_run_id": "SR-001", "step_key": "s1", "status": "success"},
            {"step_run_id": "SR-002", "step_key": "s2", "status": "pending"},
        ]

        resp = client.get("/api/pipelines/PR-001/steps", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


def test_pipeline_lookup_quotes_untrusted_domain_id_before_feishu_filter(settings, monkeypatch):
    from urllib.parse import quote

    from app.feishu.table_map import TableMapConfig

    monkeypatch.setenv("FEISHU_TABLE_ID_PIPELINE_RUNS", "tbl_pipeline_runs")
    monkeypatch.setenv("FEISHU_TABLE_ID_STEP_RUNS", "tbl_step_runs")
    feishu = MagicMock()
    feishu.get.return_value = {"data": {"items": [], "has_more": False}}
    app = create_app(settings)
    unsafe_id = 'PR-1" || CurrentValue.[status] = "approved'
    with patch("app.api.routes.pipelines._get_client", return_value=feishu), \
         patch("app.api.routes.pipelines._get_config", return_value=TableMapConfig("test-base")), \
         TestClient(app) as http:
        response = http.get(f"/api/pipelines/{quote(unsafe_id, safe='')}",
                            headers={"x-api-key": settings.BACKEND_API_KEY})
    assert response.status_code == 404
    assert feishu.get.call_count == 1
    assert feishu.get.call_args.kwargs["params"]["filter"] == (
        'CurrentValue.[pipeline_run_id] = "PR-1\\" || CurrentValue.[status] = \\"approved"')


def test_pipeline_lookup_rejects_duplicate_business_ids(client, mock_pipeline_repo, auth_headers):
    from app.storage import DuplicateKey

    mock_pipeline_repo.find_by_business_key.side_effect = DuplicateKey("duplicate")
    response = client.get("/api/pipelines/PR-duplicated", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Duplicate pipeline run ID"
