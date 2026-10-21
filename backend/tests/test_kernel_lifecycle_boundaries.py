"""
[INPUT]: Actual Kernel/API and mapped Feishu HTTP fixture.
[OUTPUT]: Existing lifecycle, registration, state and cancellation contracts.
[POS]: ZEN-104 coverage of behavior boundaries; no replaced business methods.
[PROTOCOL]: Update this header when changing the contract, then check CLAUDE.md.
"""
import copy
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.harness import HarnessKernel, TransitionConflict
from app.main import create_app
from app.storage import MissingRecord
from tests.test_harness_kernel import runtime as runtime


def freeze(storage, transport):
    for collection in ['pipeline_runs', 'step_runs', 'approval_events']:
        storage.list(collection)
    transport.calls.clear()
    return copy.deepcopy(transport.tables)


def reads_only(transport):
    assert all(r.method == 'GET' or r.method == 'POST' and r.url.path.endswith('/records/search')
               for r in transport.calls)


@pytest.mark.parametrize('limits', [{'poll_interval': 0}, {'poll_interval': -1}, {'max_retries': -1}])
def test_reject_scheduler_limits_before_storage_or_journal(runtime, tmp_path, limits):
    _, storage, transport, _ = runtime
    before = freeze(storage, transport)
    directory = tmp_path/'rejected-scheduler'
    with pytest.raises(ValueError, match='Invalid scheduler limits'):
        HarnessKernel(storage, journal_dir=directory, **limits)
    assert transport.tables == before and not transport.calls
    assert not directory.exists()


@pytest.mark.parametrize('key,steps,message', [
    (' ', [{'step_key': 'a', 'handler': 'noop'}], 'request_key and steps'),
    ('missing-steps', [], 'request_key and steps'),
    ('unknown-handler', [{'step_key': 'a', 'handler': 'unregistered'}], 'Unregistered step handler'),
    ('unknown-kind', [{'step_key': 'a', 'handler': 'noop', 'kind': 'system-agent'}], 'Invalid step kind'),
])
def test_invalid_workflow_definition_has_no_partial_storage_effect(runtime, key, steps, message):
    kernel, storage, transport, _ = runtime
    before = freeze(storage, transport)
    with pytest.raises(ValueError, match=message):
        kernel.create(key, 'boundary', steps)
    assert transport.tables == before and not transport.calls
    run = kernel.create('corrected', 'boundary', [{'step_key': 'a', 'handler': 'noop'}])
    kernel.tick()
    observed = kernel.get(run['pipeline_run_id'])
    assert observed['status'] == 'completed' and observed['steps'][0]['status'] == 'success'
    assert len(storage.list('pipeline_runs')) == len(storage.list('step_runs')) == 1


def test_live_registry_is_frozen_and_repeated_start_keeps_same_scheduler(runtime):
    kernel, storage, transport, _ = runtime
    freeze(storage, transport)
    kernel.start()
    try:
        original_thread, original_lock = kernel._thread, kernel._process_lock
        original_handlers = dict(kernel.handlers)
        assert kernel.running
        with pytest.raises(RuntimeError, match='before startup'):
            kernel.register('late', lambda step: {'result': 'late'})
        assert kernel.handlers == original_handlers
        kernel.start()
        assert kernel.running and kernel._thread is original_thread and kernel._process_lock is original_lock
    finally:
        kernel.stop()
    calls = []
    kernel.register('late', lambda step: calls.append(step['step_run_id']) or {'result': 'registered-before-start'})
    run = kernel.create('valid-registration', 'boundary', [{'step_key': 'a', 'handler': 'late'}])
    kernel.start()
    try:
        deadline = time.monotonic()+3
        while kernel.get(run['pipeline_run_id'])['status'] != 'completed':
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert calls == [kernel.get(run['pipeline_run_id'])['steps'][0]['step_run_id']]
    finally:
        kernel.stop()


def test_transition_service_refuses_missing_and_illegal_states(runtime):
    kernel, storage, transport, _ = runtime
    before = freeze(storage, transport)
    with pytest.raises(MissingRecord):
        kernel._transition('step_runs', 'SR-missing', 'running')
    assert transport.tables == before
    reads_only(transport)
    run = kernel.create('state-guard', 'boundary', [{'step_key': 'a', 'handler': 'noop'}])
    before = freeze(storage, transport)
    with pytest.raises(TransitionConflict, match='Invalid transition'):
        kernel._transition('pipeline_runs', run['pipeline_run_id'], 'invented-status')
    assert transport.tables == before
    reads_only(transport)
    kernel.tick()
    assert kernel.get(run['pipeline_run_id'])['status'] == 'completed'


