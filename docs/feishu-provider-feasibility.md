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
| Ambiguous create | Read by stable key; no second POST; unresolved outcome stops | Mock and stateful HTTP verified, including a committed POST with a malformed 2xx reply |
| PATCH / Base v3 | v3 single-record update is PATCH; batch partial update is POST | User CLI PATCH changed only `version`; `domain_id`, `kind`, and `payload` survived. Seven batch partial updates also preserved other fields. Backend app identity remains untested. |
| Batch behavior | Not used for runtime writes | 35 creates / 7 updates succeeded |
| Record history | Not used for artifact versioning | Create + update events visible after propagation delay |
| Limits / conflicts / throughput | No distributed CAS claim; serialized application writes | Two concurrent same-record updates both returned success; an older logical version was the final value. A 50,000-character synthetic Chinese chapter payload round-tripped; absolute size and rate ceilings remain unmeasured. |
| Bot identity | Backend uses app/bot credentials | v3 bot read blocked by missing `base:record:read`; direct v1 list also denied for both CLI identities because the response listed `bitable:app:readonly`, `bitable:app`, `base:record:retrieve` scopes |

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
| User-identity single-record PATCH (2026-09-29) | The registered `+record-upsert --record-id` dry-run showed `PATCH /open-apis/base/v3/bases/{base}/tables/{table}/records/{record}`. On synthetic record `reczz28HLxhpa78F`, a request containing only `{"version":2}` returned `updated=true`. A projected read returned the original `domain_id=probe-partial-20260929-a18f`, `kind=PatchProbe`, `payload=baseline`, and `version=2` at Base rev 10. The row was deleted; a later get listed it in `record_not_found` at rev 11. This verifies partial-update behavior under the CLI user identity, not the backend app. |
| Bot-identity read (2026-09-29) | Denied with Feishu code `99991672`, missing app scope `base:record:read`; no bot write was attempted |
| Same-record concurrent writes (2026-09-29) | A synthetic WorkflowRun row began at logical version 1. Two user-identity `batch_update` commands set versions 2 and 3 concurrently; both returned success. The final read showed version 2 at Base `rev=7`, and history later showed version 3 → 2 at rev 7. Each call took roughly 1.5–1.7 s including CLI overhead. This is one bounded race, not a rate-limit benchmark. |
| Direct `bitable/v1` list (2026-09-29) | The exact read path used by `BaseRepository` was dry-run and then called with `page_size=1` against the approved Base. User identity returned authorization code `99991679`; bot identity returned `99991672`. Both errors listed missing `bitable:app:readonly`, `bitable:app`, `base:record:retrieve`. Neither reached record data, so this does not establish v1 schema compatibility or incompatibility. |
| Chapter-sized text (2026-09-29) | A synthetic ChapterVersion record with 50,000 Chinese prose characters in a JSON text field was created through Base v3 under user identity. The stored payload had 50,032 characters and read back byte-for-byte equal to the submitted payload (SHA-256 `36c1b3ab18ee238f6fe3729fa25f90851e655d2fbd440737ae8a4f0491e7f00c`). This covers the code's current 50,000-character prose cap in this test table; it is not a measured platform ceiling or a production schema test. |

CLI dry-run confirms POST `/open-apis/base/v3/bases/{base}/tables/{table}/records/batch_create`,
POST `.../records/batch_update`, and single-record PATCH as shown above. The
official [v1 update-record documentation](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update.md)
specifies PUT with incremental field semantics; that is the separate endpoint
used by the production adapter. CLI help states a 200-record batch maximum;
we measured only 35, without stress testing or intentionally flooding the tenant.
History visibility is eventually consistent: an immediate empty response does
not prove absence. The same caution motivates fail-closed create reconciliation.

**Still open:** backend-runtime v1 CRUD after the listed access scopes are granted, bot-authenticated v3 CRUD/PATCH after `base:record:read` and the necessary write scopes are granted, absolute
payload limits beyond the tested chapter size, throttling behavior, and runtime v1↔v3 schema
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

The `bitable/v1` probe used the production adapter's
`GET /bitable/v1/apps/{app_token}/tables/{table_id}/records` path, but the CLI's own
OAuth application identities, not backend runtime credentials. The user result
means its OAuth grant lacks a listed access scope; the bot result means the CLI
app has not applied for a listed access scope. The backend's configured app
identity remains unknown because its credentials are absent. Granting the CLI
scopes could unblock a compatibility probe, but would still not certify the
backend app. Until these permissions are available, the stateful HTTP contract
tests remain the only evidence for the runtime v1 mapping.

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

