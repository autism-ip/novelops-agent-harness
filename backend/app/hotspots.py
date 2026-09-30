"""Deterministic public hotspot ingestion; no model calls or platform record IDs."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.generation import digest
from app.harness import encode, stable_id
from app.storage import AmbiguousWrite, MissingRecord
from app.tools.errors import OpenCLIOutputError


class IngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=30, le=50)
    command_hash: str


class HotspotRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["douyin"]
    hotspot_id: str
    dedupe_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(max_length=2048)
    rank: int = Field(ge=0)
    heat_value: int = Field(ge=0)
    category: str = Field(max_length=200)
    captured_at: datetime
    raw_json: dict
    status: str

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Empty hotspot title")
        return value

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        if value:
            parts = urlsplit(value)
            if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("Invalid source URL")
        return value

    @field_validator("captured_at")
    @classmethod
    def aware_capture(cls, value):
        if value.tzinfo is None:
            raise ValueError("Capture timestamp requires timezone")
        return value.astimezone(timezone.utc)


class HotspotService:
    def __init__(self, kernel, adapter, *, collection_enabled=True):
        self.kernel = kernel
        self.adapter = adapter
        self.collection_enabled = collection_enabled
        runner = getattr(adapter, "_runner", None)
        self.command_hash = digest({"command": getattr(adapter, "_cmd", []),
                                    "binary": getattr(runner, "_bin", "")})
        if collection_enabled:
            kernel.register("hotspots.fetch", self.fetch)
        kernel.register("hotspots.persist", self.persist)

    def enqueue(self, request_key: str, limit: int = 50):
        if not self.collection_enabled:
            raise ValueError("Hotspot collection is disabled")
        if not request_key.strip():
            raise ValueError("request_key must not be blank")
        spec = IngestionInput(limit=limit, command_hash=self.command_hash)
        return self.kernel.create("hotspots:" + request_key, "hotspot_ingestion_v1", [
            {"step_key": "fetch", "handler": "hotspots.fetch", "kind": "tool", "input": spec.model_dump()},
            {"step_key": "persist", "handler": "hotspots.persist", "kind": "service", "depends_on": ["fetch"]}])

    def fetch(self, step):
        if not self.collection_enabled:
            raise AmbiguousWrite("Hotspot collection disabled; reconcile workflow configuration")
        spec = IngestionInput.model_validate(step["input"])
        if spec.command_hash != self.command_hash:
            raise AmbiguousWrite("Ingestion command changed; reconcile workflow configuration")
        result = self.adapter.fetch()
        valid = []
        for record in result.records:
            try:
                valid.append(HotspotRecord.model_validate(asdict(record)).model_dump(mode="json"))
            except (ValidationError, ValueError):
                continue
        if result.raw_count and not valid:
            raise OpenCLIOutputError("Feed contained no valid public hotspot records")
        # Keep the first occurrence in source rank order, regardless of transient UUIDs.
        unique = {}
        for record in valid:
            unique.setdefault(record["dedupe_hash"], record)
        selected = list(unique.values())[:spec.limit]
        counts = {"fetched": result.raw_count, "accepted": len(valid),
            "rejected": result.raw_count-len(valid), "duplicate_in_batch": len(valid)-len(unique),
            "selected": len(selected), "omitted": len(unique)-len(selected)}
        snapshot = {"records": selected, "counts": counts, "command_hash": self.command_hash}
        return {**snapshot, "batch_hash": digest(snapshot), "duration_ms": result.duration_ms,
                "source": "douyin", "command_hash": self.command_hash}

    def persist(self, step):
        with self.kernel.writer:
            run = self.kernel.get(step["pipeline_run_id"])
            fetched = next((s for s in run["steps"] if s["step_key"] == "fetch"), None)
            if fetched is None or fetched["status"] != "success":
                raise AmbiguousWrite("Persist requires a successful fetch snapshot")
            try:
                snapshot = json.loads(fetched["output_json"])
                if snapshot["command_hash"] != self.command_hash:
                    raise ValueError("Ingestion command changed")
                if digest({k: snapshot[k] for k in ("records", "counts", "command_hash")}) != snapshot["batch_hash"]:
                    raise ValueError("Snapshot hash mismatch")
                records = [HotspotRecord.model_validate(r) for r in snapshot["records"]]
            except (ValueError, TypeError, KeyError):
                raise AmbiguousWrite("Invalid persisted ingestion snapshot") from None
            refs = []
            created = reconciled = updated = 0
            for record in records:
                matches = self.kernel.storage.list("hotspots", dedupe_hash=record.dedupe_hash)
                if len(matches) > 1:
                    raise AmbiguousWrite("Duplicate hotspot dedupe keys require reconciliation")
                domain_id = matches[0]["hotspot_id"] if matches else stable_id("HS-", record.dedupe_hash)
                fields = record.model_dump(mode="json")
                fields.update(hotspot_id=domain_id, status="normalized", raw_json=encode(record.raw_json),
                              last_ingestion_run_id=step["pipeline_run_id"])
                if matches:
                    existing = matches[0]
                    reconciled += 1
                else:
                    existing = self.kernel._ensure("hotspots", "hotspot_id", fields)
                    created += 1
                if any(existing.get(k) != fields[k] for k in ("source", "title", "url", "dedupe_hash")):
                    raise AmbiguousWrite("Hotspot identity does not match its dedupe key")
                try:
                    previous = datetime.fromisoformat(existing["captured_at"].replace("Z", "+00:00"))
                    if previous.tzinfo is None:
                        raise ValueError("Missing timezone")
                except (KeyError, ValueError, TypeError, AttributeError):
                    raise AmbiguousWrite("Invalid stored capture timestamp") from None
                if record.captured_at > previous:
                    # Repeated capture updates metadata but never resets an approval/discard status.
                    metadata = {key: fields[key] for key in ("rank", "heat_value", "category", "captured_at", "raw_json", "last_ingestion_run_id")}
                    self.kernel.storage.update("hotspots", domain_id, metadata)
                    updated += 1
                refs.append(domain_id)
            return {"counts": snapshot["counts"], "created": created, "reconciled": reconciled,
                    "updated": updated, "output_refs": refs, "batch_hash": snapshot["batch_hash"]}

    @staticmethod
    def public(row):
        try:
            payload = json.loads(row.get("raw_json") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("Stored payload must be an object")
            return {**row, "raw_json": payload}
        except (ValueError, TypeError):
            raise AmbiguousWrite("Invalid stored hotspot payload") from None

    def get(self, hotspot_id):
        with self.kernel.writer:
            row = self.kernel.storage.get("hotspots", hotspot_id)
            if row is None:
                raise MissingRecord(hotspot_id)
            return self.public(row)

    def list(self, *, source=None, status=None, captured_from=None, captured_to=None, offset=0, limit=50):
        if captured_from and captured_to and captured_from > captured_to:
            raise ValueError("captured_from must precede captured_to")
        with self.kernel.writer:
            rows = self.kernel.storage.list("hotspots", **{k: v for k, v in {"source": source, "status": status}.items() if v})
            selected = []
            for row in rows:
                try:
                    capture = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
                    if capture.tzinfo is None:
                        raise ValueError("Missing timezone")
                except (KeyError, ValueError, TypeError, AttributeError):
                    raise AmbiguousWrite("Invalid stored capture timestamp") from None
                if (captured_from is None or capture >= captured_from) and (captured_to is None or capture <= captured_to):
                    selected.append((capture, row))
            selected.sort(key=lambda item: (item[0], item[1]["hotspot_id"]), reverse=True)
            return {"items": [self.public(r) for _, r in selected[offset:offset+limit]],
                    "total": len(selected), "offset": offset, "limit": limit}
