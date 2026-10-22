"""
[INPUT]: Actual chapter API/kernel/artifact/store with controlled external Feishu state.
[OUTPUT]: Corrupt chapter projection refusal, exact evidence restoration and finalization safety.
[POS]: ZEN-40 projection consistency regression contracts; deterministic provider outputs are setup, not model-quality proof.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.storage import AmbiguousWrite
from tests.test_chapter_loop import chapter as chapter, pass_run

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")
HEADERS = {"x-api-key": "synthetic-api-key"}


def transport_of(kernel):
    transport = kernel.storage._repos["artifacts"]._client._http._transport.handler
    for repo in kernel.storage._repos.values():
        transport.tables.setdefault(repo._table_id, {})
    return transport


def raw_record(kernel, transport, collection, field, value):
    repo = kernel.storage._repos[collection]
    name = repo._field_map[field]
    matches = [(record_id, row) for record_id, row in transport.tables[repo._table_id].items()
               if row["fields"].get(name) == value]
    assert len(matches) == 1
    return matches[0]


def readonly(calls):
    assert all(call.method == "GET" or call.method == "POST"
               and call.url.path.endswith("/records/search") for call in calls)


def api_for(kernel):
    # Deliberately no lifespan: the actual scheduler must not race an external fault.
    return TestClient(create_app(Settings(_env_file=None, BACKEND_API_KEY="synthetic-api-key",
                                          HARNESS_ENABLED=False), kernel=kernel))


def test_final_lock_refuses_same_number_projection_from_an_unrelated_run(chapter, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    assert view["run"]["status"] == "completed" and view["selected"]
    version = view["versions"][0]
    transport = transport_of(kernel)
    _, original = raw_record(kernel, transport, "chapter_versions", "version_id", version["version_id"])
    shadow = copy.deepcopy(original)
    fields = kernel.storage._repos["chapter_versions"]._field_map
    shadow["record_id"] = "rec-shadow-projection"
    shadow["fields"].update({fields["version_id"]: "CV-" + "d" * 32,
                             fields["run_id"]: "PR-" + "d" * 32,
                             fields["status"]: "candidate"})
    table = kernel.storage._repos["chapter_versions"]._table_id
    transport.tables[table][shadow["record_id"]] = shadow
    before = copy.deepcopy(transport.tables)
    calls, model_calls = len(transport.calls), list(provider.calls)
    command = {"version_id": version["version_id"], "artifact_id": version["artifact_id"],
               "version_no": version["version_no"], "operator": "synthetic-editor"}
    api = api_for(kernel)
    try:
        context = api.get(f"/api/books/{book_id}/chapters/1/generation/context", headers=HEADERS)
        assert context.status_code == 503
        with pytest.raises(AmbiguousWrite, match="Duplicate ChapterVersion number"):
            kernel.chapter_loop.context(book_id, 1)
        response = api.post(f"/api/books/{book_id}/chapters/1/final-lock", headers=HEADERS, json=command)
        (tmp_path / "chapter-final-duplicate-observation.json").write_text(json.dumps({
            "status": response.status_code, "body": response.json(), "before": before,
            "after": transport.tables, "model_calls_before": model_calls,
            "model_calls_after": provider.calls}, indent=2))
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()


FAULTS = [
    ("duplicate_projection", "Duplicate ChapterVersion number"),
    ("duplicate_artifact", "ChapterVersion artifact identity changed"),
    ("artifact_logical_id", "ChapterVersion artifact identity changed"),
    ("artifact_id", "ChapterVersion artifact identity changed"),
    ("artifact_number", "ChapterVersion artifact identity changed"),
    ("missing_projection", "Unprojected ChapterVersion artifact"),
    ("projection_artifact", "Unprojected ChapterVersion artifact"),
    ("missing_artifact", "Projected ChapterVersion artifact missing"),
    ("multiple_finals", "Multiple final ChapterVersions"),
]


def corrupt_projection(kernel, transport, version, fault):
    """Inject external persisted state, bypassing application write validation."""
    cv_repo = kernel.storage._repos["chapter_versions"]
    ar_repo = kernel.storage._repos["artifacts"]
    cv_id, cv = raw_record(kernel, transport, "chapter_versions", "version_id", version["version_id"])
    ar_id, artifact = raw_record(kernel, transport, "artifacts", "artifact_id", version["artifact_id"])
    cv_fields, ar_fields = cv_repo._field_map, ar_repo._field_map
    if fault in {"duplicate_projection", "multiple_finals"}:
        shadow = copy.deepcopy(cv)
        shadow["record_id"] = "rec-external-shadow"
        shadow["fields"].update({cv_fields["version_id"]: "CV-" + "d" * 32,
                                 cv_fields["run_id"]: "PR-" + "d" * 32})
        if fault == "multiple_finals":
            cv["fields"][cv_fields["status"]] = "final"
            shadow["fields"].update({cv_fields["version_no"]: 2, cv_fields["status"]: "final"})
        else:
            shadow["fields"][cv_fields["status"]] = "candidate"
        transport.tables[cv_repo._table_id][shadow["record_id"]] = shadow
    elif fault == "duplicate_artifact":
        shadow = copy.deepcopy(artifact)
        shadow["record_id"] = "rec-external-artifact"
        shadow["fields"][ar_fields["artifact_id"]] = "AR-" + "d" * 32
        transport.tables[ar_repo._table_id][shadow["record_id"]] = shadow
    elif fault.startswith("artifact_"):
        field, value = {"artifact_logical_id": ("logical_id", "books/foreign/chapters/1/versions"),
                        "artifact_id": ("artifact_id", "AR-" + "d" * 32),
                        "artifact_number": ("version", 2)}[fault]
        artifact["fields"][ar_fields[field]] = value
    elif fault == "missing_projection":
        del transport.tables[cv_repo._table_id][cv_id]
    elif fault == "projection_artifact":
        cv["fields"][cv_fields["artifact_id"]] = "AR-" + "d" * 32
    elif fault == "missing_artifact":
        del transport.tables[ar_repo._table_id][ar_id]
    else:
        raise AssertionError(fault)


@pytest.mark.parametrize("fault,message", FAULTS)
@pytest.mark.parametrize("locked_replay", [False, True], ids=["first-finalization", "locked-replay"])
def test_finalization_refuses_external_ambiguity_and_recovers_exactly(chapter, fault, message,
                                                                   locked_replay, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    version = view["versions"][0]
    command = {key: version[key] for key in ("version_id", "artifact_id", "version_no")}
    command["operator"] = "synthetic-editor"
    transport = transport_of(kernel)
    api = api_for(kernel)
    path = f"/api/books/{book_id}/chapters/1/final-lock"
    try:
        if locked_replay:
            healthy = api.post(path, headers=HEADERS, json=command)
            assert healthy.status_code == 200 and healthy.json()["status"] == "final"
        baseline = copy.deepcopy(transport.tables)
        artifact_before = kernel.artifacts.get(version["artifact_id"])
        corrupt_projection(kernel, transport, version, fault)
        corrupt = copy.deepcopy(transport.tables)
        calls, model_calls = len(transport.calls), list(provider.calls)
        response = api.post(path, headers=HEADERS, json=command)
        (tmp_path / "refusal.json").write_text(json.dumps({
            "fault": fault, "locked_replay": locked_replay, "status": response.status_code,
            "body": response.json(), "before": corrupt, "after": transport.tables}, indent=2))
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        with pytest.raises(AmbiguousWrite, match=message):
            kernel.chapter_loop.lock_final(book_id, 1, **command)
        assert transport.tables == corrupt
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls

        # Repair only the external fixture, then exercise the unchanged public command.
        transport.tables = copy.deepcopy(baseline)
        restored = api.post(path, headers=HEADERS, json=command)
        assert restored.status_code == 200, restored.text
        final = restored.json()
        assert final["status"] == "final" and final["locked_by"] == command["operator"]
        assert all(final[key] == command[key] for key in ("version_id", "artifact_id", "version_no"))
        if locked_replay:
            assert final == healthy.json() and transport.tables == baseline
        final_state = copy.deepcopy(transport.tables)
        calls = len(transport.calls)
        replay = api.post(path, headers=HEADERS, json=command)
        assert replay.status_code == 200 and replay.json() == final
        assert transport.tables == final_state
        readonly(transport.calls[calls:])
        assert kernel.artifacts.get(version["artifact_id"]) == artifact_before
        assert provider.calls == model_calls
    finally:
        api.close()
