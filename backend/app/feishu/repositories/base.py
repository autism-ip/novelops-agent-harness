"""
[INPUT]: 依赖 app.feishu.client.FeishuClient 的 HTTP 能力
[OUTPUT]: 对外提供 BaseRepository——通用 Bitable CRUD + CAS + 字段过滤 + 业务键查找基类
[POS]: repositories 包的抽象基类，被 16 个具体 repository 继承
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from app.feishu.client import FeishuAPIError, FeishuClient, FeishuNotFoundError
from app.feishu.table_map import FLOAT_FIELD_NAMES, INTEGER_FIELD_NAMES

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
        for name, value in mapped.items():
            if name not in INTEGER_FIELD_NAMES and name not in FLOAT_FIELD_NAMES:
                continue
            if value is None or value == "":
                continue
            try:
                number = Decimal(str(value))
            except InvalidOperation:
                raise FeishuAPIError("Invalid numeric cell", code=0) from None
            if not number.is_finite():
                raise FeishuAPIError("Invalid numeric cell", code=0)
            if name in INTEGER_FIELD_NAMES:
                if number != number.to_integral_value():
                    raise FeishuAPIError("Non-integral integer cell", code=0)
                mapped[name] = int(number)
            else:
                mapped[name] = float(number)
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
                clauses.append(f'CurrentValue.[{feishu_field}] = {json.dumps(value, ensure_ascii=False)}')
        return " && ".join(clauses)

    def find_by_business_key(self, **conditions: str | int) -> dict | None:
        """Return a unique business-key match, rejecting duplicate records."""
        results = self.list(filter_expr=self._field_filter(**conditions), page_size=100)
        if len(results) > 1:
            from app.storage import DuplicateKey
            raise DuplicateKey("Duplicate business key")
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
        payload = resp.get("data") if isinstance(resp, dict) else None
        record = payload.get("record") if isinstance(payload, dict) else None
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("record_id"), str)
            or not record["record_id"]
            or not isinstance(record.get("fields"), dict)
        ):
            # The POST may have committed even if its success envelope is broken.
            raise FeishuAPIError("Malformed create response", code=0)
        return self._from_feishu(record)

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
            next_token = data.get("page_token")
            if not next_token or next_token == page_token:
                raise ValueError("Invalid Feishu pagination token")
            page_token = next_token

        return results

    def update(self, record_id: str, fields: dict, *, previous: dict | None = None) -> dict:
        """Update fields and return a complete row even when PUT echoes only the patch."""
        current = previous if previous is not None else self.get(record_id)
        if current is None:
            raise FeishuNotFoundError("Record to update does not exist")
        if current.get("record_id") != record_id:
            raise ValueError("Previous record identity does not match update target")
        path = f"{self._base_path()}/{record_id}"
        body = {"fields": self._to_feishu(fields)}
        resp = self._client.put(path, body=body)
        payload = resp.get("data") if isinstance(resp, dict) else None
        record = payload.get("record") if isinstance(payload, dict) else None
        if (not isinstance(record, dict) or record.get("record_id") != record_id
                or not isinstance(record.get("fields"), dict)):
            raise FeishuAPIError("Malformed update response", code=0)
        updated = self._from_feishu(record)
        if any(key not in updated for key in fields):
            raise FeishuAPIError("Update response omitted changed fields", code=0)
        return {**current, **updated}

    def delete(self, record_id: str) -> bool:
        """Delete a record. Returns True on success."""
        path = f"{self._base_path()}/{record_id}"
        self._client.delete(path)
        return True

    def conditional_update(
        self, record_id: str, fields: dict, condition: dict
    ) -> dict:
        """Legacy read/check/write helper, NOT an atomic server-side CAS.

        Callers must hold the application's single-writer lock. The record PUT
        contract has no documented conditional filter parameter.
        """
        current = self.get(record_id)
        if current is None or any(current.get(k) != v for k, v in condition.items()):
            raise ValueError("Record condition does not match")
        return self.update(record_id, fields, previous=current)
