"""
[INPUT]: Actual review HTTP API/Kernel with externally duplicated Feishu projection state.
[OUTPUT]: Editorial commands refuse ambiguous source versions before durable decisions or revision intents.
[POS]: ZEN-41 regression; deterministic provider outputs prepare the source, not semantic acceptance.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json

import pytest

from tests.test_chapter_loop import pass_run
from tests.test_chapter_review import chapter as chapter, target
from tests.test_chapter_projection_boundaries import HEADERS, api_for, raw_record, readonly, transport_of

pytest_plugins = ("tests.test_story_planning",)


@pytest.mark.parametrize("operation", ["decision", "revision"])
def test_editorial_command_refuses_projection_that_already_breaks_review_read(chapter, operation, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    command = target(view)
    transport = transport_of(kernel)
    _, original = raw_record(kernel, transport, "chapter_versions", "version_id", command["version_id"])
    fields = kernel.storage._repos["chapter_versions"]._field_map
    shadow = copy.deepcopy(original)
    shadow["record_id"] = "rec-external-editorial-duplicate"
    shadow["fields"].update({fields["version_id"]: "CV-" + "e" * 32,
                             fields["run_id"]: "PR-" + "e" * 32,
                             fields["status"]: "candidate"})
    transport.tables[kernel.storage._repos["chapter_versions"]._table_id][shadow["record_id"]] = shadow
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    if operation == "decision":
        command["action"] = "approve"
    else:
        command["constraints"] = {"must_change": ["Clarify the dialogue"]}
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1"
        review = api.get(path + "/review", headers=HEADERS)
        assert review.status_code == 503, review.text
        response = api.post(path + "/review/" + operation, headers=HEADERS, json=command)
        (tmp_path / "editorial-duplicate-observation.json").write_text(json.dumps({
            "operation": operation, "review_status": review.status_code,
            "command_status": response.status_code, "command_body": response.json(),
            "before": before, "after": transport.tables,
            "model_calls_before": model_calls, "model_calls_after": provider.calls}, indent=2))
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "AmbiguousWrite", "reconciliation_required": True}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()
