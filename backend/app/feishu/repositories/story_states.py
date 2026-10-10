"""Feishu projection of immutable canonical StoryState versions."""
from __future__ import annotations

from app.feishu.client import FeishuClient
from app.feishu.repositories.base import BaseRepository
from app.feishu.table_map import FIELD_MAPS


class StoryStatesRepo(BaseRepository):
    def __init__(self, client: FeishuClient, app_token: str, table_id: str) -> None:
        super().__init__(client, app_token, table_id, FIELD_MAPS["story_states"])

    def find_by_book(self, book_id: str) -> list[dict]:
        return self.list(filter_expr=self._field_filter(book_id=book_id))
