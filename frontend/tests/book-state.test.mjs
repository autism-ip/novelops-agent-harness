import assert from "node:assert/strict";
import test from "node:test";
import { parsePendingBook } from "../src/components/books/state.ts";

test("book creation replays exact approved source IDs after an unknown response", () => {
  const command = { book_id: `BK-${"a".repeat(32)}`, cover_run_id: `PR-${"b".repeat(32)}`,
    cover_artifact_id: `AR-${"c".repeat(32)}`, title_artifact_id: `AR-${"d".repeat(32)}`,
    opportunity_artifact_id: `AR-${"e".repeat(32)}` };
  assert.deepEqual(parsePendingBook(JSON.stringify(command)), command);
  for (const invalid of [null, "bad", "{}", JSON.stringify({ ...command, book_id: "other" }),
    JSON.stringify({ ...command, title_artifact_id: "" })]) {
    assert.equal(parsePendingBook(invalid), null);
  }
});
