"""Book bootstrap and the canonical, immutable StoryState v1 boundary."""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from app.generation import ArtifactIntegrityError, CallContext, Prompt, digest
from app.harness import TransitionConflict, encode, now, stable_id
from app.storage import AmbiguousWrite, MissingRecord


class BootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: str = Field(min_length=1, max_length=200)
    cover_run_id: str = Field(min_length=1, max_length=200)
    cover_artifact_id: str = Field(min_length=1, max_length=200)
    title_artifact_id: str = Field(min_length=1, max_length=200)
    opportunity_artifact_id: str = Field(min_length=1, max_length=200)


class StoryStateContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    StoryBible: dict
    World: dict
    Characters: dict
    PowerSystem: dict
    Timeline: dict
    Plot: dict
    Foreshadowing: dict
    StyleContract: dict


BOOTSTRAP_PROMPT = Prompt(version="book-bootstrap-v1", template="Deterministic projection of approved opportunity, title and cover into StoryState v1.")


class StoryContextProvider:
    """The only book-scoped story truth consumed by later workflows."""

    def __init__(self, kernel):
        self.kernel = kernel

    def get(self, book_id: str) -> dict:
        with self.kernel.writer:
            book = self.kernel.storage.get("books", book_id)
            if not book or book.get("status") != "ready":
                raise MissingRecord(book_id)
            state_id = book.get("story_state_id", "")
            row = self.kernel.storage.get("story_states", state_id) if state_id else None
            if not row or row.get("book_id") != book_id or row.get("version") != book.get("story_state_version"):
                raise AmbiguousWrite("Book points to a missing or mismatched StoryState")
            try:
                artifact = self.kernel.artifacts.get(row["artifact_id"])
                row_refs = json.loads(row["source_refs_json"])
                book_refs = json.loads(book["source_refs_json"])
            except (MissingRecord, ArtifactIntegrityError, KeyError, TypeError, ValueError):
                raise AmbiguousWrite("StoryState artifact or provenance is unreadable") from None
            if (artifact["artifact_type"] != "StoryState" or artifact["version"] != row["version"] or
                artifact["content_hash"] != row["content_hash"] or
                artifact["source_refs"] != row_refs or artifact["source_refs"] != book_refs or
                artifact["content_hash"] != book.get("story_state_hash") or
                artifact["logical_id"] != f"books/{book_id}/story-state"):
                raise AmbiguousWrite("StoryState provenance or book pointer changed")
            try:
                content = StoryStateContent.model_validate(artifact["content"]).model_dump()
            except ValueError:
                raise AmbiguousWrite("StoryState content no longer matches its schema") from None
            return {"book": book, "state": {**row, "source_refs": artifact["source_refs"],
                "content": content, "created_at": artifact["created_at"]}}


