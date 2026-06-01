"""
[INPUT]: 依赖 app.feishu.repositories.base 的 BaseRepository，依赖 app.feishu.client 的 FeishuClient
[OUTPUT]: 对外提供 BaseRepository 的行为级测试用例——字段映射、CRUD 操作、分页逻辑、字段过滤、业务键查找
[POS]: tests 的 repository 基类门禁，验证 Python↔Feishu 字段映射与五种标准数据访问方法的外部行为
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.feishu.client import FeishuNotFoundError
from app.feishu.repositories.base import BaseRepository
from app.feishu.client import FeishuAuthError, FeishuNotFoundError


# ============================================================
# fixtures
# ============================================================


_FIELD_MAP = {"book_id": "Book ID", "title": "Book Title"}

_APP_TOKEN = "bascn_test_token"
_TABLE_ID = "tbl_test"


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_client: MagicMock) -> BaseRepository:
    return BaseRepository(
        client=mock_client,
        app_token=_APP_TOKEN,
        table_id=_TABLE_ID,
        field_map=_FIELD_MAP,
    )


# ============================================================
# field mapping — _to_feishu
# ============================================================


class TestToFeishu:
    """Python keys → Feishu keys via field_map."""

    def test_maps_known_keys(self, repo: BaseRepository) -> None:
        result = repo._to_feishu({"book_id": "B001", "title": "Test Book"})
        assert result == {"Book ID": "B001", "Book Title": "Test Book"}

    def test_unknown_key_passes_through(self, repo: BaseRepository) -> None:
        result = repo._to_feishu({"unknown_field": "val"})
        assert result == {"unknown_field": "val"}

    def test_empty_dict(self, repo: BaseRepository) -> None:
        assert repo._to_feishu({}) == {}


# ============================================================
# field mapping — _from_feishu
# ============================================================


class TestFromFeishu:
    """Feishu record → Python dict with record_id."""

    def test_maps_known_fields(self, repo: BaseRepository) -> None:
        record = {"record_id": "rec-001", "fields": {"Book ID": "B001"}}
        result = repo._from_feishu(record)
        assert result == {"book_id": "B001", "record_id": "rec-001"}

    def test_unknown_field_passes_through(self, repo: BaseRepository) -> None:
        record = {"record_id": "rec-002", "fields": {"Extra": "data"}}
        result = repo._from_feishu(record)
        assert result == {"Extra": "data", "record_id": "rec-002"}

    def test_missing_record_id_defaults_empty(self, repo: BaseRepository) -> None:
        record = {"fields": {"Book ID": "B002"}}
        result = repo._from_feishu(record)
        assert result["record_id"] == ""

    def test_missing_fields_defaults_empty(self, repo: BaseRepository) -> None:
        record = {"record_id": "rec-003"}
        result = repo._from_feishu(record)
        assert result == {"record_id": "rec-003"}


# ============================================================
# base_path
# ============================================================


class TestBasePath:
    """_base_path constructs the correct Feishu Bitable URL segment."""

    def test_path_structure(self, repo: BaseRepository) -> None:
        path = repo._base_path()
        assert path == f"/bitable/v1/apps/{_APP_TOKEN}/tables/{_TABLE_ID}/records"


# ============================================================
# create
# ============================================================


class TestCreate:
    """create POSTs mapped fields and returns mapped record."""

    def test_create_success(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "record": {
                    "record_id": "rec-new",
                    "fields": {"Book ID": "B010", "Book Title": "New Book"},
                }
            }
        }

        result = repo.create({"book_id": "B010", "title": "New Book"})

        mock_client.post.assert_called_once_with(
            repo._base_path(),
            body={"fields": {"Book ID": "B010", "Book Title": "New Book"}},
        )
        assert result["book_id"] == "B010"
        assert result["title"] == "New Book"
        assert result["record_id"] == "rec-new"


# ============================================================
# get
# ============================================================


class TestGet:
    """get fetches a single record by ID and maps it."""

    def test_get_success(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "record": {
                    "record_id": "rec-005",
                    "fields": {"Book ID": "B005"},
                }
            }
        }

        result = repo.get("rec-005")

        expected_path = f"{repo._base_path()}/rec-005"
        mock_client.get.assert_called_once_with(expected_path)
        assert result["book_id"] == "B005"
        assert result["record_id"] == "rec-005"

    def test_get_returns_none_on_error(
        self, repo: BaseRepository, mock_client: MagicMock
    ) -> None:
        mock_client.get.side_effect = FeishuNotFoundError("not found", code=1254043)

        result = repo.get("rec-missing")
        assert result is None

    def test_get_propagates_auth_error(
        self, repo: BaseRepository, mock_client: MagicMock
    ) -> None:
        mock_client.get.side_effect = FeishuAuthError("token expired")

        with pytest.raises(FeishuAuthError):
            repo.get("rec-001")


# ============================================================
# list with pagination
# ============================================================


class TestList:
    """list auto-follows page_token across multiple pages."""

    def test_single_page(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "items": [
                    {"record_id": "r1", "fields": {"Book ID": "B1"}},
                    {"record_id": "r2", "fields": {"Book ID": "B2"}},
                ],
                "has_more": False,
            }
        }

        results = repo.list()

        assert len(results) == 2
        assert results[0]["book_id"] == "B1"
        assert results[1]["book_id"] == "B2"

    def test_multi_page_concatenation(
        self, repo: BaseRepository, mock_client: MagicMock
    ) -> None:
        page1 = {
            "data": {
                "items": [{"record_id": "r1", "fields": {"Book ID": "B1"}}],
                "has_more": True,
                "page_token": "pt_abc",
            }
        }
        page2 = {
            "data": {
                "items": [{"record_id": "r2", "fields": {"Book ID": "B2"}}],
                "has_more": False,
            }
        }
        mock_client.get.side_effect = [page1, page2]

        results = repo.list(page_size=1)

        assert len(results) == 2
        assert results[0]["book_id"] == "B1"
        assert results[1]["book_id"] == "B2"
        assert mock_client.get.call_count == 2

        # second call should include page_token
        second_call = mock_client.get.call_args_list[1]
        params = second_call.kwargs.get("params", second_call[1].get("params", {}))
        assert params["page_token"] == "pt_abc"

    def test_filter_passed_to_params(
        self, repo: BaseRepository, mock_client: MagicMock
    ) -> None:
        mock_client.get.return_value = {
            "data": {"items": [], "has_more": False}
        }

        repo.list(filter_expr='CurrentValue.[status] = "active"')

        call = mock_client.get.call_args
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["filter"] == 'CurrentValue.[status] = "active"'


# ============================================================
# update
# ============================================================


class TestUpdate:
    """update PUTs mapped fields and returns mapped record."""

    def test_update_success(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        mock_client.put.return_value = {
            "data": {
                "record": {
                    "record_id": "rec-010",
                    "fields": {"Book ID": "B010", "Book Title": "Updated"},
                }
            }
        }

        result = repo.update("rec-010", {"title": "Updated"})

        expected_path = f"{repo._base_path()}/rec-010"
        mock_client.put.assert_called_once_with(
            expected_path, body={"fields": {"Book Title": "Updated"}}
        )
        assert result["title"] == "Updated"
        assert result["record_id"] == "rec-010"


# ============================================================
# delete
# ============================================================


class TestDelete:
    """delete DELETEs the record and returns True."""

    def test_delete_success(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}

        result = repo.delete("rec-del")

        expected_path = f"{repo._base_path()}/rec-del"
        mock_client.delete.assert_called_once_with(expected_path)
        assert result is True


# ============================================================
# _field_filter
# ============================================================


class TestFieldFilter:
    """_field_filter builds correct Bitable filter expressions."""

    def test_maps_known_keys(self, repo: BaseRepository) -> None:
        result = repo._field_filter(book_id="B001")
        assert result == 'CurrentValue.[Book ID] = "B001"'

    def test_int_values_unquoted(self) -> None:
        """int values appear without quotes in the filter."""
        field_map = {"chapter_no": "Chapter No"}
        int_repo = BaseRepository(
            client=MagicMock(),
            app_token=_APP_TOKEN,
            table_id=_TABLE_ID,
            field_map=field_map,
        )
        result = int_repo._field_filter(chapter_no=5)
        assert result == "CurrentValue.[Chapter No] = 5"

    def test_multi_field_and(self, repo: BaseRepository) -> None:
        result = repo._field_filter(book_id="B001", title="Test")
        # order is deterministic: book_id then title
        assert result == 'CurrentValue.[Book ID] = "B001" && CurrentValue.[Book Title] = "Test"'


# ============================================================
# find_by_business_key
# ============================================================


class TestFindByBusinessKey:
    """find_by_business_key resolves business fields to a Feishu record."""

    def test_returns_first_match(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        """Given a record in the table, find_by_business_key returns it."""
        mock_client.get.return_value = {
            "data": {
                "items": [
                    {"record_id": "rec-abc", "fields": {"Book ID": "B001", "Book Title": "Found"}},
                ],
                "has_more": False,
            }
        }

        result = repo.find_by_business_key(book_id="B001")

        assert result is not None
        assert result["record_id"] == "rec-abc"
        assert result["book_id"] == "B001"

        # verify the filter was built correctly
        call = mock_client.get.call_args
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["filter"] == 'CurrentValue.[Book ID] = "B001"'
        assert params["page_size"] == "1"

    def test_returns_none_when_empty(self, repo: BaseRepository, mock_client: MagicMock) -> None:
        """When no record matches, find_by_business_key returns None."""
        mock_client.get.return_value = {
            "data": {"items": [], "has_more": False}
        }

        result = repo.find_by_business_key(book_id="MISSING")

        assert result is None
