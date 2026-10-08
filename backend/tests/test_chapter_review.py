"""ZEN-41: exact editorial commands, revision tasks and selective gates."""
import json

import pytest
from fastapi.testclient import TestClient

from app.chapter_loop import ChapterLoopService
from app.config import Settings
from app.harness import TransitionConflict, stable_id
from app.main import create_app
from app.generation import Route
from app.storage import AmbiguousWrite
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
    newer, older = history
    kernel.storage.update("chapter_versions", newer["record"]["version_id"],
                          {"review_report_id": older["report"]["artifact_id"]})
    with pytest.raises(AmbiguousWrite, match="review report provenance"):
        kernel.chapter_loop.versions(book_id, 1)
    kernel.storage.update("chapter_versions", newer["record"]["version_id"],
                          {"review_report_id": newer["report"]["artifact_id"],
                           "artifact_id": older["artifact"]["artifact_id"]})
    with pytest.raises(AmbiguousWrite, match="same Artifact"):
        kernel.chapter_loop.versions(book_id, 1)


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
    queued_task = kernel.chapter_loop.review_state(book_id, 1)["revision_tasks"][0]
    assert queued_task["run_status"] == created["run"]["status"]
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
    completed_task = kernel.chapter_loop.review_state(book_id, 1)["revision_tasks"][0]
    assert completed_task["status"] == "queued"
    assert completed_task["run_status"] == "completed"
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


@pytest.mark.parametrize("decision,max_rewrites", [("reject", 1), ("revise", 0)])
def test_low_score_terminal_critic_still_reaches_editor(chapter, decision, max_rewrites):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, max_rewrites=max_rewrites,
                                              review_score_threshold=3)
    run_id, request, snapshot = start(kernel, book_id)
    report = {**critique(decision), "pacing": {"score": 2, "evidence": "The chapter loses momentum."}}
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), report])
    settle(kernel, 5)
    review = kernel.chapter_loop.review_state(book_id, 1)
    assert review["latest"]["run"]["status"] == "awaiting_approval"
    assert review["latest"]["selected"]["version"] == 1
    assert review["review_gate"]["status"] == "awaiting_approval"
    assert review["latest"]["critique"]["content"]["decision"] == decision
    assert provider.calls[-2:] == ["writer", "critic"]
    assert kernel.chapter_loop.read(run_id)["versions"][0]["status"] == "review"


def test_review_state_expands_only_latest_run(chapter, monkeypatch):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    latest = pass_run(kernel, provider, book_id)
    read = kernel.chapter_loop.read
    expanded = []
    def counted(run_id, **options):
        expanded.append(run_id)
        return read(run_id, **options)
    monkeypatch.setattr(kernel.chapter_loop, "read", counted)
    review = kernel.chapter_loop.review_state(book_id, 1)
    assert expanded == [latest["run"]["pipeline_run_id"]]
    assert review["latest"]["run"]["pipeline_run_id"] != first["run"]["pipeline_run_id"]
    assert len(review["versions"]) == 2


def test_revision_replay_rejects_corrupted_frozen_request(chapter):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    command = {**target(first), "constraints": {"must_keep": ["Mira"],
        "must_change": ["Sharper dialogue"], "do_not_change": []}}
    created = kernel.chapter_loop.request_revision(book_id, 1, **command)
    task_id = created["task"]["revision_task_id"]
    frozen = created["task"]["request_json"]
    request = json.loads(frozen)
    changes = ({"book_id": "BK-other"}, {"chapter_no": 2},
               {"source_version_id": "CV-other"},
               {"constraints": {"must_keep": ["Mira"], "must_change": ["Different change"],
                                "do_not_change": []}}, {"version": request["version"] + 1})
    for change in changes:
        kernel.storage.update("revision_tasks", task_id,
                              {"request_json": json.dumps({**request, **change})})
        with pytest.raises((TransitionConflict, AmbiguousWrite), match="frozen|request"):
            kernel.chapter_loop.request_revision(book_id, 1, **command)
    kernel.storage.update("revision_tasks", task_id, {"request_json": frozen,
        "run_id": "PR-wrong"})
    with pytest.raises((TransitionConflict, AmbiguousWrite), match="frozen|request"):
        kernel.chapter_loop.request_revision(book_id, 1, **command)


