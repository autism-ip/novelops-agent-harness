import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";
import { parsePendingReview } from "../src/components/books/review-state";

const book = `BK-${"a".repeat(32)}`;
const otherBook = `BK-${"b".repeat(32)}`;
const target = { run_id: `PR-${"c".repeat(32)}`, version_id: `CV-${"d".repeat(32)}`,
  artifact_id: `AR-${"e".repeat(32)}`, version_no: 9, operator: "Original editor", expected_gate_version: 7 };
const empty = { latest: null, versions: [], revision_tasks: [] };
function command(bookId: string, chapterNo: number, action: string) {
  const root = `/api/books/${bookId}/chapters/${chapterNo}`;
  if (action === "revision") return { path: root + "/review/revision", body: { ...target,
    constraints: { must_keep: ["Keep the setting"], must_change: ["Clarify the cost"], do_not_change: [] } } };
  if (action === "final-lock") return { path: root + "/final-lock", body: {
    version_id: target.version_id, artifact_id: target.artifact_id, version_no: target.version_no,
    operator: target.operator } };
  return { path: root + "/review/decision", body: { ...target, action, reason: "Exact previous decision" } };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

for (const action of ["approve", "reject", "revision", "final-lock"]) {
  test.each([[otherBook, 1], [book, 2]] as const)(
    `${action} saved under another book or chapter never posts from this review desk: %s/%s`,
    async (bookId, chapterNo) => {
      const key = `novelops.chapter-review.pending.${book}.1`;
      const original = JSON.stringify(command(bookId, chapterNo, action));
      sessionStorage.setItem(key, original);
      const transport = vi.fn((_url: unknown, init: RequestInit) => Promise.resolve(init.method === "POST"
        ? Response.json({ detail: "Unexpected foreign review target" }, { status: 409 }) : Response.json(empty)));
      vi.stubGlobal("fetch", transport);
      const onChanged = vi.fn();
      render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
      await screen.findByText("Generate a chapter to open its review desk.");
      const retry = screen.queryByRole("button", { name: "Retry the same command" });
      if (retry) fireEvent.click(retry);
      await act(async () => {});
      expect(transport.mock.calls.filter(([, init]) => init.method === "POST").map(([url, init]) => ({
        path: url, body: JSON.parse(String(init.body)),
      }))).toEqual([]);
      expect(screen.queryByRole("button", { name: "Retry the same command" })).toBeNull();
      expect(screen.getByText("The saved review command is unreadable. Check the version history before clearing it.")).toBeTruthy();
      expect(sessionStorage.getItem(key)).toBe(original);
      expect(onChanged).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole("button", { name: "I checked the version history" }));
      expect(sessionStorage.getItem(key)).toBeNull();
      expect(transport.mock.calls.every(([url]) => url === `/api/books/${book}/chapters/1/review`)).toBe(true);
    });

  test.each([1, 10000])(`${action} replays only its own scoped command at chapter %s`, async chapterNo => {
    const key = `novelops.chapter-review.pending.${book}.${chapterNo}`;
    const exact = command(book, chapterNo, action);
    sessionStorage.setItem(key, JSON.stringify(exact));
    const transport = vi.fn((_url: unknown, init: RequestInit) => Promise.resolve(Response.json(
      init.method === "POST" ? { saved: true } : empty)));
    vi.stubGlobal("fetch", transport);
    const onChanged = vi.fn();
    render(<ChapterReviewDesk bookId={book} chapterNo={chapterNo} refresh={0} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry the same command" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
    const posts = transport.mock.calls.filter(([, init]) => init.method === "POST");
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe(exact.path);
    expect(JSON.parse(String(posts[0][1].body))).toEqual(exact.body);
    expect(posts[0][1].headers).not.toHaveProperty("x-api-key");
    expect(sessionStorage.getItem(key)).toBeNull();
  });
}

test.each([10001, Number.MAX_SAFE_INTEGER, 1e100])(
  "unsupported saved chapter %s is never a replayable command", chapterNo => {
    expect(parsePendingReview(JSON.stringify(command(book, chapterNo, "approve")))).toBeNull();
  });
