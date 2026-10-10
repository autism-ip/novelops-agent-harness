"""Manual product controls use the same persisted workflow and single writer."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.harness import HarnessKernel
from app.hotspots import HotspotService
from tests import test_hotspot_ingestion as fixtures

ingestion = fixtures.ingestion
complete = fixtures.complete


def api(kernel):
    return TestClient(create_app(Settings(BACKEND_API_KEY="test"), kernel=kernel))


HEADERS = {"x-api-key": "test"}
MANUAL = {"request_key": "manual-1", "title": "人工选题", "url": "https://example.com/story", "category": "社会"}


def test_manual_add_replay_and_discard_survive_refresh(ingestion):
    kernel, _, storage, _, _, _ = ingestion
    client = api(kernel)
    assert client.post('/api/hotspots/manual', json=MANUAL).status_code == 401
    result = client.post('/api/hotspots/manual', headers=HEADERS, json=MANUAL)
    assert result.status_code == 201, result.text
    run_id = result.json()['pipeline_run_id']
    assert complete(kernel, run_id)['status'] == 'completed'
    replay = client.post('/api/hotspots/manual', headers=HEADERS, json=MANUAL)
    assert replay.json()['pipeline_run_id'] == run_id
    assert len(storage.list('hotspots')) == 1
    row = client.get('/api/hotspots?source=manual', headers=HEADERS).json()['items'][0]
    assert row['title'] == MANUAL['title'] and row['status'] == 'normalized'
    body = {"request_key": "discard-1", "expected_status": row['status']}
    response = client.post(f'/api/hotspots/{row["hotspot_id"]}/discard', headers=HEADERS, json=body)
    assert response.status_code == 201
    run = complete(kernel, response.json()['pipeline_run_id'])
    assert run['status'] == 'completed'
    assert json.loads(run['steps'][0]['output_json'])['hotspot_id'] == row['hotspot_id']
    assert client.get('/api/hotspots?status=discarded', headers=HEADERS).json()['total'] == 1
    assert client.post('/api/hotspots/manual', headers=HEADERS, json={**MANUAL, 'request_key': 'new'}).status_code == 201
    for _ in range(3):
        kernel.tick()
    assert len(storage.list('hotspots')) == 1
    assert storage.get('hotspots', row['hotspot_id'])['status'] == 'discarded'
    client.close()


def test_manual_key_conflict_and_invalid_fields_are_rejected(ingestion):
    kernel, _, _, _, _, _ = ingestion
    client = api(kernel)
    client.post('/api/hotspots/manual', headers=HEADERS, json=MANUAL)
    assert client.post('/api/hotspots/manual', headers=HEADERS, json={**MANUAL, 'title': 'changed'}).status_code == 409
    for fields in ({'title': ' '}, {'url': 'javascript:alert(1)'}, {'url': 'https://u:p@example.com'}, {'source': 'douyin'}, {'raw_json': []}, {'category': 'x'*201}):
        assert client.post('/api/hotspots/manual', headers=HEADERS, json={**MANUAL, **fields}).status_code == 422
    client.close()


def test_discard_stale_status_blocks_without_overwriting_newer_decision(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    complete(kernel, service.enqueue('initial')['pipeline_run_id'])
    row = storage.list('hotspots')[0]
    client = api(kernel)
    response = client.post(f'/api/hotspots/{row["hotspot_id"]}/discard', headers=HEADERS,
                           json={'request_key': 'stale', 'expected_status': 'normalized'})
    assert response.status_code == 201
    storage.update('hotspots', row['hotspot_id'], {'status': 'approved'})
    assert complete(kernel, response.json()['pipeline_run_id'])['status'] == 'blocked'
    assert storage.get('hotspots', row['hotspot_id'])['status'] == 'approved'
    client.close()


def test_manual_and_discard_work_when_collection_disabled(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    service.collection_enabled = False
    client = api(kernel)
    response = client.post('/api/hotspots/manual', headers=HEADERS, json=MANUAL)
    assert response.status_code == 201
    assert complete(kernel, response.json()['pipeline_run_id'])['status'] == 'completed'
    assert len(storage.list('hotspots')) == 1
    assert client.get('/api/hotspots/capabilities', headers=HEADERS).json() == {
        'fetch': False, 'manual_add': True, 'discard': True, 'analyze': False, 'creative': False}
    assert client.post('/api/hotspots/missing/discard', headers=HEADERS,
                       json={'request_key': 'missing', 'expected_status': 'new'}).status_code == 404
    client.close()


@pytest.mark.parametrize("committed", [True, False])
def test_manual_create_timeout_is_reconciled_without_blind_repost(ingestion, committed):
    kernel, service, storage, transport, _, _ = ingestion
    original = transport.__call__
    attempts = []
    def request(req):
        if req.method == 'POST' and req.url.path.endswith('/tables/hotspots/records'):
            attempts.append(req)
            if committed:
                original(req)
            raise httpx.ReadTimeout('unknown', request=req)
        return original(req)
    repo_client = storage._repos['hotspots']._client
    repo_client._http.close()
    repo_client._http = httpx.Client(transport=httpx.MockTransport(request))
    run = service.controls.enqueue_add('timeout', {k: v for k, v in MANUAL.items() if k != 'request_key'})
    assert complete(kernel, run['pipeline_run_id'])['status'] == ('completed' if committed else 'blocked')
    again = service.controls.enqueue_add('retry', {k: v for k, v in MANUAL.items() if k != 'request_key'})
    assert complete(kernel, again['pipeline_run_id'])['status'] == ('completed' if committed else 'blocked')
    assert len(attempts) == 1
    assert len(storage.list('hotspots')) == int(committed)


def test_manual_restart_and_discard_replay_keep_single_row(ingestion, monkeypatch):
    kernel, service, storage, _, _, root = ingestion
    run = service.controls.enqueue_add('restart', {'title': 'restart'})
    original = storage.update
    def fail(collection, domain_id, fields):
        if collection == 'step_runs' and fields.get('status') == 'success':
            raise RuntimeError('completion response lost')
        return original(collection, domain_id, fields)
    monkeypatch.setattr(storage, 'update', fail)
    with pytest.raises(RuntimeError):
        kernel.tick()
    monkeypatch.setattr(storage, 'update', original)
    restarted = HarnessKernel(storage, journal_dir=root/'journal')
    controls = HotspotService(restarted, service.adapter).controls
    restarted.recover()
    assert complete(restarted, run['pipeline_run_id'])['status'] == 'completed'
    rows = storage.list('hotspots')
    assert len(rows) == 1
    for key in ('one', 'two'):
        discard = controls.enqueue_discard(rows[0]['hotspot_id'], key, 'normalized')
        assert complete(restarted, discard['pipeline_run_id'])['status'] == 'completed'
    assert storage.list('hotspots')[0]['status'] == 'discarded'


def test_manual_and_discard_request_keys_cannot_collide_with_fetch(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    fetch = service.enqueue('manual:shared')
    manual = service.controls.enqueue_add('shared', {'title': 'manual key'})
    assert fetch['pipeline_run_id'] != manual['pipeline_run_id']
    assert complete(kernel, manual['pipeline_run_id'])['status'] == 'completed'
    row = storage.list('hotspots', source='manual')[0]
    fetch2 = service.enqueue('discard:shared')
    discard = service.controls.enqueue_discard(row['hotspot_id'], 'shared', 'normalized')
    assert fetch2['pipeline_run_id'] != discard['pipeline_run_id']
    assert complete(kernel, discard['pipeline_run_id'])['status'] == 'completed'


def test_manual_fields_with_colons_keep_distinct_identities(ingestion):
    kernel, service, storage, _, _, _ = ingestion
    pairs = [('a', 'http://x/path:http://y'), ('a:http://x/path', 'http://y')]
    for index, (title, url) in enumerate(pairs):
        run = service.controls.enqueue_add(str(index), {'title': title, 'url': url})
        assert complete(kernel, run['pipeline_run_id'])['status'] == 'completed'
    rows = storage.list('hotspots')
    assert len(rows) == 2
    assert len({row['dedupe_hash'] for row in rows}) == 2
    assert {(row['title'], row['url']) for row in rows} == set(pairs)
