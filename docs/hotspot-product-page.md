# Hotspots product page — ZEN-34 / #7

The `/hotspots` page uses the existing signed-session `/api/*` proxy. It provides a password form when the session is absent or expires; `AUTH_PASSWORD`, `SESSION_SECRET`, `BACKEND_API_URL` and `BACKEND_API_KEY` remain server-only variables. Configure the runtime and tables from `hotspot-ingestion.md`. `HOTSPOTS_ENABLED=true` supports manual controls and reads while collection is disabled.

## Product contract

- Source/status/local-calendar-date filters, 20-row pagination, explicit loading/empty/error views and detail drawer with normalized fields, safe source link and raw JSON.
- Fetch creates a persisted collection workflow. Recent activity shows run IDs, status, step progress and sanitized errors. Active selected runs poll every two seconds until terminal; completion refreshes content. Idle list/activity refresh every 15 seconds. Manual Refresh is always available.
- Manual add accepts title, optional HTTP(S) URL and category. It creates a `hotspot_manual_v1` workflow; the single writer persists a manual-source record using a stable dedupe identity. Re-adding the same source/title/URL preserves existing ID/status/metadata, including a prior discard.
- Discard creates `hotspot_discard_v1` with the observed status. A different status at execution blocks the command for review. Replaying an already committed discard is safe. This is a single-writer precondition, not a distributed compare-and-swap guarantee.
- Analyze selected is visibly unavailable pending #8. Selection works, but this PR does not fake an analysis result or enqueue an undefined handler.

## Mutation APIs

| Endpoint | Body / response |
|---|---|
| `GET /api/hotspots/capabilities` | fetch/manual_add/discard/analyze availability flags |
| `POST /api/hotspots/manual` | request_key, title, optional url/category; HTTP201 WorkflowRun |
| `POST /api/hotspots/{id}/discard` | request_key, expected_status; HTTP201 WorkflowRun; missing record404 |

All require existing authentication. Unknown body fields, blank title/request key, invalid URLs and excess field lengths are rejected. Same request key with changed input returns409. Command identity is namespaced per operation.

The UI saves a pending request body/key in tab-scoped session storage **before** posting. A timeout/5xx leaves it available after reload; Retry same request resends the exact command. A rejected retry does not disprove a previous committed attempt and does not discard the saved key. While an outcome is unknown, new mutations are disabled. No secret or backend API key is stored there. If browser storage is unavailable, mutation fails before posting. Closing the tab loses that pending descriptor; review backend activity before starting a replacement request. Backend records and workflows remain in Feishu.

## Reproducible local browser acceptance

Use Node24 and the normal backend development dependencies. The fixture below is a **loopback-only test application** with synthetic subprocess output and a stateful mocked Feishu HTTP transport. It exercises the production API, scheduler, provider and session proxy; it does not certify a live Feishu deployment.

1. In `backend`, run `python -m tests.ui_fixture_app` (127.0.0.1:18000).
2. In `frontend`, run `npm ci`, `npm test`, `npm run check`.
3. Start `npm start -- --hostname 127.0.0.1 --port 13000` with `BACKEND_API_URL=http://127.0.0.1:18000`, `BACKEND_API_KEY=ui-fixture-key`, `AUTH_PASSWORD=ui-fixture-password`, and a synthetic `SESSION_SECRET` of at least32 characters. These values are fixture-only.
4. Open `/hotspots`; verify unsigned API calls are denied and sign in through the form. Confirm empty state. Add a manual title/category/source URL, inspect normalized/raw fields, discard it, reload and verify the retained discarded row.
5. Filter by normalized status to see an empty list; clear the filter and fetch. The fixture returns35 public rows. Verify36 total, pages20/16, selected rows reset on pagination, and analysis remains explicitly unavailable.
6. Test failure: authenticated POST `/api/_fixture/source-failure` changes only the fixture payload. Fetch again; observe failed fetch, canceled persistence and an `OpenCLIOutputError` message. Existing rows remain readable.
7. Test uncertain result: authenticated POST `/api/_fixture/uncertain-manual`, then add a new manual topic. The fixture commits the workflow and deliberately returns503 once. Reload, Retry same request, and verify only one corresponding workflow/record exists and the pending descriptor clears.
8. At390px width, verify there is no page overflow; the table scrolls within its container. Inspect keyboard-accessible modal close, filters and navigation.

Fixture control routes exist only in `tests/ui_fixture_app.py`, are protected by the normal middleware and are absent from the production app/package. Stop both local servers after verification. Do not expose the test app publicly.
