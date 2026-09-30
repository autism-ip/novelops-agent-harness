import assert from "node:assert/strict";
import test from "node:test";
import {
  listPath,
  parsePending,
  safeSourceUrl,
  canClearRejected,
  clampOffset,
  workflowBusy,
} from "../src/components/hotspots/state.ts";

test("discarding the last result on a page returns to the last populated page", () => {
  assert.equal(clampOffset(20, 21), 20);
  assert.equal(clampOffset(20, 20), 0);
  assert.equal(clampOffset(40, 21), 20);
  assert.equal(clampOffset(20, 0), 0);
  assert.equal(clampOffset(0, 35), 0);
});

test("analysis retries preserve explicit versions and reject malformed manifests", () => {
  const item = { hotspot_id: "HS-one", version: 2, source_hash: "a".repeat(64) };
  const command = { path: "/api/analyses", body: { request_key: "batch", items: [item] } };
  assert.deepEqual(parsePending(JSON.stringify(command)), command);
  for (const items of [[], [null], [{ ...item, version: 0 }], [{ ...item, version: 1.5 }], [{ ...item, source_hash: "bad" }]]) {
    assert.equal(parsePending(JSON.stringify({ ...command, body: { request_key: "batch", items } })), null);
  }
  assert.equal(parsePending(JSON.stringify({ path: "/api/analyses" })), null);
});

test("human research gates do not lock all hotspot controls indefinitely", () => {
  assert.equal(workflowBusy({ pipeline_type: "hotspot_research_v1", status: "awaiting_approval" }), false);
  assert.equal(workflowBusy({ pipeline_type: "hotspot_research_v1", status: "running" }), true);
  assert.equal(workflowBusy({ pipeline_type: "hotspot_ingestion_v1", status: "awaiting_approval" }), true);
  assert.equal(workflowBusy({ pipeline_type: "hotspot_research_v1", status: "completed" }), false);
});

test("an authentication rejection after an uncertain submission never drops its key", () => {
  for (const status of [401, 404, 409, 422]) {
    assert.equal(canClearRejected(status, false), true);
    assert.equal(canClearRejected(status, true), false);
  }
  assert.equal(canClearRejected(503, false), false);
});

test("filters encode an inclusive local date range and reset bounds explicitly", () => {
  const path = listPath(
    {
      source: "manual",
      status: "discarded",
      from: "2026-09-28",
      to: "2026-09-28",
    },
    20,
  );
  const query = new URL(path, "http://localhost").searchParams;
  assert.equal(query.get("source"), "manual");
  assert.equal(query.get("offset"), "20");
  assert.equal(
    query.get("captured_from"),
    new Date("2026-09-28T00:00:00").toISOString(),
  );
  assert.equal(
    query.get("captured_to"),
    new Date("2026-09-28T23:59:59.999").toISOString(),
  );
  assert.throws(() =>
    listPath(
      { source: "", status: "", from: "2026-09-29", to: "2026-09-28" },
      0,
    ),
  );
});
test("uncertain submissions retain the exact key/body and reject corrupted storage", () => {
  const command = {
    path: "/api/hotspots/manual",
    body: { request_key: "stable-key", title: "Manual" },
  };
  assert.deepEqual(parsePending(JSON.stringify(command)), command);
  for (const value of [
    "bad",
    "null",
    "{}",
    JSON.stringify({ ...command, path: "/api/workflows" }),
  ]) {
    assert.equal(parsePending(value), null);
  }
});
test("source links cannot execute script or embed credentials", () => {
  assert.equal(
    safeSourceUrl("https://example.com/story"),
    "https://example.com/story",
  );
  for (const value of [
    "javascript:alert(1)",
    "//example.com",
    "https://u:p@example.com",
    "data:text/html,x",
  ]) {
    assert.equal(safeSourceUrl(value), null);
  }
});
