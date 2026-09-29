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
with distinct simulated record IDs. The opt-in DeepSeek fixture probe made paid
calls; full backend deployment and a live model-to-Feishu workflow remain untested.
