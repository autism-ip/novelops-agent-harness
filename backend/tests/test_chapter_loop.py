"""ZEN-40: verified chapter versions, actionable critique and bounded rewrite."""
import pytest
from fastapi.testclient import TestClient

from app.chapter_loop import ChapterLoopService
from app.config import Settings
from app.generation import ModelFailure, Route
from app.harness import TransitionConflict
from app.main import create_app
from app.runtime import build_runtime
from tests.test_story_planning import approve_bible, bible, brief, settle

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


def draft(snapshot_id, brief_id, chapter_no=1, *, prose=None):
    return {"chapter_no": chapter_no, "snapshot_artifact_id": snapshot_id,
            "brief_artifact_id": brief_id, "title": f"The Garden Gate {chapter_no}",
            "prose": prose or ("Mira entered the garden at dawn and chose to help her neighbors. " * 8)}


def critique(decision="pass"):
    dimension = {"score": 4, "evidence": "The scene advances the shared garden conflict."}
    return {"decision": decision, **{key: dimension for key in
            ("pacing", "style", "repetition", "dialogue", "reader_promise", "continuity", "ai_patterns")},
            "summary": "The chapter has a concrete hook and earned payoff.",
            "constraints": {"must_keep": ["Mira helps the neighbors"] if decision == "revise" else [],
                            "must_change": ["Make the conflict more specific"] if decision == "revise" else [],
                            "do_not_change": ["The garden gate opens at dawn"] if decision == "revise" else []}}


@pytest.fixture
def chapter(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    request = kernel.story_planning.brief_context(book_id, 1)
    kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    kernel.model_router.routes.update({name: Route(provider="openai", model=name, max_retries=1)
                                       for name in ("writer", "critic", "rewrite")})
    kernel.chapter_loop = ChapterLoopService(kernel)
    return kernel, provider, book_id


def start(kernel, book_id, chapter_no=1, **changes):
    request = {**kernel.chapter_loop.context(book_id, chapter_no), **changes}
    run = kernel.chapter_loop.enqueue(request)
    snapshot = kernel.chapter_loop.read(run["pipeline_run_id"])["snapshot_artifact_id"]
    return run["pipeline_run_id"], request, snapshot


def pass_run(kernel, provider, book_id, chapter_no=1, **changes):
    run_id, request, snapshot = start(kernel, book_id, chapter_no, **changes)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"], chapter_no), critique()])
    settle(kernel, 5)
    return kernel.chapter_loop.read(run_id)


def test_first_three_chapters_have_exact_sources_and_usage(chapter):
    kernel, provider, book_id = chapter
    for chapter_no in (1, 2, 3):
        if chapter_no > 1:
            request = kernel.story_planning.brief_context(book_id, chapter_no)
            kernel.story_planning.enqueue_brief(request)
            provider.outputs.append(brief())
            settle(kernel, 2)
        view = pass_run(kernel, provider, book_id, chapter_no)
        assert view["run"]["status"] == "completed"
        assert view["selected"]["version"] == 1
        assert view["selected"]["content"]["chapter_no"] == chapter_no
        snapshot = kernel.artifacts.get(view["snapshot_artifact_id"])
        assert snapshot["content"]["brief_artifact_id"] == view["request"]["brief_artifact_id"]
        assert snapshot["content"]["state_artifact_id"] == view["request"]["state_artifact_id"]
        assert view["selected"]["source_refs"][0] == snapshot["artifact_id"]
        assert view["versions"][0]["story_context_snapshot_id"] == snapshot["artifact_id"]
        assert not view["versions"][0].get("agent_team_snapshot_id")
        assert view["usage"]["attempts"] == 2
        traces = kernel.telemetry.list(run_id=view["run"]["pipeline_run_id"])
        assert {t["route"] for t in traces if t["kind"] == "model"} == {"writer", "critic"}
        assert all(t["prompt_version"] and t["latency_ms"] >= 0 for t in traces if t["kind"] == "model")
        assert all(t["input_tokens"] == 100 and t["output_tokens"] == 50 for t in traces if t["kind"] == "model")


def test_actionable_critique_rewrites_once_and_preserves_versions(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("revise"),
                             draft(snapshot, request["brief_artifact_id"], prose="A revised scene. " * 20)])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "completed"
    assert view["selected"]["version"] == 2
    assert [row["version_no"] for row in view["versions"]] == [1, 2]
    assert [row["status"] for row in view["versions"]] == ["candidate", "review"]
    assert view["critique"]["content"]["constraints"]["must_change"]
    assert view["usage"]["attempts"] == 3
    assert provider.calls[-3:] == ["writer", "critic", "rewrite"]