@pytest.mark.parametrize("fail_at", ["decide", "enqueue"])
def test_open_revision_intent_replays_after_interruption(chapter, monkeypatch, fail_at):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, review_first_n=1)
    run_id, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request["brief_artifact_id"]), critique()])
    settle(kernel, 5)
    review = kernel.chapter_loop.review_state(book_id, 1)
    command = {**target(review["latest"]),
        "expected_gate_version": review["review_gate"]["output_version"],
        "constraints": {"must_keep": ["Mira"], "must_change": ["Sharper dialogue"],
                        "do_not_change": []}}
    def interrupted(*args, **kwargs):
        raise RuntimeError("synthetic interruption")
    with monkeypatch.context() as patch:
        patch.setattr(kernel if fail_at == "decide" else kernel.chapter_loop,
                      fail_at, interrupted)
        with pytest.raises(RuntimeError, match="synthetic interruption"):
            kernel.chapter_loop.request_revision(book_id, 1, **command)
    task_id = stable_id("RT-", "chapter-revision/" + command["version_id"])
    intent = kernel.storage.get("revision_tasks", task_id)
    assert intent and intent["status"] == "open"
    if fail_at == "enqueue":
        generic = kernel.chapter_loop.context(book_id, 1)
        with pytest.raises(TransitionConflict, match="revision intent"):
            kernel.chapter_loop.enqueue(generic)
        with pytest.raises(TransitionConflict, match="revision intent"):
            kernel.chapter_loop.decide_review(book_id, 1, **{**target(review["latest"]),
                "expected_gate_version": command["expected_gate_version"], "action": "approve"})
        with pytest.raises(TransitionConflict, match="revision intent"):
            kernel.chapter_loop.lock_final(book_id, 1, **{
                key: command[key] for key in ("version_id", "artifact_id", "version_no", "operator")})
    resumed = kernel.chapter_loop.request_revision(book_id, 1, **command)
    assert resumed["task"]["status"] == "queued"
    assert resumed["run"]["pipeline_run_id"] == intent["run_id"]
    assert kernel.chapter_loop.read(run_id)["run"]["status"] == "failed"


def test_revision_replay_after_queued_marker_committed(chapter, monkeypatch):
    kernel, provider, book_id = chapter
    first = pass_run(kernel, provider, book_id)
    command = {**target(first), "constraints": {"must_keep": [],
        "must_change": ["Sharper dialogue"], "do_not_change": []}}
    original_update = kernel.storage.update
    def committed_then_interrupted(collection, domain_id, fields):
        result = original_update(collection, domain_id, fields)
        if collection == "revision_tasks" and fields.get("status") == "queued":
            raise RuntimeError("synthetic response lost after commit")
        return result
    with monkeypatch.context() as patch:
        patch.setattr(kernel.storage, "update", committed_then_interrupted)
        with pytest.raises(RuntimeError, match="response lost"):
            kernel.chapter_loop.request_revision(book_id, 1, **command)
    task_id = stable_id("RT-", "chapter-revision/" + command["version_id"])
    committed = kernel.storage.get("revision_tasks", task_id)
    assert committed["status"] == "queued"
    resumed = kernel.chapter_loop.request_revision(book_id, 1, **command)
    assert resumed["task"] == committed
    assert resumed["run"]["pipeline_run_id"] == committed["run_id"]
    assert len(kernel.chapter_loop._runs(book_id, 1)) == 2


def test_review_response_reuses_validated_immutable_artifacts(chapter):
    kernel, provider, book_id = chapter
    _, request, snapshot = start(kernel, book_id)
    provider.outputs.extend([draft(snapshot, request['brief_artifact_id']), critique('revise'),
                             draft(snapshot, request['brief_artifact_id'], prose='A revised scene. ' * 20)])
    settle(kernel, 5)
    calls = []
    client = kernel.storage._repos['artifacts']._client._http
    client.event_hooks['request'].append(calls.append)
    review = kernel.chapter_loop.review_state(book_id, 1)
    latest = review['latest']
    assert latest['selected'] == review['versions'][0]['artifact']
    assert latest['critique'] == review['versions'][0]['report']
    assert review['verification'] == review['versions'][0]['verification']
    assert review['versions'][1]['report']['source_refs'][2] == review['versions'][1]['artifact']['artifact_id']
    assert latest['usage']['attempts'] == 3
    assert all(request.method == 'GET' for request in calls)
    for artifact_id in {snapshot, latest['selected']['artifact_id'], latest['critique']['artifact_id'],
                        *(item['verification']['artifact_id'] for item in review['versions'])}:
        assert sum(artifact_id in request.url.params.get('filter', '') for request in calls
                   if '/tables/artifacts/' in request.url.path) == 1