class BookService:
    def __init__(self, kernel):
        if not getattr(kernel, "creative", None) or not getattr(kernel, "artifacts", None):
            raise ValueError("Book bootstrap requires creative selections and artifacts")
        self.kernel = kernel
        self.context_provider = StoryContextProvider(kernel)

    def source(self, cover_run_id: str) -> dict:
        """Resolve every currently approved link, ending at the selected cover."""
        with self.kernel.writer:
            cover = self.kernel.creative.selected("covers", cover_run_id)
            cover_run = self.kernel.creative.read(cover_run_id)
            title_run_id = cover_run["request"]["source_run_id"]
            title = self.kernel.creative.selected("titles", title_run_id)
            if cover_run["request"]["source_artifact_id"] != title["artifact_id"]:
                raise TransitionConflict("Cover no longer belongs to selected title")
            title_run = self.kernel.creative.read(title_run_id)
            analysis_run_id = title_run["request"]["source_run_id"]
            opportunity = self.kernel.research.approved(analysis_run_id)
            if title_run["request"]["source_artifact_id"] != opportunity["artifact_id"]:
                raise TransitionConflict("Title no longer belongs to approved opportunity")
            analysis = self.kernel.research.get(analysis_run_id)
            return {"cover_run_id": cover_run_id, "cover": cover, "title": title,
                "opportunity": opportunity, "analysis": analysis}

    @staticmethod
    def content(source: dict) -> dict:
        opportunity = source["opportunity"]["content"]
        title = source["title"]["content"]
        cover = source["cover"]["content"]
        return StoryStateContent(
            StoryBible={"premise": opportunity["summary"], "reader_promise": opportunity["reader_promise"],
                "core_emotions": opportunity["core_emotions"], "genre_fit": opportunity["genre_fit"],
                "title": title["title"], "cover_direction": cover["visual_direction"]},
            World={"setting": "", "rules": []},
            Characters={"characters": []},
            PowerSystem={"systems": [], "constraints": []},
            Timeline={"events": []},
            Plot={"directions": opportunity["novelization_directions"], "hit_patterns": opportunity["hit_patterns"],
                "outline": []},
            Foreshadowing={"threads": []},
            StyleContract={"hook": title["hook"], "selling_point": title["selling_point"],
                "cover_style": cover["style"], "rules": []},
        ).model_dump()

    def context(self, cover_run_id: str) -> dict:
        source = self.source(cover_run_id)
        cover, title, opportunity = (source[name] for name in ("cover", "title", "opportunity"))
        return {"cover_run_id": cover_run_id, "cover_artifact_id": cover["artifact_id"],
            "title_artifact_id": title["artifact_id"], "opportunity_artifact_id": opportunity["artifact_id"],
            "book_id": stable_id("BK-", cover["artifact_id"])}

    def bootstrap(self, value: dict) -> dict:
        request = BootstrapRequest.model_validate(value)
        with self.kernel.writer:
            book_id = stable_id("BK-", request.cover_artifact_id)
            if request.book_id != book_id:
                raise TransitionConflict("Book ID does not match selected cover")
            state_id = stable_id("SS-", book_id + "/1")
            refs = [request.opportunity_artifact_id, request.title_artifact_id, request.cover_artifact_id]
            fingerprint = digest({"run": request.cover_run_id, "refs": refs})
            existing = self.kernel.storage.get("books", book_id)
            if existing:
                if (existing.get("bootstrap_hash") != fingerprint or existing.get("story_state_id") != state_id):
                    raise TransitionConflict("Book business key is reserved for different source artifacts")
                if existing.get("status") == "ready":
                    return self.read(book_id)
            source = self.source(request.cover_run_id)
            if [source[name]["artifact_id"] for name in ("opportunity", "title", "cover")] != refs:
                raise TransitionConflict("Approved source selection changed; refresh book context")
            content = self.content(source)
            analysis = source["analysis"]
            book_fields = {"book_id": book_id, "hotspot_id": analysis["request"]["hotspot_id"],
                "analysis_id": stable_id("AN-", self.kernel.research.identity(analysis["request"])),
                "title_id": stable_id("TI-", request.title_artifact_id),
                "cover_id": stable_id("CO-", request.cover_artifact_id),
                "book_title": source["title"]["content"]["title"],
                "genre": ", ".join(source["opportunity"]["content"]["genre_fit"]),
                "bootstrap_hash": fingerprint, "source_refs_json": encode(refs),
                "story_state_id": state_id, "story_state_version": 1}
            if existing is None:
                existing = self.kernel._ensure("books", "book_id", {**book_fields,
                    "status": "initializing", "created_at": now()})
            if any(existing.get(k) != v for k, v in book_fields.items()):
                raise AmbiguousWrite("Book bootstrap projection conflicts with existing record")
            # The artifact is immutable. A partial create is retried with the same IDs and content.
            artifact = self.kernel.artifacts.save(logical_id=f"books/{book_id}/story-state", version=1,
                artifact_type="StoryState", content=content,
                context=CallContext(run_id=request.cover_run_id, step_id="", input_refs=tuple(refs),
                    workflow_version="book-bootstrap-v1"), prompt=BOOTSTRAP_PROMPT,
                route="deterministic", provider="", model="", input_hash=fingerprint,
                creator="book-bootstrap")
            state_fields = {"story_state_id": state_id, "book_id": book_id, "version": 1,
                "artifact_id": artifact["artifact_id"], "content_hash": artifact["content_hash"],
                "source_refs_json": encode(refs), "created_at": artifact["created_at"]}
            state = self.kernel._ensure("story_states", "story_state_id", state_fields)
            if any(state.get(k) != v for k, v in state_fields.items()):
                raise AmbiguousWrite("StoryState v1 conflicts with existing record")
            if existing.get("status") != "ready":
                self.kernel.storage.update("books", book_id,
                    {"status": "ready", "story_state_hash": artifact["content_hash"]})
            return self.read(book_id)

    def list_books(self) -> list[dict]:
        with self.kernel.writer:
            return sorted(self.kernel.storage.list("books"),
                key=lambda row: row.get("created_at", ""), reverse=True)

    def read(self, book_id: str) -> dict:
        with self.kernel.writer:
            book = self.kernel.storage.get("books", book_id)
            if book is None:
                raise MissingRecord(book_id)
            if not book.get("story_state_id") or book.get("status") != "ready":
                return {"book": book, "state": None,
                    "legacy": not bool(book.get("story_state_id"))}
            return {**self.context_provider.get(book_id), "legacy": False}
