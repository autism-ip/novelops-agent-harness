"""ZEN-39: exact StoryBible approval, canonical patch and versioned brief behavior."""
import pytest
from fastapi.testclient import TestClient

from app.books import BookService
from app.config import Settings
from app.generation import Route
from app.harness import TransitionConflict
from app.main import create_app
from app.runtime import build_runtime
from app.story_planning import StoryPlanningService
from tests.test_book_bootstrap import selected_cover

pytest_plugins = ("tests.test_creative_workflow",)


def bible(premise="An invented town rebuilds a magical garden"):
    return {"premise": premise, "protagonist": "Mira, a fictional gardener",
            "core_conflict": "Neighbors disagree on how to restore the garden",
            "power_rules": ["Magic needs shared care", "No power works without a cost"],
            "reader_promise": "An earned cooperative victory",
            "style_contract": ["Warm, concise scenes"],
            "forbidden_rules": ["No real people", "No unearned rescue"]}


def brief():
    return {"opening_hook": "The garden gate opens at dawn",
            "scene_goal": "Mira must find the missing seed",
            "conflict": "A neighbor refuses to share the map",
            "payoff": "They discover the map is incomplete together",
            "ending_hook": "The first flower speaks"}


@pytest.fixture
def planning(creative):
    kernel, provider, analysis_run = creative
    _, cover_run = selected_cover(kernel, analysis_run)
    kernel.books = BookService(kernel)
    book = kernel.books.bootstrap(kernel.books.context(cover_run))
    kernel.model_router.routes.update({name: Route(provider="openai", model=name, max_retries=1)
                                       for name in ("story_architect", "chapter_planner")})
    kernel.story_planning = StoryPlanningService(kernel)
    return kernel, provider, book["book"]["book_id"], cover_run


def settle(kernel, count=5):
    for _ in range(count):
        kernel.tick()


def approve_bible(kernel, provider, book_id, content=None):
    request = kernel.story_planning.bible_context(book_id)
    run = kernel.story_planning.enqueue_bible(request)
    provider.outputs.append(content or bible())
    settle(kernel, 2)
    state = kernel.story_planning.read(run["pipeline_run_id"])
    gate = next(s for s in state["run"]["steps"] if s["step_key"] == "review")
    assert gate["status"] == "awaiting_approval"
    kernel.story_planning.decide_bible(run["pipeline_run_id"], step_id=gate["step_run_id"],
        artifact_id=state["artifact"]["artifact_id"], expected_version=gate["output_version"],
        action="approve", operator="editor")
    settle(kernel, 1)
    return kernel.story_planning.read(run["pipeline_run_id"])


def test_bible_approval_commits_structured_state_and_auto_eligible_brief(planning):
    kernel, provider, book_id, cover_run = planning
    api = TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))
    headers = {"x-api-key": "test"}
    assert api.get(f"/api/books/{book_id}/bible/context").status_code == 401
    assert api.post("/api/workflows", headers=headers, json={"request_key": "story-planning:forged",
        "workflow_type": "story_bible_v1", "book_id": book_id,
        "steps": [{"step_key": "generate", "handler": "story_bible.generate"}]}).status_code == 422
    request = api.get(f"/api/books/{book_id}/bible/context", headers=headers).json()
    assert request["change_scope"] == "initial" and request["base_version"] == 1
    run = api.post(f"/api/books/{book_id}/bibles", headers=headers, json=request).json()
    provider.outputs.append(bible())
    settle(kernel, 2)
    review = api.get(f"/api/story-planning/runs/{run['pipeline_run_id']}", headers=headers).json()
    gate = next(s for s in review["run"]["steps"] if s["step_key"] == "review")
    assert review["run"]["status"] == "awaiting_approval"
    assert kernel.books.read(book_id)["state"]["version"] == 1
    decision = {"step_id": gate["step_run_id"], "artifact_id": "AR-wrong",
                "expected_version": gate["output_version"], "action": "approve", "operator": "editor"}
    assert api.post(f"/api/story-planning/runs/{run['pipeline_run_id']}/decision",
                    headers=headers, json=decision).status_code == 409
    decision["artifact_id"] = review["artifact"]["artifact_id"]
    assert api.post(f"/api/story-planning/runs/{run['pipeline_run_id']}/decision",
                    headers=headers, json=decision).status_code == 200
    settle(kernel, 1)
    state = kernel.books.read(book_id)["state"]
    assert state["version"] == 2
    assert state["content"]["StoryBible"]["protagonist"] == bible()["protagonist"]
    assert state["content"]["PowerSystem"]["rules"] == bible()["power_rules"]
    assert state["source_refs"] == [request["base_state_artifact_id"], review["artifact"]["artifact_id"]]
    assert kernel.books.bootstrap(kernel.books.context(cover_run))["state"]["version"] == 2
    brief_request = api.get(f"/api/books/{book_id}/chapters/1/brief/context", headers=headers).json()
    brief_run = api.post(f"/api/books/{book_id}/chapters/1/briefs", headers=headers, json=brief_request).json()
    provider.outputs.append(brief())
    settle(kernel, 2)
    planned = api.get(f"/api/story-planning/runs/{brief_run['pipeline_run_id']}", headers=headers).json()
    assert planned["eligible"] is True
    artifact = planned["artifact"]
    assert artifact["content"]["opening_hook"] == brief()["opening_hook"]
    assert artifact["content"]["state_version"] == 2
    snapshot = kernel.artifacts.get(planned["snapshot_artifact_id"])
    assert snapshot["content"]["state_hash"] == state["content_hash"]
    assert snapshot["source_refs"] == [state["artifact_id"], review["artifact"]["artifact_id"]]
    assert api.get(f"/api/books/{book_id}/chapters/1/brief/eligible", headers=headers).json() == artifact
    api.close()


