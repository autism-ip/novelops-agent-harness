"""Durable chapter conflicts halt before another model or output write."""
import json

import pytest

from app.harness import encode
from app.storage import AmbiguousWrite
from tests.test_chapter_loop import chapter as chapter, critique, draft, start
from tests.test_story_planning import settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


def transport_of(kernel):
    return kernel.storage._repos["artifacts"]._client._http._transport.handler


def assert_reads_only(transport, offset):
    assert all(request.method == "GET" or request.method == "POST"
               and request.url.path.endswith("/records/search")
               for request in transport.calls[offset:])


@pytest.mark.parametrize("fault", ["unreadable", "empty_steps", "changed_definition"])
def test_corrupt_run_manifest_blocks_context_without_writes(chapter, fault):
    kernel, provider, book_id = chapter
    run_id, request, _ = start(kernel, book_id)
    original = kernel.storage.get("pipeline_runs", run_id)
    definition = json.loads(original["definition_json"])
    if fault == "unreadable":
        changed = "{"
    elif fault == "empty_steps":
        changed = encode({**definition, "steps": []})
    else:
        changed = encode({**definition, "book_id": "BK-another"})
    kernel.storage.update("pipeline_runs", run_id, {"definition_json": changed})
    transport = transport_of(kernel)
    offset, calls = len(transport.calls), list(provider.calls)
    with pytest.raises(AmbiguousWrite, match="Invalid chapter workflow definition"):
        kernel.chapter_loop.context(book_id, 1)
    assert_reads_only(transport, offset)
    assert provider.calls == calls
    assert kernel.storage.list("chapter_versions") == []
    kernel.storage.update("pipeline_runs", run_id, {"definition_json": original["definition_json"]})
    assert kernel.chapter_loop.enqueue(request)["pipeline_run_id"] == run_id


@pytest.mark.parametrize("fault,detail", [
    ("unreadable", "Rewrite selection is unreadable"),
    ("empty_refs", "Rewrite selection is unreadable"),
    ("foreign_artifact", "Final selection does not belong to the chapter run"),
    ("missing_projection", "Selected ChapterVersion projection missing"),
    ("changed_projection", "Selected ChapterVersion projection missing"),
    ("changed_status", "Selected ChapterVersion review status changed"),
    ("changed_report", "Selected ChapterVersion review status changed"),
])
def test_final_verification_rejects_ambiguous_selection_and_exactly_recovers(chapter, fault, detail):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 4)
    run = kernel.get(run_id)
    final = next(step for step in run["steps"] if step["step_key"] == "final_verify")
    rewrite = next(step for step in run["steps"] if step["step_key"] == "rewrite")
    assert final["status"] == "pending" and rewrite["status"] == "success"
    original = kernel.storage.list("chapter_versions", book_id=book_id)[0]
    artifact = kernel.artifacts.get(original["artifact_id"])
    if fault in {"unreadable", "empty_refs", "foreign_artifact"}:
        output = "{" if fault == "unreadable" else encode({"output_refs": [] if fault == "empty_refs" else [snapshot]})
        kernel.storage.update("step_runs", rewrite["step_run_id"], {"output_json": output})
    elif fault == "missing_projection":
        kernel.storage.delete("chapter_versions", original["version_id"])
    else:
        changes = {"artifact_id": snapshot} if fault == "changed_projection" else (
            {"status": "approved"} if fault == "changed_status" else {"status": "review", "review_report_id": snapshot})
        kernel.storage.update("chapter_versions", original["version_id"], changes)
    transport = transport_of(kernel)
    offset, calls = len(transport.calls), list(provider.calls)
    with kernel.writer, pytest.raises(AmbiguousWrite, match=detail):
        kernel.chapter_loop.final_verify(final)
    assert_reads_only(transport, offset)
    assert provider.calls == calls
    assert kernel.artifacts.get(original["artifact_id"]) == artifact
    if fault in {"unreadable", "empty_refs", "foreign_artifact"}:
        kernel.storage.update("step_runs", rewrite["step_run_id"], {"output_json": rewrite["output_json"]})
    elif fault == "missing_projection":
        kernel.storage.ensure("chapter_versions", original)
    else:
        kernel.storage.update("chapter_versions", original["version_id"], original)
    settle(kernel, 1)
    recovered = kernel.chapter_loop.read(run_id)
    assert recovered["run"]["status"] in {"completed", "awaiting_approval"}
    assert recovered["selected"] == artifact
    assert len(recovered["versions"]) == 1 and recovered["versions"][0]["status"] == "review"
    assert provider.calls == calls


@pytest.mark.parametrize("fault", ["truncated_refs", "reordered_refs", "book_id", "chapter_no",
    "state_artifact_id", "state_version", "version_no", "source_version_id",
    "snapshot_artifact_id", "brief_artifact_id", "run_id", "chapter_id", "verification_artifact_id",
    "bool:chapter_no", "bool:state_version", "bool:version_no"])
