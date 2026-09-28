"""Deterministic single-scheduler/single-writer runtime for NovelOps v0.2."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.pipeline.engine import _validate_step_defs
from app.pipeline.models import StepDef
from app.storage import AmbiguousWrite, MissingRecord, StorageProvider


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def stable_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:32]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TransitionConflict(ValueError):
    pass


class InvalidHandlerOutput(ValueError):
    """Execution returned, but its output cannot be safely persisted."""


class PermanentStepFailure(Exception):
    """Handler exhausted its own retry policy; the scheduler must not retry."""


@dataclass(frozen=True)
class StepResult:
    payload: dict
    requires_approval: bool = False


class CreationJournal:
    """Fsynced POST-intent markers, not a database or copy of business records.

    Keep this directory across restarts. Losing it loses proof of attempted
    creates. A marker is written *before* POST; uncertain absence fails closed.
    """
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def begin(self, collection: str, domain_id: str) -> bool:
        path = self.directory / stable_id("intent-", collection + "/" + domain_id)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as output:
            output.write(collection + "/" + domain_id)
            output.flush()
            os.fsync(output.fileno())
        directory_fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True


STEP_TRANSITIONS = {
    "pending": {"running", "cancelled", "blocked"},
    "running": {"pending", "success", "awaiting_approval", "failed", "blocked", "cancelled"},
    "awaiting_approval": {"success", "failed", "cancelled", "blocked"},
    "success": set(), "failed": set(), "blocked": set(), "cancelled": set(),
}
RUN_TRANSITIONS = {
    "creating": {"pending", "blocked", "cancelled"},
    "pending": {"running", "blocked", "failed", "cancelled", "completed"},
    "running": {"awaiting_approval", "completed", "failed", "blocked", "cancelled"},
    "awaiting_approval": {"running", "completed", "failed", "blocked", "cancelled"},
    "completed": set(), "failed": set(), "blocked": set(), "cancelled": set(),
}


class HarnessKernel:
    def __init__(self, storage: StorageProvider, *, journal_dir: Path,
                 poll_interval: float = 1, max_retries: int = 3):
        if poll_interval <= 0 or max_retries < 0:
            raise ValueError("Invalid scheduler limits")
        self.storage = storage
        self.writer = threading.RLock()
        self.journal = CreationJournal(journal_dir)
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.handlers: dict[str, Callable] = {"noop": lambda step: {"output_refs": []}}
        self.projectors: dict[str, Callable] = {}
        self.approval_guards: dict[str, Callable] = {}
        self._stop = threading.Event()
        self._thread = None
        self._process_lock = None
        self.last_error = None
        self.last_tick = None
        self.telemetry = None
        self._metrics_lock = threading.Lock()
        self._observed = {"pipeline_runs": {}, "step_runs": {}}
        self._counts = {"active_pipeline_runs": 0, "pending_steps": 0, "failed_steps": 0}

    def _observe(self, collection, row):
        """Disposable status counters; rebuilt from Feishu on startup."""
        if collection not in self._observed:
            return
        key = "pipeline_run_id" if collection == "pipeline_runs" else "step_run_id"
        groups = ({"active_pipeline_runs": {"creating", "pending", "running", "awaiting_approval"}}
                  if collection == "pipeline_runs" else
                  {"pending_steps": {"pending"}, "failed_steps": {"failed", "blocked"}})
        with self._metrics_lock:
            old = self._observed[collection].get(row[key])
            for metric, statuses in groups.items():
                self._counts[metric] += int(row["status"] in statuses) - int(old in statuses)
            self._observed[collection][row[key]] = row["status"]

    def register(self, name: str, handler: Callable):
        with self.writer:
            if self.running:
                raise RuntimeError("Register handlers before startup")
            self.handlers[name] = handler

    def _ensure(self, collection, key, data):
        row = self.storage.ensure(collection, data,
            allow_create=self.journal.begin(collection, data[key]))
        self._observe(collection, row)
        return row

    def register_projector(self, workflow_type, projector):
        with self.writer:
            if self.running:
                raise RuntimeError("Register projectors before startup")
            self.projectors[workflow_type] = projector

    def register_approval_guard(self, handler, guard):
        with self.writer:
            if self.running:
                raise RuntimeError("Register guards before startup")
            self.approval_guards[handler] = guard

    def _project(self, run_id):
        run = self.get(run_id)
        projector = self.projectors.get(run["pipeline_type"])
        if projector:
            projector(run)

    def _transition(self, collection, domain_id, status, **fields):
        row = self.storage.get(collection, domain_id)
        if row is None:
            raise MissingRecord(domain_id)
        transitions = RUN_TRANSITIONS if collection == "pipeline_runs" else STEP_TRANSITIONS
        if status != row["status"] and status not in transitions.get(row["status"], set()):
            raise TransitionConflict(f"Invalid transition {row['status']} -> {status}")
        result = self.storage.update(collection, domain_id, {**fields, "status": status})
        self._observe(collection, result)
        return result

    def create(self, request_key: str, workflow_type: str, steps: list[dict],
               *, book_id: str = "", source_hotspot_id: str = "") -> dict:
        with self.writer:
            if not request_key.strip() or not steps:
                raise ValueError("request_key and steps are required")
            normalized = []
            for step in steps:
                if step.get("handler") not in self.handlers:
                    raise ValueError("Unregistered step handler")
                kind = step.get("kind", "service")
                if kind not in {"service", "tool", "agent"}:
                    raise ValueError("Invalid step kind")
                normalized.append({"step_key": step["step_key"], "handler": step["handler"],
                    "kind": kind, "depends_on": step.get("depends_on", []),
                    "requires_approval": step.get("requires_approval", False),
                    "input": step.get("input", {})})
            _validate_step_defs([StepDef(s["step_key"], "", tuple(s["depends_on"])) for s in normalized])
            definition = encode({"workflow_type": workflow_type, "steps": normalized,
                                 "book_id": book_id, "source_hotspot_id": source_hotspot_id})
            run_id = stable_id("PR-", request_key)
            run = self._ensure("pipeline_runs", "pipeline_run_id", {
                "pipeline_run_id": run_id, "pipeline_type": workflow_type,
                "status": "creating", "definition_json": definition,
                "book_id": book_id, "source_hotspot_id": source_hotspot_id,
                "created_at": now(), "updated_at": now()})
            if run.get("definition_json") != definition:
                raise TransitionConflict("Request key already used with different inputs")
            if run["status"] == "creating":
                self._finish_creation(run)
            return self.storage.get("pipeline_runs", run_id)

    def _finish_creation(self, run):
        definition = json.loads(run["definition_json"])
        run_id = run["pipeline_run_id"]
        for spec in definition["steps"]:
            sid = stable_id("SR-", run_id + "/" + spec["step_key"])
            self._ensure("step_runs", "step_run_id", {
                "step_run_id": sid, "pipeline_run_id": run_id,
                "step_key": spec["step_key"], "handler": spec["handler"], "kind": spec["kind"],
                "depends_on": ",".join(spec["depends_on"]), "status": "pending",
                "requires_approval": spec["requires_approval"], "input_json": encode(spec["input"]),
                "retry_count": 0, "output_version": 0})
        self._transition("pipeline_runs", run_id, "pending", updated_at=now())

    def get(self, run_id):
        with self.writer:
            run = self.storage.get("pipeline_runs", run_id)
            if run is None:
                raise MissingRecord(run_id)
            return {**run, "steps": self.storage.list("step_runs", pipeline_run_id=run_id)}

    def list(self):
        with self.writer:
            return self.storage.list("pipeline_runs")

    def runnable(self, steps):
        """The only runnable-step selection path used by scheduler/recovery."""
        successful = {s["step_key"] for s in steps if s["status"] == "success"}
        return sorted([s for s in steps if s["status"] == "pending" and
                set(filter(None, s.get("depends_on", "").split(","))) <= successful],
                key=lambda s: (s["step_key"], s["step_run_id"]))

    def _cancel_siblings(self, steps):
        for step in steps:
            if "cancelled" in STEP_TRANSITIONS.get(step["status"], set()):
                self._transition("step_runs", step["step_run_id"], "cancelled")

    def _refresh_parent(self, run_id):
        run = self.get(run_id)
        if run["status"] in {"failed", "cancelled", "blocked"}:
            self._cancel_siblings(run["steps"])
            self._project(run_id)
            return
        if run["status"] in {"completed", "failed", "cancelled", "blocked", "creating"}:
            if run["status"] == "completed":
                self._project(run_id)
            return
        statuses = [s["status"] for s in run["steps"]]
        if "blocked" in statuses:
            status = "blocked"
        elif "failed" in statuses:
            status = "failed"
        elif statuses and all(s == "success" for s in statuses):
            status = "completed"
        elif self.runnable(run["steps"]):
            status = "running"
        elif "awaiting_approval" in statuses:
            status = "awaiting_approval"
        else:
            status = "running"
        self._transition("pipeline_runs", run_id, status, updated_at=now())
        if status in {"failed", "blocked"}:
            self._cancel_siblings(run["steps"])
        self._project(run_id)

    def tick(self):
        with self.writer:
            self.last_tick = now()
            for run in sorted(self.storage.list("pipeline_runs"), key=lambda r: r["pipeline_run_id"]):
                if run["status"] not in {"pending", "running", "awaiting_approval"}:
                    continue
                run_id = run["pipeline_run_id"]
                steps = self.storage.list("step_runs", pipeline_run_id=run_id)
                runnable = self.runnable(steps)
                if not runnable:
                    self._refresh_parent(run_id)
                    continue
                step = runnable[0]
                sid = step["step_run_id"]
                if step["handler"] not in self.handlers:
                    self._transition("step_runs", sid, "blocked", error_message="Unavailable handler: reconciliation required")
                    self._refresh_parent(run_id)
                    return
                self._transition("pipeline_runs", run_id, "running", updated_at=now())
                self._transition("step_runs", sid, "running", started_at=now())
                trace_id = None
                started = time.monotonic()
                if self.telemetry:
                    trace_id = self.telemetry.start({"kind": step.get("kind", "service"),
                        "run_id": run_id, "step_id": sid, "handler": step["handler"],
                        "chapter_id": json.loads(step["input_json"]).get("chapter_id", ""),
                        "attempt": step.get("retry_count", 0), "correlation_id": sid})
                failure_class = None
                try:
                    result = self.handlers[step["handler"]]({**step, "input": json.loads(step["input_json"])})
                    requires_approval = bool(step.get("requires_approval"))
                    if isinstance(result, StepResult):
                        if not isinstance(result.payload, dict) or type(result.requires_approval) is not bool:
                            raise InvalidHandlerOutput()
                        requires_approval = requires_approval or result.requires_approval
                        result = result.payload
                    if result is None:
                        result = {}
                    try:
                        output_json = encode(result)
                    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                        raise InvalidHandlerOutput() from exc
                except InvalidHandlerOutput:
                    failure_class = "InvalidHandlerOutput"
                    self._transition("step_runs", sid, "blocked", error_message="InvalidHandlerOutput: reconciliation required")
                except AmbiguousWrite:
                    failure_class = "AmbiguousWrite"
                    self._transition("step_runs", sid, "blocked", error_message="AmbiguousWrite: reconciliation required")
                except PermanentStepFailure as exc:
                    failure_class = type(exc.__cause__ or exc).__name__
                    self._transition("step_runs", sid, "failed", error_message=failure_class + ": handler exhausted retries")
                except Exception as exc:
                    failure_class = type(exc).__name__
                    retries = step.get("retry_count", 0)
                    self._transition("step_runs", sid, "pending" if retries < self.max_retries else "failed",
                        retry_count=retries + 1, error_message=type(exc).__name__ + ": handler failed")
                else:
                    # Completion persistence is outside handler retry: do not rerun a
                    # successful external effect because its status update timed out.
                    self._transition("step_runs", sid,
                        "awaiting_approval" if requires_approval else "success",
                        requires_approval=requires_approval,
                        output_json=output_json, output_version=step.get("output_version", 0) + 1,
                        finished_at=now(), error_message="")
                if trace_id:
                    self.telemetry.finish(trace_id, status="failed" if failure_class else "success",
                        failure_class=failure_class, latency_ms=round((time.monotonic()-started)*1000,3),
                        output_refs=result.get("output_refs", []) if not failure_class and isinstance(result, dict) else [])
                self._refresh_parent(run_id)
                return

    def decide(self, step_id, action, expected_version, operator, *, reason="", choice_id=""):
        with self.writer:
            if action not in {"approve", "reject", "revise"}:
                raise ValueError("Unsupported decision")
            reason = reason.strip()
            if action == "revise" and not reason:
                raise ValueError("Revision reason is required")
            step = self.storage.get("step_runs", step_id)
            if step is None:
                raise MissingRecord(step_id)
            if step.get("output_version") != expected_version:
                raise TransitionConflict("Stale output version")
            approval_id = stable_id("AP-", step_id + "/" + str(expected_version))
            previous = self.storage.get("approval_events", approval_id)
            if previous and (previous["action"] != action or previous.get("reason", "") != reason or
                             previous.get("choice_id", "") != choice_id):
                raise TransitionConflict("This version already has a different decision")
            target = "success" if action == "approve" else "failed"
            if previous and step["status"] == target:
                self._refresh_parent(step["pipeline_run_id"])
                return step
            parent = self.storage.get("pipeline_runs", step["pipeline_run_id"])
            if parent is None or parent["status"] in {"completed", "failed", "blocked", "cancelled"}:
                raise TransitionConflict("Workflow is terminal")
            if step["status"] != "awaiting_approval":
                raise TransitionConflict("Step is not awaiting approval")
            # A persisted decision is already committed; recovery must finish it
            # even if the domain has changed since it was accepted.
            guard = self.approval_guards.get(step["handler"])
            if guard and not previous:
                if choice_id:
                    guard(step, action, choice_id)
                else:
                    guard(step, action)
            self._ensure("approval_events", "approval_id", {"approval_id": approval_id,
                "target_type": "step_run", "target_id": step_id, "target_version": expected_version,
                "action": action, "operator": operator, "reason": reason, "choice_id": choice_id,
                "created_at": now()})
            result = self._transition("step_runs", step_id, target)
            self._refresh_parent(step["pipeline_run_id"])
            return result

    def cancel(self, run_id):
        with self.writer:
            run = self.get(run_id)
            if run["status"] == "cancelled":
                self._refresh_parent(run_id)
                return run
            self._transition("pipeline_runs", run_id, "cancelled", updated_at=now())
            for step in run["steps"]:
                if "cancelled" in STEP_TRANSITIONS.get(step["status"], set()):
                    self._transition("step_runs", step["step_run_id"], "cancelled")
            self._project(run_id)
            return self.get(run_id)

    def recover(self):
        with self.writer:
            with self._metrics_lock:
                self._observed = {"pipeline_runs": {}, "step_runs": {}}
                self._counts = {"active_pipeline_runs": 0, "pending_steps": 0, "failed_steps": 0}
            for collection in self._observed:
                for row in self.storage.list(collection):
                    self._observe(collection, row)
            for run in self.storage.list("pipeline_runs"):
                run_id = run["pipeline_run_id"]
                if run["status"] in {"completed", "failed", "blocked", "cancelled"}:
                    self._refresh_parent(run_id)
                    continue
                if run["status"] == "creating":
                    try:
                        self._finish_creation(run)
                    except Exception as exc:
                        self._transition("pipeline_runs", run_id, "blocked", error_message=type(exc).__name__)
                        self._refresh_parent(run_id)
                    continue
                if run["status"] not in {"pending", "running", "awaiting_approval"}:
                    continue
                for step in self.storage.list("step_runs", pipeline_run_id=run_id):
                    sid = step["step_run_id"]
                    if step["status"] == "running":
                        retries = step.get("retry_count", 0)
                        # Registered handlers MUST reconcile external effects by the
                        # stable step ID; exhausted restarts stop explicitly.
                        self._transition("step_runs", sid, "pending" if retries < self.max_retries else "failed",
                            retry_count=retries + 1, error_message="Interrupted: recovered after restart")
                    elif step["status"] == "awaiting_approval":
                        aid = stable_id("AP-", sid + "/" + str(step["output_version"]))
                        decision = self.storage.get("approval_events", aid)
                        if decision:
                            self.decide(sid, decision["action"], step["output_version"], decision["operator"],
                                        reason=decision.get("reason", ""), choice_id=decision.get("choice_id", ""))
                self._refresh_parent(run_id)

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        lockfile = open(self.journal.directory / "writer.lock", "a")
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._process_lock = lockfile
            self.recover()
        except Exception:
            lockfile.close()
            self._process_lock = None
            raise
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="novelops-scheduler", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
                self.last_error = None
            except Exception as exc:
                # Stop on storage/completion ambiguity. Never keep executing
                # dependent work while persistence outcomes are uncertain.
                self.last_error = type(exc).__name__
                self._stop.set()
                break
            self._stop.wait(self.poll_interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=35)
            if self._thread.is_alive():
                raise RuntimeError("Scheduler shutdown timed out; retain writer lock")
        if self._process_lock:
            self._process_lock.close()
            self._process_lock = None

    def status(self):
        with self._metrics_lock:
            return {"worker_status": "running" if self.running else "stopped",
                "feishu_status": "unreachable" if self.last_error else "connected",
                "last_error": self.last_error, "last_tick": self.last_tick, **self._counts}
