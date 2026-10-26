import { afterEach, test } from "vitest";
import { ChapterGeneration } from "../src/components/books/chapter-generation";
import { exerciseReplayRecovery, resetReplayBoundary } from "./helpers/saved-replay-contract";
const book = `BK-${"a".repeat(32)}`, artifact = `AR-${"c".repeat(32)}`, root = `/api/books/${book}/chapters/1`;
const path = root + "/generations", body = { book_id: book, chapter_no: 1, version: 2, start_version_no: 1,
  state_artifact_id: artifact, state_version: 2, brief_artifact_id: artifact, brief_version: 1,
  source_version_id: "", constraints: { must_keep: [], must_change: [], do_not_change: [] } };
afterEach(resetReplayBoundary);
test("same-turn generation replay/replay/clear retains one owned request through unknown outcome and exact recovery", async () => {
  await exerciseReplayRecovery({ key: `novelops.chapter-generation.pending.${book}`, raw: { path, body }, path, body,
    retry: "Retry the same request", clear: "I checked the history", view: <ChapterGeneration bookId={book} />,
    getResponses: { [root + "/generation/latest"]: null, [root + "/brief/eligible"]: {
      artifact_id: artifact, version: 1, content: {}, source_refs: [] },
    [root + "/review"]: { latest: null, versions: [], revision_tasks: [] } },
    successBody: { saved: true }, successStatus: 201 });
});
