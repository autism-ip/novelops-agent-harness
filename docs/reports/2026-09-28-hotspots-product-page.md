# ZEN-34 / #7 — Hotspots product page delivery

## Objective and scope

Deliver the first content/workflow-oriented Hotspots screen: browse/filter/detail, public collection, manual add and discard, plus visible workflow progress/errors. [ZEN-34](https://linear.app/zenhungyep/issue/ZEN-34) / [GitHub #7](https://github.com/autism-ip/novelops-agent-harness/issues/7) owns this implementation on `codex/zen-34-hotspots-page`, stacked on ZEN-33 PR #27 at `2ab5741908ef72b89355bfabcaa91df29c17ea0f`.

Analysis selection is rendered with an explicit unavailable state as specified in #7's repository-alignment acceptance notes. ZEN-35 / #8 must supply the semantic workflow and enable this control. This report does not treat that dependency as completed.

## Actual changes and decisions

- `/hotspots` adds source/status/local-calendar-date filters, 20-row pagination, selection, native modal detail drawer, normalized/raw payload inspection and safe source links. Empty/loading/failed/success states are distinct.
- Existing signed-session proxy and password endpoint are reused. Backend/provider credentials stay server-side. Recent activity shows persisted run identity, state, step results and sanitized failures. Selected runs poll until terminal, completion refreshes content, idle list/activity polling is15 seconds.
- `hotspot_controls.py` registers manual-add/discard handlers in the existing single-writer kernel. Request keys and domain IDs are stable. Repeated manual content preserves the existing record/status. Discard carries an expected status and blocks when a newer decision differs.
- Before a POST, the UI retains its body/key in tab-scoped session storage. Unknown outcomes can be retried after reload with the same key. A rejected retry cannot establish that a previous attempt never committed, so its key is retained. New mutations are disabled while an outcome is unknown or work is active.
- Next.js / matching ESLint config upgraded16.2.7→16.3.6; compatible transitive lockfile repairs address the existing npm audit findings. This is a same-major upgrade following the [official version16 guide](https://nextjs.org/docs/app/guides/upgrading/version-16); no major-version codemod was required.
- Added frontend behavioral contracts to existing required CI, without weakening lint, type, build, coverage or backend checks.

Main files: backend `hotspot_controls.py`, hotspot routes/service registration and tests; frontend `components/hotspots`, page/navigation/layout/API types and dependency lockfile; operator contract `docs/hotspot-product-page.md`.

## Verified evidence

| Check | Observed result |
|---|---|
| Full backend offline suite | 276 passed;9 existing live integration tests deselected; existing Starlette/httpx deprecation warning |
| Coverage | app91.87%; controls94.34%; hotspot routes97.56%; prior87.81558726673984% minimum unchanged |
| New backend acceptance | 9 tests: auth/validation, replay/conflict, stale discard, disabled collection, committed/unknown timeout, restart, namespace and field-encoding collisions |
| Frontend contract tests | 5 passed: dates, pending identity, rejection-after-uncertainty, safe links and automatic pagination clamp |
| Static/build | Ruff, zero-warning ESLint, route types/TypeScript, Next.js production build, backend sdist/wheel passed |
| Dependency audit | Existing8 findings (including1 critical) reduced to0 in `npm audit` after locked compatible upgrades |
| Browser credentials | Fixture backend key/session secret absent from `.next/static`; real login uses HTTP-only session cookie and server proxy |

### Browser acceptance with actual production build

Used the installed Ego browser CLI (no relevant browser MCP found in discovery), production Next.js on127.0.0.1:13000 and the real FastAPI/Harness on127.0.0.1:18000. Storage was the stateful **mocked Feishu HTTP transport**; public collection used35 synthetic subprocess records. No live Feishu or model call was made for these checks.

1. Unsigned requests produced login state; signing in through the real password form unlocked the empty page.
2. Added a manual idea, inspected normalized/raw fields, discarded it, reloaded and observed retained discarded status.
3. Normalized-status filtering produced an empty result; clearing it and collecting produced36 total rows. Pagination showed20/16 rows and cleared prior selection.
4. Injected malformed upstream JSON through a fixture-only route; the page showed failed fetch, canceled persist and `OpenCLIOutputError` while preserving prior records.
5. Injected a503 **after** manual workflow creation, then reloaded and retried. Same key survived reload; backend inspection confirmed exactly1 workflow and1 manual record; pending descriptor cleared.
6. Initial390px mobile verification found598px page overflow. Added flex shrink and pagination wrapping; recheck returned viewport/body/root widths all390px. The table scrolls inside its own container.

Reproduction steps and fixture boundaries are in `docs/hotspot-product-page.md`. Screenshots are local evidence, not a claim of live deployment. Test-only failure controls are absent from the production app/package. The fixture and frontend processes are stopped after verification.

## Review and readiness

Delivery is [PR #28](https://github.com/autism-ip/novelops-agent-harness/pull/28). Initial commit `b25012b8d85a66aeca9cbf8fcf00ea84835821d6` passed all six [CI jobs](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36343087332). Later changes clarify empty pages after result shrinkage and count only selected records still visible. They were rechecked with the four frontend tests, lint and types; their own current-head CI is checked after push.

Initial reviewable implementation includes regression fixes discovered during development (mobile overflow and request-key retention after an uncertain attempt). All PR review sources were empty at the first post-publication check; absence of comments is not reviewer approval. Remote CI and review sources are rechecked after the final push and recorded in the PR. No human approval is assumed.

### Automated review follow-up

The later review on `b25012b8d8` raised three valid P2 findings, all addressed in this PR:

| Finding | Resolution and evidence |
|---|---|
| Fetch keys could alias manual/discard keys | Manual/discard use independent `hotspot-manual:` / `hotspot-discard:` namespaces, preserving existing fetch identities. A regression first reproduced409 with `manual:shared`; fetch/manual/discard now remain distinct and complete. |
| Colon-delimited identity encoding was ambiguous | Hash canonical JSON of source/title/URL. The two valid title/URL pairs in the review first reproduced a blocked second record; both now persist with different hashes. |
| A shrinking result set left an out-of-range page | On each live list response, clamp offset to the last populated page and refetch. Contract tests cover21→20 rows,40→21 rows, empty sets and unchanged valid offsets. The prior empty-page wording fix alone was insufficient. |

After these changes, the full backend suite276, frontend contracts5, Ruff, ESLint, types and production build passed. Review threads are resolved only after the fixes are pushed; latest CI links and final thread state belong to the PR. Browser journeys above were executed before this review follow-up; the follow-up is covered by the new regression contracts and full suites rather than a claimed second complete browser run.

Engineering judgment: the implemented UI/control scope is suitable for code review after current-head gates pass. The whole stack is **not yet proven safe to merge/deploy**: PR #23's Base v3/application-auth compatibility and live capacity/latency gates remain pending, and selected analysis awaits #8. Linear must not be marked Done merely because these offline and browser checks pass.

## Limits, risks and follow-up

- Browser evidence proves UI→session proxy→API→scheduler→provider behavior under controlled storage, not app-authenticated Feishu production operation.
- Single-writer status preconditions do not provide distributed CAS against external edits. Retain runtime journals and run one process.
- Manual duplicate detection preserves the first record; it is not an edit/revive operation. Uncertain creates remain blocked until reconciled.
- Tab-scoped pending descriptors survive reload but not closing the tab. Backend history remains authoritative; review it before replacing an uncertain request.
- Idle polling and filtered scans are bounded in the UI, but remote workload/capacity still needs measurement. Large workflow histories need provider-side pagination in a later optimization; the current workflow list contract returns all runs.
- Next.js security upgrade passed existing routes' build checks and the new authenticated browser journey. This does not claim exhaustive testing of every framework feature.

## Reusable workflow assessment

Reused `issue-pr-delivery`, TDD, `next-upgrade` and `ego-browser` workflows. No new personal skill was needed; the documented loopback fixture and failure injection are the reusable project acceptance assets. Next substantive issue is ZEN-35 / #8 semantic research and risk analysis, including enabling Analyze selected. Remaining domain issues retain separate PR deliverables.
