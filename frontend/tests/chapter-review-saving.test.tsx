import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";

vi.mock("@/components/hotspots/editor-identity", () => ({
  useEditorIdentity: () => ({ operator: "editor", update: vi.fn() }),
}));
const book = `BK-${"a".repeat(32)}`;
const run = `PR-${"b".repeat(32)}`;
const version = `CV-${"c".repeat(32)}`;
const artifact = `AR-${"d".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
const storageKey = `novelops.chapter-review.pending.${book}.1`;
const chapter = {
  latest: { run: { pipeline_run_id: run, status: "completed" }, current: true,
    selected: { artifact_id: artifact, version: 1,
      content: { title: "Garden at dawn", prose: "Mira opens the garden gate." }, source_refs: [] },
    usage: { attempts: 2, input_tokens: 100, output_tokens: 50, estimated_cost: null, retries: 0 } },
  versions: [{ record: { version_id: version, version_no: 1, status: "review",
    chapter_title: "Garden at dawn", content: "Mira opens the garden gate.", artifact_id: artifact },
    artifact: { artifact_id: artifact, version: 1,
      content: { title: "Garden at dawn", prose: "Mira opens the garden gate." }, source_refs: [] },
    legacy: false, report: null, verification: null }],
  revision_tasks: [], review_gate: { step_id: "gate", status: "success", output_version: 1 },
};
afterEach(() => { cleanup(); sessionStorage.clear(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function transportWithWriteDelay(delay: number | null) {
  let bodiesRead = 0;
  let finishRefresh: () => void = () => undefined;
  const refreshed = new Promise<void>(resolve => { finishRefresh = resolve; });
  const transport = vi.fn((_input: unknown, init: RequestInit) => {
    if (init.method !== "POST") {
      const response = Response.json(chapter);
      const readBody = response.json.bind(response);
      response.json = async () => {
        const body = await readBody();
        if (++bodiesRead >= 2) finishRefresh();
        return body;
      };
      return Promise.resolve(response);
    }
    return new Promise<Response>((resolve, reject) => {
      const timer = delay === null ? null : setTimeout(() => resolve(Response.json({ saved: true })), delay);
      init.signal?.addEventListener("abort", () => {
        if (timer !== null) clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      });
    });
  });
  vi.stubGlobal("fetch", transport);
  return { transport, refreshed };
}

async function openDesk() {
  const onChanged = vi.fn();
  const view = render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("Mira opens the garden gate.")).toBeTruthy();
  return { onChanged, view };
}

test.each([
  ["Approve", "/review/decision", { action: "approve", reason: "" }],
  ["Reject", "/review/decision", { action: "reject", reason: "" }],
  ["Lock final", "/final-lock", {}],
  ["Create revision and rewrite", "/review/revision", { constraints: {
    must_keep: [], must_change: ["Sharper dialogue"], do_not_change: [] } }],
] as const)("%s can save a 34-second exact chapter action once", async (label, suffix, extra) => {
  vi.useFakeTimers();
  const { transport, refreshed } = transportWithWriteDelay(34_463);
  const { onChanged } = await openDesk();
  if (suffix === "/review/revision") {
    fireEvent.click(screen.getByText("Request a constrained revision"));
    fireEvent.change(screen.getByLabelText("Must change"), { target: { value: "  Sharper dialogue  " } });
  }
  const button = screen.getByRole("button", { name: label }) as HTMLButtonElement;
  fireEvent.click(button);
  fireEvent.click(button);
  expect(button.disabled).toBe(true);
  expect(screen.getByText("Saving your chapter action… This may take a minute.")).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect(onChanged).not.toHaveBeenCalled();
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(1);
  const [path, init] = writes[0];
  expect(path).toBe(root + suffix);
  expect(init.signal?.aborted).toBe(false);
  expect(init.headers).not.toHaveProperty("x-api-key");
  expect(JSON.parse(String(init.body))).toEqual({ version_id: version, artifact_id: artifact,
    version_no: 1, operator: "editor", ...(suffix === "/final-lock" ? {} : {
      run_id: run, expected_gate_version: 0 }), ...extra });
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? "null").path).toBe(root + suffix);
  await act(async () => { await vi.advanceTimersByTimeAsync(24_463); });
  // POST acknowledgement starts a separate refresh GET. Wait for its body
  // so both request deadlines have completed before checking timer cleanup.
  await act(async () => { await refreshed; });
  expect(onChanged).toHaveBeenCalledOnce();
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(1);
  expect(vi.getTimerCount()).toBe(0);
});

test("a hung action expires at 120 seconds and retries only the persisted exact command", async () => {
  vi.useFakeTimers();
  const { transport, refreshed } = transportWithWriteDelay(null);
  const { onChanged, view } = await openDesk();
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(119_999); });
  expect(screen.queryByRole("alert")).toBeNull();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(screen.getByRole("alert").textContent).toContain("Request timed out");
  const pending = sessionStorage.getItem(storageKey);
  expect(pending).not.toBeNull();
  expect(onChanged).not.toHaveBeenCalled();
  const first = transport.mock.calls.find(([, init]) => init.method === "POST");
  expect(first?.[1].signal?.aborted).toBe(true);
  transport.mockImplementationOnce(() => Promise.resolve(Response.json({ saved: true })));
  fireEvent.click(screen.getByRole("button", { name: "Retry the same command" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(2);
  expect(writes[1][0]).toBe(first?.[0]);
  expect(writes[1][1].body).toBe(first?.[1].body);
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  // POST acknowledgement starts a separate refresh GET. Wait for its body
  // so both request deadlines have completed before checking timer cleanup.
  await act(async () => { await refreshed; });
  expect(onChanged).toHaveBeenCalledOnce();
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});
