"""Deterministic single-scheduler/single-writer runtime for NovelOps v0.2."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.pipeline.engine import _validate_step_defs
from app.pipeline.models import StepDef
from app.storage import AmbiguousWrite, MissingRecord, StorageProvider


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:32]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TransitionConflict(ValueError):
    pass


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
        self._stop = threading.Event()
        self._thread = None
        self._process_lock = None
        self.last_error = None
        self.last_tick = None

    def register(self, name: str, handler: Callable):
        with self.writer:
            if self.running:
                raise RuntimeError("Register handlers before startup")
            self.handlers[name] = handler

    def _ensure(self, collection, key, data):
        return self.storage.ensure(collection, data,
            allow_create=self.journal.begin(collection, data[key]))

    def _transition(self, collection, domain_id, status, **fields):
        row = self.storage.get(collection, domain_id)
        if row is None:
            raise MissingRecord(domain_id)
        transitions = RUN_TRANSITIONS if collection == "pipeline_runs" else STEP_TRANSITIONS
        if status != row["status"] and status not in transitions.get(row["status"], set()):
            raise TransitionConflict(f"Invalid transition {row['status']} -> {status}")
        return self.storage.update(collection, domain_id, {**fields, "status": status})

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
        return [s for s in steps if s["status"] == "pending" and
                set(filter(None, s.get("depends_on", "").split(","))) <= successful]

    def _refresh_parent(self, run_id):
        run = self.get(run_id)
        if run["status"] in {"completed", "failed", "cancelled", "blocked", "creating"}:
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

    def tick(self):
        with self.writer:
            self.last_tick = now()
            for run in self.storage.list("pipeline_runs"):
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
                self._transition("pipeline_runs", run_id, "running", updated_at=now())
                self._transition("step_runs", sid, "running", started_at=now())
                try:
                    result = self.handlers[step["handler"]]({**step, "input": json.loads(step["input_json"])}) or {}
                except AmbiguousWrite:
                    self._transition("step_runs", sid, "blocked", error_message="AmbiguousWrite: reconciliation required")
                except Exception as exc:
                    retries = step.get("retry_count", 0)
                    self._transition("step_runs", sid, "pending" if retries < self.max_retries else "failed",
                        retry_count=retries + 1, error_message=type(exc).__name__ + ": handler failed")
                else:
                    # Completion persistence is outside handler retry: do not rerun a
                    # successful external effect because its status update timed out.
                    self._transition("step_runs", sid,
                        "awaiting_approval" if step.get("requires_approval") else "success",
                        output_json=encode(result), output_version=step.get("output_version", 0) + 1,
                        finished_at=now(), error_message="")
                self._refresh_parent(run_id)
                return

    def decide(self, step_id, action, expected_version, operator):
        with self.writer:
            if action not in {"approve", "reject"}:
                raise ValueError("Unsupported decision")
            step = self.storage.get("step_runs", step_id)
            if step is None:
                raise MissingRecord(step_id)
            if step.get("output_version") != expected_version:
                raise TransitionConflict("Stale output version")
            approval_id = stable_id("AP-", step_id + "/" + str(expected_version))
            previous = self.storage.get("approval_events", approval_id)
            if previous and previous["action"] != action:
                raise TransitionConflict("This version already has a different decision")
            target = "success" if action == "approve" else "failed"
            if previous and step["status"] == target:
                return step
            if step["status"] != "awaiting_approval":
                raise TransitionConflict("Step is not awaiting approval")
            self._ensure("approval_events", "approval_id", {"approval_id": approval_id,
                "target_type": "step_run", "target_id": step_id, "target_version": expected_version,
                "action": action, "operator": operator, "created_at": now()})
            result = self._transition("step_runs", step_id, target)
            self._refresh_parent(step["pipeline_run_id"])
            return result

    def cancel(self, run_id):
        with self.writer:
            run = self.get(run_id)
            if run["status"] == "cancelled":
                return run
            self._transition("pipeline_runs", run_id, "cancelled", updated_at=now())
            for step in run["steps"]:
                if "cancelled" in STEP_TRANSITIONS.get(step["status"], set()):
                    self._transition("step_runs", step["step_run_id"], "cancelled")
            return self.get(run_id)

    def recover(self):
        with self.writer:
            for run in self.storage.list("pipeline_runs"):
                run_id = run["pipeline_run_id"]
                if run["status"] == "creating":
                    try:
                        self._finish_creation(run)
                    except Exception as exc:
                        self._transition("pipeline_runs", run_id, "blocked", error_message=type(exc).__name__)
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
                            self.decide(sid, decision["action"], step["output_version"], decision["operator"])
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
        with self.writer:
            runs = self.storage.list("pipeline_runs")
            steps = self.storage.list("step_runs")
            return {"worker_status": "running" if self.running else "stopped",
                "feishu_status": "connected", "last_error": self.last_error, "last_tick": self.last_tick,
                "active_pipeline_runs": sum(r["status"] in {"pending", "running", "creating", "awaiting_approval"} for r in runs),
                "pending_steps": sum(s["status"] == "pending" for s in steps),
                "failed_steps": sum(s["status"] in {"failed", "blocked"} for s in steps)}
