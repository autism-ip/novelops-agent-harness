"""A real chapter-service sequence carries prior final prose through every model role."""
import json

import pytest

from app.generation import digest
from app.harness import encode
from app.storage import AmbiguousWrite
from tests.test_chapter_loop import chapter as chapter, critique, draft, pass_run, start
from tests.test_story_planning import brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


def locked_first(kernel, provider, book_id):
    view = pass_run(kernel, provider, book_id)
    row = view["versions"][0]
    locked = kernel.chapter_loop.lock_final(book_id, 1, version_id=row["version_id"],
        artifact_id=row["artifact_id"], version_no=row["version_no"], operator="editor")
    return locked, view["selected"]


def plan_second(kernel, provider, book_id):
    run = kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 2))
    provider.outputs.append(brief())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    assert view["eligible"] is True
    return kernel.artifacts.get(view["snapshot_artifact_id"])


@pytest.mark.parametrize("decision", ["pass", "revise"])
def test_writer_critic_and_conditional_rewrite_share_exact_prior_final_history(chapter, decision):
    kernel, provider, book_id = chapter
    locked, artifact = locked_first(kernel, provider, book_id)
    planning = plan_second(kernel, provider, book_id)
    run_id, request, snapshot_id = start(kernel, book_id, chapter_no=2)
    snapshot = kernel.artifacts.get(snapshot_id)
    history = planning["content"]["prior_final_chapters"]
    assert snapshot["content"]["prior_final_chapters"] == history
    assert history[0]["artifact_id"] == artifact["artifact_id"]
    assert snapshot["source_refs"][-1] == artifact["artifact_id"]
    offset = len(provider.messages)
    provider.outputs.extend([draft(snapshot_id, request["brief_artifact_id"], chapter_no=2), critique(decision)])
    if decision == "revise":
        provider.outputs.append(draft(snapshot_id, request["brief_artifact_id"], chapter_no=2,
            prose="Mira turned from the repaired gate to organize tomorrow's planting. " * 8))
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "completed"
    assert len(view["versions"]) == (2 if decision == "revise" else 1)
    for messages in provider.messages[offset:]:
        inputs = json.loads(messages[1]["content"])
        assert inputs["snapshot"]["prior_final_chapters"] == history
        assert history[0]["content"]["prose"] in messages[1]["content"]
    assert provider.calls[-(3 if decision == "revise" else 2):] == (
        ["writer", "critic", "rewrite"] if decision == "revise" else ["writer", "critic"])
    assert kernel.storage.get("chapter_versions", locked["version_id"]) == locked
    assert kernel.artifacts.get(artifact["artifact_id"]) == artifact


def test_new_final_history_invalidates_a_queued_writer_without_generating(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    plan_second(kernel, provider, book_id)
    run_id, _, snapshot_id = start(kernel, book_id, chapter_no=2)
    original = kernel.artifacts.get(snapshot_id)
    row = first["versions"][0]
    kernel.chapter_loop.lock_final(book_id, 1, version_id=row["version_id"], artifact_id=row["artifact_id"],
        version_no=row["version_no"], operator="editor")
    calls = list(provider.calls)
    settle(kernel, 1)
    assert kernel.get(run_id)["status"] == "failed"
    assert provider.calls == calls
    assert kernel.storage.list("chapter_versions", book_id=book_id, chapter_no=2) == []
    assert kernel.artifacts.get(snapshot_id) == original


@pytest.mark.parametrize("fault", ["drop_content", "change_prose", "drop_reference"])
def test_chapter_snapshot_cannot_lose_or_change_frozen_planning_history(chapter, fault):
    kernel, provider, book_id = chapter
    locked_first(kernel, provider, book_id)
    plan_second(kernel, provider, book_id)
    run_id, _, snapshot_id = start(kernel, book_id, chapter_no=2)
    original = kernel.artifacts.get(snapshot_id)
    changed = json.loads(encode(original))
    if fault == "drop_content":
        changed["content"].pop("prior_final_chapters", None)
    elif fault == "change_prose":
        changed["content"]["prior_final_chapters"][0]["content"]["prose"] = "The key was never returned. " * 12
    else:
        changed["source_refs"] = changed["source_refs"][:-1]
    changed["content_hash"] = digest(changed["content"])
    kernel.storage.update("artifacts", snapshot_id, {"payload_json": encode(changed)})
    calls = list(provider.calls)
    writer = next(s for s in kernel.get(run_id)["steps"] if s["step_key"] == "writer")
    with kernel.writer, pytest.raises(AmbiguousWrite, match="Chapter snapshot history changed"):
        kernel.chapter_loop.write(writer)
    assert provider.calls == calls
    assert kernel.storage.list("chapter_versions", book_id=book_id, chapter_no=2) == []
    kernel.storage.update("artifacts", snapshot_id, {"payload_json": encode(original)})
    assert kernel.chapter_loop.read(run_id)["current"] is True
