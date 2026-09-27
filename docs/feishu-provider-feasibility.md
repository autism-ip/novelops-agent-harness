# Feishu provider feasibility — ZEN-105 / #21

## Decision and evidence (2026-09-27)

Retain official `bitable/v1` OpenAPI behind `StorageProvider`. Do not claim
Base product v3 implies an available `/base/v3` record API. The official
[create](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create),
[update](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update)
and [list](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/list)
documentation entry points were accessible; their dynamic bodies were not
readable through the documentation fetcher. No undocumented endpoint was selected.

| Capability | Implementation / evidence | Live measurement |
| --- | --- | --- |
| CRUD | Official v1 GET/POST/PUT/DELETE; stateful HTTP contract tests | Pending credentials |
| Domain identity | Provider resolves business keys, rejects duplicates/missing mutations | Mock verified |
| Pagination | Existing pagination; rejects missing/repeated continuation token | Mock verified |
| Ambiguous create | Read by stable key; no second POST; unresolved outcome stops | Mock verified |
| PATCH / Base v3 | Unverified; not enabled | Pending official contract and tenant probe |
| Batch behavior | Not used for runtime writes | Pending isolated workload probe |
| Record history | Not used for artifact versioning | Pending capability probe |
| Limits / conflicts / throughput | No distributed CAS claim; serialized application writes | Pending isolated workload probe |

Environment inspection found no FEISHU_APP_ID, FEISHU_APP_SECRET or
FEISHU_APP_TOKEN. There are **no measured production performance or Base v3
results** in this PR. The live gate must remain open; mocks do not certify it.

## Contract

`get/list/ensure/update/delete` accept collection names and business IDs.
`record_id` never leaves the provider. `ensure` is replay-safe for an existing
business key. Missing mutations raise `MissingRecord`; duplicate IDs raise
`DuplicateKey`; IDs cannot be changed by update. Mutable field conflicts are
owned by the workflow's version/transition checks under one writer.

Transport failures, invalid responses and 5xx after POST are ambiguous. Read
reconciliation may recover the existing record. Otherwise `AmbiguousWrite`
stops execution. In-process retries cannot issue another POST. Following a
restart, callers must use `allow_create=False` for a previously attempted create
until absence is established operationally. A new process must not assume its
empty memory proves that an earlier POST did not happen. #20 owns the persistent
creation intent and recovery policy using this contract.

Legacy repository `conditional_update` now checks before PUT and is explicitly
**not atomic**. Hold the single-writer lock; manual edits/other backends are not
covered. Deploy one backend process, not multiple uvicorn workers.

## Live feasibility protocol

Use a dedicated test Base and explicit `FEISHU_FEASIBILITY_LIVE=1`; run
`pytest tests/test_storage_live.py -m integration -v`. Never point this at a
production table. Record tenant capabilities and timestamps alongside results.
The gated suite measures domain CRUD/replay on representative runtime tables.
PATCH, history, payload ceilings, batches, throttling and cross-client conflicts
require confirmed official endpoints and a bounded follow-up probe; those are
not silently marked passed by the CRUD suite.

## Additive rollout and rollback

1. Export existing table field definitions and record counts; preserve business
   IDs and all `AgentTeamSnapshots` / legacy chapter references.
2. Add new tables/fields for Artifact, trace, canonical StoryState and context
   snapshots as their owning issues define them. JSON structures use text fields;
   explicit versions use numeric fields. Do not rename/drop legacy fields.
3. Configure `FEISHU_TABLE_ID_*` and validate duplicate business keys before
   enabling runtime writes. Resolve duplicates manually; never choose first.
4. Backfill deterministic business keys in small batches with a reviewed mapping;
   compare counts and hashes, retaining exports and prior IDs.
5. Enable one writer. Roll back by stopping it and deploying the prior code;
   retain new fields/records for forward recovery. Do not delete artifact history.

No second primary database is introduced. Existing legacy engine/worker callers
are replaced by the provider-based runtime in #20; they are not evidence of
v0.2 production composition by themselves.
