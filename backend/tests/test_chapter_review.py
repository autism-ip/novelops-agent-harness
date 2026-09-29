"""ZEN-41: exact editorial commands, revision tasks and selective gates."""
import pytest
from fastapi.testclient import TestClient

from app.chapter_loop import ChapterLoopService
from app.config import Settings
from app.harness import TransitionConflict
from app.main import create_app
from app.generation import Route
from tests.test_chapter_loop import critique, draft, pass_run, start
from tests.test_story_planning import approve_bible, brief, settle

pytest_plugins = ("tests.test_story_planning",)


@pytest.fixture
def chapter(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 1))
    provider.outputs.append(brief())
    settle(kernel, 2)
    kernel.model_router.routes.update({name: Route(provider="openai", model=name, max_retries=1)
                                       for name in ("writer", "critic", "rewrite")})
    kernel.chapter_loop = ChapterLoopService(kernel)
    return kernel, provider, book_id

def target(view, *, operator="editor"):
    row = next(row for row in view["versions"] if row["artifact_id"] == view["selected"]["artifact_id"])
    return {"run_id": view["run"]["pipeline_run_id"], "version_id": row["version_id"],
            "artifact_id": row["artifact_id"], "version_no": row["version_no"], "operator": operator}


def test_first_chapter_gate_requires_exact_approval_then_final_lock(chapter):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, review_first_n=1)
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    review = kernel.chapter_loop.review_state(book_id, 1)
    view = review["latest"]
    assert view["run"]["status"] == "awaiting_approval"
    assert review["review_gate"]["status"] == "awaiting_approval"
    assert review["snapshot"]["artifact_id"] == snapshot
    assert review["story_state"]["StoryBible"]["bible_artifact_id"] == review["story_bible"]["artifact_id"]
    assert review["brief"]["artifact_id"] == request["brief_artifact_id"]
    assert review["verification"]["content"]["passed"] is True
    assert len(review["traces"]) >= 5
    command = {**target(view), "expected_gate_version": review["review_gate"]["output_version"],
               "action": "approve"}
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    path = f"/api/books/{book_id}/chapters/1"
    headers = {"x-api-key": "test"}
    assert api.get(path + "/review").status_code == 401
    assert api.post(f"/api/workflows/steps/{review['review_gate']['step_id']}/decision",
        headers=headers, json={"action": "approve", "expected_version": command["expected_gate_version"],
                               "operator": "editor"}).status_code == 422
    assert api.post(path + "/review/decision", headers=headers,
        json={**command, "expected_gate_version": 99}).status_code == 409
    approved = api.post(path + "/review/decision", headers=headers, json=command)
    assert approved.status_code == 200
    assert approved.json()["version"]["status"] == "approved"
    assert approved.json()["run"]["status"] == "completed"
    assert api.post(path + "/review/decision", headers=headers, json=command).status_code == 200
    locked = api.post(path + "/final-lock", headers=headers, json={
        key: command[key] for key in ("version_id", "artifact_id", "version_no", "operator")})
    assert locked.status_code == 200 and locked.json()["status"] == "final"
    assert len(api.get(path + "/versions", headers=headers).json()) == 1
    api.close()


