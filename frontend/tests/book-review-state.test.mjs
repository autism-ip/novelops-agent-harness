import assert from "node:assert/strict";
import { test } from "vitest";
import { parsePendingReview } from "../src/components/books/review-state.ts";
const ids = { book: `BK-${"a".repeat(32)}`, run: `PR-${"b".repeat(32)}`,
  version: `CV-${"c".repeat(32)}`, artifact: `AR-${"d".repeat(32)}` };
const root = `/api/books/${ids.book}/chapters/1`;
const target = { run_id: ids.run, version_id: ids.version, artifact_id: ids.artifact,
  version_no: 1, operator: "editor", expected_gate_version: 1 };

test("pending review parser keeps exact version and action", () => {
  const command = { path: root + "/review/decision", body: { ...target, action: "approve" } };
  assert.deepEqual(parsePendingReview(JSON.stringify(command)), command);
  assert.equal(parsePendingReview(JSON.stringify({ ...command, body: { ...target, version_id: "wrong" } })), null);
  assert.equal(parsePendingReview(JSON.stringify({ ...command, path: "/api/workflows/steps/x/decision" })), null);
});

test("revision requires concrete changes and final-lock names exact version", () => {
  const revision = { path: root + "/review/revision", body: { ...target,
    constraints: { must_keep: [], must_change: ["Tighten pacing"], do_not_change: [] } } };
  assert.deepEqual(parsePendingReview(JSON.stringify(revision)), revision);
  assert.equal(parsePendingReview(JSON.stringify({ ...revision, body: { ...target,
    constraints: { must_keep: [], must_change: [], do_not_change: [] } } })), null);
  const lock = { path: root + "/final-lock", body: { version_id: ids.version,
    artifact_id: ids.artifact, version_no: 1, operator: "editor" } };
  assert.deepEqual(parsePendingReview(JSON.stringify(lock)), lock);
});