def test_reject_and_hard_failure_never_reach_review(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("reject")])
    settle(kernel, 5)
    rejected = kernel.chapter_loop.read(run_id)
    assert rejected["run"]["status"] == "failed"
    assert rejected["selected"] is None
    assert len(rejected["versions"]) == 1 and rejected["versions"][0]["status"] == "candidate"
    assert provider.calls[-2:] == ["writer", "critic"]
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.append(draft(snapshot, request["brief_artifact_id"], chapter_no=2))
    settle(kernel, 5)
    invalid = kernel.chapter_loop.read(run_id)
    assert invalid["run"]["status"] == "failed"
    assert invalid["versions"] == []
    assert provider.calls[-1] == "writer"


def test_inconsistent_pass_is_retried_and_cannot_promote_a_version(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    inconsistent = {**critique(), "pacing": {"score": 1, "evidence": "The scene loses its goal."}}
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), inconsistent, inconsistent])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "failed"
    assert view["selected"] is None and view["critique"] is None
    assert view["versions"][0]["status"] == "candidate"
    assert provider.calls[-3:] == ["writer", "critic", "critic"]


def test_provider_retry_and_final_lock_are_exact_and_idempotent(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([ModelFailure("RateLimited", retryable=True),
        draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "completed" and view["usage"]["retries"] == 1
    row = view["versions"][0]
    command = {"version_id": row["version_id"], "artifact_id": row["artifact_id"],
               "version_no": row["version_no"], "operator": "editor"}
    locked = kernel.chapter_loop.lock_final(book_id, 1, **command)
    assert locked["status"] == "final"
    assert kernel.chapter_loop.lock_final(book_id, 1, **command) == locked
    with pytest.raises(TransitionConflict):
        kernel.chapter_loop.context(book_id, 1)
    with pytest.raises(TransitionConflict):
        kernel.chapter_loop.lock_final(book_id, 1, **{**command, "artifact_id": "AR-wrong"})
    assert kernel.chapter_loop.versions(book_id, 1)[0]["artifact"] == view["selected"]


def test_revision_requires_exact_latest_version_and_constraints(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    prior = first["versions"][0]
    with pytest.raises(ValueError):
        start(kernel, book_id, source_version_id=prior["version_id"])
    run_id, request, snapshot = start(kernel, book_id,
        source_version_id=prior["version_id"],
        constraints={"must_keep": ["Mira"], "must_change": ["Sharper dialogue"], "do_not_change": []})
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "completed" and view["selected"]["version"] == 2
    assert view["selected"]["content"]["source_version_id"] == prior["version_id"]
    assert provider.calls[-2:] == ["rewrite", "critic"]
    assert [row["version_no"] for row in kernel.chapter_loop._versions(book_id, 1)] == [1, 2]


def test_pass_without_rewrite_uses_next_contiguous_version(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    second = pass_run(kernel, provider, book_id)
    assert [first["selected"]["version"], second["selected"]["version"]] == [1, 2]
    assert [item["record"]["version_no"] for item in kernel.chapter_loop.versions(book_id, 1)] == [2, 1]


def test_api_auth_exact_source_and_generic_forgery(chapter):
    kernel, provider, book_id = chapter
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    context_path = f"/api/books/{book_id}/chapters/1/generation/context"
    assert api.get(context_path).status_code == 401
    request = api.get(context_path, headers=headers).json()
    assert api.post("/api/workflows", headers=headers, json={"request_key": "chapter-loop:forged",
        "workflow_type": "chapter_loop_v1", "book_id": book_id,
        "steps": [{"step_key": "writer", "handler": "chapter.writer"}]}).status_code == 422
    path = f"/api/books/{book_id}/chapters/1/generations"
    assert api.post(path, headers=headers, json={**request, "brief_artifact_id": "AR-stale"}).status_code == 409
    run = api.post(path, headers=headers, json=request)
    assert run.status_code == 201
    assert api.post(path, headers=headers, json=request).json()["pipeline_run_id"] == run.json()["pipeline_run_id"]
    snapshot = kernel.chapter_loop.read(run.json()["pipeline_run_id"])["snapshot_artifact_id"]
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    assert api.get(path, headers=headers).json()[0]["selected"]["artifact_type"] == "ChapterVersion"
    api.close()


def test_hard_literal_rule_blocks_chapter_version(planning):
    kernel, provider, book_id, _ = planning
    content = {**bible(), "forbidden_rules": ["literal:unearned rescue"]}
    approve_bible(kernel, provider, book_id, content)
    kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 1))
    provider.outputs.append(brief())
    settle(kernel, 2)
    kernel.model_router.routes.update({name: Route(provider="openai", model=name)
                                       for name in ("writer", "critic", "rewrite")})
    kernel.chapter_loop = ChapterLoopService(kernel)
    run_id, request, snapshot = start(kernel, book_id)
    bad_prose = "Mira chose an unearned rescue in the garden. " * 9
    provider.outputs.append(draft(snapshot, request["brief_artifact_id"], prose=bad_prose))
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "failed" and view["versions"] == []
    assert provider.calls[-1] == "writer"


def test_provider_failure_and_rewrite_budget_exhaustion(chapter):
    kernel, provider, book_id = chapter
    run_id, _, _ = start(kernel, book_id)
    provider.outputs.extend([ModelFailure("Timeout", retryable=True), ModelFailure("Timeout", retryable=True)])
    settle(kernel, 5)
    failed = kernel.chapter_loop.read(run_id)
    assert failed["run"]["status"] == "failed" and failed["versions"] == []
    assert failed["usage"]["attempts"] == 2 and failed["usage"]["retries"] == 1
    kernel.chapter_loop = ChapterLoopService(kernel, max_rewrites=0)
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("revise")])
    settle(kernel, 5)
    exhausted = kernel.chapter_loop.read(run_id)
    assert exhausted["run"]["status"] == "failed" and len(exhausted["versions"]) == 1
    assert provider.calls[-2:] == ["writer", "critic"]


def test_estimated_cost_cap_stops_additional_rewrite(chapter):
    kernel, provider, book_id = chapter
    kernel.model_router.routes.update({name: Route(provider="openai", model=name,
        input_cost_per_million=1, output_cost_per_million=1)
        for name in ("writer", "critic", "rewrite")})
    kernel.chapter_loop = ChapterLoopService(kernel, max_estimated_cost=0.0002)
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("revise")])
    settle(kernel, 5)
    view = kernel.chapter_loop.read(run_id)
    assert view["run"]["status"] == "failed"
    assert view["usage"]["estimated_cost"] == pytest.approx(0.0003)
    assert len(view["versions"]) == 1 and provider.calls[-2:] == ["writer", "critic"]


def test_stale_story_state_cannot_generate_chapter(chapter):
    kernel, provider, book_id = chapter
    request = kernel.chapter_loop.context(book_id, 1)
    approve_bible(kernel, provider, book_id, {**bible(), "premise": "A different garden direction"})
    with pytest.raises(TransitionConflict):
        kernel.chapter_loop.enqueue(request)
    assert kernel.storage.list("chapter_versions") == []


def test_flag_requires_story_planning():
    with pytest.raises(ValueError, match="CHAPTER_LOOP_ENABLED requires STORY_PLANNING_ENABLED"):
        build_runtime(Settings(BACKEND_API_KEY="test", CHAPTER_LOOP_ENABLED=True))
