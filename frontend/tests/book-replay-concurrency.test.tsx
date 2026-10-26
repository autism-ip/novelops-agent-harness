import { afterEach, test } from "vitest";
import { BookBootstrap } from "../src/components/books/book-bootstrap";
import { exerciseReplayRecovery, resetReplayBoundary } from "./helpers/saved-replay-contract";
const book = `BK-${"a".repeat(32)}`, run = `PR-${"b".repeat(32)}`;
const context = { book_id: book, cover_run_id: run, cover_artifact_id: `AR-${"c".repeat(32)}`,
  title_artifact_id: `AR-${"d".repeat(32)}`, opportunity_artifact_id: `AR-${"e".repeat(32)}` };
afterEach(resetReplayBoundary);
test("same-turn book replay/replay/clear retains one owned request through unknown outcome and exact recovery", async () => {
  await exerciseReplayRecovery({ key: `novelops.books.bootstrap.${run}`, raw: context, path: "/api/books", body: context,
    retry: "Retry the same book request", clear: "I checked the Books list", view: <BookBootstrap coverRunId={run} disabled={false} />,
    getResponses: {}, successBody: { book: { book_id: book } }, successStatus: 201 });
});
