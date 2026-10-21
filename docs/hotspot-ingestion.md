# Hotspot ingestion — ZEN-33

The registered `hotspot_ingestion_v1` workflow has two deterministic steps:

1. `hotspots.fetch` calls the existing `OpenCLIRunner` and `DouyinHotspotAdapter`, validates public-source records, deduplicates the batch and saves a hashed snapshot in the fetch StepRun output.
2. `hotspots.persist` reads that successful snapshot and reconciles Hotspots through the single writer and storage provider. It does not fetch the source again after partial persistence or a restart.

No LLM, model route or model API key is needed. Tool/service traces use the existing Traces table independently of `GENERATION_ENABLED`.

## Configuration and rollout

Apply the foundation schemas from #23–25 first. Configure the runtime tables, `FEISHU_TABLE_ID_HOTSPOTS`, and `FEISHU_TABLE_ID_TRACES`. Add a text field `last_ingestion_run_id` to Hotspots. Existing fields retain their mappings; `raw_json` remains serialized JSON text in Feishu and becomes an object in the read API.

```dotenv
HARNESS_ENABLED=true
HOTSPOTS_ENABLED=true
OPENCLI_ENABLED=true
OPENCLI_BIN=opencli
OPENCLI_TIMEOUT=30
OPENCLI_DOUYIN_COMMAND=["novelops","douyin-hotspots","--limit","50","-f","json"]
GENERATION_ENABLED=false
```

Install the repository's PUBLIC adapter using Node 24 (the CI version), from the repository root:

```sh
npm ci --ignore-scripts --prefix tools/opencli
tools/opencli/node_modules/.bin/opencli list -f json
mkdir -p "$HOME/.opencli/clis/novelops"
cp tools/opencli/douyin-hotspots.js "$HOME/.opencli/clis/novelops/douyin-hotspots.js"
tools/opencli/node_modules/.bin/opencli validate novelops
tools/opencli/node_modules/.bin/opencli novelops douyin-hotspots --limit 50 -f json
```

Inspect an existing adapter before replacing it. Set `OPENCLI_BIN` to the absolute path of that local `tools/opencli/node_modules/.bin/opencli` executable, or an installed OpenCLI 1.8.8 binary. The registry initialization creates OpenCLI's own user configuration directory; the adapter must be installed for the same OS user as the backend. No browser extension or login is needed. OpenCLI is pinned in the lockfile, with offline contract tests in CI.

The built-in Douyin creator-center adapter requires browser credentials. This separate adapter uses the unauthenticated [public word billboard](https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/) through OpenCLI's documented PUBLIC extension interface. It checks upstream status/schema, uses a fixed host, disallows redirects and times out after 10 seconds. `url` identifies the feed, not an invented video URL; raw source fields and `active_time` remain in the payload. The endpoint currently returns at most 50 rows and has no verified stable API guarantee. Schema drift fails visibly. Empty results use OpenCLI exit 66, which the Python adapter maps to a zero-count success; other exits remain failures.

The command above returned 50 real rows on 2026-09-28. Empty configured argv still fails startup when collection is enabled. The backend passes argv directly without a shell; API callers cannot supply command arguments or select a source URL. Only public hotspot extraction is in scope: no login bypass, comments, publishing or credential scraping.

`OPENCLI_ENABLED=true` also enables Hotspot reads. To retain reads while disabling collection, use `HOTSPOTS_ENABLED=true` and `OPENCLI_ENABLED=false`. The Traces table is only required when collection or generation is enabled. A persisted fetch referencing a changed command/binary is blocked for reconciliation. Do not change the configured command while a workflow is running.

Retain `HARNESS_JOURNAL_DIR` across restarts and run one backend process. Rollback: disable collection, drain/inspect workflows and retain all tables/journals; the schema addition does not require deleting existing data.

## Authenticated APIs

All endpoints require the existing `x-api-key` header.

| Endpoint | Contract |
|---|---|
| `POST /api/hotspots/fetch` | `{ "request_key": "user-generated-id", "limit": 50 }`; limit 30–50, default 50. Returns the queued WorkflowRun with HTTP 201. Same key+definition returns the existing run; changing the definition returns 409. Unknown body fields are rejected. |
| `GET /api/hotspots` | Filters `source`, `status`, timezone-aware `captured_from`/`captured_to`; `offset` >= 0 and `limit` 1–100. Returns `{items,total,offset,limit}`. Sorted by capture time descending, then domain ID. |
| `GET /api/hotspots/{hotspot_id}` | Domain record with parsed raw payload; 404 if absent. |
| `GET /api/workflows/{run_id}` | Step statuses, sanitized errors, persisted counts, snapshot and output refs. |
| `GET /api/workflows/{run_id}/trace` | Tool/service attempts and typed failures. No model usage is fabricated. |

Missing runtime/service or disabled collection returns 503. Manual add, discard, selection and semantic-analysis UI belong to #7/#8.

## Identity and update policy

- Reuse the adapter's source/title/URL `dedupe_hash`. New canonical IDs are deterministic `HS-` hashes of this key; transient adapter UUIDs never become new canonical IDs.
- When an existing dedupe key has a legacy UUID, preserve that UUID and the existing status (including discarded/approved). Multiple stored rows with one dedupe key block processing rather than choose one arbitrarily.
- Update rank, heat, category, captured time, raw payload and ingestion-run provenance only when the incoming capture time is newer. An older snapshot cannot revert newer metadata. Same timestamp retains the first committed metadata.
- Existing identity fields must agree with the dedupe key's source/title/URL. Corrupt identities/timestamps require reconciliation.
- Write a durable intent before each create. A committed timeout is read back by business ID. Uncertain absence blocks without another POST, including across restarts or fresh ingestion requests.

## Counts and failure behavior

Fetch output includes fetched raw items, accepted records, rejected records, duplicates within the batch, selected unique records and omitted unique records beyond the requested limit. Accepted includes duplicates; selected is the subset persisted. Empty/fewer-than-30 feeds are reported accurately, never padded. A nonempty feed with zero valid records fails with `OpenCLIOutputError`. Mixed feeds preserve valid records and expose rejection counts.

Persist output includes created/ensured-new-key and reconciled-existing-key counts for that attempt, updated metadata count, output IDs and batch hash. These are attempt-local observations: after a restart previously written items are counted as reconciled, not newly created again. A batch is not a cross-record transaction; committed records remain visible if later records fail.

Tool timeout, exit and schema errors are sanitized in StepRuns/traces and use bounded kernel retries. Unknown creates, invalid snapshots or identity conflicts block for reconciliation. Do not resubmit identical uncertain creates with random IDs.

## Verification and limits

`tests/test_hotspot_ingestion.py` covers 35-row real subprocess → adapter → FastAPI lifespan scheduler → stateful Feishu HTTP transport → read API; pagination/filtering; restart/snapshot replay; committed and unknown timeouts; storage/schema/tool failure; legacy IDs/status; older captures; command changes; and zero model calls.

Additionally, the installed OpenCLI adapter fetched 50 real public rows into the Harness and a stateful mocked Feishu HTTP transport: 50 accepted/created, zero rejected, replay reconciled 50 with no duplicates or model calls. The CLI took 922 ms and the saved snapshot was 36,561 UTF-8 bytes for that observation. This verifies the live source, not a live Feishu deployment. Base v3 migration/application credentials and payload/rate/conflict limits remain #21 acceptance gates. Snapshot text size and sequential write latency need real-platform measurement before enabling production ingestion. The current provider paginates filtered rows before local date filtering/response pagination; large-history query performance remains a measured follow-up, not an indexed-query guarantee.
