"""Manual hotspot commands run through the kernel's single writer and journal."""
import hashlib

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.harness import encode, stable_id
from app.hotspots import HotspotRecord
from app.storage import AmbiguousWrite, MissingRecord


class ManualInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(default="", max_length=2048)
    category: str = Field(default="", max_length=200)

    @field_validator("title")
    @classmethod
    def title_valid(cls, value):
        return HotspotRecord.title_not_blank(value).strip()

    @field_validator("url")
    @classmethod
    def url_valid(cls, value):
        return HotspotRecord.public_url(value.strip())


class HotspotControls:
    def __init__(self, service):
        self.service = service
        self.kernel = service.kernel
        self.kernel.register("hotspots.manual_add", self.add)
        self.kernel.register("hotspots.discard", self.discard)

    def enqueue_add(self, request_key, fields):
        spec = ManualInput.model_validate(fields)
        return self.kernel.create("hotspots:manual:" + request_key, "hotspot_manual_v1", [
            {"step_key": "save", "handler": "hotspots.manual_add", "input": spec.model_dump()}])

    def enqueue_discard(self, hotspot_id, request_key, expected_status):
        self.service.get(hotspot_id)
        return self.kernel.create("hotspots:discard:" + request_key, "hotspot_discard_v1", [
            {"step_key": "discard", "handler": "hotspots.discard",
             "input": {"hotspot_id": hotspot_id, "expected_status": expected_status}}],
            source_hotspot_id=hotspot_id)

    def add(self, step):
        spec = ManualInput.model_validate(step["input"])
        key = hashlib.sha256(f"manual:{spec.title}:{spec.url}".encode()).hexdigest()
        with self.kernel.writer:
            existing = self.kernel.storage.list("hotspots", dedupe_hash=key)
            if len(existing) > 1:
                raise AmbiguousWrite("Duplicate manual hotspot identities")
            fields = {**spec.model_dump(), "source": "manual", "dedupe_hash": key,
                "hotspot_id": stable_id("HS-", key), "rank": 0, "heat_value": 0,
                "captured_at": self.kernel.get(step["pipeline_run_id"])["created_at"],
                "status": "normalized", "raw_json": encode(spec.model_dump()),
                "last_ingestion_run_id": step["pipeline_run_id"]}
            row = existing[0] if existing else self.kernel._ensure("hotspots", "hotspot_id", fields)
            if any(row.get(k) != fields[k] for k in ("source", "title", "url", "dedupe_hash")):
                raise AmbiguousWrite("Manual hotspot identity mismatch")
            return {"hotspot_id": row["hotspot_id"], "status": row["status"]}

    def discard(self, step):
        with self.kernel.writer:
            hotspot_id = step["input"]["hotspot_id"]
            row = self.kernel.storage.get("hotspots", hotspot_id)
            if row is None:
                raise MissingRecord(hotspot_id)
            if row["status"] != "discarded":
                if row["status"] != step["input"]["expected_status"]:
                    raise AmbiguousWrite("Hotspot status changed; refresh and review before discarding")
                self.kernel.storage.update("hotspots", hotspot_id, {"status": "discarded"})
            return {"hotspot_id": hotspot_id, "status": "discarded"}