def test_review_refresh_and_decision_revalidate_remote_artifacts(chapter):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    first = kernel.chapter_loop.review_state(book_id, 1)
    assert first['latest']['selected'] == view['selected']
    artifact_id = view['selected']['artifact_id']
    row = kernel.storage.get('artifacts', artifact_id)
    corrupt = json.loads(row['payload_json'])
    corrupt['content']['prose'] = 'Tampered remote prose'
    kernel.storage.update('artifacts', artifact_id, {'payload_json': json.dumps(corrupt)})
    with pytest.raises(AmbiguousWrite, match='Final ChapterVersion is unreadable'):
        kernel.chapter_loop.review_state(book_id, 1)
    with pytest.raises(AmbiguousWrite, match='Final ChapterVersion is unreadable'):
        kernel.chapter_loop.decide_review(book_id, 1, **target(view), action='approve')
    assert kernel.storage.list('approval_events', target_type='chapter_version') == []
    kernel.storage.update('artifacts', artifact_id, {'payload_json': row['payload_json']})
    restored = kernel.chapter_loop.review_state(book_id, 1)
    assert restored['latest']['selected'] == view['selected']
    assert restored['versions'][0]['record']['status'] == 'review'


def test_http_editorial_revision_approval_and_lock_preserve_history(chapter):
    kernel, provider, book_id = chapter
    kernel.chapter_loop = ChapterLoopService(kernel, review_first_n=1)
    first = pass_run(kernel, provider, book_id)
    api = TestClient(create_app(Settings(BACKEND_API_KEY='test'), kernel=kernel))
    headers = {'x-api-key': 'test'}
    root = f'/api/books/{book_id}/chapters/1'
    assert api.get(root + '/review').status_code == 401
    review = api.get(root + '/review', headers=headers).json()
    assert review['latest']['run']['status'] == 'awaiting_approval'
    command = {**target(first), 'expected_gate_version': review['review_gate']['output_version'],
               'constraints': {'must_keep': ['Mira helps neighbors'],
                               'must_change': ['Sharper dialogue'], 'do_not_change': []}}
    stale = api.post(root + '/review/revision', headers=headers,
                     json={**command, 'artifact_id': 'AR-other'})
    assert stale.status_code == 409
    assert kernel.storage.list('revision_tasks') == []
    created = api.post(root + '/review/revision', headers=headers, json=command)
    assert created.status_code == 201
    task = created.json()['task']
    run_id = created.json()['run']['pipeline_run_id']
    assert task['source_artifact_id'] == first['selected']['artifact_id']
    assert task['from_version_id'] == command['version_id']
    assert api.post(root + '/review/revision', headers=headers, json=command).json()['task'] == task
    pending = api.get(f'/api/chapter-generations/{run_id}', headers=headers).json()
    assert pending['request']['constraints'] == command['constraints']
    provider.outputs.extend([draft(pending['snapshot_artifact_id'], first['request']['brief_artifact_id']), critique()])
    settle(kernel, 5)
    newer = api.get(root + '/review', headers=headers).json()
    assert newer['latest']['run']['status'] == 'awaiting_approval'
    assert [item['record']['version_no'] for item in newer['versions']] == [2, 1]
    approval = {**target(newer['latest']), 'action': 'approve',
                'expected_gate_version': newer['review_gate']['output_version']}
    accepted = api.post(root + '/review/decision', headers=headers, json=approval)
    assert accepted.status_code == 200 and accepted.json()['version']['status'] == 'approved'
    locked = api.post(root + '/final-lock', headers=headers, json={
        key: approval[key] for key in ('version_id', 'artifact_id', 'version_no', 'operator')})
    assert locked.status_code == 200 and locked.json()['status'] == 'final'
    history = api.get(root + '/versions', headers=headers).json()
    assert history[1]['artifact'] == first['selected']
    assert history[0]['record']['status'] == 'final'
    assert len(kernel.storage.list('revision_tasks')) == 1
    api.close()
