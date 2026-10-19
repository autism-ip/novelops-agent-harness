# Model, Artifact and eval foundations — ZEN-106 / #22

## Ownership

Semantic workflows use `SemanticRuntime.execute` with explicit input/output
Pydantic schemas, Prompt version/template, logical route, CallContext, artifact
type, logical identity and version. Domain workflows own their prompts/schemas;
the shared runtime owns validation, model calls, artifact identity and telemetry.
This PR does not implement Research/Writer/etc. workflow issues itself.

## Model routing and configuration

Set `GENERATION_ENABLED=true` alongside the Harness configuration. Provision
Artifacts and Traces tables and set FEISHU_TABLE_ID_ARTIFACTS / FEISHU_TABLE_ID_TRACES.
`MODEL_ROUTES_JSON` maps logical routes to validated immutable configuration:

```json
{"research":{"provider":"deepseek","model":"YOUR_CONFIGURED_MODEL","max_retries":1,"timeout":8,"max_output_tokens":2048}}
```

Set DEEPSEEK_API_KEY and/or OPENAI_API_KEY on the backend. No default model or
pricing is fabricated. Configure supported JSON Chat Completions models for each
route; missing routes/keys fail explicitly. No paid API call is made by the
offline test/eval suite. Downstream workflow composition registers semantic
handlers before kernel startup and accesses `kernel.semantic`.

`ModelRouter.generate` keeps its validated-output API. `generate_recorded` also
returns the confirmed trace ID and returned model for that exact call.
`SemanticRuntime` uses this result directly, rather than rediscovering provenance
through a potentially incomplete or older history list. Retries still use one
call ID, the immutable route's 0–2 retry limit and the same backoff. Each attempt
returns a successful result, raises at exhaustion, or advances that finite budget;
there is no implicit missing output after the retry loop.
For local development, backend Settings loads `.env` then `.env.local`; the latter
overrides file values, and process environment variables override both. Both
files are ignored by Git. The backend still requires `BACKEND_API_KEY` to start.

The two adapters share a contract and use official HTTPS endpoints through
httpx. They request JSON objects and then validate them locally with Pydantic;
JSON mode alone does not promise schema adherence. HTTP errors, timeout,
malformed responses, truncated output and schema failures are classified without
persisting provider error bodies or credentials. Retry counts and per-request
timeouts are bounded. DeepSeek's current Chat Completions default enables thinking;
the JSON adapter explicitly disables it unless a DeepSeek route opts in with
`deepseek_thinking: "enabled"`. Thinking consumes output tokens before final JSON
and can truncate structured results. A StoryBible route may need
`{"timeout":20,"max_retries":0,"max_output_tokens":2048}`. The sum of request
timeouts and retry backoff is capped at 25 seconds, below the kernel's 35-second
shutdown wait. Handlers adding passes must budget for them.

