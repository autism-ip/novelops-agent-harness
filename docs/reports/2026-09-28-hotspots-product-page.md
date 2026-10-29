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


## 2026-10-07 full frontend source-coverage baseline

The new delivery objective requires 100% applicable statement, line, function and branch coverage. PR #28 now adds Vitest with V8 coverage for every `frontend/src/**/*.{ts,tsx}` file, including files that no test imports, and adds three React Testing Library checks for the user-visible backend health states (checking, connected, unreachable after a non-OK response or request failure). The existing five Node behavior tests remain in `npm test`; no test or coverage gate was removed. `npm ci`, all eight frontend tests, and `npm run check` (lint, TypeScript and production build) pass.

The measured **Vitest source baseline**, which does not yet incorporate the separately run Node helper tests, is **3.37% statements (14/415), 3.08% lines (12/389), 4.13% functions (5/121), and 2.16% branches (6/277)**. This honest all-source report is far below 100%; neither this issue nor the wider stack can be called done under the new goal. The Next.js/Vitest setup follows their official guides, using Vite's native `resolve.tsconfigPaths`.

`npm audit` currently reports five high findings through the pre-existing development-only `eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces@3.0.3` chain. The same `braces` version exists in the branch's original lockfile; `npm audit --omit=dev` reports zero vulnerabilities. [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists no patched `braces` version as of this check. This is a tooling availability risk when processing attacker-controlled glob patterns, not evidence of a production dependency vulnerability. It remains open for upstream remediation and should not be hidden by an audit ignore rule or a forced Next.js downgrade.


### Unified frontend test measurement

The same five original hotspot behavior assertions now execute directly under Vitest, alongside the three React tests. They import the real `state.ts` module, so the all-source report counts their executed paths rather than leaving them in a separate Node process. No assertion was removed or weakened. **8/8 frontend tests pass**; coverage increases to **9.87% statements (41/415), 9.51% lines (37/389), 8.26% functions (10/121), 12.63% branches (35/277)**. All unimported source still contributes zero; 100% remains open.

### 2026-10-08 signed-session security regression

Four new tests call the real WebCrypto HMAC session module and assert successful verification before expiry; rejection at expiry; rejection of changed payloads and malformed signatures; refusal to sign without a 32-character server secret; and fail-closed behavior when browser cryptography throws. `session.ts` now has **100% statement, line, function and branch coverage**. On this ZEN-34 head, **12/12 frontend tests**, lint, TypeScript and production build pass. The full-source report is **19.51% statements (81/415), 19.02% lines (74/389), 12.39% functions (15/121), 18.41% branches (51/277)**. Other routes and UI components remain below the required 100%.

### 2026-10-08 proxy path-normalization remediation

A route-level test with a valid signed session reproduced a real guard bypass: decoded `..\\private` reached the backend proxy and returned its mocked 200 response; WHATWG URL normalization can also collapse `%2e%2e` and treat `?`/`#` as URL syntax. The catch-all proxy now accepts only literal API route/domain-ID segments (`A-Z`, `a-z`, `0-9`, `_`, `-`) before building the backend URL. This matches all current backend path contracts. Regression cases reject dot, slash, backslash, encoded dot, query and fragment segments before fetch. Separate tests confirm public health is forwarded without an API key; protected routes require a signed session and inject only the server key; missing key/secret fail closed; POST/PUT/PATCH/DELETE preserve their method, body and upstream response.

The proxy route now has **100% statement, line, function and branch coverage**. On this head, **17/17 frontend tests**, lint, TypeScript and production build pass. Full-source frontend coverage is **28.43% statements (118/415), 28.53% lines (111/389), 17.35% functions (21/121), 27.37% branches (75/274)**. The changed branch denominator reflects replacing three blacklist checks with one allowlist; no source file was excluded. The full-stack 100% target remains open. The security review checklist confirmed the server-only API key, HttpOnly session and fail-closed paths; production security gates remain outside this local route test.

### 2026-10-08 Hotspots and HTTP lifecycle verification

Eight new tests render the real HotspotsWorkbench with its real resource hook and API client against a controlled HTTP fixture. They assert visible pagination/filter selection resets, manual form values, detail source-link safety and discard status preconditions, persistence of an uncertain create across remount, identical retry identity, login/reload, exact collection request, disabled collection, invalid date range, new-command rejection versus uncertain-retry rejection, and corrupt-command recovery. JSDOM lacks native dialog methods, so only `showModal`/`close` receive a DOM polyfill. The fixture does not prove live Feishu idempotency or model behavior; it verifies the frontend's actual command and recovery wiring.

The login interaction first exposed an ambiguous wrong-password message. It now explicitly reports an invalid workspace password. A real login-route test also reproduced an uncaught signing error when `SESSION_SECRET` is missing; the endpoint now returns a controlled 503 and issues no Cookie. Successful login tests use real HMAC signing and verify the 24-hour expiry, HttpOnly/SameSite attributes and production Secure Cookie. Additional real-client/resource tests assert server-key injection, JSON serialization, malformed upstream errors, ten-second AbortController timeout, timer release, 401 polling stop, transient recovery and no state/polling restart after unmount. Health checks also reject late updates after navigation. Pending request parsers reject malformed business identities.

**42/42 frontend tests**, zero-warning lint, TypeScript and production build pass on this owning branch. Full-source coverage is **89.20% statements (372/417), 89.51% lines (350/391), 81.81% functions (99/121), 92.44% branches (257/278)**. `api/client.ts`, `use-resource.ts`, HealthIndicator, the login route, session module and catch-all proxy each reach 100% on all four metrics. The two added login failure statements and password-error branches remain included. Static shell/pages and remaining Hotspots branches prevent the overall 100% target; no ignore, assertion weakening or source exclusion was used.

## Native read transport propagation (2026-10-09)

The manual-create timeout probe now injects at the actual hotspot-record POST,
not the native search POST introduced by the storage adapter. It still verifies
committed-response loss completes without duplicate creation and an unobserved
create blocks without replay. No product behavior or assertion was relaxed.
