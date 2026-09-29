# Feishu provider feasibility — ZEN-105 / #21

## Decision and evidence (2026-09-27)

Retain official `bitable/v1` OpenAPI behind `StorageProvider`. Do not claim
Base product v3 alone implies endpoint compatibility. The installed CLI subsequently
confirmed and successfully called `/base/v3` endpoints; see live evidence below. The official
[create](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create),
[update](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update)
and [list](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/list)
documentation entry points were accessible; their dynamic bodies were not
readable through the documentation fetcher. No undocumented endpoint was selected.

| Capability | Implementation / evidence | Live measurement |
| --- | --- | --- |
| CRUD | Official v1 GET/POST/PUT/DELETE; stateful HTTP contract tests | v3 create/read/update/delete verified through user CLI; backend v1/delete not live tested |
| Domain identity | Provider resolves business keys, rejects duplicates/missing mutations | Mock verified |
| Pagination | v1 token pagination guarded; v3 CLI uses offset | v3 pages 10 + 25 = 35, final has_more=false |
| Ambiguous create | Read by stable key; no second POST; unresolved outcome stops | Mock verified |
| PATCH / Base v3 | v3 batch partial update is POST, not PATCH | 7 partial updates preserved other fields; literal HTTP PATCH remains unverified |
| Batch behavior | Not used for runtime writes | 35 creates / 7 updates succeeded |
| Record history | Not used for artifact versioning | Create + update events visible after propagation delay |
| Limits / conflicts / throughput | No distributed CAS claim; serialized application writes | Two concurrent same-record updates both returned success; an older logical version was the final value. Rate and payload ceilings remain unmeasured. |
| Bot identity | Backend uses app/bot credentials | Bot read blocked by missing `base:record:read` scope; user identity succeeds |

Environment inspection found no backend FEISHU_APP_ID, FEISHU_APP_SECRET or
FEISHU_APP_TOKEN. However, `lark-cli 1.0.96` has working bot and user identities outside the
sandbox. No Feishu MCP is exposed. After explicit user authorization, an isolated
[test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph)
was created and retained. These CLI measurements do not certify the backend's
bot-authenticated v1 production configuration.

## Live v3 evidence

All records are synthetic, in `RuntimeProbe` (`tbljg9eBkvui8zuP`). Field schema:
domain_id/kind/payload text, version number. Seven representative payload kinds:
WorkflowRun, StepRun, Artifact, StoryState, ChapterVersion, Review, Approval.

| Probe | Observed result |
| --- | --- |
| Batch create 35 | Success, 35 distinct returned record IDs; 3.242 s including CLI overhead |
| Batch update 7 | Success, version 1 → 2; 3.226 s including CLI overhead |
| Projection + pagination | First 10 records (has_more=true, next_offset=10); then 25 (has_more=false) |
| JSON text payload | 16,449-character payload round-tripped; this is a tested size, not a platform ceiling |
| History | First immediate query returned []; later query returned create rev=1 and update rev=2, with before=1/after=2 |
| Identity | Stable domain_id values `probe-00`…`probe-34` differ from returned rec IDs |
| Partial update | Submitted only version; original payload/domain_id/kind remained present |
| User-identity create/delete (2026-09-29) | Created synthetic `RuntimeProbe` record `reczz28H19Qjc3bi`, deleted it with `--yes`, and confirmed a subsequent read returned Record not found |
| Bot-identity read (2026-09-29) | Denied with Feishu code `99991672`, missing app scope `base:record:read`; no bot write was attempted |
| Same-record concurrent writes (2026-09-29) | A synthetic WorkflowRun row began at logical version 1. Two user-identity `batch_update` commands set versions 2 and 3 concurrently; both returned success. The final read showed version 2 at Base `rev=7`, and history later showed version 3 → 2 at rev 7. Each call took roughly 1.5–1.7 s including CLI overhead. This is one bounded race, not a rate-limit benchmark. |

CLI dry-run confirms POST `/open-apis/base/v3/bases/{base}/tables/{table}/records/batch_create`
and POST `.../records/batch_update`. CLI help states a 200-record batch maximum;
we measured only 35, without stress testing or intentionally flooding the tenant.
History visibility is eventually consistent: an immediate empty response does
not prove absence. The same caution motivates fail-closed create reconciliation.

**Still open:** actual HTTP PATCH, backend-runtime v1 delete, bot-authenticated v3 access after the missing scope is granted, upper
payload limits, throttling behavior, and runtime v1↔v3 schema
compatibility. Unknown outcomes/rate errors are simulated in code, not induced
on the live service. Keep this PR in draft until the remaining feasibility gates
are resolved or explicitly deferred. Do not introduce PostgreSQL on this evidence.

The concurrent probe demonstrates that the numeric `version` field is not a
server-side compare-and-swap precondition. Both writes were accepted despite
starting from the same observed logical version; the final record held the
older logical value. Base history visibility was delayed and an immediate
history response did not contain every observed revision. The retained test
row uses domain key `probe-conflict-20260929` in the approved synthetic Base.
Keep application writes serialized and reject stale domain transitions before
the provider update; do not infer conflict safety from either successful response.

The delete probe applies only to a disposable synthetic record under the user's
CLI identity. The bot-scope denial is an observed application permission gap, not
evidence that Base v3 lacks a record-read endpoint. The Feishu app must receive
`base:record:read` before a bot-authenticated runtime probe can continue.
A repeat bot probe on 2026-09-29 returned the same code and missing scope.

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