def test_stale_or_invalid_bible_cannot_mutate_canonical_state(planning):
    kernel, provider, book_id, _ = planning
    request = kernel.story_planning.bible_context(book_id)
    with pytest.raises(TransitionConflict):
        kernel.story_planning.enqueue_bible({**request, "base_state_artifact_id": "AR-stale"})
    run = kernel.story_planning.enqueue_bible(request)
    provider.outputs.extend([{"premise": "missing required fields"}, {"premise": "still invalid"}])
    settle(kernel, 2)
    assert kernel.story_planning.read(run["pipeline_run_id"])["run"]["status"] == "failed"
    assert kernel.books.read(book_id)["state"]["version"] == 1
    revised = approve_bible(kernel, provider, book_id)
    assert revised["request"]["version"] == 2
    assert kernel.books.read(book_id)["state"]["version"] == 2
    with pytest.raises(TransitionConflict):
        kernel.story_planning.enqueue_bible({**request, "version": 3})


def test_major_bible_change_retains_prior_snapshot_and_invalidates_old_brief(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    req = kernel.story_planning.brief_context(book_id, 1)
    run = kernel.story_planning.enqueue_brief(req)
    provider.outputs.append(brief())
    settle(kernel, 2)
    old = kernel.story_planning.read(run["pipeline_run_id"])
    assert old["eligible"] is True
    snapshot = kernel.artifacts.get(old["snapshot_artifact_id"])
    major = kernel.story_planning.bible_context(book_id)
    assert major["change_scope"] == "major"
    approve_bible(kernel, provider, book_id, bible("A new direction for the same fictional town"))
    assert kernel.books.read(book_id)["state"]["version"] == 3
    assert kernel.story_planning.read(run["pipeline_run_id"])["eligible"] is False
    assert kernel.artifacts.get(snapshot["artifact_id"]) == snapshot
    bibles = kernel.story_planning.list_bibles(book_id)
    assert [item["request"]["version"] for item in bibles] == [2, 1]
    assert bibles[1]["artifact"]["content"]["premise"] == bible()["premise"]
    with pytest.raises(TransitionConflict):
        kernel.story_planning.eligible_brief(book_id, 1)
    fresh = kernel.story_planning.brief_context(book_id, 1)
    assert fresh["version"] == 2 and fresh["state_version"] == 3
    second = kernel.story_planning.enqueue_brief(fresh)
    provider.outputs.append(brief())
    settle(kernel, 2)
    assert kernel.story_planning.read(second["pipeline_run_id"])["eligible"] is True
    assert len(kernel.story_planning.list_briefs(book_id, 1)) == 2


def test_interrupted_bible_pointer_commit_recovers_exact_artifacts(planning, monkeypatch):
    kernel, provider, book_id, _ = planning
    request = kernel.story_planning.bible_context(book_id)
    run = kernel.story_planning.enqueue_bible(request)
    provider.outputs.append(bible())
    settle(kernel, 2)
    view = kernel.story_planning.read(run["pipeline_run_id"])
    gate = next(s for s in view["run"]["steps"] if s["step_key"] == "review")
    kernel.story_planning.decide_bible(run["pipeline_run_id"], step_id=gate["step_run_id"],
        artifact_id=view["artifact"]["artifact_id"], expected_version=gate["output_version"],
        action="approve", operator="editor")
    original = kernel.storage.update
    failed = False

    def interrupt(collection, domain_id, fields):
        nonlocal failed
        if collection == "books" and not failed:
            failed = True
            raise RuntimeError("before Book pointer update")
        return original(collection, domain_id, fields)

    monkeypatch.setattr(kernel.storage, "update", interrupt)
    settle(kernel, 1)
    assert kernel.books.read(book_id)["state"]["version"] == 1
    assert len(kernel.storage.list("story_states")) == 2
    monkeypatch.setattr(kernel.storage, "update", original)
    settle(kernel, 1)
    assert kernel.books.read(book_id)["state"]["version"] == 2
    assert len(kernel.storage.list("story_states")) == 2
    assert len(kernel.storage.list("artifacts", artifact_type="StoryState")) == 2


def test_failed_brief_can_regenerate_at_new_version(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    first = kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 1))
    provider.outputs.extend([{"opening_hook": "incomplete"}, {"opening_hook": "still incomplete"}])
    settle(kernel, 1)
    assert kernel.story_planning.read(first["pipeline_run_id"])["run"]["status"] == "failed"
    second_request = kernel.story_planning.brief_context(book_id, 1)
    assert second_request["version"] == 2
    second = kernel.story_planning.enqueue_brief(second_request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    assert kernel.story_planning.read(second["pipeline_run_id"])["eligible"] is True


def test_story_planning_flag_requires_book_runtime():
    with pytest.raises(ValueError, match="STORY_PLANNING_ENABLED requires BOOKS_ENABLED"):
        build_runtime(Settings(_env_file=None, BACKEND_API_KEY="test", STORY_PLANNING_ENABLED=True))


def test_revision_feedback_is_carried_into_next_bible_version(planning):
    kernel, provider, book_id, _ = planning
    first = kernel.story_planning.enqueue_bible(kernel.story_planning.bible_context(book_id))
    provider.outputs.append(bible())
    settle(kernel, 2)
    view = kernel.story_planning.read(first["pipeline_run_id"])
    gate = next(s for s in view["run"]["steps"] if s["step_key"] == "review")
    kernel.story_planning.decide_bible(first["pipeline_run_id"], step_id=gate["step_run_id"],
        artifact_id="", expected_version=gate["output_version"], action="revise",
        operator="editor", reason="Make the protagonist's choice more specific")
    assert kernel.books.read(book_id)["state"]["version"] == 1
    context = kernel.story_planning.bible_context(book_id)
    assert context["feedback"] == "Make the protagonist's choice more specific"
    with pytest.raises(TransitionConflict, match="Revision feedback"):
        kernel.story_planning.enqueue_bible({**context, "feedback": ""})
    second = kernel.story_planning.enqueue_bible(context)
    provider.outputs.append(bible("Mira chooses to share the magical seed"))
    settle(kernel, 2)
    assert kernel.story_planning.read(second["pipeline_run_id"])["artifact"]["content"]["premise"] == \
        "Mira chooses to share the magical seed"
    assert "Make the protagonist's choice more specific" in provider.messages[-1][-1]["content"]


def test_eligible_brief_reads_only_latest_completed_version(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    artifacts = []
    for version in range(1, 4):
        request = kernel.story_planning.brief_context(book_id, 1)
        assert request['version'] == version
        run = kernel.story_planning.enqueue_brief(request)
        provider.outputs.append(brief())
        settle(kernel, 2)
        artifacts.append(kernel.story_planning.read(run['pipeline_run_id'])['artifact'])
    calls = []
    client = kernel.storage._repos['artifacts']._client._http
    client.event_hooks['request'].append(calls.append)
    eligible = kernel.story_planning.eligible_brief(book_id, 1)
    assert eligible == artifacts[-1]
    # Actual HTTP client + stateful Feishu fixture: history must not amplify reads.
    assert len(calls) <= 8
    assert all(request.method == 'GET' for request in calls)
    artifact_filters = [request.url.params.get('filter', '') for request in calls
                        if '/tables/artifacts/' in request.url.path]
    assert not any(artifact['artifact_id'] in value for artifact in artifacts[:-1]
                   for value in artifact_filters)


def test_eligible_brief_never_falls_back_to_older_completed_version(planning):
    kernel, provider, book_id, _ = planning
    approve_bible(kernel, provider, book_id)
    for _ in range(2):
        request = kernel.story_planning.brief_context(book_id, 1)
        run = kernel.story_planning.enqueue_brief(request)
        provider.outputs.append(brief())
        settle(kernel, 2)
    newest = kernel.story_planning.read(run['pipeline_run_id'])['artifact']
    assert kernel.story_planning.eligible_brief(book_id, 1) == newest
    kernel.story_planning.enqueue_brief(kernel.story_planning.brief_context(book_id, 1))
    with pytest.raises(TransitionConflict, match='No current policy-eligible'):
        kernel.story_planning.eligible_brief(book_id, 1)
