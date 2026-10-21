"""Expose the exact original planning request to internal chapter consumers."""
import pytest
from tests.test_planning_history import history as history
from tests.test_story_planning import brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


@pytest.mark.parametrize("direction", ["", "KEEP_START" + "原" * 3982 + "KEEP_END"], ids=["empty", "maximum-4000"])
def test_eligible_brief_exposes_fresh_complete_original_request(history, direction):
    kernel, provider, book_id = history
    request = {**kernel.story_planning.brief_context(book_id, 2), "feedback": direction}
    run = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    calls = list(provider.calls)
    artifact, snapshot, source = kernel.story_planning.eligible_brief(book_id, 2, _with_source=True)
    assert artifact == view["artifact"]
    assert snapshot == kernel.artifacts.get(view["snapshot_artifact_id"])
    assert source == request and source["feedback"] == direction
    assert kernel.story_planning.eligible_brief(book_id, 2) == artifact
    source["feedback"] = "Caller-local mutation must not become a new author instruction"
    _, _, fresh = kernel.story_planning.eligible_brief(book_id, 2, _with_source=True)
    assert fresh == request
    assert kernel.story_planning.read(run["pipeline_run_id"]) == view
    assert provider.calls == calls
