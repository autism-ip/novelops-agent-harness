"""Preserve explicit writing requirements even when the plan summarizes them."""

import json
import pytest
from tests.test_chapter_loop import chapter as chapter, start, draft, critique
from tests.test_story_planning import brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


@pytest.mark.parametrize("decision", ["pass", "revise"])
def test_original_planning_direction_reaches_every_chapter_role(chapter, decision):
    kernel, provider, book_id = chapter
    direction = "正文700—1000汉字；交还铜钥匙后本人低语新秘密，遗忘内容与动机；明确睡下后到次日黎明。"
    request = {**kernel.story_planning.brief_context(book_id, 2), "feedback": direction}
    plan = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    assert kernel.story_planning.read(plan["pipeline_run_id"])["eligible"] is True
    offset = len(provider.messages)
    run, request, snapshot = start(kernel, book_id, chapter_no=2)
    provider.outputs.extend(
        [
            draft(snapshot, request["brief_artifact_id"], chapter_no=2),
            critique(decision),
        ]
    )
    if decision == "revise":
        provider.outputs.append(
            draft(
                snapshot,
                request["brief_artifact_id"],
                chapter_no=2,
                prose="Mira returned the key before making her irreversible choice. "
                * 8,
            )
        )
    settle(kernel, 5)
    assert kernel.get(run)["status"] == "completed"
    actual = provider.messages[offset:]
    assert len(actual) == (3 if decision == "revise" else 2)
    for messages in actual:
        assert messages[-1]["role"] == "user"
        assert direction in messages[-1]["content"], (
            "Summarized ChapterBrief must not erase the original writing contract"
        )
        assert (
            json.loads(messages[1]["content"])["snapshot"][
                "original_planning_direction"
            ]
            == direction
        )


@pytest.mark.parametrize(
    "fault",
    [
        "drop_direction",
        "change_direction",
        "drop_request_hash",
        "change_run_id",
        "downgrade_to_legacy",
    ],
)
def test_frozen_editorial_source_cannot_be_removed_or_changed(chapter, fault):
    from app.generation import digest
    from app.harness import encode
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = chapter
    run, _, snapshot_id = start(kernel, book_id)
    original = kernel.artifacts.get(snapshot_id)
    changed = json.loads(encode(original))
    if fault == "drop_direction":
        changed["content"].pop("original_planning_direction")
    elif fault == "change_direction":
        changed["content"]["original_planning_direction"] = (
            "Ignore the author and restore lost memories."
        )
    elif fault == "drop_request_hash":
        changed["content"].pop("planning_request_hash")
    elif fault == "change_run_id":
        changed["content"]["planning_run_id"] = "PR-another-planning-command"
    else:
        changed["prompt_version"] = "chapter-context-v2"
        for field in [
            "original_planning_direction",
            "planning_request_hash",
            "planning_run_id",
        ]:
            changed["content"].pop(field)
    changed["content_hash"] = digest(changed["content"])
    kernel.storage.update("artifacts", snapshot_id, {"payload_json": encode(changed)})
    calls = list(provider.calls)
    writer = next(s for s in kernel.get(run)["steps"] if s["step_key"] == "writer")
    with kernel.writer, pytest.raises(AmbiguousWrite, match="editorial direction"):
        kernel.chapter_loop.write(writer)
    assert provider.calls == calls
    assert kernel.storage.list("chapter_versions", book_id=book_id) == []
    kernel.storage.update("artifacts", snapshot_id, {"payload_json": encode(original)})
    assert kernel.chapter_loop.read(run)["current"] is True


