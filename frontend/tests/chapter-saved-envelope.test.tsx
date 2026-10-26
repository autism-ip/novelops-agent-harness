import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChapterGeneration } from "../src/components/books/chapter-generation";
import { parsePendingChapter } from "../src/components/books/chapter-state";

const book = `BK-${"a".repeat(32)}`, artifact = `AR-${"b".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`, key = `novelops.chapter-generation.pending.${book}`;
const body = { book_id: book, chapter_no: 1, version: 2, start_version_no: 1,
  state_artifact_id: artifact, state_version: 2, brief_artifact_id: artifact, brief_version: 1,
  source_version_id: "", constraints: { must_keep: [], must_change: [], do_not_change: [] } };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

test.each([null, "not an object", false])("a malformed saved chapter body %s stays unreadable without being sent", async value => {
  const bytes = JSON.stringify({ path: root + "/generations", body: value }); sessionStorage.setItem(key, bytes);
  const posts: Request[] = [];
  vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init);
    if (request.method === "POST") { posts.push(request); return Response.json({ detail: "Synthetic unknown outcome" }, { status: 503 }); }
    const path = new URL(request.url).pathname;
    if (path === root + "/generation/latest") return Response.json(null);
    if (path === root + "/brief/eligible") return Response.json({ artifact_id: artifact, version: 1, content: {}, source_refs: [] });
    if (path === root + "/review") return Response.json({ latest: null, versions: [], revision_tasks: [] });
    throw new Error(`Unexpected saved chapter read ${path}`);
  });
  render(<ChapterGeneration bookId={book} />); await act(async () => {});
  const retry = screen.queryByRole("button", { name: "Retry the same request" }); if (retry) fireEvent.click(retry);
  await act(async () => {});
  expect(posts).toHaveLength(0);
  expect(screen.queryByRole("button", { name: "Retry the same request" })).toBeNull();
  expect(screen.getByText("The saved request is unreadable. Check the chapter history before clearing it.")).toBeTruthy();
  expect(sessionStorage.getItem(key)).toBe(bytes);
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" })); expect(sessionStorage.getItem(key)).toBeNull();
});

test.each([null, "constraints are not an object", {},
  { must_keep: "not a list", must_change: [], do_not_change: [] },
  { must_keep: [], must_change: ["unapproved revision"], do_not_change: [] }])(
  "an ordinary generation cannot replay malformed or unapproved revision constraints: %s", constraints => {
    const command = { path: root + "/generations", body: { ...body, constraints } };
    expect(parsePendingChapter(JSON.stringify(command), book)).toBeNull();
  });
