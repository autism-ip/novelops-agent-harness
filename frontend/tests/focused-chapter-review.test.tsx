import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChapterReviewPage from "../src/app/books/[bookId]/chapters/[chapterNo]/review/page";

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NEXT_NOT_FOUND"); } }));
const book = `BK-${"a".repeat(32)}`;
const run = `PR-${"b".repeat(32)}`;
const version = `CV-${"c".repeat(32)}`;
const artifact = `AR-${"d".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
function review(approved = false) {
  const selected = { artifact_id: artifact, version: 9, content: { title: "The returned pin", prose: "The pin reaches its owner." }, source_refs: [] };
  return { latest: { run: { pipeline_run_id: run, status: approved ? "completed" : "awaiting_approval" }, current: true,
      selected, snapshot_artifact_id: "snapshot", usage: { attempts: 2, input_tokens: 30, output_tokens: 20, estimated_cost: 0.01, latency_ms: 20, retries: 0 } },
    versions: [{ record: { version_id: version, version_no: 9, status: approved ? "approved" : "review", chapter_title: "The returned pin", content: selected.content.prose, artifact_id: artifact },
      artifact: selected, legacy: false, report: null, verification: null }], revision_tasks: [],
    review_gate: { step_id: "gate", status: approved ? "success" : "awaiting_approval", output_version: 1 } };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); sessionStorage.clear(); });

test.each([
  ["", "1"], ["x".repeat(201), "1"], ["book/other", "1"], ["../book", "1"],
  [book, "0"], [book, "10001"], [book, "-1"], [book, "1.5"], [book, "01"], [book, "NaN"],
])("invalid review routes reject before loading business data (%s, %s)", async (bookId, chapterNo) => {
  const transport = vi.fn(); vi.stubGlobal("fetch", transport);
  await expect(ChapterReviewPage({ params: Promise.resolve({ bookId, chapterNo }) })).rejects.toThrow("NEXT_NOT_FOUND");
  expect(transport).not.toHaveBeenCalled();
});

test.each(["1", "10000"])("valid chapter route binds its own book and chapter %s", async chapterNo => {
  const transport = vi.fn().mockResolvedValue(Response.json({ latest: null, versions: [], revision_tasks: [] }));
  vi.stubGlobal("fetch", transport);
  render(await ChapterReviewPage({ params: Promise.resolve({ bookId: book, chapterNo }) }));
  expect(screen.getByRole("heading", { name: `Chapter ${chapterNo} review`, level: 1 })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Back to book" }).getAttribute("href")).toBe(`/books/${book}`);
  await screen.findByText("Generate a chapter to open its review desk.");
  expect(transport).toHaveBeenCalledOnce();
  expect(transport.mock.calls[0][0]).toBe(`/api/books/${book}/chapters/${chapterNo}/review`);
});

test("focused review loads only its review endpoint, stays quiet at the human gate, and refreshes on request", async () => {
  vi.useFakeTimers();
  const transport = vi.fn().mockImplementation(() => Promise.resolve(Response.json(review())));
  vi.stubGlobal("fetch", transport);
  render(await ChapterReviewPage({ params: Promise.resolve({ bookId: book, chapterNo: "1" }) }));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("The pin reaches its owner.")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Chapter review desk", level: 2 })).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(transport).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "Refresh review" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(transport).toHaveBeenCalledTimes(2);
  expect(transport.mock.calls.every(([url]) => url === root + "/review")).toBe(true);
});

test("a focused approval preserves the exact target and refreshes the persisted review", async () => {
  let approved = false;
  const transport = vi.fn((url: unknown, init: RequestInit) => {
    if (init.method === "POST") { approved = true; return Promise.resolve(Response.json({ saved: true })); }
    return Promise.resolve(Response.json(review(approved)));
  });
  vi.stubGlobal("fetch", transport);
  render(await ChapterReviewPage({ params: Promise.resolve({ bookId: book, chapterNo: "1" }) }));
  await screen.findByLabelText("Editor identity");
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "Mei" } });
  fireEvent.change(screen.getByLabelText("Decision note"), { target: { value: "Return and cost verified" } });
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Lock final" }) as HTMLButtonElement).disabled).toBe(false));
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toBe(root + "/review/decision");
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ run_id: run, version_id: version,
    artifact_id: artifact, version_no: 9, operator: "Mei", expected_gate_version: 1,
    action: "approve", reason: "Return and cost verified" });
  expect(sessionStorage.getItem(`novelops.chapter-review.pending.${book}.1`)).toBeNull();
  expect(transport.mock.calls.filter(([, init]) => (init.method ?? "GET") === "GET")).toHaveLength(2);
});
