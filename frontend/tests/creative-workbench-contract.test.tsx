import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HotspotsWorkbench } from "../src/components/hotspots/workbench";
import type { CreativeRun, Hotspot, OpportunityAnalysis, WorkflowRun } from "../src/api/types";
const stamp = "2026-10-10T00:00:00Z", storageKey = "novelops.hotspots.pending";
const id = (prefix: string, digit: string) => `${prefix}-${digit.repeat(32)}`;
const sourceRunId = id("PR", "1"), titleRunId = id("PR", "2"), coverRunId = id("PR", "3");
const row: Hotspot = { hotspot_id: id("HS", "1"), title: "The vanished library", source: "manual", url: "https://example.test/library", rank: 1, heat_value: 100, category: "fantasy", captured_at: stamp, status: "normalized", dedupe_hash: "a".repeat(64), raw_json: { original: "Synthetic source" } };
function workflow(runId: string, pipeline: string, status = "completed"): WorkflowRun {
  return { pipeline_run_id: runId, pipeline_type: pipeline, status, created_at: stamp, updated_at: stamp, steps: [] };
}
function creative(kind: "titles" | "covers", selected = true): CreativeRun {
  const run = workflow(kind === "titles" ? titleRunId : coverRunId, kind === "titles" ? "title_candidates_v1" : "cover_plans_v1", selected ? "completed" : "awaiting_approval");
  run.steps = [{ step_run_id: id("SR", kind === "titles" ? "2" : "3"), step_key: "select", status: selected ? "completed" : "awaiting_approval", output_version: 2 }];
  const candidates = Array.from({ length: kind === "titles" ? 10 : 3 }, (_, index) => ({ artifact_id: id("AR", String(index + 1)), version: 2, model: "synthetic-model", prompt_version: "creative-v2", route: "creative-test", content: kind === "titles" ? { title: `Library title ${index + 1}`, hook: "A missing archive", selling_point: "Memory and mystery", click_score: 0.8, genre_fit_score: 0.9, risk_notes: "Synthetic fiction" } : { visual_direction: `Cover direction ${index + 1}`, style: "Minimal ink", main_elements: ["Library", "Key"], cover_prompt: "A library at dawn", negative_prompt: "No text" } }));
  return { run, kind, request: { source_run_id: kind === "titles" ? sourceRunId : titleRunId, source_artifact_id: id("AR", "a"), version: 2 }, current: true, decision: selected ? { choice_id: candidates[0].artifact_id, action: "approve" } : null, candidates };
}
function fixture(options: { titleSelected?: boolean; historical?: boolean; holdHistory?: boolean; researchRevision?: boolean; batchRejected?: boolean } = {}) {
  const title = creative("titles", options.titleSelected ?? true), cover = creative("covers");
  if (options.historical) title.current = false;
  const analysis: OpportunityAnalysis = { run: workflow(sourceRunId, "hotspot_research_v1"), request: { hotspot_id: row.hotspot_id, version: 1 }, source: { title: row.title }, current: true, approval_status: "approved", decisions: [], opportunity: { artifact_id: id("AR", "a"), model: "synthetic-model", prompt_version: "research-v1", route: "research-test", content: { summary: "The city forgets its books", core_emotions: ["Wonder"], hit_patterns: ["Lost memories"], genre_fit: ["Fantasy"], reader_promise: "Solve the archive mystery", novelization_directions: ["An apprentice archivist"] } }, risk: null };
  if (options.researchRevision) {
    analysis.approval_status = "revision_requested";
    analysis.decisions = [{ action: "revise", reason: "Develop the archive mystery", target_id: id("SR", "1"), target_version: 1 }];
  }
  const contexts: { path: string; resolve: (response: Response) => void }[] = [];
  const writes: ((response: Response) => void)[] = [];
  const commands: { path: string; body: Record<string, unknown>; headers: Headers; saved: string | null }[] = [];
  let contextStatus = 200, writeStatus = 200, available = true, interrupt = false, holdContext = false, holdWrites = false, historyStatus = 200, historyResolve: ((response: Response) => void) | undefined;
  const run = workflow(id("PR", "4"), "title_candidates_v1");
  const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://frontend.test"), path = url.pathname;
    if (init?.method === "POST") {
      commands.push({ path, body: JSON.parse(String(init.body)), headers: new Headers(init.headers), saved: sessionStorage.getItem(storageKey) });
      if (writeStatus !== 200) return Response.json({ detail: "Exact decision rejected" }, { status: writeStatus });
      if (interrupt) { interrupt = false; throw new TypeError("Creative outcome unknown"); }
      if (holdWrites) return new Promise<Response>(resolve => writes.push(resolve));
      if (path === "/api/analyses" && options.batchRejected) return Response.json({ runs: [], errors: [{ hotspot_id: row.hotspot_id, detail: "Hotspot discarded after context" }] }, { status: 201 });
      run.pipeline_type = path === "/api/analyses" ? "hotspot_research_v1" : path === "/api/creative/covers" ? "cover_plans_v1" : "title_candidates_v1";
      return Response.json(path === "/api/analyses" ? { runs: [run], errors: [] } : run);
    }
    if (path === "/api/hotspots/capabilities") return Response.json({ fetch: true, manual_add: true, discard: true, analyze: true, creative: true });
    if (path === "/api/hotspots") return Response.json({ items: [row], total: 1, offset: 0, limit: 20 });
    if (path === "/api/workflows") return Response.json([]);
    if (path === `/api/analyses/${run.pipeline_run_id}`) return Response.json({ ...analysis, run, request: { ...analysis.request, version: 3 } });
    if (path === `/api/workflows/${run.pipeline_run_id}`) return Response.json(run);
    if (path === `/api/creative/titles/${run.pipeline_run_id}/runs` || path === `/api/creative/covers/${run.pipeline_run_id}/runs`) return Response.json([]);
    if (path === `/api/hotspots/${row.hotspot_id}`) return Response.json(row);
    if (path === `/api/hotspots/${row.hotspot_id}/analyses`) return Response.json([analysis]);
    if (path.endsWith("/context") || path.endsWith("/research-context")) {
      if (holdContext) return new Promise<Response>(resolve => { contexts.push({ path, resolve }); });
      contexts.push({ path, resolve: () => {} });
      return contextStatus === 200 ? Response.json({ source_artifact_id: id("AR", "b"), next_version: 3, source_hash: "b".repeat(64), can_analyze: available }) : Response.json({ detail: "Source context unavailable" }, { status: contextStatus });
    }
    if (path === `/api/creative/titles/${sourceRunId}/runs`) {
      if (options.holdHistory) return new Promise<Response>(resolve => { historyResolve = resolve; });
      return historyStatus === 200 ? Response.json([title]) : Response.json({ detail: "Candidate history unavailable" }, { status: historyStatus });
    }
    if (path === `/api/creative/covers/${titleRunId}/runs`) return Response.json([cover]);
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal("fetch", transport);
  return { analysis, title, cover, commands, contexts, transport, holdWrites: () => { holdWrites = true; }, finishWrites: async () => { await act(async () => { for (const resolve of writes) resolve(Response.json(run)); }); }, rejectHistory: () => { historyStatus = 503; }, holdContexts: () => { holdContext = true; },
    finishContexts: async () => { await act(async () => { for (const context of contexts) context.resolve(Response.json({ source_artifact_id: id("AR", "b"), next_version: 3, source_hash: "b".repeat(64), can_analyze: available })); }); },
    finishHistory: async () => { await act(async () => { historyResolve?.(Response.json([title])); }); },
    discardSource: () => { available = false; }, rejectWrite: (status: number) => { writeStatus = status; }, rejectContext: (status: number) => { contextStatus = status; }, interruptWrite: () => { interrupt = true; } };
}
beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  Object.defineProperty(HTMLDialogElement.prototype, "show", { configurable: true, value: function () { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function () { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function open() { const table = await screen.findByRole("table"); fireEvent.click(await within(table).findByRole("button", { name: row.title })); return screen.findByRole("dialog", { name: "Hotspot details" }); }
for (const kind of ["titles", "covers"] as const) {
  test(`${kind}: one command owns context preparation, persistence and POST`, async () => {
    const store = fixture(); store.holdContexts(); render(<HotspotsWorkbench />); const dialog = await open();
    const button = await within(dialog).findByRole("button", { name: kind === "titles" ? "Generate next title version" : "Generate next cover version" });
    fireEvent.click(button); fireEvent.click(button);
    const contextCount = store.contexts.length, globalDisabled = (screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled, progress = within(dialog).queryByText("Preparing request…");
    await store.finishContexts(); await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
    expect(contextCount).toBe(1); expect(globalDisabled).toBe(true); expect(progress).not.toBeNull(); expect(store.commands).toHaveLength(1);
    const command = store.commands[0]; expect(command.path).toBe(`/api/creative/${kind}`);
    expect(command.body).toEqual({ source_run_id: kind === "titles" ? sourceRunId : titleRunId, source_artifact_id: id("AR", "b"), version: 3 });
    expect(JSON.parse(command.saved!)).toMatchObject({ path: command.path, body: { ...command.body, request_key: expect.any(String) } }); expect(command.headers.has("x-api-key")).toBe(false);
    await waitFor(() => expect((screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled).toBe(false));
  });
}
for (const status of [401, 409, 503]) {
  test(`context ${status} never persists or submits and allows a fresh retry`, async () => {
    const store = fixture(); store.rejectContext(status); render(<HotspotsWorkbench />); const dialog = await open(); const button = await within(dialog).findByRole("button", { name: "Generate next title version" });
    fireEvent.click(button); await screen.findAllByText(status === 401 ? "Sign in to view and manage hotspots." : "Source context unavailable");
    expect(store.commands).toHaveLength(0); expect(sessionStorage.getItem(storageKey)).toBeNull(); expect((button as HTMLButtonElement).disabled).toBe(false);
    store.rejectContext(200); fireEvent.click(button); await waitFor(() => expect(store.commands).toHaveLength(1)); expect(store.contexts).toHaveLength(2);
  });
}
test("unknown creative outcome survives remount and replays exact prepared source without another GET", async () => {
  const store = fixture(); store.interruptWrite(); const first = render(<HotspotsWorkbench />); const dialog = await open();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Generate next title version" })); await screen.findAllByText("Creative outcome unknown");
  const saved = sessionStorage.getItem(storageKey); expect(saved).not.toBeNull(); first.unmount(); render(<HotspotsWorkbench />);
  fireEvent.click(await screen.findByRole("button", { name: "Retry same request" })); await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(store.commands).toHaveLength(2); expect(store.commands[1].body).toEqual(store.commands[0].body); expect(store.commands[1].saved).toBe(saved); expect(store.contexts).toHaveLength(1);
});
test("unreadable intent blocks creative preparation and preserves its bytes", async () => {
  const store = fixture(); sessionStorage.setItem(storageKey, "{unreadable"); render(<HotspotsWorkbench />); const dialog = await open();
  const button = await within(dialog).findByRole("button", { name: "Generate next title version" }); fireEvent.click(button);
  expect((button as HTMLButtonElement).disabled).toBe(true); expect(store.contexts).toHaveLength(0); expect(store.commands).toHaveLength(0); expect(sessionStorage.getItem(storageKey)).toBe("{unreadable");
});
test("history loading prevents generating an uninformed initial version", async () => {
  const store = fixture({ holdHistory: true }); render(<HotspotsWorkbench />); const dialog = await open(); const button = await within(dialog).findByRole("button", { name: "Generate titles" });
  const disabled = (button as HTMLButtonElement).disabled; fireEvent.click(button); await store.finishHistory();
  expect(disabled).toBe(true); expect(store.contexts).toHaveLength(0); expect(store.commands).toHaveLength(0);
});
test("selection freezes exact candidate Artifact and selection step version", async () => {
  const store = fixture({ titleSelected: false }); render(<HotspotsWorkbench />); const dialog = await open();
  expect(await within(dialog).findByText("1. Library title 1")).toBeTruthy(); expect(within(dialog).getByText("10. Library title 10")).toBeTruthy();
  fireEvent.change(within(dialog).getByLabelText("Editor name"), { target: { value: " Editor Lin " } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Select title 2" })); await waitFor(() => expect(store.commands).toHaveLength(1));
  expect(store.commands[0]).toMatchObject({ path: `/api/creative/runs/${titleRunId}/decision`, body: { step_id: id("SR", "2"), artifact_id: store.title.candidates[1].artifact_id, expected_version: 2, action: "approve", operator: "Editor Lin", reason: "" } }); expect(store.contexts).toHaveLength(0);
});
test("historical titles retain content and provenance without selection or cover generation", async () => {
  const store = fixture({ titleSelected: false, historical: true }); render(<HotspotsWorkbench />); const dialog = await open(); await within(dialog).findByText("Historical version: selection is disabled.");
  expect(within(dialog).getByText("10. Library title 10")).toBeTruthy(); expect(within(dialog).getAllByText(/synthetic-model.*creative-v2/)).toHaveLength(10);
  expect(within(dialog).queryByRole("button", { name: "Select title 1" })).toBeNull(); expect(within(dialog).queryByRole("button", { name: /cover version/ })).toBeNull(); expect(store.commands).toHaveLength(0);
});

test("the exact command stays saved and all creative actions stay disabled until POST completes", async () => {
  const store = fixture(); store.holdWrites(); render(<HotspotsWorkbench />); const dialog = await open();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Generate next cover version" }));
  await waitFor(() => expect(store.commands).toHaveLength(1));
  const progress = within(dialog).queryByText("Saving request…");
  expect(store.commands).toHaveLength(1); const saved = sessionStorage.getItem(storageKey);
  expect(saved).toBe(store.commands[0].saved); expect(saved).not.toBeNull();
  const titleButton = within(dialog).getByRole("button", { name: "Generate next title version" });
  expect((titleButton as HTMLButtonElement).disabled).toBe(true); fireEvent.click(titleButton);
  expect(store.contexts).toHaveLength(1); expect(store.commands).toHaveLength(1);
  await store.finishWrites(); await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(progress).not.toBeNull();
  expect(screen.queryByText("Saving request…")).toBeNull();
});

test("history failure retains a readable cause and blocks generation without GET or POST", async () => {
  const store = fixture(); store.rejectHistory(); render(<HotspotsWorkbench />); const dialog = await open();
  await within(dialog).findByText("Candidate history unavailable");
  const button = within(dialog).getByRole("button", { name: "Generate titles" });
  expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button);
  expect(store.contexts).toHaveLength(0); expect(store.commands).toHaveLength(0);
});

test("failure to persist the prepared creative command prevents every POST and permits recovery", async () => {
  const store = fixture(); render(<HotspotsWorkbench />); const dialog = await open();
  const button = await within(dialog).findByRole("button", { name: "Generate next title version" });
  const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Browser cannot save the request"); });
  fireEvent.click(button); await screen.findAllByText("Browser cannot save the request");
  expect(store.contexts).toHaveLength(1); expect(store.commands).toHaveLength(0); expect(sessionStorage.getItem(storageKey)).toBeNull();
  write.mockRestore(); fireEvent.click(button); await waitFor(() => expect(store.commands).toHaveLength(1));
  expect(store.contexts).toHaveLength(2);
});

test("research revision owns the lock during context GET and submits one exact feedback version", async () => {
  const store = fixture({ researchRevision: true }); store.holdContexts(); render(<HotspotsWorkbench />); const dialog = await open();
  const button = await within(dialog).findByRole("button", { name: "Regenerate analysis from feedback" });
  fireEvent.click(button); fireEvent.click(button);
  const count = store.contexts.length, disabled = (screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled, progress = within(dialog).queryByText("Preparing request…");
  await store.finishContexts();
  expect(count).toBe(1); expect(disabled).toBe(true); expect(progress).not.toBeNull(); expect(store.commands).toHaveLength(1);
  expect(store.commands[0]).toMatchObject({ path: "/api/analyses", body: { request_key: expect.any(String), items: [{ hotspot_id: row.hotspot_id,
    source_hash: "b".repeat(64), version: 3, revision_of: sourceRunId, feedback: "Develop the archive mystery" }] } });
  expect(JSON.parse(store.commands[0].saved!)).toEqual({ path: store.commands[0].path, body: store.commands[0].body });
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
});

function gate(store: ReturnType<typeof fixture>, key: "selection" | "risk_gate" = "selection") {
  store.analysis.approval_status = key === "selection" ? "awaiting_selection" : "awaiting_risk_review";
  store.analysis.run.status = "awaiting_approval";
  store.analysis.run.steps = [{ step_run_id: id("SR", "1"), step_key: key, status: "awaiting_approval", output_version: 4 }];
}
for (const action of ["approve", "reject", "revise"] as const) {
  test(`research ${action} binds editor, note, exact source Artifact and gate version`, async () => {
    const store = fixture(); gate(store); render(<HotspotsWorkbench />); const dialog = await open();
    const section = await within(dialog).findByRole("region", { name: "Opportunity decision" });
    const button = within(section).getByRole("button", { name: action === "approve" ? "Approve opportunity" : action === "reject" ? "Reject" : "Request revision" });
    expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button); expect(store.commands).toHaveLength(0);
    fireEvent.change(await within(section).findByLabelText("Editor name"), { target: { value: "  Editor Chen  " } });
    if (action === "revise") {
      fireEvent.click(button); await within(section).findByText("Add revision feedback before requesting changes."); expect(store.commands).toHaveLength(0);
    }
    fireEvent.change(within(section).getByLabelText("Decision note or revision request"), { target: { value: "  Strengthen the reader promise  " } });
    fireEvent.click(button); await waitFor(() => expect(store.commands).toHaveLength(1));
    expect(store.commands[0]).toMatchObject({ path: `/api/analyses/${sourceRunId}/decision`, body: { step_id: id("SR", "1"), artifact_id: id("AR", "a"), expected_version: 4, action, operator: "Editor Chen", reason: "Strengthen the reader promise" } });
    expect(store.commands[0].body).not.toHaveProperty("request_key"); expect(store.commands[0].headers.has("x-api-key")).toBe(false);
    expect(sessionStorage.getItem("novelops.editor.name")).toBe("  Editor Chen  ");
    await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  });
}
for (const action of ["reject", "revise"] as const) {
  test(`creative ${action} uses the selection version and preserves revision feedback`, async () => {
    const store = fixture({ titleSelected: false }); render(<HotspotsWorkbench />); const dialog = await open();
    const section = await within(dialog).findByRole("region", { name: "Title candidates" });
    fireEvent.change(await within(section).findByLabelText("Editor name"), { target: { value: " Editor Lin " } });
    const button = within(section).getByRole("button", { name: action === "revise" ? "Request revision" : "Reject titles" });
    if (action === "revise") {
      fireEvent.click(button); await within(section).findByText("Add revision feedback before requesting changes."); expect(store.commands).toHaveLength(0);
    }
    fireEvent.change(within(section).getByLabelText("Decision note or revision request"), { target: { value: "  Emphasize the missing archive  " } });
    fireEvent.click(button); await waitFor(() => expect(store.commands).toHaveLength(1));
    expect(store.commands[0]).toMatchObject({ path: `/api/creative/runs/${titleRunId}/decision`, body: { step_id: id("SR", "2"), artifact_id: "", action, expected_version: 2, operator: "Editor Lin", reason: "Emphasize the missing archive" } });
  });
}
for (const kind of ["titles", "covers"] as const) {
  test(`${kind} regeneration retains the exact revised source run and previous feedback`, async () => {
    const store = fixture(); const result = kind === "titles" ? store.title : store.cover;
    result.decision = { choice_id: "", action: "revise", reason: "Use a stronger library motif" };
    render(<HotspotsWorkbench />); const dialog = await open();
    // Covers require the original title to remain selected; the revised cover remains visible.
    fireEvent.click(await within(dialog).findByRole("button", { name: `Regenerate ${kind} from feedback` }));
    await waitFor(() => expect(store.commands).toHaveLength(1));
    expect(store.commands[0]).toMatchObject({ path: `/api/creative/${kind}`, body: { source_run_id: kind === "titles" ? sourceRunId : titleRunId,
      source_artifact_id: id("AR", "b"), version: 3, revision_of: result.run.pipeline_run_id, feedback: "Use a stronger library motif" } });
    expect(result.request.version).toBe(2); expect(result.candidates).toHaveLength(kind === "titles" ? 10 : 3);
  });
}

test("a discarded research source rejects regeneration before intent persistence or writes", async () => {
  const store = fixture({ researchRevision: true }); store.discardSource(); render(<HotspotsWorkbench />); const dialog = await open();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Regenerate analysis from feedback" }));
  await screen.findAllByText("This source is no longer available for analysis.");
  expect(store.contexts).toHaveLength(1); expect(store.commands).toHaveLength(0); expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect((screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled).toBe(false);
});

test("historical research revision remains readable and cannot regenerate or approve", async () => {
  const store = fixture({ researchRevision: true }); store.analysis.current = false; render(<HotspotsWorkbench />); const dialog = await open();
  await within(dialog).findByText(/Historical analysis:/);
  expect(within(dialog).queryByRole("region", { name: "Opportunity decision" })).toBeNull();
  expect(within(dialog).getByText("The city forgets its books")).toBeTruthy();
  expect(store.commands).toHaveLength(0); expect(store.contexts).toHaveLength(0);
});

test("risk approval uses the risk gate and its exact immutable opportunity Artifact", async () => {
  const store = fixture(); gate(store, "risk_gate"); store.analysis.risk = { content: { level: "high", requires_review: true, rule_flags: ["Named person"],
    assessments: [{ reasons: ["Potential factual claim"], uncertainties: ["Missing source confirmation"], flags: ["Verify attribution"], confidence: 0.8 }] } };
  render(<HotspotsWorkbench />); const dialog = await open();
  expect(await within(dialog).findByText("Human risk review is required before this opportunity can continue.")).toBeTruthy();
  expect(within(dialog).getByText("Rule flags: Named person")).toBeTruthy();
  fireEvent.change(within(dialog).getByLabelText("Editor name"), { target: { value: "Risk editor" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Approve risk" })); await waitFor(() => expect(store.commands).toHaveLength(1));
  expect(store.commands[0].body).toMatchObject({ step_id: id("SR", "1"), artifact_id: id("AR", "a"), action: "approve", expected_version: 4, operator: "Risk editor" });
});

test("rejected approval shows the cause and clears only the new exact decision intent", async () => {
  const store = fixture(); gate(store); store.rejectWrite(409); render(<HotspotsWorkbench />); const dialog = await open();
  fireEvent.change(await within(dialog).findByLabelText("Editor name"), { target: { value: "Editor Lin" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Approve opportunity" })); await screen.findAllByText("Exact decision rejected");
  expect(store.commands).toHaveLength(1); expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect((within(dialog).getByRole("button", { name: "Approve opportunity" }) as HTMLButtonElement).disabled).toBe(false);
});


test("known HTTP 201 research item failure is visible inside the current mobile dialog", async () => {
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  const store = fixture({ researchRevision: true, batchRejected: true }); render(<HotspotsWorkbench />); const dialog = await open();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Regenerate analysis from feedback" }));
  await within(dialog).findByText(`${row.hotspot_id}: Hotspot discarded after context`);
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(store.commands).toHaveLength(1); expect(store.contexts).toHaveLength(1);
  expect(store.commands[0]).toMatchObject({ path: "/api/analyses", body: { items: [{ hotspot_id: row.hotspot_id, version: 3, source_hash: "b".repeat(64), revision_of: sourceRunId, feedback: "Develop the archive mystery" }] } });
  expect((within(dialog).getByRole("button", { name: "Regenerate analysis from feedback" }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.queryByRole("button", { name: "Retry same request" })).toBeNull();
});
