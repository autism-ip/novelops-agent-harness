"""Provider-neutral domain storage; Feishu record identities stay in the adapter.

The application must serialize machine writes. This interface does not promise
transactions, unique constraints, or distributed compare-and-swap.
"""
from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.feishu.client import FeishuAPIError
from app.feishu.repositories.base import BaseRepository


class StorageError(RuntimeError):
    pass


class MissingRecord(StorageError):
    pass


class DuplicateKey(StorageError):
    pass


class AmbiguousWrite(StorageError):
    """Stop execution and reconcile; this error must not enter blind retry."""


class StorageProvider(Protocol):
    def get(self, collection: str, domain_id: str) -> dict | None: ...
    def list(self, collection: str, **conditions: str | int) -> list[dict]: ...
    def ensure(self, collection: str, data: dict, *, allow_create: bool = True) -> dict: ...
    def update(self, collection: str, domain_id: str, fields: dict) -> dict: ...
    def delete(self, collection: str, domain_id: str) -> None: ...


class FeishuStorageProvider:
    """A single-process writer boundary over official Feishu OpenAPI repos.

    Recovery callers use ``allow_create=False`` when a prior process might have
    sent a POST. Absence from a read is not proof a timed-out create failed.
    Unknown outcomes stop rather than risk duplicates. There is no local SSOT.
    """

    capabilities = {"api": "bitable/v1", "atomic_cas": False,
                    "transactions": False, "record_history": "unverified",
                    "base_v3": "unverified", "patch": "unverified"}

    def __init__(self, repositories: dict[str, BaseRepository], keys: dict[str, str]):
        self._repos = repositories
        self._keys = keys
        self._lock = RLock()
        self._uncertain: set[tuple[str, str]] = set()

    @staticmethod
    def _public(record: dict) -> dict:
        return {k: v for k, v in record.items() if k != "record_id"}

    def _resolve(self, collection: str, domain_id: str) -> dict | None:
        if not domain_id:
            raise ValueError("A non-empty domain ID is required")
        repo = self._repos[collection]
        matches = repo.list(filter_expr=repo._field_filter(**{self._keys[collection]: domain_id}))
        if len(matches) > 1:
            raise DuplicateKey(f"Duplicate business key in {collection}")
        return matches[0] if matches else None

    def get(self, collection: str, domain_id: str) -> dict | None:
        with self._lock:
            row = self._resolve(collection, domain_id)
            return self._public(row) if row else None

    def list(self, collection: str, **conditions: str | int) -> list[dict]:
        with self._lock:
            repo = self._repos[collection]
            return [self._public(r) for r in repo.list(
                filter_expr=repo._field_filter(**conditions) if conditions else None)]

    def ensure(self, collection: str, data: dict, *, allow_create: bool = True) -> dict:
        with self._lock:
            domain_id = data[self._keys[collection]]
            key = (collection, domain_id)
            existing = self.get(collection, domain_id)
            if existing is not None:
                self._uncertain.discard(key)
                return existing
            if not allow_create or key in self._uncertain:
                raise AmbiguousWrite(f"Reconciliation required for {collection}/{domain_id}")
            try:
                return self._public(self._repos[collection].create(data))
            except FeishuAPIError as exc:
                # Transport, malformed responses and HTTP 5xx have unknown outcomes.
                if exc.code != 0 and not 500 <= exc.code <= 599:
                    raise
                self._uncertain.add(key)
                try:
                    existing = self.get(collection, domain_id)
                except Exception as read_exc:
                    raise AmbiguousWrite(f"Reconciliation unavailable for {collection}/{domain_id}") from read_exc
                if existing is not None:
                    self._uncertain.discard(key)
                    return existing
                raise AmbiguousWrite(f"Reconciliation required for {collection}/{domain_id}") from exc

    def update(self, collection: str, domain_id: str, fields: dict) -> dict:
        with self._lock:
            key = self._keys[collection]
            if key in fields and fields[key] != domain_id:
                raise ValueError("Domain identity is immutable")
            row = self._resolve(collection, domain_id)
            if row is None:
                raise MissingRecord(f"Missing {collection}/{domain_id}")
            return self._public(self._repos[collection].update(row["record_id"], fields))

    def delete(self, collection: str, domain_id: str) -> None:
        with self._lock:
            row = self._resolve(collection, domain_id)
            if row is None:
                raise MissingRecord(f"Missing {collection}/{domain_id}")
            self._repos[collection].delete(row["record_id"])