The 2026-09-29 regression review found that a committed POST followed by a
well-formed JSON envelope missing `data.record` previously raised a raw
`KeyError`; a response record missing the requested business key could also
return apparent success. The repository now classifies malformed create
envelopes as uncertain and the provider validates the returned business key
before success. Both paths reconcile by the requested key without another
POST, or stop with `AmbiguousWrite` if the read cannot establish the result.
The stateful HTTP fixture verified one committed row and one POST despite a
malformed success reply. Local offline backend verification: 183 passed,
9 live integration tests deselected, 88.50% coverage (floor 87.82%). This
does not establish behavior of the live Feishu service.

Legacy repository `conditional_update` now checks before PUT and is explicitly
**not atomic**. Hold the single-writer lock; manual edits/other backends are not
covered. Deploy one backend process, not multiple uvicorn workers.

## Live feasibility protocol

Run this only against a dedicated, disposable test Base. The retained
`RuntimeProbe` table above does **not** have the five runtime table schemas
required by this suite. The CLI's bot and user identities also differ from the
backend app: configure and verify the **backend app ID** used by `FeishuClient`,
not just `lark-cli` OAuth access.

1. In the Feishu developer console, grant the backend app the Bitable record
   read, create, update, and delete permissions needed by its official
   `bitable/v1` endpoints. Publish/apply the permission change and give that app
   access to the dedicated Base. The observed v1 list denial named
   `bitable:app:readonly`, `bitable:app`, and `base:record:retrieve` as possible
   read scopes; use the console/API response to confirm the actual grant.
2. Use five separate tables in that Base, with a text business-key field
   named exactly as shown below. These empty tables were created under the
   authorized user identity on 2026-09-29; put their real IDs in the matching
   variables. This suite writes only those business-key fields, but the
   adapter's field names and response shape still need live confirmation.

   | Table | Required text field | Test table ID | Environment variable |
   | --- | --- | --- | --- |
   | PipelineRuns | `pipeline_run_id` | `tblvc86TtHXy2iC7` | `FEISHU_TABLE_ID_PIPELINE_RUNS` |
   | StepRuns | `step_run_id` | `tbl0MbCJRiMaTgGV` | `FEISHU_TABLE_ID_STEP_RUNS` |
   | ChapterVersions | `version_id` | `tbl27O2lmeJFf7M8` | `FEISHU_TABLE_ID_CHAPTER_VERSIONS` |
   | ReviewReports | `review_id` | `tblSVz3EvX4wV8CY` | `FEISHU_TABLE_ID_REVIEW_REPORTS` |
   | ApprovalEvents | `approval_id` | `tbllS5i8YmwiBV5B` | `FEISHU_TABLE_ID_APPROVAL_EVENTS` |

3. Supply `FEISHU_APP_ID` and `FEISHU_APP_SECRET` for that backend app,
   `FEISHU_APP_TOKEN` for the dedicated Base, and the five table IDs through
   the local process environment or a secret manager. Do not commit or paste
   secrets into a PR. `.env.example` is a template; this pytest module reads
   `os.environ` directly and does not load `.env` by itself.
4. From `backend/`, run the **read-only** preflight below with the same
   exported environment. It checks all five mappings and v1 list access using
   the backend's tenant token. It deliberately prints no credentials or row
   data. Stop if any table fails; a successful CLI v3 call is not a substitute.

   ```sh
   python - <<'PY'
   import os
   from app.feishu.client import FeishuClient
   from app.feishu.table_map import TableMapConfig

   names = (
       "pipeline_runs", "step_runs", "chapter_versions",
       "review_reports", "approval_events",
   )
   client = FeishuClient(os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"])
   config = TableMapConfig(os.environ["FEISHU_APP_TOKEN"])
   try:
       for name in names:
           table_id = config.get_table_id(name)
           client.get(
               f"/bitable/v1/apps/{config.app_token}/tables/{table_id}/records",
               params={"page_size": "1"},
           )
           print(f"{name}: v1 list OK")
   finally:
       client._http.close()
   PY
   ```

5. Only after the preflight succeeds, opt into the write/delete probe:
   `FEISHU_FEASIBILITY_LIVE=1 pytest tests/test_storage_live.py -m integration -v`.
   It creates a unique `probe-...` business ID in each table, checks replay,
   get and update, then deletes the row on normal completion. If a create
   times out or a test fails before cleanup, inspect those IDs in the test
   Base before retrying; an uncertain POST may have left a record.

Record the timestamp, backend app identity (ID only), tenant/Base capability,
five per-table outcomes and latency, and any leftover probe IDs in this report.
Never point the suite at production tables. The gated suite measures domain
CRUD/replay on representative runtime tables.
The suite does not cover the separately observed user-identity PATCH, history,
batch and chapter-size probes. Absolute payload ceilings, throttling and
cross-client conflicts need bounded follow-up measurements; none are silently
marked passed by the CRUD suite.

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
