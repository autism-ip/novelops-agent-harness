"""
[INPUT]: 依赖 app.feishu.client.FeishuClient 的 HTTP 能力
[OUTPUT]: 对外提供 BaseRepository——通用 Bitable CRUD + CAS + 字段过滤 + 业务键查找基类
[POS]: repositories 包的抽象基类，被 16 个具体 repository 继承
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

from app.feishu.client import FeishuClient, FeishuNotFoundError

# ============================================================
# base repository
# ============================================================


class BaseRepository:
    """Generic CRUD operations over Feishu Bitable.

    Subclasses set ``table_id`` and ``field_map`` at construction time
    and inherit all five standard data-access methods.
    """

    def __init__(
        self,
        client: FeishuClient,
        app_token: str,
        table_id: str,
        field_map: dict[str, str],
    ) -> None:
        self._client = client
        self._app_token = app_token
        self._table_id = table_id
        self._field_map = field_map

    # ----------------------------------------------------------
    # field mapping
    # ----------------------------------------------------------

    def _to_feishu(self, data: dict) -> dict:
        """Map Python field names -> Feishu field names."""
        return {self._field_map.get(k, k): v for k, v in data.items()}

    def _from_feishu(self, record: dict) -> dict:
        """Map Feishu field names -> Python field names."""
        reverse = {v: k for k, v in self._field_map.items()}
        fields = record.get("fields", {})
        mapped = {reverse.get(k, k): v for k, v in fields.items()}
        mapped["record_id"] = record.get("record_id", "")
        return mapped

    def _field_filter(self, **conditions: str | int) -> str:
        """Build a Bitable filter expression from Python field names.

        - Maps keys through ``self._field_map``.
        - int values are unquoted; str values are double-quoted.
        - Multiple conditions are joined with `` && ``.
        """
        clauses: list[str] = []
        for key, value in conditions.items():
            feishu_field = self._field_map.get(key, key)
            if isinstance(value, int):
                clauses.append(f'CurrentValue.[{feishu_field}] = {value}')
            else:
                clauses.append(f'CurrentValue.[{feishu_field}] = "{value}"')
        return " && ".join(clauses)

    def find_by_business_key(self, **conditions: str | int) -> dict | None:
        """Look up a record by business fields, returning the first match or None."""
        results = self.list(filter_expr=self._field_filter(**conditions), page_size=1)
        return results[0] if results else None

    # ----------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------

    def _base_path(self) -> str:
        return (
            f"/bitable/v1/apps/{self._app_token}"
            f"/tables/{self._table_id}/records"
        )

    def create(self, data: dict) -> dict:
        """Create a record and return the mapped result."""
        body = {"fields": self._to_feishu(data)}
        resp = self._client.post(self._base_path(), body=body)
        return self._from_feishu(resp["data"]["record"])

    def get(self, record_id: str) -> dict | None:
        """Fetch a single record by ID, or None if not found."""
        path = f"{self._base_path()}/{record_id}"
        try:
            resp = self._client.get(path)
        except FeishuNotFoundError:
            return None
        return self._from_feishu(resp["data"]["record"])

    def list(
        self,
        filter_expr: str | None = None,
        page_size: int = 20,
    ) -> list[dict]:
        """List records with automatic pagination."""
        results: list[dict] = []
        page_token: str | None = None

        while True:
            params: dict[str, str] = {"page_size": str(page_size)}
            if filter_expr:
                params["filter"] = filter_expr
            if page_token:
                params["page_token"] = page_token

            resp = self._client.get(self._base_path(), params=params)
            data = resp.get("data", {})

            for item in data.get("items", []):
                results.append(self._from_feishu(item))

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        return results

    def update(self, record_id: str, fields: dict) -> dict:
        """Update specific fields of a record."""
        path = f"{self._base_path()}/{record_id}"
        body = {"fields": self._to_feishu(fields)}
        resp = self._client.put(path, body=body)
        return self._from_feishu(resp["data"]["record"])

    def delete(self, record_id: str) -> bool:
        """Delete a record. Returns True on success."""
        path = f"{self._base_path()}/{record_id}"
        self._client.delete(path)
        return True

    def conditional_update(
        self, record_id: str, fields: dict, condition: dict
    ) -> dict:
        """CAS update — applies *fields* only when *condition* matches.

        Builds a Bitable filter from *condition* and includes it in the
        PUT request.  Raises on mismatch so callers can detect races.
        """
        path = f"{self._base_path()}/{record_id}"
        body = {"fields": self._to_feishu(fields)}

        # Build filter from condition dict: CurrentValue.[field] = "value"
        if condition:
            parts = [
                f'CurrentValue.[{self._field_map.get(k, k)}] = "{v}"'
                for k, v in condition.items()
            ]
            body["filter"] = " AND ".join(parts)

        resp = self._client.put(path, body=body)
        return self._from_feishu(resp["data"]["record"])
