import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import BooksPage from "../src/app/books/page";
import BookPage from "../src/app/books/[bookId]/page";

const id = "BK-source ?one";
const root = `/api/books/${encodeURIComponent(id)}`;
const book = { book_id: id, book_title: "The tidal ledger", genre: "Urban mystery", status: "ready",
  created_at: "2026-10-16T00:00:00Z", story_state_version: 2 };
const state = { story_state_id: "SS-source", version: 2, artifact_id: "AR-state", content_hash: "canonical-hash",
  source_refs: ["AR-opportunity", "AR-title", "AR-cover"], created_at: book.created_at,
  content: { StoryBible: { bible_artifact_id: "AR-bible", rule: "Every recovered object costs a secret" },
    ReaderPromise: { core_emotions: ["Curiosity", "Cost"], themes: [], promise: "", unresolved: null,
      planned_count: 3, limits: { no_free_recovery: true } } } };

function transport(view: unknown, status = 200) {
  const fetch = vi.fn(async (input: unknown, init?: RequestInit) => {
    const path = String(input);
    if ((init?.method ?? "GET") !== "GET") throw new Error(`Unexpected mutation ${path}`);
    if (path === root || path === "/api/books") return Response.json(view, { status });
    if (path === `${root}/bibles` || path === `${root}/chapters/1/briefs`) return Response.json([]);
    if (path === `${root}/chapters/1/generation/latest`) return Response.json(null);
    if (path === `${root}/chapters/1/review`) return Response.json({ latest: null, versions: [], revision_tasks: [] });
    if (path === `${root}/chapters/1/brief/eligible`) return Response.json({ detail: "No current policy-eligible ChapterBrief" }, { status: 409 });
    throw new Error(`Unexpected read ${path}`);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

test("the books route sends an empty workspace back to the source workflow", async () => {
  const fetch = transport([]);
  render(<BooksPage />);
  expect(screen.getByRole("status").textContent).toBe("Loading books…");
  expect(await screen.findByRole("heading", { name: "No books yet" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Go to hotspots" }).getAttribute("href")).toBe("/hotspots");
  expect(fetch).toHaveBeenCalledOnce();
});

test("the books route preserves canonical status, legacy fallback and encoded destinations", async () => {
  transport([book, { ...book, book_id: "BK-legacy", book_title: "Older book", genre: "", story_state_version: undefined }]);
  render(<BooksPage />);
  const canonical = await screen.findByRole("link", { name: /The tidal ledger/ });
  expect(canonical.getAttribute("href")).toBe(`/books/${encodeURIComponent(id)}`);
  expect(canonical.textContent).toContain("StoryState v2 · ready");
  const legacy = screen.getByRole("link", { name: /Older book/ });
  expect(legacy.textContent).toContain("Legacy book");
  expect(legacy.textContent).toContain("Genre to be developed");
});

test.each([401, 503])("a books read failure %s is visible and cannot appear as an empty workspace", async status => {
  transport({ detail: "Book store unavailable" }, status);
  render(<BooksPage />);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe(status === 401 ? "Sign in to continue in this workspace." : "Book store unavailable");
  expect(screen.queryByText("No books yet")).toBeNull();
});

test.each([false, true])("a state-less book (legacy=%s) stays readable without enabling chapter generation", async legacy => {
  const fetch = transport({ book, state: null, legacy });
  render(await BookPage({ params: Promise.resolve({ bookId: id }) }));
  expect(await screen.findByRole("heading", { name: book.book_title })).toBeTruthy();
  expect(screen.getByRole("link", { name: "← All books" }).getAttribute("href")).toBe("/books");
  expect(screen.getByText(legacy ? /has not been migrated/ : /Retry the original creation request/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Generate chapter" })).toBeNull();
  expect(fetch).toHaveBeenCalledOnce();
});

test("a canonical detail route presents source provenance and rules alongside real planning and generation controls", async () => {
  const fetch = transport({ book, state });
  render(await BookPage({ params: Promise.resolve({ bookId: id }) }));
  expect(await screen.findByRole("heading", { name: book.book_title })).toBeTruthy();
  expect(screen.getByText("Canonical StoryState · v2")).toBeTruthy();
  const bible = screen.getByRole("heading", { name: "Story Bible" }).closest("section")!;
  expect(within(bible).getByText("Every recovered object costs a secret")).toBeTruthy();
  const promise = screen.getByRole("heading", { name: "Reader Promise" }).closest("section")!;
  expect(within(promise).getByText("Curiosity · Cost")).toBeTruthy();
  expect(within(promise).getAllByText("Not defined yet")).toHaveLength(3);
  expect(within(promise).getByText("3")).toBeTruthy();
  expect(within(promise).getByText('{"no_free_recovery":true}')).toBeTruthy();
  const provenance = screen.getByText("Version and source provenance").closest("details")!;
  expect(within(provenance).getByText("SS-source")).toBeTruthy();
  expect(within(provenance).getByText("AR-state")).toBeTruthy();
  expect(within(provenance).getByText("canonical-hash")).toBeTruthy();
  expect(within(provenance).getByText("AR-opportunity · AR-title · AR-cover")).toBeTruthy();
  expect((await screen.findByRole("button", { name: "Generate chapter" }) as HTMLButtonElement).disabled).toBe(true);
  expect(await screen.findByText("Approve the StoryBible and generate a current chapter brief first.")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(fetch.mock.calls.every(([, init]) => (init?.method ?? "GET") === "GET")).toBe(true);
});

test("a missing book is reported without rendering a stale canonical state", async () => {
  transport({ detail: "Book not found" }, 404);
  render(await BookPage({ params: Promise.resolve({ bookId: id }) }));
  expect((await screen.findByRole("alert")).textContent).toBe("Book not found");
  expect(screen.queryByRole("heading", { name: book.book_title })).toBeNull();
  expect(screen.queryByText("Version and source provenance")).toBeNull();
});
