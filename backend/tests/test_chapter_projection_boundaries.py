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