References checked using available documentation tools:
[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
and [DeepSeek JSON output](https://api-docs.deepseek.com/guides/json_mode/).
DeepSeek's [thinking-mode reference](https://api-docs.deepseek.com/guides/thinking_mode/)
documents the enabled default and explicit switch.
The implementation uses `max_completion_tokens` for OpenAI and `max_tokens` for
DeepSeek. No CLI or MCP is called by the production model adapter.

## Artifact and provenance

Artifact identity derives from logical ID + explicit version. Stored payloads
contain type, content/hash, input hash/source refs, run/step/chapter, workflow
version, creator, prompt version/hash, route/config hash, provider/actual returned
model and timestamp. Replaying identical generation returns the persisted
artifact without another model call. Changed inputs/prompts/routes or content
require a new version; there is no overwrite API.

New direct model outputs include `model_trace_id` in their immutable JSON payload.
The output link is checked against that trace's run, step, inputs, model,
prompt/route/workflow versions and output hash. An exact replay can finish a
failed link write after Artifact creation without another model request. A
missing, conflicting or differently linked trace requires reconciliation; a
settled link is not rewritten. Derived outputs continue tracing their versioned
source Artifacts.

This optional JSON field needs no Base column migration. Older payloads without
it keep their previous read shape and can replay without a guessed trace lookup.
An empty optional value is omitted from normalized output. No old payload is
backfilled or rewritten. New payloads use the updated Artifact schema; the older
strict schema does not recognize this added metadata when explicitly reading a
new output.

Inputs must reference immutable source versions. Prompt and workflow definitions
should be version-controlled; trace rows include route snapshots/request hashes.
The journal and provider reconcile ambiguous artifact creation. A failure after
model execution but before artifact persistence can require a later new model
attempt; every persisted attempt is counted, and unknown billing remains unknown.

## Trace and usage

Every configured deterministic handler gets a tool/service trace with run/step
correlation, attempt, latency, output refs and sanitized failure class. It does
not produce fake model usage. Each model attempt has its own trace, including
failed schema attempts that still consumed tokens. Running/incomplete traces
survive crashes and count as unknown usage until reconciled.

Before starting its scheduler, the kernel recovers persisted traces under its
writer lock. An abandoned `running` observation becomes `interrupted`, with
`failure_class=Interrupted` and `outcome_unknown=true`. This is an interrupted
observation, not proof of provider success/failure or billing. `finished_at`
records the reconciliation time; missing token/cost/latency fields are not
invented. Existing successful, failed and interrupted observations are unchanged.
Recovery validates the whole trace read, including row/payload identity and status,
before any repair; corrupt records or an unconfirmed repair stop startup. Exact
recovery after a committed response timeout reconciles without a second write.

This does not change handler retry policy. A resumed semantic handler still
reuses its immutable Artifact when present, without another model request.
If a model response was never persisted as an Artifact, its external outcome
may remain unknown; this recovery does not claim to retrieve that response.

Usage aggregates all model attempts per run or chapter. Missing token counts or
prices yield null totals and explicit unknown counts; they are never silently
zeroed. Optional input_cost_per_million/output_cost_per_million values are
operator-maintained estimates; currency/account discounts/cache pricing need
appropriate route configuration. The shared estimate is not a provider invoice.

Protected API endpoints:

- GET `/api/workflows/{run_id}/trace`
- GET `/api/workflows/{run_id}/usage`
- GET `/api/chapters/{chapter_id}/usage`
- GET `/api/artifacts/{artifact_id}`

## Additive tables

Artifacts: artifact_id, logical_id, artifact_type, run_id, chapter_id, payload_json
(text); version (number). Traces: trace_id, run_id, step_id, chapter_id, kind,
payload_json (text). These use domain-ID resolution and the same writer as runs.
Legacy AgentRuns/AgentTeamSnapshots are retained. Do not use record history as a
substitute for immutable Artifact versions.

## Offline evaluation

Run `python -m app.evals --output comparison.json` from backend. The packaged
fixtures cover opportunity analysis, StoryBible, chapter planning, generation,
continuity detection and constrained rewrite. Two prompt/provider/route variants
use the same fixtures through the actual ModelRouter with a fixture provider.

The report includes configuration/fixture hashes, schema pass rate, deterministic
constraint violations, revision recommendation rate, retry rate, token/cost
estimates and measured local latency. Human revision rate is null because there
are no human observations. Pricing and model outputs are explicitly synthetic.
The report tests harness regressions; it is not evidence that one real model is
better. Expand domain schemas with their owning issues, retain fixture versions,
and require measured quality/cost improvement before adding Agent roles/passes.

An explicitly opt-in live probe uses the same six fixtures through `ModelRouter`:

```sh
DEEPSEEK_API_KEY=... python -m app.evals \
  --live-provider deepseek --live-model deepseek-flash \
  --output live-eval.json
```

Set the key through the environment or a local secret loader; never put it in a
committed command or report. `--live-prompt` can compare another prompt variant
with the same fixture hash. The report stores output hashes, findings, route and
prompt hashes, token use and latency; it does not store generated prose or a
provider invoice. Model behavior can vary between runs, so compare measured
results rather than assuming a single pass is stable. See the
[ZEN-106 live evidence](reports/2026-09-30-model-foundations.md).
For larger JSON schemas, set `--live-timeout` and `--live-max-output-tokens`
within the route budget. `--live-deepseek-thinking enabled` is an explicit
comparison variant; it can need a larger token budget.

## Verification limits

HTTP MockTransport tests cover both providers, retries, bad schema, missing
configuration, timeouts, rate limits, usage, sanitization and immutable replay.
Provider/Artifact/trace APIs run against the real Feishu client/repository stack
with distinct simulated record IDs. A separate, authorized synthetic Base check
also persisted a real DeepSeek StoryBible Artifact and linked Trace through the
backend application's Feishu credentials, verified same-version replay and
readback, then deleted only the two probe rows. See the linked report for table
IDs, usage and cleanup evidence. Full Book/Harness approval and production
deployment remain untested.

### Evaluation CLI input and failure contract

`python -m app.evals` requires a non-empty JSON array of fixtures before constructing a live provider. Empty arrays and non-array containers fail with an argparse error and no client or model call. Provider/model/key combinations are validated before client creation. Live evaluation keeps strict schema, truncation, malformed response, timeout and rate-limit failure classes; unknown usage/cost remains unknown. The owned HTTP client closes after both success and failure. Offline and HTTP-controlled tests prove evaluator behavior, not real model quality or deployment readiness.

### Explicit validated instruction fields

Internal `SemanticRuntime.execute(..., instruction_field="editor_instruction")` selects only a top-level string from the validated input schema. It retains the complete source JSON and appends the exact non-empty instruction as the final user message; canonical system rules retain their role. Empty strings add no empty message. Missing/non-string selectors fail before traces, artifacts or provider calls. The input hash binds both validated inputs and the selected field, so changing or removing the selector cannot silently replay an existing Artifact. The default path retains its original message and hash contract. This is not a public request field and does not promote similarly named narrative text. Prompt owners must version the opt-in contract before changing queued workflows. HTTP tests verify transport/provenance; real semantic behavior remains a separate gate.
