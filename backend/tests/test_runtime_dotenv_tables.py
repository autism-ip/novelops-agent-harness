"""Startup must consume the same dotenv sources for credentials and table wiring."""
import os

import pytest

from app.config import Settings
from app.runtime import build_runtime


@pytest.mark.parametrize("process_override", [False, True])
def test_runtime_uses_local_dotenv_table_wiring_with_process_precedence(tmp_path, monkeypatch, process_override):
    for name in list(os.environ):
        if name.startswith("FEISHU_") or name == "BACKEND_API_KEY":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("BACKEND_API_KEY=base-synthetic\nFEISHU_APP_TOKEN=base-token\n")
    (tmp_path / ".env.local").write_text(
        "BACKEND_API_KEY=local-synthetic\nFEISHU_APP_ID=synthetic-id\nFEISHU_APP_SECRET=synthetic-secret\n"
        "FEISHU_APP_TOKEN=local-token\nFEISHU_TABLE_ID_PIPELINE_RUNS=local-pipeline\n"
        "FEISHU_TABLE_ID_STEP_RUNS=local-step\nFEISHU_TABLE_ID_APPROVAL_EVENTS=local-approval\n")
    expected_token = "local-token"
    expected_pipeline = "local-pipeline"
    if process_override:
        monkeypatch.setenv("FEISHU_APP_TOKEN", "process-token")
        monkeypatch.setenv("FEISHU_TABLE_ID_PIPELINE_RUNS", "process-pipeline")
        expected_token, expected_pipeline = "process-token", "process-pipeline"
    settings = Settings(HARNESS_ENABLED=True, OPENCLI_ENABLED=False, HOTSPOTS_ENABLED=False,
        GENERATION_ENABLED=False, RESEARCH_ENABLED=False, CREATIVE_ENABLED=False, BOOKS_ENABLED=False,
        STORY_PLANNING_ENABLED=False, CHAPTER_LOOP_ENABLED=False)
    assert settings.BACKEND_API_KEY == "local-synthetic"
    kernel = client = None
    try:
        kernel, client = build_runtime(settings)
        repos = kernel.storage._repos
        assert set(repos) == {"pipeline_runs", "step_runs", "approval_events"}
        assert all(repo._app_token == expected_token for repo in repos.values())
        assert repos["pipeline_runs"]._table_id == expected_pipeline
        assert repos["step_runs"]._table_id == "local-step"
        assert repos["approval_events"]._table_id == "local-approval"
        assert os.environ.get("FEISHU_TABLE_ID_STEP_RUNS") is None
    finally:
        if kernel and getattr(kernel, "model_router", None):
            kernel.model_router.close()
        if client:
            client._http.close()


def test_explicit_table_mapping_is_copied_and_never_falls_back_to_ambient_env(monkeypatch):
    from app.feishu.table_map import TableMapConfig
    monkeypatch.setenv("FEISHU_APP_TOKEN", "ambient-base")
    monkeypatch.setenv("FEISHU_TABLE_ID_PIPELINE_RUNS", "ambient-table")
    mapping = {"pipeline_runs": "configured-table"}
    config = TableMapConfig(app_token="configured-base", table_ids=mapping)
    mapping["pipeline_runs"] = "mutated-after-startup"
    assert config.app_token == "configured-base"
    assert config.get_table_id("pipeline_runs") == "configured-table"
    empty = TableMapConfig(app_token="", table_ids={})
    assert empty.app_token == ""
    with pytest.raises(ValueError, match="FEISHU_TABLE_ID_PIPELINE_RUNS"):
        empty.get_table_id("pipeline_runs")
    legacy = TableMapConfig()
    assert legacy.app_token == "ambient-base"
    assert legacy.get_table_id("pipeline_runs") == "ambient-table"


def test_all_registered_table_fields_load_from_dotenv(tmp_path, monkeypatch):
    from app.feishu.table_map import FIELD_MAPS, TableMapConfig
    for key in list(os.environ):
        if key.startswith("FEISHU_"):
            monkeypatch.delenv(key, raising=False)
    path = tmp_path / "all-tables.env"
    path.write_text("BACKEND_API_KEY=synthetic\nFEISHU_APP_TOKEN=all-tables-base\n" + "".join(
        f"FEISHU_TABLE_ID_{name.upper()}=table-{name}\n" for name in FIELD_MAPS))
    settings = Settings(_env_file=path)
    configured = {name: getattr(settings, "FEISHU_TABLE_ID_" + name.upper()) for name in FIELD_MAPS}
    config = TableMapConfig(app_token=settings.FEISHU_APP_TOKEN, table_ids=configured)
    assert {name: config.get_table_id(name) for name in FIELD_MAPS} == {
        name: "table-" + name for name in FIELD_MAPS}
    assert not any(key.startswith("FEISHU_") for key in os.environ)


def test_two_settings_instances_keep_separate_bases_and_tables(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("FEISHU_"):
            monkeypatch.delenv(key, raising=False)
    clients = []
    try:
        for label in ("first", "second"):
            path = tmp_path / (label + ".env")
            path.write_text(f"BACKEND_API_KEY=synthetic\nFEISHU_APP_ID=id\nFEISHU_APP_SECRET=secret\n"
                f"FEISHU_APP_TOKEN={label}-base\nFEISHU_TABLE_ID_PIPELINE_RUNS={label}-pipeline\n"
                f"FEISHU_TABLE_ID_STEP_RUNS={label}-step\nFEISHU_TABLE_ID_APPROVAL_EVENTS={label}-approval\n")
            settings = Settings(_env_file=path, HARNESS_JOURNAL_DIR=str(tmp_path / label),
                OPENCLI_ENABLED=False, HOTSPOTS_ENABLED=False, GENERATION_ENABLED=False,
                RESEARCH_ENABLED=False, CREATIVE_ENABLED=False, BOOKS_ENABLED=False,
                STORY_PLANNING_ENABLED=False, CHAPTER_LOOP_ENABLED=False)
            kernel, client = build_runtime(settings)
            clients.append((label, kernel, client))
        for label, kernel, _ in clients:
            assert kernel.storage._repos["pipeline_runs"]._app_token == label + "-base"
            assert kernel.storage._repos["pipeline_runs"]._table_id == label + "-pipeline"
        assert not any(key.startswith("FEISHU_") for key in os.environ)
    finally:
        for _, _, client in clients:
            client._http.close()
