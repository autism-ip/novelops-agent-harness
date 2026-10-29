"""Projection must stay fresh without loading unused step snapshots."""
import pytest

from app.harness import HarnessKernel
from app.storage import MissingRecord
from tests.test_harness_kernel import definition, runtime as harness_runtime

runtime = harness_runtime


def step_reads(transport):
    return [r for r in transport.calls if r.method == 'GET' and
            '/tables/step_runs/records' in r.url.path]


def test_unprojected_tick_keeps_completion_without_unused_step_read(runtime):
    kernel, _, transport, _ = runtime
    run = kernel.create('no-projection', 'plain', [definition()[0]])
    transport.calls.clear()
    kernel.tick()
    # Selection and parent status each need a fresh snapshot; no third snapshot
    # is needed when this workflow has no domain projection.
    assert len(step_reads(transport)) == 2
    result = kernel.get(run['pipeline_run_id'])
    assert result['status'] == 'completed'
    assert result['steps'][0]['status'] == 'success'
    assert result['steps'][0]['output_version'] == 1


def test_projection_selects_current_type_and_reads_latest_steps(runtime):
    kernel, storage, transport, _ = runtime
    old, current = [], []
    kernel.register_projector('old', old.append)
    kernel.register_projector('current', current.append)
    run = kernel.create('fresh-projection', 'old', [definition()[0]])
    storage.update('pipeline_runs', run['pipeline_run_id'], {'pipeline_type': 'current'})
    transport.calls.clear()
    kernel.tick()
    assert old == []
    assert len(current) == 1
    projected = current[0]
    assert projected == kernel.get(run['pipeline_run_id'])
    assert projected['pipeline_type'] == 'current'
    assert projected['status'] == 'completed'
    assert projected['steps'][0]['status'] == 'success'
    assert projected['steps'][0]['output_version'] == 1
    # Four includes the independent assertion read above: the projected tick
    # still performs selection, parent refresh and fresh projection reads.
    assert len(step_reads(transport)) == 4


def test_cancel_projection_observes_all_sibling_terminal_states(runtime):
    kernel, _, _, _ = runtime
    seen = []
    kernel.register_projector('cancelled-projection', seen.append)
    run = kernel.create('cancel-projection', 'cancelled-projection', definition())
    result = kernel.cancel(run['pipeline_run_id'])
    assert seen == [result]
    assert result['status'] == 'cancelled'
    assert len(result['steps']) == 2
    assert {s['status'] for s in result['steps']} == {'cancelled'}


def test_projection_failure_recovers_without_repeating_completed_effect(runtime):
    kernel, storage, _, journal = runtime
    effects, seen = [], []

    def effect(step):
        effects.append(step['step_run_id'])
        return {'output_refs': ['saved-once']}

    def unavailable(run):
        seen.append(run)
        raise RuntimeError('projection unavailable')

    kernel.register('effect', effect)
    kernel.register_projector('repair-projection', unavailable)
    run = kernel.create('repair-projection', 'repair-projection',
                        [{'step_key': 'effect', 'handler': 'effect'}])
    with pytest.raises(RuntimeError, match='projection unavailable'):
        kernel.tick()
    assert seen[0]['status'] == 'completed'
    assert len(effects) == 1
    repaired = []
    restarted = HarnessKernel(storage, journal_dir=journal)
    restarted.register_projector('repair-projection', repaired.append)
    restarted.recover()
    restarted.tick()
    assert repaired == [kernel.get(run['pipeline_run_id'])]
    assert len(effects) == 1
    assert repaired[0]['steps'][0]['output_version'] == 1


def test_missing_projection_run_still_fails_explicitly(runtime):
    kernel, _, transport, _ = runtime
    transport.calls.clear()
    with pytest.raises(MissingRecord, match='missing-run'):
        kernel._project('missing-run')
    assert step_reads(transport) == []
