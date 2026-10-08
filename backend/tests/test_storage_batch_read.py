"""Batch domain reads: native search, strict pages and safe retry semantics."""
import json
from copy import deepcopy
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.feishu.client import FeishuAPIError, FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.storage import DuplicateKey, FeishuStorageProvider
from tests.feishu_transport import make_storage


def page(*rows, **extra):
    return {"data": {"items": [{"record_id": f"rec-{key}", "fields": {
        "ID": [{"type": "text", "text": key}], **fields}} for key, fields in rows],
        "has_more": False, **extra}}


@pytest.fixture
def fixture():
    client = MagicMock()
    repo = BaseRepository(client, "app", "table", {"id": "ID", "status": "Status"})
    return client, FeishuStorageProvider({"runs": repo}, {"runs": "id"})


def test_empty_duplicate_missing_and_reordered_ids(fixture):
    client, provider = fixture
    assert provider.get_many("runs", []) == {}
    client.search_records.assert_not_called()
    client.search_records.return_value = page(("second", {"Status": [
        {"type": "text", "text": "do"}, {"type": "text", "text": "ne"}]}), ("first", {"Status": []}))
    assert provider.get_many("runs", ["first", "absent", "second", "first"]) == {
        "first": {"id": "first", "status": ""}, "second": {"id": "second", "status": "done"}}
    client.search_records.assert_called_once_with("app", "table", body={"filter": {
        "conjunction": "or", "conditions": [{"field_name": "ID", "operator": "is", "value": [key]}
                                            for key in ["first", "absent", "second"]]}},
        params={"page_size": "500"})
    with pytest.raises(KeyError):
        provider.get_many("unknown", [])


@pytest.mark.parametrize("bad", ["", "  ", 2, None, [], {}])
def test_invalid_ids_before_http(fixture, bad):
    client, provider = fixture
    with pytest.raises(ValueError, match="Non-empty string"):
        provider.get_many("runs", ["valid", bad])
    client.search_records.assert_not_called()


def test_real_http_search_is_read_only_and_injection_text_stays_literal():
    storage, transport, client = make_storage()
    key = 'id"\\ && CurrentValue.[status] = "success'
    try:
        storage.ensure("pipeline_runs", {"pipeline_run_id": key, "status": "pending"})
        storage.ensure("pipeline_runs", {"pipeline_run_id": "unrelated", "status": "success"})
        before = deepcopy(transport.tables)
        transport.calls.clear()
        assert storage.get_many("pipeline_runs", [key, "missing"]) == {
            key: {"pipeline_run_id": key, "status": "pending"}}
        assert transport.tables == before and len(transport.calls) == 1
        request = transport.calls[0]
        assert request.method == "POST" and request.url.path.endswith("/records/search")
        assert json.loads(request.content)["filter"]["conditions"][0]["value"] == [key]
    finally:
        client._http.close()


def test_fifty_condition_chunks_and_all_pages(fixture):
    client, provider = fixture
    ids = [f"id-{i}" for i in range(51)]
    client.search_records.side_effect = [page((ids[49], {}), has_more=True, page_token="next"),
                                         page((ids[0], {})), page((ids[50], {}))]
    assert provider.get_many("runs", ids) == {key: {"id": key} for key in [ids[0], ids[49], ids[50]]}
    calls = client.search_records.call_args_list
    assert [len(c.kwargs["body"]["filter"]["conditions"]) for c in calls] == [50, 50, 1]
    assert [c.kwargs["params"] for c in calls] == [
        {"page_size": "500"}, {"page_size": "500", "page_token": "next"}, {"page_size": "500"}]


@pytest.mark.parametrize("response", [None, [], {}, {"data": None}, {"data": []}, {"data": {}},
    {"data": {"items": None, "has_more": False}}, {"data": {"items": [], "has_more": 0}},
    {"data": {"items": []}}])
def test_malformed_envelopes_cannot_claim_absence(fixture, response):
    client, provider = fixture
    client.search_records.return_value = response
    with pytest.raises(FeishuAPIError, match="Malformed search response"):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("record", [None, [], {}, {"record_id": 1, "fields": {}},
    {"record_id": "", "fields": {}}, {"record_id": "rec", "fields": None}])
def test_malformed_records(fixture, record):
    client, provider = fixture
    client.search_records.return_value = {"data": {"items": [record], "has_more": False}}
    with pytest.raises(FeishuAPIError, match="Malformed search record"):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("value", [[None], [{"type": "mention", "text": "wanted"}],
                                   [{"type": "text", "text": 1}], [{"type": "text"}]])
