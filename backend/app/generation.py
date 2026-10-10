"""Versioned artifacts, provider-neutral model calls and persistent telemetry."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.harness import encode, now, stable_id
from app.storage import MissingRecord


def digest(value) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


class Prompt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: str = Field(min_length=1)
    template: str = Field(min_length=1)


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    artifact_id: str
    logical_id: str
    version: int = Field(ge=1)
    artifact_type: str
    content: dict
    content_hash: str
    source_refs: list[str]
    run_id: str
    step_id: str
    chapter_id: str
    workflow_version: str
    prompt_version: str
    prompt_hash: str
    route: str
    route_hash: str
    provider: str
    model: str
    creator: str
    input_hash: str
    created_at: str


class Route(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    provider: Literal["openai", "deepseek"]
    model: str = Field(min_length=1)
    max_retries: int = Field(default=1, ge=0, le=2)
    timeout: float = Field(default=8, gt=0, le=25)
    max_output_tokens: int = Field(default=2048, ge=1, le=16384)
    deepseek_thinking: Literal["disabled", "enabled"] = "disabled"
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def bounded_call(self):
        retry_backoff = sum(0.2 * 2 ** attempt for attempt in range(self.max_retries))
        if self.timeout * (self.max_retries + 1) + retry_backoff > 25:
            raise ValueError("Model route call budget exceeds 25 seconds")
        if self.provider != "deepseek" and self.deepseek_thinking != "disabled":
            raise ValueError("deepseek_thinking requires a DeepSeek route")
        return self


@dataclass(frozen=True)
class CallContext:
    run_id: str
    step_id: str
    chapter_id: str = ""
    input_refs: tuple[str, ...] = ()
    workflow_version: str = "v1"


@dataclass(frozen=True)
class Completion:
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = "stop"


class ModelFailure(RuntimeError):
    def __init__(self, failure_class: str, retryable: bool = False):
        super().__init__(failure_class)
        self.failure_class = failure_class
        self.retryable = retryable


class ModelProvider(Protocol):
    def complete(self, route: Route, messages: list[dict]) -> Completion: ...


class ChatProvider:
    """Official OpenAI / DeepSeek Chat Completions with local schema validation."""
    URLS = {"openai": "https://api.openai.com/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/chat/completions"}

    def __init__(self, provider: str, api_key: str, *, client=None):
        if provider not in self.URLS:
            raise ValueError("Unsupported model provider")
        self.provider = provider
        self._api_key = api_key
        self._http = client or httpx.Client()
        self._owns_client = client is None

    def close(self):
        if self._owns_client:
            self._http.close()

    def complete(self, route: Route, messages: list[dict]) -> Completion:
        if not self._api_key:
            raise ModelFailure("MissingConfiguration")
        token_key = "max_completion_tokens" if self.provider == "openai" else "max_tokens"
        body = {"model": route.model, "messages": messages,
                "response_format": {"type": "json_object"}, token_key: route.max_output_tokens}
        if self.provider == "deepseek":
            body["thinking"] = {"type": route.deepseek_thinking}
        try:
            response = self._http.post(self.URLS[self.provider],
                headers={"Authorization": "Bearer " + self._api_key}, json=body, timeout=route.timeout)
        except httpx.TimeoutException:
            raise ModelFailure("Timeout", retryable=True) from None
        except httpx.HTTPError:
            raise ModelFailure("TransportFailure", retryable=True) from None
        if response.status_code >= 400:
            failure = "RateLimited" if response.status_code == 429 else "ProviderFailure"
            raise ModelFailure(failure, retryable=response.status_code == 429 or response.status_code >= 500)
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Non-text output")
            usage = data.get("usage") or {}
            def count(name):
                value = usage.get(name)
                return value if type(value) is int and value >= 0 else None
            return Completion(content, data.get("model", route.model), count("prompt_tokens"), count("completion_tokens"),
                              data["choices"][0].get("finish_reason"))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ModelFailure("MalformedResponse", retryable=True) from None


class TraceRecorder:
    def __init__(self, kernel):
        self.kernel = kernel

    def start(self, data: dict) -> str:
        with self.kernel.writer:
            trace_id = "TR-" + uuid.uuid4().hex
            row = {"trace_id": trace_id, "run_id": data.get("run_id", ""),
                   "step_id": data.get("step_id", ""), "chapter_id": data.get("chapter_id", ""),
                   "kind": data["kind"], "payload_json": encode({**data, "trace_id": trace_id,
                       "status": "running", "created_at": now(), "failure_class": None,
                       "input_tokens": None, "output_tokens": None, "estimated_cost": None})}
            self.kernel._ensure("traces", "trace_id", row)
            return trace_id

    def finish(self, trace_id: str, **fields):
        with self.kernel.writer:
            row = self.kernel.storage.get("traces", trace_id)
            if row is None:
                raise MissingRecord(trace_id)
            payload = json.loads(row["payload_json"])
            payload.update(fields, finished_at=now())
            self.kernel.storage.update("traces", trace_id, {"payload_json": encode(payload)})

    def list(self, *, run_id: str = "", chapter_id: str = ""):
        with self.kernel.writer:
            conditions = {k:v for k,v in {"run_id":run_id,"chapter_id":chapter_id}.items() if v}
            rows = self.kernel.storage.list("traces", **conditions)
            return sorted([json.loads(row["payload_json"]) for row in rows], key=lambda r:r["created_at"])

    def usage(self, *, run_id: str = "", chapter_id: str = ""):
        rows = [r for r in self.list(run_id=run_id, chapter_id=chapter_id) if r["kind"] == "model"]
        def total(field):
            if any(r.get(field) is None for r in rows):
                return None
            return sum(r[field] for r in rows)
        unknown = sum(r.get("input_tokens") is None or r.get("output_tokens") is None for r in rows)
        return {"attempts": len(rows), "input_tokens": total("input_tokens"), "output_tokens":total("output_tokens"),
                "estimated_cost":total("estimated_cost"), "cost_status": "unavailable" if total("estimated_cost") is None else "estimated",
                "unknown_usage_attempts":unknown, "latency_ms":total("latency_ms"),
                "retries":sum(r.get("attempt", 0)>0 for r in rows)}


class ModelRouter:
    def __init__(self, routes: dict[str, Route], providers: dict[str, ModelProvider], trace: TraceRecorder,
                 *, sleep=time.sleep):
        self.routes = routes
        self.providers = providers
        self.trace = trace
        self.sleep = sleep

    def generate(self, route_name: str, prompt: Prompt, inputs: dict,
                 output_schema: type[BaseModel], context: CallContext):
        route = self.routes.get(route_name)
        if route is None:
            raise ModelFailure("MissingRoute")
        messages = [{"role":"system", "content":prompt.template + "\nReturn only JSON matching this schema: " + encode(output_schema.model_json_schema())},
                    {"role":"user", "content":encode(inputs)}]
        call_id = "CALL-" + uuid.uuid4().hex
        for attempt in range(route.max_retries + 1):
            trace_id = self.trace.start({"kind":"model", "run_id":context.run_id,"step_id":context.step_id,
                "chapter_id":context.chapter_id, "input_refs":list(context.input_refs), "output_refs":[],
                "workflow_version":context.workflow_version, "call_id":call_id, "attempt":attempt,
                "route":route_name,"route_config":route.model_dump(),"route_hash":digest(route.model_dump()),
                "provider":route.provider,"model":route.model,"prompt_version":prompt.version,
                "prompt_hash":digest(prompt.model_dump()), "request_hash":digest(messages)})
            started = time.monotonic()
            completion = None
            error = None
            output = None
            try:
                provider = self.providers.get(route.provider)
                if provider is None:
                    raise ModelFailure("MissingConfiguration")
                completion = provider.complete(route, messages)
                if completion.finish_reason == "length":
                    raise ModelFailure("TruncatedOutput", retryable=True)
                if completion.finish_reason != "stop":
                    raise ModelFailure("IncompleteOutput")
                try:
                    output = output_schema.model_validate_json(completion.content)
                except ValidationError:
                    raise ModelFailure("SchemaFailure", retryable=True) from None
            except ModelFailure as exc:
                error = exc
            cost = None
            if (completion is not None and completion.input_tokens is not None and completion.output_tokens is not None
                and route.input_cost_per_million is not None and route.output_cost_per_million is not None):
                cost = (completion.input_tokens * route.input_cost_per_million + completion.output_tokens * route.output_cost_per_million) / 1_000_000
            self.trace.finish(trace_id, status="failed" if error else "success", failure_class=error.failure_class if error else None,
                latency_ms=round((time.monotonic()-started)*1000,3),
                model=completion.model if completion else route.model,
                input_tokens=completion.input_tokens if completion else None,
                output_tokens=completion.output_tokens if completion else None,
                estimated_cost=cost, cost_status="estimated" if cost is not None else "unavailable",
                output_hash=digest(output.model_dump()) if output is not None else None)
            if error is None:
                return output
            if not error.retryable or attempt == route.max_retries:
                raise error
            self.sleep(0.2 * (2 ** attempt))

    def close(self):
        for provider in self.providers.values():
            close = getattr(provider, "close", None)
            if close:
                close()


class ArtifactIntegrityError(ValueError):
    """Persisted artifact no longer matches its identity or content hash."""


class ArtifactStore:
    def __init__(self, kernel):
        self.kernel = kernel

    def get(self, artifact_id: str):
        with self.kernel.writer:
            row = self.kernel.storage.get("artifacts", artifact_id)
            if row is None:
                raise MissingRecord(artifact_id)
            return self._decode(artifact_id, row)

    def get_many(self, artifact_ids: list[str]) -> dict[str, dict]:
        """Read present immutable artifacts in one batch, checking each payload.

        Missing IDs are omitted, as in the storage contract. A caller requiring
        one ID still uses get (or checks membership). No cache survives a call.
        """
        with self.kernel.writer:
            rows = self.kernel.storage.get_many("artifacts", artifact_ids)
            return {artifact_id: self._decode(artifact_id, row) for artifact_id, row in rows.items()}

    @staticmethod
    def _decode(artifact_id: str, row: dict) -> dict:
        try:
            payload = Artifact.model_validate_json(row["payload_json"]).model_dump()
            if (payload["artifact_id"] != artifact_id or
                stable_id("AR-", payload["logical_id"] + "/" + str(payload["version"])) != artifact_id or
                digest(payload["content"]) != payload["content_hash"]):
                raise ArtifactIntegrityError("Artifact integrity check failed")
        except (ValueError, KeyError, TypeError):
            raise ArtifactIntegrityError("Artifact integrity check failed") from None
        return payload

    def save(self, *, logical_id: str, version: int, artifact_type: str, content: dict,
             context: CallContext, prompt: Prompt, route: str, provider: str, model: str,
             route_hash: str = "", input_hash: str = "", creator: str = "semantic-runtime"):
        if version < 1 or not logical_id or not artifact_type:
            raise ValueError("Artifact type, logical ID and positive version required")
        with self.kernel.writer:
            aid = stable_id("AR-", logical_id + "/" + str(version))
            immutable = {"artifact_id":aid,"logical_id":logical_id,"version":version,"artifact_type":artifact_type,
                "content":content,"content_hash":digest(content),"source_refs":list(context.input_refs),
                "run_id":context.run_id,"step_id":context.step_id,"chapter_id":context.chapter_id,
                "workflow_version":context.workflow_version,"prompt_version":prompt.version,
                "prompt_hash":digest(prompt.model_dump()),"route":route,"route_hash":route_hash,
                "provider":provider,"model":model,"creator":creator,"input_hash":input_hash}
            existing = self.kernel.storage.get("artifacts", aid)
            if existing:
                previous = json.loads(existing["payload_json"])
                if {k:v for k,v in previous.items() if k != "created_at"} != immutable:
                    raise ValueError("Artifact version is immutable")
                return previous
            payload = Artifact.model_validate({**immutable,"created_at":now()}).model_dump()
            record = self.kernel._ensure("artifacts", "artifact_id", {"artifact_id":aid,
                "logical_id":logical_id,"version":version,"artifact_type":artifact_type,
                "run_id":context.run_id,"chapter_id":context.chapter_id,"payload_json":encode(payload)})
            persisted = json.loads(record["payload_json"])
            if {k:v for k,v in persisted.items() if k != "created_at"} != immutable:
                raise ValueError("Artifact version is immutable")
            return persisted


class SemanticRuntime:
    """Shared validated execution contract used by downstream domain workflows."""
    def __init__(self, router: ModelRouter, artifacts: ArtifactStore):
        self.router = router
        self.artifacts = artifacts

    def execute(self, *, route: str, prompt: Prompt, inputs: dict,
                input_schema: type[BaseModel], output_schema: type[BaseModel],
                context: CallContext, logical_id: str, version: int, artifact_type: str):
        validated = input_schema.model_validate(inputs)
        aid = stable_id("AR-", logical_id + "/" + str(version))
        route_config = self.router.routes.get(route)
        if route_config is None:
            raise ModelFailure("MissingRoute")
        with self.artifacts.kernel.writer:
            try:
                existing = self.artifacts.get(aid)
            except MissingRecord:
                existing = None
            if existing:
                if (existing["prompt_hash"] != digest(prompt.model_dump()) or
                    existing["input_hash"] != digest(validated.model_dump()) or
                    existing["artifact_type"] != artifact_type or
                    existing["chapter_id"] != context.chapter_id or
                    existing["workflow_version"] != context.workflow_version or
                    existing["source_refs"] != list(context.input_refs) or
                    existing["route"] != route or
                    existing["route_hash"] != digest(route_config.model_dump()) or
                    existing["run_id"] != context.run_id or existing["step_id"] != context.step_id):
                    raise ValueError("Artifact version is immutable; use a new version")
                output_schema.model_validate(existing["content"])
                return existing
            output = self.router.generate(route, prompt, validated.model_dump(), output_schema, context)
            attempts = self.router.trace.list(run_id=context.run_id)
            matching = [t for t in attempts if t["kind"] == "model" and t.get("step_id") == context.step_id and t["status"] == "success"]
            artifact = self.artifacts.save(logical_id=logical_id,version=version,artifact_type=artifact_type,
                content=output.model_dump(),context=context,prompt=prompt,route=route,
                provider=route_config.provider,model=matching[-1]["model"] if matching else route_config.model,route_hash=digest(route_config.model_dump()),
                input_hash=digest(validated.model_dump()))
            # Link the successful attempt to the immutable output after persistence.
            if matching:
                self.router.trace.finish(matching[-1]["trace_id"], output_refs=[artifact["artifact_id"]])
            return artifact
