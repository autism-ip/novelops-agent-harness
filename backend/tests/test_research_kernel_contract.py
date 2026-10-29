"""Conditional gates, versioned revision decisions and durable projections."""
import json

import pytest

from app.harness import HarnessKernel, StepResult, PermanentStepFailure, TransitionConflict
from tests import test_harness_kernel as fixtures

runtime = fixtures.runtime


@pytest.mark.parametrize('required', [False, True])
def test_handler_can_add_a_persisted_conditional_gate(runtime, required):
    kernel, _, _, _ = runtime
    kernel.register('risk', lambda _: StepResult({'artifact_id': 'AR-exact'}, required))
    run = kernel.create('conditional', 'research', [{'step_key': 'risk', 'handler': 'risk'}])
    kernel.tick()
    result = kernel.get(run['pipeline_run_id'])
    assert result['status'] == ('awaiting_approval' if required else 'completed')
    assert result['steps'][0]['requires_approval'] == required
    assert json.loads(result['steps'][0]['output_json']) == {'artifact_id': 'AR-exact'}


def test_conditional_result_cannot_disable_configured_gate(runtime):
    kernel, _, _, _ = runtime
    kernel.register('risk', lambda _: StepResult({}, False))
    run = kernel.create('configured', 'research', [{'step_key': 'risk', 'handler': 'risk', 'requires_approval': True}])
    kernel.tick()
    assert kernel.get(run['pipeline_run_id'])['status'] == 'awaiting_approval'


def test_permanent_failure_does_not_multiply_model_router_retries(runtime):
    kernel, _, _, _ = runtime
    calls = []
    def fail(_):
        calls.append(1)
        raise PermanentStepFailure()
    kernel.register('semantic', fail)
    run = kernel.create('bounded-model', 'research', [{'step_key': 'generate', 'handler': 'semantic'}])
    for _ in range(5):
        kernel.tick()
    assert calls == [1]
    assert kernel.get(run['pipeline_run_id'])['status'] == 'failed'


def test_projection_failure_reconciles_completed_run_without_reexecuting(runtime):
    kernel, storage, _, root = runtime
    kernel.register('effect', lambda _: {'artifact_id': 'AR-once'})
    def fail(_):
        raise RuntimeError('projection offline')
    kernel.register_projector('research', fail)
    run = kernel.create('projection', 'research', [{'step_key': 'generate', 'handler': 'effect'}])
    with pytest.raises(RuntimeError):
        kernel.tick()
    assert kernel.get(run['pipeline_run_id'])['status'] == 'completed'
    replay = HarnessKernel(storage, journal_dir=root)
    projected = []
    replay.register('effect', lambda _: pytest.fail('do not repeat effect'))
    replay.register_projector('research', lambda state: projected.append(state['status']))
    replay.recover()
    assert projected == ['completed']


def test_revision_reason_and_guard_are_part_of_shared_decision_contract(runtime):
    kernel, storage, _, _ = runtime
    run = kernel.create('revise', 'research', fixtures.definition(True))
    kernel.tick()
    step = kernel.get(run['pipeline_run_id'])['steps'][0]
    def guard(_, action):
        if action == 'approve':
            raise TransitionConflict('artifact is stale')
    kernel.register_approval_guard('noop', guard)
    with pytest.raises(TransitionConflict):
        kernel.decide(step['step_run_id'], 'approve', 1, 'editor')
    assert storage.list('approval_events') == []
    with pytest.raises(ValueError):
        kernel.decide(step['step_run_id'], 'revise', 1, 'editor')
    kernel.decide(step['step_run_id'], 'revise', 1, 'editor', reason='Use a fictional setting')
    kernel.decide(step['step_run_id'], 'revise', 1, 'editor', reason='Use a fictional setting')
    events = storage.list('approval_events')
    assert len(events) == 1 and events[0]['action'] == 'revise'
    assert events[0]['reason'] == 'Use a fictional setting'
    with pytest.raises(TransitionConflict):
        kernel.decide(step['step_run_id'], 'revise', 1, 'editor', reason='Changed feedback')
