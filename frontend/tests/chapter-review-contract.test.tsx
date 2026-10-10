import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";

const book = `BK-${"1".repeat(32)}`;
const run = `PR-${"2".repeat(32)}`;
const version = `CV-${"3".repeat(32)}`;
const artifact = `AR-${"4".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
const pendingKey = `novelops.chapter-review.pending.${book}.1`;
const command = { path: root + "/review/decision", body: {
  run_id: run, version_id: version, artifact_id: artifact, version_no: 1,
  operator: "editor", expected_gate_version: 0, action: "approve", reason: "" } };
const empty = { latest: null, versions: [], revision_tasks: [] };

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); sessionStorage.clear(); vi.unstubAllGlobals(); });

test.each([JSON.stringify(command), "{unreadable"])(
  "clearing checked history reports storage failure and preserves saved intent: %s", async saved => {
    sessionStorage.setItem(pendingKey, saved);
    const transport = serve(empty);
    render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
    await screen.findByText("Generate a chapter to open its review desk.");
    const remove = vi.spyOn(Object.getPrototypeOf(sessionStorage), "removeItem")
      .mockImplementation(() => { throw new Error("Cannot clear saved command"); });
    fireEvent.click(screen.getByRole("button", { name: "I checked the version history" }));
    expect(await screen.findByText("Could not clear the saved review command. Cannot clear saved command Check browser storage access and try again.")).toHaveProperty("role", "alert");
    expect(sessionStorage.getItem(pendingKey)).toBe(saved);
    expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
    remove.mockRestore();
    fireEvent.click(screen.getByRole("button", { name: "I checked the version history" }));
    await waitFor(() => expect(sessionStorage.getItem(pendingKey)).toBeNull());
    expect(screen.queryByRole("button", { name: "Retry the same command" })).toBeNull();
    expect(screen.queryByText(/Could not clear the saved review command/)).toBeNull();
  });

function completedReview() {
  const oldArtifact = `AR-${"5".repeat(32)}`;
  const oldVersion = `CV-${"6".repeat(32)}`;
  const selected = { artifact_id: artifact, version: 2,
    content: { title: "Shared garden", prose: "Mira and the neighbors reopen the garden." },
    source_refs: ["AR-snapshot-v2", "AR-brief-v2", oldArtifact] };
  const report = { artifact_id: "AR-critic-v1", version: 1,
    content: { summary: "The gate scene needs clearer dialogue.", decision: "revise",
      pacing: { score: 3, evidence: "The middle scene slows down." } },
    source_refs: ["AR-snapshot-v1", "AR-brief-v1", oldArtifact] };
  return {
    latest: { run: { pipeline_run_id: run, status: "completed" }, current: true,
      selected, critique: report, snapshot_artifact_id: "AR-snapshot-v2",
      usage: { attempts: 3, input_tokens: 150, output_tokens: 75, estimated_cost: 0.02, latency_ms: 40, retries: 1 } },
    versions: [
      { record: { version_id: version, version_no: 2, status: "review", chapter_title: "Shared garden",
          content: selected.content.prose, artifact_id: artifact },
        artifact: selected, legacy: false, report,
        verification: { artifact_id: "AR-verifier-v2", version: 2,
          content: { checks: { exact_sources: true, prose_length: true } }, source_refs: [artifact] } },
      { record: { version_id: oldVersion, version_no: 1, status: "candidate", chapter_title: "Old gate scene",
          content: "The original gate scene remains in history.", artifact_id: oldArtifact },
        artifact: { artifact_id: oldArtifact, version: 1,
          content: { title: "Old gate scene", prose: "The original gate scene remains in history." },
          source_refs: ["AR-snapshot-v1", "AR-brief-v1"] }, legacy: false, report,
        verification: { artifact_id: "AR-verifier-v1", version: 1,
          content: { checks: { exact_sources: true, forbidden_literal: false } }, source_refs: [oldArtifact] } },
    ],
    story_bible: { artifact_id: "AR-bible", version: 1,
      content: { premise: "A shared magical garden", protagonist: "Mira" }, source_refs: [] },
    brief: { artifact_id: "AR-brief-v2", version: 2, source_refs: [], content: {
      opening_hook: "The gate opens at dawn", scene_goal: "Find the seed", conflict: "The map is missing",
      payoff: "Neighbors cooperate", ending_hook: "The flower speaks" } },
    snapshot: { artifact_id: "AR-snapshot-v2", version: 2, content: { state_artifact_id: "AR-story-state" }, source_refs: [] },
    story_state: { Characters: { protagonist: "Mira" } },
    revision_tasks: [
      { revision_task_id: "RT-1", from_version_id: oldVersion, status: "queued", run_status: "running" },
      { revision_task_id: "RT-2", from_version_id: "missing-old-version", status: "open", run_status: null },
    ],
    review_gate: { step_id: "SR-gate", status: "success", output_version: 2 },
    traces: [
      { kind: "model", route: "writer", model: "fixture-writer", prompt_version: "writer-v3", latency_ms: 40 },
      { kind: "model", route: "critic", model: "fixture-critic", prompt_version: "critic-v2" },
      { kind: "service", route: "internal-service", model: "not-a-model", prompt_version: "service-v1" },
    ],
  };
}

function serve(data: unknown) {
  const transport = vi.fn((_input: unknown, init: RequestInit) => Promise.resolve(
    Response.json(init.method === "POST" ? { saved: true } : data)));
  vi.stubGlobal("fetch", transport);
  return transport;
}
async function open(data: unknown = completedReview()) {
  const transport = serve(data);
  const onChanged = vi.fn();
  const view = render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  await screen.findByLabelText("Editor identity");
  return { transport, onChanged, view };
}

test("the real editor identity disables blank signatures and binds a trimmed decision note", async () => {
  const { transport, onChanged } = await open();
  const approve = screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement;
  expect(approve.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "   " } });
  expect(approve.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "  Mei  " } });
  expect(approve.disabled).toBe(false);
  expect(sessionStorage.getItem("novelops.editor.name")).toBe("  Mei  ");
  fireEvent.change(screen.getByLabelText("Decision note"), { target: { value: "  Ready for publication  " } });
  fireEvent.click(approve);
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toBe(root + "/review/decision");
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ ...command.body,
    version_no: 2, operator: "Mei", action: "approve", reason: "Ready for publication" });
  expect(writes[0][1].headers).not.toHaveProperty("x-api-key");
  expect(sessionStorage.getItem(pendingKey)).toBeNull();
});

test("sources, quality checks and revision progress stay bound to the displayed version", async () => {
  await open();
  expect(screen.getByText("A shared magical garden")).toBeTruthy();
  expect(screen.getByText("The flower speaks")).toBeTruthy();
  fireEvent.click(screen.getByText("Quality dimensions"));
  expect(screen.getByText("pacing · 3/5")).toBeTruthy();
  expect(screen.getByText("The middle scene slows down.")).toBeTruthy();
  expect(screen.getByText("style · ?/5")).toBeTruthy();
  expect(screen.getAllByText("No evidence")).toHaveLength(6);
  fireEvent.click(screen.getByText("Deterministic checks"));
  expect(screen.getByText("✓ exact sources")).toBeTruthy();
  fireEvent.click(screen.getByText("Sources, usage and trace"));
  expect(screen.getByText("Chapter artifact").nextElementSibling?.textContent).toBe(artifact);
  expect(screen.getByText("150 input · 75 output")).toBeTruthy();
  expect(screen.getByText("0.02")).toBeTruthy();
  expect(screen.getByText("writer · fixture-writer · writer-v3 · 40 ms")).toBeTruthy();
  expect(screen.getByText("critic · fixture-critic · critic-v2 · ? ms")).toBeTruthy();
  expect(screen.queryByText(/internal-service/)).toBeNull();
  expect(screen.getByText("Revision tasks: v1 → run running · v? → open")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "v1 · candidate" }));
  expect(screen.getByText("The original gate scene remains in history.")).toBeTruthy();
  expect(screen.getByText("! forbidden literal")).toBeTruthy();
  expect(screen.getByText("Chapter artifact").nextElementSibling?.textContent).toBe(completedReview().versions[1].artifact.artifact_id);
  expect(screen.getByText("AR-snapshot-v1")).toBeTruthy();
  expect(screen.getByText("AR-brief-v1")).toBeTruthy();
  expect(screen.queryByText(/This Critic report scored v1 before the rewrite/)).toBeNull();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
});

test("absent usage and legacy artifact sources are shown as unavailable rather than invented", async () => {
  const review = completedReview();
  await open({ ...review,
    latest: { ...review.latest, usage: { ...review.latest.usage,
      input_tokens: null, output_tokens: null, estimated_cost: null } },
    versions: [review.versions[0], { ...review.versions[1], artifact: null, legacy: true,
      report: null, verification: null }],
    story_bible: undefined, brief: undefined, snapshot: undefined, story_state: undefined,
  });
  fireEvent.click(screen.getByText("Sources, usage and trace"));
  expect(screen.getByText("unknown input · unknown output")).toBeTruthy();
  expect(screen.getByText("unavailable")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "v1 · candidate" }));
  expect(screen.getByText("The original gate scene remains in history.")).toBeTruthy();
  expect(screen.getByText("Legacy version: exact Artifact provenance is unavailable.")).toBeTruthy();
  expect(screen.getByText("The structured critique appears after a verified draft.")).toBeTruthy();
  expect(screen.getByText("Chapter artifact").nextElementSibling?.textContent).toBe("Unavailable");
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(3);
});

test("a replay keeps its original version and signature after the editor changes", async () => {
  sessionStorage.setItem(pendingKey, JSON.stringify(command));
  const transport = vi.fn((_input: unknown, init: RequestInit) => {
    const stale = init.method === "POST" && JSON.parse(String(init.body)).version_no === 1;
    return Promise.resolve(Response.json(stale ? { detail: "This version is stale" } :
      init.method === "POST" ? { saved: true } : completedReview(), { status: stale ? 409 : 200 }));
  });
  vi.stubGlobal("fetch", transport);
  const onChanged = vi.fn();
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  await screen.findByLabelText("Editor identity");
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "New editor" } });
  fireEvent.click(screen.getByRole("button", { name: "Retry the same command" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "This version is stale");
  const writes = () => transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes()).toHaveLength(1);
  expect(JSON.parse(String(writes()[0][1].body))).toEqual(command.body);
  expect(JSON.parse(sessionStorage.getItem(pendingKey) ?? "null")).toEqual(command);
  expect(onChanged).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "I checked the version history" }));
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(writes()).toHaveLength(2);
  expect(JSON.parse(String(writes()[1][1].body))).toEqual({ ...command.body,
    version_no: 2, operator: "New editor" });
});

test("expired write authentication preserves exact intent and can recover after sign-in", async () => {
  sessionStorage.setItem("novelops.editor.name", "Signed editor");
  let expired = true;
  const transport = vi.fn((_input: unknown, init: RequestInit) => Promise.resolve(
    Response.json(init.method === "POST" ? { saved: !expired } : completedReview(),
      { status: init.method === "POST" && expired ? 401 : 200 })));
  vi.stubGlobal("fetch", transport);
  const onChanged = vi.fn();
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  await screen.findByLabelText("Editor identity");
  fireEvent.click(screen.getByRole("button", { name: "Reject" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Sign in to review chapters.");
  const saved = sessionStorage.getItem(pendingKey);
  expect(saved).not.toBeNull();
  expect(onChanged).not.toHaveBeenCalled();
  expired = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry the same command" }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(2);
  expect(writes[0][0]).toBe(writes[1][0]);
  expect(writes[0][1].body).toBe(writes[1][1].body);
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ ...command.body,
    version_no: 2, operator: "Signed editor", action: "reject" });
  expect(sessionStorage.getItem(pendingKey)).toBeNull();
});

test("a blocked browser store retains an in-memory editor name but prevents untracked writes", async () => {
  const { transport, onChanged } = await open();
  const prototype = Object.getPrototypeOf(sessionStorage);
  vi.spyOn(prototype, "getItem").mockImplementation(() => { throw new Error("Storage is blocked"); });
  vi.spyOn(prototype, "setItem").mockImplementation(() => { throw new Error("Storage is blocked"); });
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "Memory editor" } });
  expect(screen.getByLabelText("Editor identity")).toHaveProperty("value", "Memory editor");
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Storage is blocked");
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
  expect(onChanged).not.toHaveBeenCalled();
});

test("loading history remains bounded to a read and shows progress before an empty chapter arrives", async () => {
  let deliver!: (response: Response) => void;
  const transport = vi.fn<(input: unknown, init: RequestInit) => Promise<Response>>()
    .mockImplementation(() => new Promise<Response>(resolve => { deliver = resolve; }));
  vi.stubGlobal("fetch", transport);
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByRole("status").textContent).toContain("Loading chapter review");
  expect(transport).toHaveBeenCalledOnce();
  expect(transport.mock.calls[0][0]).toBe(root + "/review");
  expect(new Request("http://localhost" + root + "/review", transport.mock.calls[0][1]).method).toBe("GET");
  expect(transport.mock.calls[0][1].headers).not.toHaveProperty("x-api-key");
  deliver(Response.json(empty));
  await screen.findByText("Generate a chapter to open its review desk.");
  expect(screen.queryByText(/Loading chapter review/)).toBeNull();
  expect(transport).toHaveBeenCalledOnce();
});

test("server rendering shows loading without leaking tab-local editor or saved command", () => {
  sessionStorage.setItem("novelops.editor.name", "Private editor");
  sessionStorage.setItem(pendingKey, JSON.stringify(command));
  const transport = serve(completedReview());
  const html = renderToString(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(html).toContain("Loading chapter review");
  expect(html).not.toContain("Private editor");
  expect(html).not.toContain("Retry the same command");
  expect(transport).not.toHaveBeenCalled();
  expect(JSON.parse(sessionStorage.getItem(pendingKey) ?? "null")).toEqual(command);
});

test("active runs poll until the selective gate, then approval unlocks final lock", async () => {
  vi.useFakeTimers();
  sessionStorage.setItem("novelops.editor.name", "Gate editor");
  const base = completedReview();
  const gated = { ...base, latest: { ...base.latest, run: { ...base.latest.run, status: "awaiting_approval" } },
    review_gate: { ...base.review_gate, status: "awaiting_approval", output_version: 7 } };
  const states = [
    { ...base, latest: { ...base.latest, selected: null, run: { ...base.latest.run, status: "pending" } }, versions: [] },
    { ...base, latest: { ...base.latest, selected: null, run: { ...base.latest.run, status: "running" } }, versions: [] },
    gated,
  ];
  let reads = 0;
  let approved = false;
  const transport = vi.fn((_input: unknown, init: RequestInit) => {
    if (init.method === "POST") { approved = true; return Promise.resolve(Response.json({ saved: true })); }
    const data = approved ? { ...base, versions: base.versions.map((entry, index) => index === 0
      ? { ...entry, record: { ...entry.record, status: "approved" } } : entry) } : states[Math.min(reads, 2)];
    reads += 1;
    return Promise.resolve(Response.json(data));
  });
  vi.stubGlobal("fetch", transport);
  const onChanged = vi.fn();
  const view = render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("No verified chapter version is ready.")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(screen.getByText("The writing loop is running.")).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(screen.getByText("This chapter needs an editor decision before the run can complete.")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(false);
  expect((screen.getByRole("button", { name: "Lock final" }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
  expect(reads).toBe(3);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(onChanged).toHaveBeenCalledOnce();
  expect(reads).toBe(4);
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Reject" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Lock final" }) as HTMLButtonElement).disabled).toBe(false);
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1].body))).toEqual({ ...command.body,
    version_no: 2, expected_gate_version: 7, operator: "Gate editor" });
  view.unmount();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(vi.getTimerCount()).toBe(0);
});
