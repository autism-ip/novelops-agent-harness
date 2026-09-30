"""Domain identity and ambiguous-write contract against real repositories."""
from unittest.mock import MagicMock

import pytest

from app.feishu.client import FeishuAPIError
from app.feishu.repositories.base import BaseRepository
from app.storage import AmbiguousWrite, DuplicateKey, FeishuStorageProvider, MissingRecord
from tests.feishu_transport import make_storage


@pytest.fixture
def setup():
    client = MagicMock()
    repo = BaseRepository(client, "app", "table", {"id": "ID", "status": "Status"})
    provider = FeishuStorageProvider({"runs": repo}, {"runs": "id"})
    return client, provider


def records(*items):
    return {"data": {"items": [{"record_id": rid, "fields": fields} for rid, fields in items]}}


def test_domain_read_update_delete_never_use_domain_id_as_record_id(setup):
    client, provider = setup
    client.get.return_value = records(("rec123", {"ID": "PR-1", "Status": "pending"}))
    client.put.return_value = {"data": {"record": {"record_id": "rec123", "fields": {"Status": "done"}}}}
    assert provider.get("runs", "PR-1") == {"id": "PR-1", "status": "pending"}
    assert provider.update("runs", "PR-1", {"status": "done"}) == {"id": "PR-1", "status": "done"}
    assert client.put.call_args.args[0].endswith("/rec123")
    provider.delete("runs", "PR-1")
    assert client.delete.call_args.args[0].endswith("/rec123")


def test_ambiguous_update_reconciles_committed_patch_without_repeating_put(setup):
    client, provider = setup
    client.get.side_effect = [records(("rec123", {"ID": "PR-1", "Status": "pending"})),
                              records(("rec123", {"ID": "PR-1", "Status": "done"}))]
    client.put.return_value = {"data": {}}
    assert provider.update("runs", "PR-1", {"status": "done"}) == {"id": "PR-1", "status": "done"}
    client.put.assert_called_once()


def test_ambiguous_update_fails_closed_when_patch_not_observed(setup):
    client, provider = setup
    client.get.return_value = records(("rec123", {"ID": "PR-1", "Status": "pending"}))
    client.put.return_value = {"data": {}}
    with pytest.raises(AmbiguousWrite, match="Update reconciliation required"):
        provider.update("runs", "PR-1", {"status": "done"})
    client.put.assert_called_once()


def test_number_cells_survive_v1_read_and_partial_update():
    storage, _, client = make_storage()
    try:
        storage.ensure("step_runs", {"step_run_id": "SR-1", "retry_count": 0,
            "output_version": 0, "status": "pending"})
        step = storage.get("step_runs", "SR-1")
        assert step["retry_count"] == 0 and step["output_version"] == 0
        updated = storage.update("step_runs", "SR-1", {"output_version": step["output_version"] + 1})
        assert updated["step_run_id"] == "SR-1" and updated["output_version"] == 1
    finally:
        client._http.close()


def test_missing_duplicate_and_identity_change_fail_explicitly(setup):
    client, provider = setup
    client.get.return_value = records()
    assert provider.get("runs", "missing") is None
    with pytest.raises(MissingRecord):
        provider.update("runs", "missing", {"status": "done"})
    with pytest.raises(MissingRecord):
        provider.delete("runs", "missing")
    client.get.return_value = records(("r1", {"ID": "same"}), ("r2", {"ID": "same"}))
    with pytest.raises(DuplicateKey):
        provider.get("runs", "same")
    with pytest.raises(ValueError):
        provider.update("runs", "same", {"id": "different"})


def test_committed_timeout_reconciles_without_second_post(setup):
    client, provider = setup
    client.get.side_effect = [records(), records(("rec1", {"ID": "stable"}))]
    client.post.side_effect = FeishuAPIError("transport timeout", code=0)
    assert provider.ensure("runs", {"id": "stable"}) == {"id": "stable"}
    client.post.assert_called_once()


def test_unknown_outcome_is_never_blindly_retried(setup):
    client, provider = setup
    client.get.return_value = records()
    client.post.side_effect = FeishuAPIError("timeout", code=0)
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "stable"})
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "stable"})
    client.post.assert_called_once()


