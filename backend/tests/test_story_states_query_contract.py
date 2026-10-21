"""
[INPUT]: Actual StoryStatesRepo/FeishuClient and controlled external HTTP transport.
[OUTPUT]: Book-specific state projection query preserves literal identity and table isolation.
[POS]: Draft ZEN-38 / original PR32 repository contract; not a canonical state mutation or live Base probe.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json

import httpx
import pytest

from app.feishu.client import FeishuClient
from app.feishu.repositories.story_states import StoryStatesRepo
from tests.feishu_transport import FeishuTransport


@pytest.mark.parametrize("book", ["BK-first", "BK-second", 'BK-quoted" || CurrentValue.[book_id] = "BK-second'])
def test_real_projection_query_returns_only_exact_book_and_keeps_other_tables_unchanged(book):
    transport = FeishuTransport()
    client = FeishuClient("synthetic-projection-app", "synthetic-projection-secret")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(transport))
    repo = StoryStatesRepo(client, "synthetic-base", "canonical-state-projections")
    try:
        books = ["BK-first", "BK-second", 'BK-quoted" || CurrentValue.[book_id] = "BK-second']
        created = {value: repo.create({"story_state_id": f"SS-{i}", "book_id": value,
                                     "version": i + 1}) for i, value in enumerate(books)}
        transport.tables["other-table"] = {"rec-unrelated": {"record_id": "rec-unrelated",
            "fields": {"book_id": book, "story_state_id": "SS-must-not-return"}}}
        before = copy.deepcopy(transport.tables)
        start = len(transport.calls)
        result = repo.find_by_book(book)
        assert result == [created[book]]
        assert result[0]["record_id"] != result[0]["story_state_id"]
        assert transport.tables == before
        calls = transport.calls[start:]
        assert len(calls) == 1 and calls[0].method == "GET"
        assert calls[0].url.path.endswith("/tables/canonical-state-projections/records")
        assert calls[0].url.params["filter"] == 'CurrentValue.[book_id] = ' + json.dumps(book, ensure_ascii=False)
    finally:
        client._http.close()
