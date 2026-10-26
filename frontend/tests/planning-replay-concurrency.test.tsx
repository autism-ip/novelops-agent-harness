import { afterEach, test } from "vitest";
import { StoryPlanning } from "../src/components/books/story-planning";
import { exerciseReplayRecovery, resetReplayBoundary } from "./helpers/saved-replay-contract";
const book = `BK-${"a".repeat(32)}`;
const path = `/api/books/${book}/bibles`, body = { book_id: book, base_state_artifact_id: `AR-${"c".repeat(32)}`,
  base_version: 2, version: 3, change_scope: "major", feedback: "Keep the original cost" };
afterEach(resetReplayBoundary);
test("same-turn planning replay/replay/clear retains one owned request through unknown outcome and exact recovery", async () => {
  await exerciseReplayRecovery({ key: `novelops.story-planning.pending.${book}`, raw: { path, body }, path, body,
    retry: "Retry the same request", clear: "I checked the history", view: <StoryPlanning bookId={book} approvedBible />,
    getResponses: { [`/api/books/${book}/bibles`]: [], [`/api/books/${book}/chapters/1/briefs`]: [] },
    successBody: { saved: true }, successStatus: 201 });
});
