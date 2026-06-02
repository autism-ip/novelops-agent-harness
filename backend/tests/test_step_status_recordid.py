"""
[INPUT]: 依赖 app.feishu.repositories.base.BaseRepository
[OUTPUT]: 对外提供 record_id 解析行为级测试
[POS]: tests 的 repository 门禁，验证 _from_feishu 将 record_id 传入映射结果
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.feishu.repositories.base import BaseRepository


# ============================================================
# helpers
# ============================================================


def _make_repo() -> BaseRepository:
    client = MagicMock()
    field_map = {"step_run_id": "step_run_id", "status": "status"}
    return BaseRepository(
        client=client,
        app_token="bascn_test",
        table_id="tbl_test",
        field_map=field_map,
    )


# ============================================================
# record_id presence
# ============================================================


class TestRecordIdPresence:
    """_from_feishu includes record_id in mapped output."""

    def test_from_feishu_includes_record_id(self) -> None:
        repo = _make_repo()
        record = {
            "record_id": "rec_abc123",
            "fields": {"step_run_id": "sr_1", "status": "pending"},
        }
        result = repo._from_feishu(record)
        assert result["record_id"] == "rec_abc123"
        assert result["step_run_id"] == "sr_1"

    def test_get_returns_record_id(self) -> None:
        repo = _make_repo()
        repo._client.get.return_value = {
            "data": {
                "record": {
                    "record_id": "rec_xyz",
                    "fields": {"step_run_id": "sr_2", "status": "running"},
                }
            }
        }
        result = repo.get("rec_xyz")
        assert result is not None
        assert result["record_id"] == "rec_xyz"

    def test_create_returns_record_id(self) -> None:
        repo = _make_repo()
        repo._client.post.return_value = {
            "data": {
                "record": {
                    "record_id": "rec_new",
                    "fields": {"step_run_id": "sr_3", "status": "pending"},
                }
            }
        }
        result = repo.create({"step_run_id": "sr_3", "status": "pending"})
        assert result["record_id"] == "rec_new"
