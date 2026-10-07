import assert from "node:assert/strict";
import { test } from "vitest";
import { parsePendingChapter } from "../src/components/books/chapter-state.ts";

const id = prefix => prefix + "a".repeat(32);

test("chapter generation replays only the exact Book, chapter and frozen source IDs", () => {
  const command = { path: `/api/books/${id("BK-")}/chapters/1/generations`, body: {
    book_id: id("BK-"), chapter_no: 1, version: 1, start_version_no: 1,
    state_artifact_id: id("AR-"), state_version: 2,
    brief_artifact_id: id("AR-"), brief_version: 1,
    source_version_id: "", constraints: { must_keep: [], must_change: [], do_not_change: [] },
  } };
  assert.deepEqual(parsePendingChapter(JSON.stringify(command)), command);
  assert.equal(parsePendingChapter(JSON.stringify({ ...command, body: { ...command.body, chapter_no: 2 } })), null);
  assert.equal(parsePendingChapter(JSON.stringify({ ...command, body: { ...command.body, brief_artifact_id: "AR-wrong" } })), null);
  assert.equal(parsePendingChapter(JSON.stringify({ ...command, body: { ...command.body, source_version_id: id("CV-") } })), null);
  assert.equal(parsePendingChapter(JSON.stringify({ ...command, path: "/api/workflows" })), null);
});