def test_non_text_rich_cells_fail_closed(fixture, value):
    client, provider = fixture
    client.search_records.return_value = page(("wanted", {"Status": value}))
    with pytest.raises(FeishuAPIError, match="Unsupported search text cell"):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("fields", [{"ID": "extra"}, {"ID": 1}, {}, {"ID": None}])
def test_missing_or_mismatched_business_keys(fixture, fields):
    client, provider = fixture
    client.search_records.return_value = {"data": {"items": [{"record_id": "rec", "fields": fields}],
                                                   "has_more": False}}
    with pytest.raises(FeishuAPIError, match="business key mismatch"):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("pages", [[page(("wanted", {}), ("wanted", {}))],
    [page(("wanted", {}), has_more=True, page_token="next"), page(("wanted", {}))]])
def test_duplicates_even_across_pages(fixture, pages):
    client, provider = fixture
    client.search_records.side_effect = pages
    with pytest.raises(DuplicateKey):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("token", [None, "", 3, [], {}])
def test_invalid_tokens_prevent_partial_results(fixture, token):
    client, provider = fixture
    client.search_records.return_value = page(("wanted", {}), has_more=True, page_token=token)
    with pytest.raises(FeishuAPIError, match="pagination token"):
        provider.get_many("runs", ["wanted"])
    assert client.search_records.call_count == 1


def test_cycles_and_second_page_failure_prevent_partial_results(fixture):
    client, provider = fixture
    client.search_records.side_effect = [page(("wanted", {}), has_more=True, page_token="a"),
                                         page(has_more=True, page_token="b"),
                                         page(has_more=True, page_token="a")]
    with pytest.raises(FeishuAPIError, match="pagination token"):
        provider.get_many("runs", ["wanted"])
    client.search_records.side_effect = [page(("wanted", {}), has_more=True, page_token="a"),
                                         FeishuAPIError("permission denied", code=403)]
    with pytest.raises(FeishuAPIError, match="permission denied"):
        provider.get_many("runs", ["wanted"])


def test_number_types_and_invalid_numbers(fixture):
    client, provider = fixture
    client.search_records.return_value = page(("wanted", {"retry_count": "2", "cost_estimate": 0.25}))
    row = provider.get_many("runs", ["wanted"])["wanted"]
    assert row == {"id": "wanted", "retry_count": 2, "cost_estimate": 0.25}
    assert isinstance(row["retry_count"], int) and isinstance(row["cost_estimate"], float)
    client.search_records.return_value = page(("wanted", {"retry_count": "bad"}))
    with pytest.raises(FeishuAPIError, match="Invalid numeric cell"):
        provider.get_many("runs", ["wanted"])


@pytest.mark.parametrize("failure", ["timeout", "internal", "forbidden"])
@pytest.mark.parametrize("recovers", [True, False])
def test_search_retry_is_bounded_and_does_not_enable_write_retry(failure, recovers):
    calls = []
    def transport(request):
        calls.append(request)
        if recovers and len(calls) > 2:
            return httpx.Response(200, json=page())
        if failure == "timeout":
            raise httpx.ReadTimeout("temporary", request=request)
        return httpx.Response(200, json={"code": 1255001 if failure == "internal" else 1254302,
                                         "msg": "unavailable"})
    client = FeishuClient("fixture", "secret")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(transport))
    client._token = "fixture"
    client._token_expires_at = float("inf")
    body = {"filter": {"conjunction": "or", "conditions": []}}
    try:
        with patch("app.feishu.client.time.sleep") as sleep:
            if recovers and failure != "forbidden":
                assert client.search_records("app", "table", body=body, params={"page_token": "a"}) == page()
            else:
                with pytest.raises(FeishuAPIError):
                    client.search_records("app", "table", body=body, params={"page_token": "a"})
        assert sleep.call_count == (0 if failure == "forbidden" else 2)
        assert len(calls) == (1 if failure == "forbidden" else 3)
        assert all(r.method == "POST" and r.url.params["page_token"] == "a"
                   and json.loads(r.content) == body for r in calls)
        calls.clear()
        with pytest.raises(FeishuAPIError):
            client.post("/bitable/v1/apps/app/tables/table/records", body={"fields": {}})
        assert len(calls) == 1
    finally:
        client._http.close()
