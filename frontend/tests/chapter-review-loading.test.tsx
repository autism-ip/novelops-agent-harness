import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";

vi.mock("@/components/hotspots/editor-identity", () => ({
  useEditorIdentity: () => ({ operator: "editor", update: vi.fn() }),
}));
const chapter = {
  latest: { run: { pipeline_run_id: "run", status: "completed" }, current: true,
    selected: { artifact_id: "chapter-artifact", version: 1,
      content: { title: "Garden at dawn", prose: "Mira opens the garden gate." }, source_refs: [] },
    snapshot_artifact_id: "snapshot", usage: { attempts: 2, input_tokens: 100, output_tokens: 50,
      estimated_cost: null, latency_ms: 100, retries: 0 } },
  versions: [{ record: { version_id: "chapter-version", version_no: 1, status: "review",
    chapter_title: "Garden at dawn", content: "Mira opens the garden gate.", artifact_id: "chapter-artifact" },
    artifact: { artifact_id: "chapter-artifact", version: 1,
      content: { title: "Garden at dawn", prose: "Mira opens the garden gate." }, source_refs: [] },
    legacy: false, report: null, verification: null }],
  revision_tasks: [], review_gate: { step_id: "gate", status: "success", output_version: 1 },
};
afterEach(() => { cleanup(); sessionStorage.clear(); vi.useRealTimers(); vi.unstubAllGlobals(); });

test("the real review hook/client can render a 65-second persisted chapter read", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((_input: unknown, init: RequestInit) => new Promise<Response>((resolve, reject) => {
    const timer = setTimeout(() => resolve(Response.json(chapter)), 65_460);
    init.signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  }));
  vi.stubGlobal("fetch", transport);
  render(<ChapterReviewDesk bookId="book" chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByRole("status").textContent).toContain("Loading chapter review");
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect(transport.mock.calls[0][1].signal?.aborted).toBe(false);
  await act(async () => { await vi.advanceTimersByTimeAsync(55_460); });
  expect(screen.getByText("Mira opens the garden gate.")).toBeTruthy();
  expect(screen.queryByRole("status")).toBeNull();
  expect(transport).toHaveBeenCalledOnce();
  expect(vi.getTimerCount()).toBe(0);
});

test("a hung chapter read still has a bounded deadline and usable recovery", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((_input: unknown, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  }));
  vi.stubGlobal("fetch", transport);
  const view = render(<ChapterReviewDesk bookId="book" chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(119_999); });
  expect(transport).toHaveBeenCalledOnce();
  expect(screen.queryByRole("alert")).toBeNull();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(screen.getByRole("alert").textContent).toContain("Request timed out");
  expect(transport.mock.calls[0][1].signal?.aborted).toBe(true);
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});
