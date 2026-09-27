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
OPENCLI_DOUYIN_COMMAND=[]
GENERATION_ENABLED=false
```

Replace `OPENCLI_DOUYIN_COMMAND` with a JSON array of arguments **verified against the installed OpenCLI public-feed adapter**. Empty arguments fail startup when collection is enabled. No executable command is guessed here: this development host has no OpenCLI binary or OpenCLI MCP, so a real public-source command has not been verified. The backend passes argv directly without a shell; API callers cannot supply command arguments or select a source URL. Only public hotspot extraction is in scope: no login bypass, comments, publishing or credential scraping.

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

This is controlled local evidence, not a live Douyin or Feishu deployment. Base v3 migration/application credentials and payload/rate/conflict limits remain #21 acceptance gates. Snapshot text size and sequential write latency need real-platform measurement before enabling production ingestion. The current provider paginates filtered rows before local date filtering/response pagination; large-history query performance remains a measured follow-up, not an indexed-query guarantee.
