import { afterEach, test } from "vitest";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";
import { exerciseReplayRecovery, resetReplayBoundary } from "./helpers/saved-replay-contract";
const book = `BK-${"a".repeat(32)}`, root = `/api/books/${book}/chapters/1`;
const path = root + "/review/decision", body = { run_id: `PR-${"b".repeat(32)}`, version_id: `CV-${"d".repeat(32)}`,
  artifact_id: `AR-${"c".repeat(32)}`, version_no: 2, operator: "Original editor", expected_gate_version: 0,
  action: "approve", reason: "Checked the prose" };
afterEach(resetReplayBoundary);
test("same-turn review replay/replay/clear retains one owned request through unknown outcome and exact recovery", async () => {
  await exerciseReplayRecovery({ key: `novelops.chapter-review.pending.${book}.1`, raw: { path, body }, path, body,
    retry: "Retry the same command", clear: "I checked the version history",
    view: <ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={() => {}} />,
    getResponses: { [root + "/review"]: { latest: null, versions: [], revision_tasks: [] } },
    successBody: { saved: true }, successStatus: 200 });
});