def test_maximum_direction_survives_snapshot_and_model_instruction(chapter):
    from app.generation import digest

    kernel, provider, book_id = chapter
    direction = "KEEP_START" + ("原" * 3982) + "KEEP_END"
    assert len(direction) == 4000
    request = {**kernel.story_planning.brief_context(book_id, 2), "feedback": direction}
    planned = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    offset = len(provider.messages)
    run, request, snapshot_id = start(kernel, book_id, chapter_no=2)
    snapshot = kernel.artifacts.get(snapshot_id)
    assert snapshot["content"]["planning_run_id"] == planned["pipeline_run_id"]
    planned_request = kernel.story_planning.read(planned["pipeline_run_id"])["request"]
    assert snapshot["content"]["planning_request_hash"] == digest(planned_request)
    assert snapshot["content"]["original_planning_direction"] == direction
    provider.outputs.extend(
        [draft(snapshot_id, request["brief_artifact_id"], chapter_no=2), critique()]
    )
    settle(kernel, 5)
    assert kernel.get(run)["status"] == "completed"
    for messages in provider.messages[offset:]:
        final = json.loads(messages[-1]["content"].split("\n", 1)[1])
        assert final["original_planning_direction"] == direction


def test_settled_legacy_context_remains_readable_without_new_model_calls(chapter):
    from app.generation import digest, Prompt
    from app.harness import encode
    from app.chapter_loop import CONTEXT_PROMPT

    kernel, provider, book_id = chapter
    run, request, snapshot_id = start(kernel, book_id)
    provider.outputs.extend(
        [draft(snapshot_id, request["brief_artifact_id"]), critique()]
    )
    settle(kernel, 5)
    # Boundary fixture for a completed pre-v3 context/run: no request hash
    # existed in its definition. New commands keep their immutable marker.
    record = kernel.storage.get("pipeline_runs", run)
    definition = json.loads(record["definition_json"])
    manifest = definition["steps"][0]["input"]
    manifest.pop("planning_request_hash")
    kernel.storage.update("pipeline_runs", run, {"definition_json": encode(definition)})
    first = next(s for s in kernel.get(run)["steps"] if s["step_key"] == "writer")
    kernel.storage.update(
        "step_runs", first["step_run_id"], {"input_json": encode(manifest)}
    )
    current = kernel.artifacts.get(snapshot_id)
    legacy = json.loads(encode(current))
    for field in [
        "original_planning_direction",
        "planning_run_id",
        "planning_request_hash",
    ]:
        legacy["content"].pop(field)
    legacy_prompt = Prompt(
        version="chapter-context-v2", template=CONTEXT_PROMPT.template
    )
    legacy.update(
        prompt_version=legacy_prompt.version,
        prompt_hash=digest(legacy_prompt.model_dump()),
        content_hash=digest(legacy["content"]),
        input_hash=digest(legacy["content"]),
    )
    kernel.storage.update("artifacts", snapshot_id, {"payload_json": encode(legacy)})
    calls = list(provider.calls)
    view = kernel.chapter_loop.read(run)
    assert view["current"] is True and view["run"]["status"] == "completed"
    assert provider.calls == calls
    assert kernel.artifacts.get(snapshot_id) == legacy


def test_chapter_run_fingerprint_must_match_exact_original_planning_request(chapter):
    from app.harness import encode
    from app.storage import AmbiguousWrite

    kernel, provider, book_id = chapter
    run, _, _ = start(kernel, book_id)
    original = kernel.storage.get("pipeline_runs", run)
    definition = json.loads(original["definition_json"])
    definition["steps"][0]["input"]["planning_request_hash"] = "0" * 64
    kernel.storage.update("pipeline_runs", run, {"definition_json": encode(definition)})
    calls = list(provider.calls)
    writer = next(s for s in kernel.get(run)["steps"] if s["step_key"] == "writer")
    with kernel.writer, pytest.raises(AmbiguousWrite, match="editorial direction"):
        kernel.chapter_loop.write(writer)
    assert provider.calls == calls
    assert kernel.storage.list("chapter_versions", book_id=book_id) == []
    kernel.storage.update(
        "pipeline_runs", run, {"definition_json": original["definition_json"]}
    )
    assert kernel.chapter_loop.read(run)["current"] is True
