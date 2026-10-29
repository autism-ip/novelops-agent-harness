"""ZEN-39: product history APIs preserve exact sources across story revisions."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.test_story_planning import approve_bible, bible, brief, settle

pytest_plugins = ('tests.test_story_planning',)


def test_authenticated_empty_history_does_not_generate_or_bill(planning):
    kernel, provider, book_id, _ = planning
    api = TestClient(create_app(Settings(BACKEND_API_KEY='test'), kernel=kernel))
    paths = (f'/api/books/{book_id}/bibles', f'/api/books/{book_id}/chapters/1/briefs')
    before_runs = kernel.storage.list('pipeline_runs')
    before_traces = kernel.storage.list('traces')
    for path in paths:
        assert api.get(path).status_code == 401
        response = api.get(path, headers={'x-api-key': 'test'})
        assert response.status_code == 200
        assert response.json() == []
    assert kernel.storage.list('pipeline_runs') == before_runs
    assert kernel.storage.list('traces') == before_traces
    api.close()


def test_http_history_retains_superseded_bible_and_brief_sources(planning):
    kernel, provider, book_id, _ = planning
    first = approve_bible(kernel, provider, book_id)
    request = kernel.story_planning.brief_context(book_id, 1)
    run = kernel.story_planning.enqueue_brief(request)
    provider.outputs.append(brief())
    settle(kernel, 2)
    original = kernel.story_planning.read(run['pipeline_run_id'])
    original_artifact = original['artifact']
    original_snapshot = kernel.artifacts.get(original['snapshot_artifact_id'])
    second = approve_bible(kernel, provider, book_id, bible('The same town must face a winter flood'))
    new_request = kernel.story_planning.brief_context(book_id, 1)
    new_run = kernel.story_planning.enqueue_brief(new_request)
    provider.outputs.append({**brief(), 'scene_goal': 'Mira must divert the flood without breaking the shared-care rule'})
    settle(kernel, 2)
    current = kernel.story_planning.read(new_run['pipeline_run_id'])
    assert new_request['state_version'] == 3
    api = TestClient(create_app(Settings(BACKEND_API_KEY='test'), kernel=kernel))
    headers = {'x-api-key': 'test'}
    bibles = api.get(f'/api/books/{book_id}/bibles', headers=headers)
    assert bibles.status_code == 200
    history = bibles.json()
    assert [item['run']['pipeline_run_id'] for item in history] == [second['run']['pipeline_run_id'], first['run']['pipeline_run_id']]
    assert [item['artifact']['artifact_id'] for item in history] == [second['artifact']['artifact_id'], first['artifact']['artifact_id']]
    assert all(item['run']['status'] == 'completed' and item['decision']['action'] == 'approve' for item in history)
    briefs = api.get(f'/api/books/{book_id}/chapters/1/briefs', headers=headers)
    assert briefs.status_code == 200
    history = briefs.json()
    assert [item['run']['pipeline_run_id'] for item in history] == [new_run['pipeline_run_id'], run['pipeline_run_id']]
    assert [item['eligible'] for item in history] == [True, False]
    assert history[0]['artifact'] == current['artifact']
    assert history[0]['artifact']['content']['state_version'] == 3
    assert history[1]['artifact']['content']['state_version'] == 2
    assert history[0]['request']['state_artifact_id'] == new_request['state_artifact_id']
    assert history[1]['artifact'] == original_artifact
    assert history[1]['request']['state_artifact_id'] == request['state_artifact_id']
    assert history[1]['snapshot_artifact_id'] == original_snapshot['artifact_id']
    assert kernel.artifacts.get(original_snapshot['artifact_id']) == original_snapshot
    eligible = api.get(f'/api/books/{book_id}/chapters/1/brief/eligible', headers=headers)
    assert eligible.status_code == 200 and eligible.json() == current['artifact']
    assert api.get(f'/api/books/{book_id}/chapters/2/briefs', headers=headers).json() == []
    api.close()