def test_final_selection_validates_domain_provenance_not_only_content_hash(chapter, fault):
    from app.generation import digest

    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 4)
    version = kernel.storage.list("chapter_versions", book_id=book_id)[0]
    original = kernel.storage.get("artifacts", version["artifact_id"])
    payload = json.loads(original["payload_json"])
    if fault == "truncated_refs":
        payload["source_refs"] = payload["source_refs"][:2]
    elif fault == "reordered_refs":
        payload["source_refs"][0:2] = reversed(payload["source_refs"][0:2])
    elif fault.startswith("bool:"):
        payload["content"][fault.removeprefix("bool:")] = True
        payload["content_hash"] = digest(payload["content"])
    elif fault in {"run_id", "chapter_id"}:
        payload[fault] = "different-source"
    else:
        value = payload["content"][fault]
        payload["content"][fault] = value + 1 if isinstance(value, int) else "different-source"
        payload["content_hash"] = digest(payload["content"])
    # A self-consistent generic Artifact envelope is insufficient to authorize a
    # chapter transition. Keep its hash valid to exercise the domain boundary.
    kernel.storage.update("artifacts", version["artifact_id"], {"payload_json": encode(payload)})
    assert kernel.artifacts.get(version["artifact_id"])["content_hash"] == payload["content_hash"]
    transport = transport_of(kernel)
    offset, calls = len(transport.calls), list(provider.calls)
    final = next(s for s in kernel.get(run_id)["steps"] if s["step_key"] == "final_verify")
    with kernel.writer, pytest.raises(AmbiguousWrite, match="Final ChapterVersion provenance changed"):
        kernel.chapter_loop.final_verify(final)
    assert_reads_only(transport, offset)
    assert provider.calls == calls
    assert kernel.storage.get("chapter_versions", version["version_id"]) == version
    kernel.storage.update("artifacts", version["artifact_id"], {"payload_json": original["payload_json"]})
    settle(kernel, 1)
    result = kernel.chapter_loop.read(run_id)
    assert result["run"]["status"] in {"completed", "awaiting_approval"}
    assert result["selected"] == json.loads(original["payload_json"])
    assert len(result["versions"]) == 1 and provider.calls == calls


def test_final_verification_replay_is_read_only_with_rewrites_disabled(chapter):
    from app.chapter_loop import ChapterLoopService

    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, max_rewrites=0)
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "completed" and len(view["versions"]) == 1
    original = kernel.storage.get("chapter_versions", view["versions"][0]["version_id"])
    final = next(s for s in view["run"]["steps"] if s["step_key"] == "final_verify")
    transport = transport_of(kernel)
    offset, calls = len(transport.calls), list(provider.calls)
    with kernel.writer:
        replay = kernel.chapter_loop.final_verify(final)
    assert replay == json.loads(final["output_json"])
    assert_reads_only(transport, offset)
    assert kernel.storage.get("chapter_versions", original["version_id"]) == original
    assert provider.calls == calls


@pytest.mark.parametrize("fault", ["changed_verification", "pass_selected_rewrite", "revise_selected_original"])
def test_final_verification_checks_evidence_and_critic_selection_before_promotion(chapter, fault):
    from app.generation import digest
    from app.harness import PermanentStepFailure

    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("revise"),
                             draft(snapshot, request["brief_artifact_id"], prose="Mira asked her neighbors to repair the gate together. " * 8)])
    settle(kernel, 4)
    run = kernel.get(run_id)
    versions = kernel.storage.list("chapter_versions", book_id=book_id)
    assert len(versions) == 2 and all(row["status"] == "candidate" for row in versions)
    rewrite = next(s for s in run["steps"] if s["step_key"] == "rewrite")
    final = next(s for s in run["steps"] if s["step_key"] == "final_verify")
    selected = kernel.artifacts.get(json.loads(rewrite["output_json"])["output_refs"][0])
    if fault == "revise_selected_original":
        original = min(versions, key=lambda row: row["version_no"])
        kernel.storage.update("step_runs", rewrite["step_run_id"],
                              {"output_json": encode({"output_refs": [original["artifact_id"]]})})
        expected, detail = AmbiguousWrite, "Revision decision did not select a rewritten version"
    else:
        artifact_id = selected["content"]["verification_artifact_id"] if fault == "changed_verification" else next(
            row["review_report_id"] for row in versions if row.get("review_report_id"))
        original = kernel.storage.get("artifacts", artifact_id)
        payload = json.loads(original["payload_json"])
        if fault == "changed_verification":
            payload["content"]["checks"]["prose_length"] = False
            expected, detail = PermanentStepFailure, None
        else:
            payload["content"] = critique()
            expected, detail = AmbiguousWrite, "Pass decision selected a rewritten version"
        payload["content_hash"] = digest(payload["content"])
        kernel.storage.update("artifacts", artifact_id, {"payload_json": encode(payload)})
    transport = transport_of(kernel)
    offset, calls = len(transport.calls), list(provider.calls)
    with kernel.writer, pytest.raises(expected, match=detail):
        kernel.chapter_loop.final_verify(final)
    assert_reads_only(transport, offset)
    assert kernel.storage.list("chapter_versions", book_id=book_id) == versions
    assert provider.calls == calls
    if fault == "revise_selected_original":
        kernel.storage.update("step_runs", rewrite["step_run_id"], {"output_json": rewrite["output_json"]})
    else:
        kernel.storage.update("artifacts", artifact_id, {"payload_json": original["payload_json"]})
    settle(kernel, 1)
    result = kernel.chapter_loop.read(run_id)
    assert result["run"]["status"] == "completed" and result["selected"] == selected
    assert len(result["versions"]) == 2 and provider.calls == calls
