"""
douyin_hotspots — DouyinHotspotAdapter normalization.

[INPUT]: Depends on app.tools.runner.OpenCLIRunner, app.tools.schemas.DouyinHotspotRecord
[OUTPUT]: Provides DouyinHotspotAdapter class, DouyinAdapterResult frozen dataclass
[POS]: app/tools/adapters/ — Douyin-specific command assembly and field normalization
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.tools.errors import OpenCLIError
from app.tools.runner import OpenCLIRunner
from app.tools.schemas import DouyinHotspotRecord


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DouyinAdapterResult:
    """Result from a Douyin hotspot adapter call."""

    records: tuple[DouyinHotspotRecord, ...]
    raw_count: int
    duration_ms: int


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class DouyinHotspotAdapter:
    """Adapter for extracting Douyin public hotspots via OpenCLI.

    Assembles the command, delegates execution to OpenCLIRunner, and
    normalizes raw JSON records into DouyinHotspotRecord instances.
    """

    def __init__(self, runner: OpenCLIRunner, settings: object) -> None:
        self._runner = runner
        self._settings = settings

    def fetch(self) -> DouyinAdapterResult:
        """Fetch and normalize Douyin hotspot data.

        Returns:
            DouyinAdapterResult with normalized records, raw count,
            and duration_ms.

        Raises:
            OpenCLIError: If OpenCLI is disabled in settings.
        """
        if not getattr(self._settings, "OPENCLI_ENABLED", True):
            raise OpenCLIError("OpenCLI is disabled")

        result = self._runner.run(["douyin", "hotspots", "--format", "json"])
        raw_records = result.data if isinstance(result.data, list) else []

        normalized: list[DouyinHotspotRecord] = []
        for raw in raw_records:
            record = self._normalize(raw)
            if record is not None:
                normalized.append(record)

        return DouyinAdapterResult(
            records=tuple(normalized),
            raw_count=len(raw_records),
            duration_ms=result.duration_ms,
        )

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw: dict[str, Any]) -> DouyinHotspotRecord | None:
        """Normalize a single raw record into DouyinHotspotRecord.

        Returns None when the record lacks a usable title — these are
        silently dropped from the result set.
        """
        title = raw.get("title") or raw.get("word") or raw.get("name")
        if not title:
            return None

        url = raw.get("url") or raw.get("link") or ""
        rank = self._to_int(
            raw.get("rank") or raw.get("position") or raw.get("index") or 0
        )
        heat_value = self._to_int(
            raw.get("heat_value")
            or raw.get("hot_value")
            or raw.get("heat")
            or raw.get("hotValue")
            or 0
        )
        category = raw.get("category") or raw.get("label") or ""
        source = raw.get("source") or "douyin"
        captured_at = (
            raw.get("captured_at")
            or raw.get("created_at")
            or datetime.now(timezone.utc).isoformat()
        )

        dedupe_hash = hashlib.sha256(
            f"{source}:{title}:{url}".encode()
        ).hexdigest()

        return DouyinHotspotRecord(
            source=str(source),
            rank=rank,
            title=str(title),
            url=str(url),
            heat_value=heat_value,
            category=str(category),
            captured_at=str(captured_at),
            raw_json=raw,
            dedupe_hash=dedupe_hash,
            hotspot_id=str(uuid.uuid4()),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_int(value: Any) -> int:
        """Safely convert value to int, returning 0 on failure."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0