def test_committed_create_with_missing_response_record_reconciles(setup):
    client, provider = setup
    client.get.side_effect = [records(), records(("rec1", {"ID": "stable"}))]
    client.post.return_value = {"code": 0, "data": {}}
    assert provider.ensure("runs", {"id": "stable"}) == {"id": "stable"}
    client.post.assert_called_once()


def test_missing_create_response_record_stops_without_second_post(setup):
    client, provider = setup
    client.get.return_value = records()
    client.post.return_value = {"code": 0, "data": {}}
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "stable"})
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "stable"})
    client.post.assert_called_once()


def test_create_response_without_requested_business_key_reconciles(setup):
    client, provider = setup
    client.get.side_effect = [records(), records(("rec1", {"ID": "stable"}))]
    client.post.return_value = {"code": 0, "data": {"record": {
        "record_id": "rec1", "fields": {"Status": "pending"},
    }}}
    assert provider.ensure("runs", {"id": "stable"}) == {"id": "stable"}
    client.post.assert_called_once()


def test_committed_malformed_http_reply_recovers_without_duplicate_post():
    from tests.feishu_transport import make_storage

    provider, transport, client = make_storage()
    transport.malformed_create_reply = "pipeline_runs"
    try:
        assert provider.ensure("pipeline_runs", {"pipeline_run_id": "PR-stable"}) == {
            "pipeline_run_id": "PR-stable",
        }
        assert len(transport.tables["pipeline_runs"]) == 1
        assert sum(
            request.method == "POST" and "/tables/pipeline_runs/" in request.url.path
            for request in transport.calls
        ) == 1
    finally:
        client._http.close()


def test_replay_reads_existing_record(setup):
    client, provider = setup
    client.get.return_value = records(("rec1", {"ID": "stable", "Status": "done"}))
    assert provider.ensure("runs", {"id": "stable", "status": "pending"})["status"] == "done"
    client.post.assert_not_called()


def test_filter_escapes_untrusted_business_keys(setup):
    client, provider = setup
    client.get.return_value = records()
    provider.get("runs", 'a"\\b')
    assert client.get.call_args.kwargs["params"]["filter"] == 'CurrentValue.[ID] = "a\\"\\\\b"'


def test_restart_reconciliation_never_posts_when_outcome_unknown(setup):
    client, provider = setup
    client.get.return_value = records()
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "prior-process"}, allow_create=False)
    client.post.assert_not_called()


def test_real_transport_contract_for_pipeline_step_and_rollback():
    from tests.feishu_transport import make_storage
    provider, transport, client = make_storage()
    try:
        provider.ensure("pipeline_runs", {"pipeline_run_id": "PR-domain", "status": "pending"})
        provider.ensure("step_runs", {"step_run_id": "SR-domain", "pipeline_run_id": "PR-domain", "status": "pending"})
        assert provider.list("step_runs", pipeline_run_id="PR-domain")[0]["step_run_id"] == "SR-domain"
        provider.update("step_runs", "SR-domain", {"status": "success"})
        provider.update("pipeline_runs", "PR-domain", {"status": "completed"})
        assert provider.get("pipeline_runs", "PR-domain")["status"] == "completed"
        provider.update("pipeline_runs", "PR-domain", {"status": "failed"})
        provider.delete("step_runs", "SR-domain")
        provider.delete("pipeline_runs", "PR-domain")
        assert not transport.tables["pipeline_runs"]
        assert not transport.tables["step_runs"]
    finally:
        client._http.close()


def test_definite_provider_rejection_does_not_become_ambiguous(setup):
    client, provider = setup
    client.get.return_value = records()
    client.post.side_effect = FeishuAPIError("permission denied", code=403)
    with pytest.raises(FeishuAPIError):
        provider.ensure("runs", {"id": "x"})


def test_unavailable_reconciliation_stops(setup):
    client, provider = setup
    client.get.side_effect = [records(), FeishuAPIError("read unavailable")]
    client.post.side_effect = FeishuAPIError("timeout")
    with pytest.raises(AmbiguousWrite):
        provider.ensure("runs", {"id": "x"})
