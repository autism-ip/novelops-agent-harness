import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChapterGeneration } from "../src/components/books/chapter-generation";
const book = `BK-${"a".repeat(32)}`, otherBook = `BK-${"b".repeat(32)}`;
const key = `novelops.chapter-generation.pending.${book}`;
function command(bookId: string, chapterNo: number) { return {
  path: `/api/books/${bookId}/chapters/${chapterNo}/generations`, body: {
    book_id: bookId, chapter_no: chapterNo, version: 7, start_version_no: 8,
    state_artifact_id: `AR-${"c".repeat(32)}`, state_version: 2,
    brief_artifact_id: `AR-${"d".repeat(32)}`, brief_version: 4,
    source_version_id: "", constraints: { must_keep: [], must_change: [], do_not_change: [] } } }; }
function serve() {
  const transport=vi.fn((url: unknown, init: RequestInit) => Promise.resolve(Response.json(
    init.method === "POST" ? { saved: true } : String(url).endsWith("/generation/latest") ? null :
    String(url).endsWith("/review") ? { latest: null, versions: [], revision_tasks: [] } : { artifact_id: "eligible", content: {} })));
  vi.stubGlobal("fetch",transport); return transport;
}
afterEach(() => { cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();sessionStorage.clear(); });
test.each([[otherBook,3],[book,10001],[book,Number.MAX_SAFE_INTEGER]] as const)(
  "a saved foreign or unsupported chapter never generates from this Book: %s/%s", async (bookId,chapterNo) => {
    const exact=command(bookId,chapterNo),bytes=JSON.stringify(exact);sessionStorage.setItem(key,bytes);
    const transport=serve();render(<ChapterGeneration bookId={book} />);
    await act(async()=>{});
    const retry=screen.queryByRole("button",{name:"Retry the same request"});if(retry)fireEvent.click(retry);await act(async()=>{});
    expect(transport.mock.calls.filter(([,init])=>init.method==="POST").map(([url,init])=>({path:url,body:JSON.parse(String(init.body))}))).toEqual([]);
    expect(screen.queryByRole("button",{name:"Retry the same request"})).toBeNull();
    expect(screen.getByText("The saved request is unreadable. Check the chapter history before clearing it.")).toBeTruthy();
    expect(sessionStorage.getItem(key)).toBe(bytes);
    fireEvent.click(screen.getByRole("button",{name:"I checked the history"}));expect(sessionStorage.getItem(key)).toBeNull();
    expect(transport.mock.calls.some(([url])=>String(url).endsWith("/generation/context"))).toBe(false);
  });
test.each([1,3,10000])("a saved own-Book chapter %s is replayed exactly despite the default chapter field", async chapterNo => {
  const exact=command(book,chapterNo);sessionStorage.setItem(key,JSON.stringify(exact));const transport=serve();render(<ChapterGeneration bookId={book} />);
  expect(screen.getByLabelText("Chapter number")).toHaveProperty("value","1");
  fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await waitFor(()=>expect(sessionStorage.getItem(key)).toBeNull());
  const posts=transport.mock.calls.filter(([,init])=>init.method==="POST");expect(posts).toHaveLength(1);expect(posts[0][0]).toBe(exact.path);expect(JSON.parse(String(posts[0][1].body))).toEqual(exact.body);
  expect(transport.mock.calls.some(([url])=>String(url).endsWith("/generation/context"))).toBe(false);
});
