import assert from "node:assert/strict";
import { test } from "vitest";
import { parsePendingPlan } from "../src/components/books/planning-state.ts";

const id = prefix => prefix + "a".repeat(32);

test("story planning retries retain only exact domain commands", () => {
  const bible = { path: `/api/books/${id("BK-")}/bibles`, body: { book_id: id("BK-"),
    base_state_artifact_id: id("AR-"), base_version: 1, version: 1, change_scope: "initial", feedback: "" } };
  const brief = { path: `/api/books/${id("BK-")}/chapters/2/briefs`, body: { book_id: id("BK-"),
    chapter_no: 2, state_artifact_id: id("AR-"), state_version: 2, version: 1, feedback: "" } };
  const decision = { path: `/api/story-planning/runs/${id("PR-")}/decision`, body: { step_id: id("SR-"),
    artifact_id: id("AR-"), expected_version: 1, action: "approve", operator: "editor", reason: "" } };
  for (const command of [bible, brief, decision])
    assert.deepEqual(parsePendingPlan(JSON.stringify(command)), command);
  assert.equal(parsePendingPlan(JSON.stringify({ ...bible, path: "/api/workflows" })), null);
  assert.equal(parsePendingPlan(JSON.stringify({ ...brief, body: { ...brief.body, chapter_no: 3 } })), null);
  assert.equal(parsePendingPlan(JSON.stringify({ ...decision, body: { ...decision.body, artifact_id: "" } })), null);
  assert.equal(parsePendingPlan(JSON.stringify({ ...decision, body: { ...decision.body, action: "reject" } })), null);
});