def test_routine_reject_regenerate_preserves_older_version(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    command = {**target(first), "action": "reject", "reason": "The ending misses the hook"}
    result = kernel.chapter_loop.decide_review(book_id, 1, **command)
    assert result["version"]["status"] == "rejected"
    assert kernel.chapter_loop.decide_review(book_id, 1, **command)["version"]["status"] == "rejected"
    second = pass_run(kernel, provider, book_id)
    assert second["selected"]["version"] == 2
    assert [(item["record"]["version_no"], item["record"]["status"])
            for item in kernel.chapter_loop.versions(book_id, 1)] == [(2, "review"), (1, "rejected")]
    history = kernel.chapter_loop.review_state(book_id, 1)["versions"]
    assert all(item["report"] and item["verification"] for item in history)
    assert history[0]["report"]["artifact_id"] != history[1]["report"]["artifact_id"]
    assert history[0]["verification"]["artifact_id"] != history[1]["verification"]["artifact_id"]
    assert all(item["artifact"]["content"]["verification_artifact_id"] ==
               item["verification"]["artifact_id"] for item in history)
    with pytest.raises(TransitionConflict):
        kernel.chapter_loop.decide_review(book_id, 1, **command)


def test_revision_task_binds_source_constraints_and_new_version(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    command = {**target(first), "constraints": {
        "must_keep": ["Mira helps her neighbors"], "must_change": ["Sharper dialogue"],
        "do_not_change": ["The gate opens at dawn"]}}
    created = kernel.chapter_loop.request_revision(book_id, 1, **command)
    assert created["task"]["from_version_id"] == command["version_id"]
    assert created["task"]["source_artifact_id"] == command["artifact_id"]
    assert created["task"]["status"] == "queued"
    assert created["run"]["pipeline_run_id"] == created["task"]["run_id"]
    assert kernel.chapter_loop.request_revision(book_id, 1, **command)["run"] == created["run"]
    for changed in ({"run_id": "PR-other"}, {"artifact_id": "AR-other"}, {"version_no": 99}):
        with pytest.raises(TransitionConflict, match="Revision replay does not match"):
            kernel.chapter_loop.request_revision(book_id, 1, **{**command, **changed})
    with pytest.raises(TransitionConflict):
        kernel.chapter_loop.request_revision(book_id, 1, **{**command, "constraints": {
            **command["constraints"], "must_change": ["Change the scene order"]}})
    run_id = created["run"]["pipeline_run_id"]
    snapshot = kernel.chapter_loop.read(run_id)["snapshot_artifact_id"]
    provider.outputs.extend([draft(snapshot, first["request"]["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    latest = kernel.chapter_loop.read(run_id)
    assert latest["run"]["status"] == "completed"
    assert latest["selected"]["version"] == 2
    assert latest["selected"]["content"]["source_version_id"] == command["version_id"]
    assert [item["record"]["version_no"] for item in kernel.chapter_loop.versions(book_id, 1)] == [2, 1]
    assert provider.calls[-2:] == ["rewrite", "critic"]


def test_low_score_anomaly_gate_and_revision_action(chapter):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, review_score_threshold=3)
    run_id, request, snapshot = start(kernel, book_id)
    note = {**critique(), "pacing": {"score": 3, "evidence": "The middle scene slows down."}}
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), note])
    settle(kernel, 5)
    review = kernel.chapter_loop.review_state(book_id, 1)
    assert review["latest"]["run"]["status"] == "awaiting_approval"
    command = {**target(review["latest"]), "expected_gate_version": review["review_gate"]["output_version"],
               "constraints": {"must_keep": [], "must_change": ["Tighten the middle scene"],
                               "do_not_change": []}}
    result = kernel.chapter_loop.request_revision(book_id, 1, **command)
    assert result["task"]["status"] == "queued"
    assert kernel.chapter_loop.read(run_id)["run"]["status"] == "failed"
    assert kernel.chapter_loop.request_revision(book_id, 1, **command)["task"] == result["task"]
    assert kernel.chapter_loop.read(result["run"]["pipeline_run_id"])["request"]["source_version_id"] == command["version_id"]


def test_rewrite_history_exposes_the_draft_that_critic_actually_scored(chapter):
    kernel, provider, book_id = chapter
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique("revise"),
                             draft(snapshot, request["brief_artifact_id"], prose="A revised scene. " * 20)])
    settle(kernel, 5)
    history = kernel.chapter_loop.review_state(book_id, 1)["versions"]
    rewritten, first_draft = history
    assert rewritten["record"]["status"] == "review"
    assert first_draft["record"]["status"] == "candidate"
    assert first_draft["report"]["source_refs"][2] == first_draft["artifact"]["artifact_id"]
    assert rewritten["report"]["artifact_id"] == first_draft["report"]["artifact_id"]
    assert rewritten["verification"]["artifact_id"] != first_draft["verification"]["artifact_id"]
    assert rewritten["artifact"]["artifact_id"] != first_draft["report"]["source_refs"][2]
    assert kernel.chapter_loop.read(run_id)["selected"]["artifact_id"] == rewritten["artifact"]["artifact_id"]
