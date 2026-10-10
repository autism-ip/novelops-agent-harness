# Opportunity research (ZEN-35 / GitHub #8)

## Runtime and configuration

`ResearchAgent` uses the shared SemanticRuntime and ModelRouter. The deterministic
workflow is `research → risk → risk_gate → selection → commit`. A valid structured
opportunity is stored before downstream risk evaluation. Invalid JSON/schema
output is regenerated within the configured ModelRouter retry budget; exhaustion
fails the step without multiplying retries in the scheduler.

Enable `HARNESS_ENABLED`, `HOTSPOTS_ENABLED` (or `OPENCLI_ENABLED`),
`GENERATION_ENABLED`, and `RESEARCH_ENABLED`. Configure both `research` and `risk`
entries in `MODEL_ROUTES_JSON`, using explicit provider/model settings, and the
corresponding server-side provider key. `RESEARCH_SELECTION_REQUIRED=true` is the
default. False enables automatic selection only after the risk gate passes.

Feishu requires the runtime/Artifact/Trace/Hotspots tables plus
`FEISHU_TABLE_ID_HOTSPOT_ANALYSES`. Add these fields before enabling research:

| Table | Additive fields | Type |
| --- | --- | --- |
| HotspotAnalyses | version | Number |
| HotspotAnalyses | pipeline_run_id, source_hash, artifact_id, risk_artifact_id | Text |
| ApprovalEvents | reason | Text |

The existing analysis fields contain summary, JSON arrays for emotions/patterns/
genres/directions, reader promise, risk notes, and approval status. No fake
writability score is generated. Final risk artifacts identify their creator,
provider and model as deterministic policy; model risk opinions retain actual
model provenance and usage.

## API contract

All endpoints require the existing API-key guard; the frontend uses the signed
session proxy and never receives provider or backend credentials.

1. `GET /api/hotspots/{id}/research-context` returns `next_version`, `source_hash`,
   and `can_analyze`.
2. `POST /api/analyses` accepts `{request_key, items: [{hotspot_id, version,
   source_hash, revision_of?, feedback?}]}` (1–20 distinct hotspots). The explicit
   hotspot/version pair is the idempotency identity. The batch request key is
   a client correlation key, not a transaction or independent version allocator.
   Store the entire body before posting; retry unchanged after an uncertain result.
3. The response has `runs` and per-item `errors`. Known stale/missing items are
   reported individually. Storage failures remain HTTP 503: earlier reservations
   may have committed. A batch is not atomic; replay reconciles existing versions.
4. `GET /api/analyses/{run_id}` returns workflow steps, frozen source, versioned
   opportunity/risk artifacts, decisions, `approval_status`, and `current`.
   `GET /api/hotspots/{id}/analyses` returns newest-first history.
5. `POST /api/analyses/{run_id}/decision` requires `{artifact_id, step_id,
   expected_version, action, operator, reason?}`. `expected_version` is the step's
   output version from the read response, not the analysis version. Supported
   actions: approve, reject, revise. Revise requires a nonblank reason.
6. Revision is an explicit new analysis version: use fresh research context and
   send `revision_of` with the revision-requested run ID plus editorial `feedback`.
   The previous opportunity becomes an immutable input reference. No model call
   occurs just because an editor requests revision.
7. Downstream consumers (#9 onward) must use
   `GET /api/analyses/{run_id}/approved` / `ResearchService.approved()`, which checks
   completion, latest version, source fingerprint and discard state. Never consume
   a Feishu status cell alone as authorization.

Each human gate has its own stable step ID and one decision per output version.
Retrying a risk approval cannot approve the later selection gate. Generic workflow
decisions invoke the same artifact guard; the generic creation API rejects reserved
research handlers so callers cannot substitute an approval-free definition.

## Risk and recovery semantics

Required fields are bounded and schema validated; blank content is rejected.
Deterministic checks flag missing source URLs, very short source context, possible
contact information, and a small set of sensitive-subject patterns. A semantic
risk opinion is included in ResearchAgent output; flagged/non-low/low-confidence/
uncertain proposals receive an additional semantic risk review. Any review trigger
remains in force even if the second opinion is more permissive. This conservative
policy is a triage mechanism, not legal clearance or factual verification.

Low risk skips only the risk approval. Opportunity selection is a separate policy.
Reject/revise ends the current workflow and persists feedback. Source changes,
discarded hotspots and superseded versions cannot be newly approved or consumed.
Historical read responses remain available and explicitly mark `current=false`.

Approval fingerprints include the stable hotspot ID, source, title and URL. Routine
recapture timestamps and feed category updates do not invalidate an existing
opportunity; the exact original metadata remains frozen in its workflow input.
Changed title/URL or discard status still blocks approval/consumption. A revision
request must reference the currently latest version and source.

Workflow definitions freeze source, policy, prompt hashes and route hashes. A
configuration change blocks pending execution rather than silently changing the
meaning of its version. Use a deliberate new version after reconciliation.

Projection callbacks run after durable step/run transitions, outside effect retry.
Startup recovery revisits terminal workflows too. A failed projection therefore
rebuilds from persisted steps, decisions and artifacts without repeating completed
model effects. Preserve the existing fsynced creation-intent directory.

## Verification and operational limits

Run backend pytest with coverage and the unchanged baseline gate, Ruff, frontend
`npm test`, and `npm run check`. `python -m tests.ui_fixture_app` serves the actual
API/kernel on loopback port 18000 with synthetic HTTP storage and synthetic models.
Its protected `_fixture/uncertain-analysis` endpoint drops one successful batch
response for browser retry testing. Category `high-risk-fixture` triggers a high
risk model fixture. Fixtures are outside the production wheel.

These checks do not prove real-model opportunity quality, live Feishu app auth,
Base v3 compatibility, quotas, concurrent human edits or large payload capacity.
ZEN-105's production storage gates remain prerequisites. Reads/projections currently
scan relevant workflow rows through the legacy adapter; production scale needs the
provider's bounded-query/capacity validation. Kernel calls remain synchronous under
the single writer; existing model/tool timeout bounds still apply.

The frontend supports batch triggering, outcome recovery, analysis history and
risk explanations. Full editorial decision controls belong to ZEN-37 / #10;
the version-bound decision contracts are implemented here for that UI.
