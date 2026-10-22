"""
[INPUT]: Actual chapter commands, deterministic provider, Kernel and Feishu HTTP adapter.
[OUTPUT]: Invalid commands preserve durable evidence; unusable Critic revisions cannot promote drafts.
[POS]: ZEN-40 command/runtime contracts and separately labelled constructor configuration checks.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy

import pytest

from app.chapter_loop import ChapterLoopService
from tests.test_chapter_loop import chapter as chapter, critique, draft, start
from tests.test_chapter_projection_boundaries import HEADERS, api_for, readonly, transport_of
from tests.test_story_planning import settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


@pytest.mark.parametrize("field", ["must_keep", "must_change", "do_not_change"])
def test_initial_generation_cannot_accept_revision_only_constraints(chapter, field):
    kernel, provider, book_id = chapter
    request = kernel.chapter_loop.context(book_id, 1)
    request["constraints"][field] = ["Preserve this editorial direction"]
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        response = api.post(f"/api/books/{book_id}/chapters/1/generations", headers=HEADERS, json=request)
        assert response.status_code == 422
        assert "Initial generation cannot carry revision constraints" in response.text
        assert transport.tables == before and len(transport.calls) == calls
        assert provider.calls == model_calls
    finally:
        api.close()


@pytest.mark.parametrize("field,value", [("start_version_no", 2), ("state_artifact_id", "AR-other-state"),
                                        ("brief_version", 2)])
def test_reserved_generation_refuses_changed_inputs_and_replays_original(chapter, field, value):
    kernel, provider, book_id = chapter
    run_id, request, _ = start(kernel, book_id)
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1/generations"
        response = api.post(path, headers=HEADERS, json={**request, field: value})
        assert response.status_code == 409
        assert response.json() == {"detail": "Chapter run version already reserved with different inputs"}
        replay = api.post(path, headers=HEADERS, json=request)
        assert replay.status_code == 201 and replay.json()["pipeline_run_id"] == run_id
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()


def test_active_generation_refuses_another_version_but_preserves_original_replay(chapter):
    kernel, provider, book_id = chapter
    run_id, original, _ = start(kernel, book_id)
    next_request = kernel.chapter_loop.context(book_id, 1)
    assert next_request["version"] == original["version"] + 1
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1/generations"
        response = api.post(path, headers=HEADERS, json=next_request)
        assert response.status_code == 409
        assert response.json() == {"detail": "Resolve the current chapter run first"}
        replay = api.post(path, headers=HEADERS, json=original)
        assert replay.status_code == 201 and replay.json()["pipeline_run_id"] == run_id
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()


def test_revision_cannot_reference_a_nonexistent_review_version(chapter):
    kernel, provider, book_id = chapter
    request = kernel.chapter_loop.context(book_id, 1)
    request.update(source_version_id="CV-" + "d" * 32,
                   constraints={"must_change": ["Clarify the opening conflict"]})
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        response = api.post(f"/api/books/{book_id}/chapters/1/generations", headers=HEADERS, json=request)
        assert response.status_code == 409
        assert response.json() == {"detail": "Revision must name the current review ChapterVersion"}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
    finally:
        api.close()


def test_unactionable_critic_revision_exhausts_bounded_retry_without_rewrite(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    invalid = critique("revise")
    invalid["constraints"]["must_change"] = []
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), invalid, invalid])
    calls_before = len(provider.calls)
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "failed"
    assert view["selected"] is None and view["critique"] is None
    assert len(view["versions"]) == 1 and view["versions"][0]["status"] == "candidate"
    assert not view["versions"][0].get("review_report_id")
    assert provider.calls[calls_before:] == ["writer", "critic", "critic"]
    assert view["usage"]["attempts"] == 3 and view["usage"]["retries"] == 1
    assert kernel.storage.list("artifacts", run_id=run_id, artifact_type="CriticReport") == []


@pytest.mark.parametrize("fault,message", [
    ("planning", "Chapter loop requires story planning"),
    ("rewrite_limit", "Chapter rewrite limit must be zero or one"),
    ("estimate_cap", "Chapter estimate cap must be positive"),
    ("writer", "Chapter loop requires writer model route"),
    ("critic", "Chapter loop requires critic model route"),
    ("rewrite", "Chapter loop requires rewrite model route"),
])
def test_invalid_configuration_registers_no_handlers_or_external_effects(chapter, fault, message):
    """Constructor contract only; not whole application startup or model acceptance."""
    kernel, provider, _ = chapter
    if fault == "planning":
        kernel.story_planning = None
    elif fault in {"writer", "critic", "rewrite"}:
        del kernel.model_router.routes[fault]
    kwargs = {"rewrite_limit": {"max_rewrites": 2}, "estimate_cap": {"max_estimated_cost": 0}}.get(fault, {})
    transport = transport_of(kernel)
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    handlers = dict(kernel.handlers)
    with pytest.raises(ValueError, match=message):
        ChapterLoopService(kernel, **kwargs)
    assert kernel.handlers == handlers and transport.tables == before
    assert len(transport.calls) == calls and provider.calls == model_calls
