# ZEN-33 / GitHub #6 — hotspot ingestion delivery review

## Goal and delivery

Deliver deterministic public-hotspot ingestion with stable identity, restart recovery, explicit counts and protected read APIs. [PR #27](https://github.com/autism-ip/novelops-agent-harness/pull/27) is the sole delivery for [ZEN-33](https://linear.app/zenhungyep/issue/ZEN-33) / [#6](https://github.com/autism-ip/novelops-agent-harness/issues/6). Branch `codex/zen-33-hotspot-ingestion` targets `codex/zen-106-model-artifacts` at `26c3438591019388ae273b748a0bb4c6d15baeb9`. Merge order is #23 → #24 → #25 → #27; #23 remains Draft.

## Implemented scope and decisions

- `backend/app/hotspots.py`: registered fetch/persist steps, validated batch snapshots including command identity, explicit source counts and deterministic reconciliation. New IDs use the existing dedupe key; legacy IDs and user status survive repeated captures. Only newer observations update source metadata.
- `backend/app/api/routes/hotspots.py`: authenticated workflow trigger, source/status/date filters, bounded response pagination and details. Collection and historical reads have separate switches.
- Runtime/config/table mapping: reuse the single writer, journal and storage provider, add ingestion-run provenance, enable tool traces without configuring any model.
- `tools/opencli`: pinned OpenCLI 1.8.8 PUBLIC extension, fixed public endpoint, schema/HTTP/timeout checks, no browser credentials. The built-in creator-center adapter requires cookies, so it was not suitable for this public-source requirement.
- Existing Python runner/adapter remains the subprocess boundary; explicit OpenCLI empty-result exit 66 becomes a successful empty observation. Other exits remain typed failures. No LLM calls.

Persist is per record, not a transaction across all records. Counts describe the current attempt; records written before a restart are subsequently reconciled. Unknown create outcomes block additional blind creates through durable intent reconciliation.

## Review findings and fixes

Automated review on initial commit `b8969ab7b4577aa8701e12126d0912b66c10ebe1` raised three valid P2 findings:

| Finding | Fix and behavioral verification |
|---|---|
| Saved fetch accepted under a changed runtime command | Hash command identity with the snapshot and require it to match current configuration before any write. Restart regression proves blocked status and zero Hotspot writes. Same-command partial-write restart still succeeds. |
| Hotspot-only telemetry made Artifact reads crash | Artifact route checks its own storage availability and returns 503. Regression exercises the authenticated route with generation absent. |
| Stored valid JSON scalars bypassed the object contract | Decode and require a dictionary. Array/null/string/number/boolean regressions verify both detail and list return reconciliation errors. |

Eight new cases first reproduced failures and then passed after fixes. Review closure refers to these changes, not to the old green CI. No human approval has been inferred.

## Verification evidence

| Check | Observed result |
|---|---|
| Backend offline suite | 267 passed; 9 existing live integration tests deselected; one existing Starlette/httpx deprecation warning |
| Coverage | app 91.68%; hotspots 91.93%; hotspot API 96%; observability API/runtime 100%; existing 87.81558726673984% gate unchanged |
| Hotspot acceptance suite | 29 passed: real fixture subprocess, production lifespan scheduler, mocked Feishu HTTP, API auth/filtering/counts, restart, committed/unknown timeout, schema/identity/config errors |
| Public adapter contract | 7 Node tests passed; schema drift, limit, short/empty feed, transport/timeout and malformed JSON paths |
| Static/package | Ruff passed; sdist and wheel built; OpenCLI `validate novelops` had zero errors/warnings |
| Initial PR CI | All five jobs passed on `b8969ab…`; the extension adds a sixth required job and final revision must pass its own CI |

Commands: `python -m ruff check app tests`; `python -m pytest tests -q --tb=short -m 'not integration' --cov=app --cov-report=term-missing`; `python -m build --no-isolation`; `npm test` in `tools/opencli`. Full release CI additionally performs dependency checks, wheel smoke testing, frontend lint/types/build and workflow lint.

### Live public-source observation, 2026-09-28

Installed OpenCLI locally (no global npm installation), installed the repository adapter in its user extension directory, and ran `opencli novelops douyin-hotspots --limit 50 -f json`. The unauthenticated [public word billboard](https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/) returned 50 rows. Its output then passed through the actual Python subprocess adapter and Harness into a **stateful mocked Feishu HTTP transport**:

- fetched/accepted/selected 50; rejected/duplicate/omitted 0; created 50;
- replay reconciled all 50 without duplicates; model attempts 0;
- CLI duration 922 ms; saved fetch snapshot 36,561 UTF-8 bytes;
- snapshot hash `50d099c764a36b15bc8f1a6f911b3c3e4296122340f3f69aa7cce63d2244aafa`.

This proves the public source and local orchestration path. It does not prove app-authenticated Feishu production writes. Raw live topic content is not included in this report. The adapter uses the feed URL as provenance; it does not fabricate topic/video URLs. [OpenCLI's source](https://github.com/jackwener/OpenCLI) and bundled adapter-author/usage skills supplied the extension conventions.

## Remaining limits and engineering assessment

- **Not yet safe to merge the full stack:** Base v3 production migration, application credentials, payload/rate/conflict semantics remain #23 acceptance gates. Existing user-CLI synthetic Base evidence is documented separately in `docs/feishu-provider-feasibility.md`; it does not satisfy app-runtime verification.
- The live snapshot size needs actual Feishu field-capacity measurement. Sequential write latency and filtered-list scans need measurement before production enablement. Date filtering currently happens after provider pagination.
- The upstream public endpoint is undocumented and has no verified stability/SLA. Pinning OpenCLI does not pin that remote schema; schema drift and timeouts surface as failures.
- The service requires one writer/process, retained journals and stable configured binary/argv during a workflow. Changing the executable's contents at the same path is not detected by the command hash; deployments should drain active work and pin their installed adapter version.
- Manual add/discard/product UI belong to #7; semantic analysis belongs to #8. They are intentionally pending issues, not hidden acceptance completion here.

Engineering judgment: implementation is ready for human code review once its current-head CI passes. Production deployment and safe stack merge remain unverified. Linear remains In Review, not Done. Review threads and current-head CI are rechecked after each push; the PR records the final run link.

## Reusable workflow and next work

Reused the personal `issue-pr-delivery` skill for capability discovery, dependent PR scope, review regressions and evidence boundaries. Its existing workflow is sufficient; no additional personal skill was needed. The project OpenCLI adapter and its lockfile/tests are the reusable deliverables specific to this source. Next executable issue: ZEN-34 / #7, the hotspot product page and manual controls, followed by ZEN-35 semantic analysis.