@pytest.mark.parametrize('operation', ['get', 'decision'])
def test_unknown_workflow_or_approval_step_returns404_without_mutation(runtime, operation):
    kernel, storage, transport, _ = runtime
    before = freeze(storage, transport)
    api = TestClient(create_app(Settings(_env_file=None, BACKEND_API_KEY='boundary-key'), kernel=kernel))
    try:
        if operation == 'get':
            response = api.get('/api/workflows/PR-unknown', headers={'x-api-key': 'boundary-key'})
        else:
            response = api.post('/api/workflows/steps/SR-unknown/decision', headers={'x-api-key': 'boundary-key'},
                json={'action': 'approve', 'expected_version': 1, 'operator': 'editor'})
        assert response.status_code == 404 and response.json() == {'detail': 'Record not found'}
        assert transport.tables == before
        reads_only(transport)
    finally:
        api.close()


def test_unsupported_core_decision_is_rejected_before_storage(runtime):
    kernel, storage, transport, _ = runtime
    before = freeze(storage, transport)
    with pytest.raises(ValueError, match='Unsupported decision'):
        kernel.decide('SR-unknown', 'publish', 1, 'editor')
    assert transport.tables == before and not transport.calls


def test_finished_non_gate_cannot_be_approved_while_dependant_pending(runtime):
    kernel, storage, transport, _ = runtime
    run = kernel.create('not-a-gate', 'boundary', [
        {'step_key': 'collect', 'handler': 'noop'},
        {'step_key': 'save', 'handler': 'noop', 'depends_on': ['collect']}])
    kernel.tick()
    observed = kernel.get(run['pipeline_run_id'])
    step = next(s for s in observed['steps'] if s['step_key'] == 'collect')
    assert observed['status'] == 'running' and step['status'] == 'success' and step['output_version'] == 1
    before = freeze(storage, transport)
    with pytest.raises(TransitionConflict, match='Step is not awaiting approval'):
        kernel.decide(step['step_run_id'], 'approve', 1, 'editor')
    assert transport.tables == before
    reads_only(transport)
    kernel.tick()
    assert kernel.get(run['pipeline_run_id'])['status'] == 'completed'
    assert not storage.list('approval_events')


def test_cancel_retains_finished_step_and_exact_replay_has_no_write(runtime):
    kernel, storage, transport, _ = runtime
    calls = []
    kernel.register('counter', lambda step: calls.append(step['step_key']) or {'result': 'done'})
    run = kernel.create('cancel-mixed', 'boundary', [
        {'step_key': 'collect', 'handler': 'counter'},
        {'step_key': 'save', 'handler': 'counter', 'depends_on': ['collect']}])
    kernel.tick()
    cancelled = kernel.cancel(run['pipeline_run_id'])
    assert cancelled['status'] == 'cancelled'
    assert {s['step_key']: s['status'] for s in cancelled['steps']} == {'collect': 'success', 'save': 'cancelled'}
    before = freeze(storage, transport)
    assert kernel.cancel(run['pipeline_run_id']) == cancelled
    assert transport.tables == before
    reads_only(transport)
    kernel.tick()
    assert calls == ['collect'] and kernel.get(run['pipeline_run_id']) == cancelled


def test_completed_run_restart_preserves_rows_and_never_reexecutes_handlers(runtime):
    kernel, storage, transport, journal = runtime
    calls = []
    kernel.register('counter', lambda step: calls.append(step['step_key']) or {'result': 'done'})
    run = kernel.create('closed-recovery', 'boundary', [{'step_key': 'collect', 'handler': 'counter'}])
    kernel.tick()
    completed = kernel.get(run['pipeline_run_id'])
    assert completed['status'] == 'completed' and calls == ['collect']
    before = freeze(storage, transport)
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.register('counter', lambda step: calls.append(step['step_key']) or {'result': 'wrong-repeat'})
    restarted.recover()
    restarted.tick()
    assert restarted.get(run['pipeline_run_id']) == completed
    assert transport.tables == before and calls == ['collect']
    reads_only(transport)
