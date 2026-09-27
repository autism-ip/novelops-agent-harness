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

The two adapters share a contract and use official HTTPS endpoints through
httpx. They request JSON objects and then validate them locally with Pydantic;
JSON mode alone does not promise schema adherence. HTTP errors, timeout,
malformed responses, truncated output and schema failures are classified without
persisting provider error bodies or credentials. Retry counts and per-request
timeouts are bounded. The conservative default budget is within the kernel's
shutdown budget for one generation; handlers adding passes must budget for them.

References checked using available documentation tools:
[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
and [DeepSeek JSON output](https://api-docs.deepseek.com/guides/json_mode/).
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

## Verification limits

HTTP MockTransport tests cover both providers, retries, bad schema, missing
configuration, timeouts, rate limits, usage, sanitization and immutable replay.
Provider/Artifact/trace APIs run against the real Feishu client/repository stack
with distinct simulated record IDs. No paid model calls or live backend
deployment are claimed.
