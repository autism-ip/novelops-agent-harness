import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HotspotsWorkbench } from "../src/components/hotspots/workbench";
import type { Hotspot, OpportunityAnalysis, WorkflowRun } from "../src/api/types";

const stamp = "2026-10-26T00:00:00Z", key = "novelops.hotspots.pending";
const rows: Hotspot[] = [1, 2, 3].map(i => ({ hotspot_id: `HS-${i}`, title: `Garden idea ${i}`,
  source: "manual", url: "", rank: i, heat_value: 100, category: "fiction", captured_at: stamp,
  status: i === 2 ? "discarded" : "normalized", dedupe_hash: String(i).repeat(64), raw_json: {} }));
const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.open = true; } });
});
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
});

for (const surface of ["table", "mobile card"] as const) {
  test(`${surface} selection preserves exact eligible identities and synchronizes both responsive surfaces`, async () => {
    const requests: Request[] = [];
    let finishContext!: () => void;
    let savedAtPost: string | null = null;
    vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
      const request = new Request(new URL(String(url), "http://frontend.test"), init); requests.push(request);
      const path = new URL(request.url).pathname;
      if (request.method === "POST") {
        if (path !== "/api/analyses") throw new Error(`Unexpected write ${path}`);
        savedAtPost = sessionStorage.getItem(key);
        return Response.json({ runs: [], errors: [] }, { status: 201 });
      }
      if (path === "/api/hotspots") return Response.json({ items: rows, total: 3, offset: 0, limit: 20 });
      if (path === "/api/hotspots/capabilities") return Response.json({ fetch: true, manual_add: true, discard: true, analyze: true });
      if (path === "/api/workflows") return Response.json([]);
      if (path === "/api/hotspots/HS-3/research-context") return await new Promise<Response>(resolve => {
        finishContext = () => resolve(Response.json({ can_analyze: true, source_hash: rows[2].dedupe_hash, next_version: 3 }));
      });
      throw new Error(`Unexpected selection read ${path}`);
    });
    render(<HotspotsWorkbench />);
    const table = await screen.findByRole("table");
    const boxes = (row: Hotspot) => screen.getAllByRole("checkbox", { name: `Select ${row.title}` }) as HTMLInputElement[];
    const box = (row: Hotspot) => surface === "table"
      ? within(table).getByRole("checkbox", { name: `Select ${row.title}` })
      : boxes(row).find(input => !input.closest("table"))!;
    fireEvent.click(box(rows[0])); fireEvent.click(box(rows[2]));
    for (const row of [rows[0], rows[2]]) expect(boxes(row).map(input => input.checked)).toEqual([true, true]);
    fireEvent.click(box(rows[0])); expect(boxes(rows[0]).map(input => input.checked)).toEqual([false, false]);
    for (const input of boxes(rows[1])) { expect(input.disabled).toBe(true); input.click(); expect(input.checked).toBe(false); }
    const analyze = screen.getByRole("button", { name: "Analyze selected" }) as HTMLButtonElement;
    await waitFor(() => expect(analyze.disabled).toBe(false)); fireEvent.click(analyze);
    await waitFor(() => expect(requests.filter(r => new URL(r.url).pathname.endsWith("/research-context"))).toHaveLength(1));
    expect(requests.find(r => new URL(r.url).pathname.endsWith("/research-context"))?.url).toBe("http://frontend.test/api/hotspots/HS-3/research-context");
    expect(requests.filter(r => r.method === "POST")).toHaveLength(0);
    expect(analyze.disabled).toBe(true);
    expect(screen.getByText("Preparing request…")).toBeTruthy();
    for (const row of rows) for (const input of boxes(row)) expect(input.disabled).toBe(true);
    await act(async () => finishContext());
    await waitFor(() => expect(requests.filter(r => r.method === "POST")).toHaveLength(1));
    const post = requests.find(r => r.method === "POST")!;
    expect(await post.clone().json()).toEqual({ request_key: expect.any(String), items: [
      { hotspot_id: "HS-3", source_hash: rows[2].dedupe_hash, version: 3 } ] });
    expect(JSON.parse(savedAtPost!)).toEqual({ path: "/api/analyses", body: await post.clone().json() });
    await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
    expect(requests.filter(r => r.method === "POST")).toHaveLength(1);
  });
}

test("canceling the native mobile detail dialog preserves an existing unknown command and sends no write", async () => {
  const original = "{unconfirmed-command"; sessionStorage.setItem(key, original);
  const requests: Request[] = [];
  vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init); requests.push(request);
    if (request.method !== "GET") throw new Error("Cancel must never submit a command");
    const path = new URL(request.url).pathname;
    if (path === "/api/hotspots") return Response.json({ items: rows, total: 3, offset: 0, limit: 20 });
    if (path === "/api/hotspots/capabilities") return Response.json({ fetch: false, manual_add: true, discard: true, analyze: false });
    if (path === "/api/workflows") return Response.json([]);
    if (path === "/api/hotspots/HS-1") return Response.json(rows[0]);
    throw new Error(`Unexpected detail read ${path}`);
  });
  render(<HotspotsWorkbench />); const table = await screen.findByRole("table");
  fireEvent.click(within(table).getByRole("button", { name: rows[0].title }));
  const dialog = await screen.findByRole("dialog", { name: "Hotspot details" });
  expect(await within(dialog).findByRole("heading", { name: rows[0].title })).toBeTruthy();
  const cancel = new Event("cancel", { bubbles: true, cancelable: true }); fireEvent(dialog, cancel);
  expect(cancel.defaultPrevented).toBe(true);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(sessionStorage.getItem(key)).toBe(original);
  expect(requests.every(r => r.method === "GET")).toBe(true);
  expect(screen.getByRole("heading", { name: "Hotspots", level: 1 })).toBeTruthy();
});

test("recent research and future hotspot workflows expose their own state while unrelated types stay out of hotspot activity", async () => {
  const runs: WorkflowRun[] = [
    { pipeline_run_id: "PR-research", pipeline_type: "hotspot_research_v1", status: "failed", created_at: stamp, updated_at: stamp,
      steps: [{ step_run_id: "SR-risk", step_key: "risk", status: "failed", error_message: "Risk source unavailable" }] },
    { pipeline_run_id: "PR-other", pipeline_type: "unrelated_workflow", status: "completed", created_at: stamp, updated_at: stamp },
    { pipeline_run_id: "PR-future", pipeline_type: "hotspot_future_workflow", status: "completed", created_at: stamp, updated_at: stamp },
  ];
  const analysis: OpportunityAnalysis = { run: runs[0], request: { version: 2, hotspot_id: rows[0].hotspot_id },
    source: { title: rows[0].title }, current: true, approval_status: "failed", decisions: [], opportunity: null, risk: null };
  const requests: Request[] = [];
  vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init); requests.push(request);
    if (request.method !== "GET") throw new Error("Recent workflow inspection must be read-only");
    const path = new URL(request.url).pathname;
    if (path === "/api/hotspots") return Response.json({ items: [], total: 0, offset: 0, limit: 20 });
    if (path === "/api/hotspots/capabilities") return Response.json({ fetch: false, manual_add: true, discard: true, analyze: false });
    if (path === "/api/workflows") return Response.json(runs);
    const run = runs.find(r => path === `/api/workflows/${r.pipeline_run_id}`);
    if (run) return Response.json(run);
    if (path === "/api/analyses/PR-research") return Response.json(analysis);
    throw new Error(`Unexpected recent workflow read ${path}`);
  });
  render(<HotspotsWorkbench />);
  const recent = screen.getByRole("region", { name: "Recent workflows" });
  const researchButton = await within(recent).findByRole("button", { name: /Research story opportunities/ });
  fireEvent.click(researchButton);
  expect(await within(recent).findByText("Run: PR-research")).toBeTruthy();
  expect(await within(recent).findByText(/Risk source unavailable — Refresh/)).toBeTruthy();
  expect(await within(recent).findByRole("heading", { name: `${rows[0].title} · Version 2` })).toBeTruthy();
  expect(within(recent).getByText("risk")).toBeTruthy();
  fireEvent.click(within(recent).getByRole("button", { name: "Hide workflow details" }));
  expect(within(recent).queryByText("Run: PR-research")).toBeNull();
  expect(within(recent).getAllByRole("button")).toHaveLength(2);
  fireEvent.click(within(recent).getByRole("button", { name: /Hotspot workflow/ }));
  expect(await within(recent).findByText("Run: PR-future")).toBeTruthy();
  await waitFor(() => expect(within(recent).queryByText("risk")).toBeNull());
  expect(requests.some(r => new URL(r.url).pathname === "/api/workflows/PR-other")).toBe(false);
  expect(within(recent).queryByText("risk")).toBeNull();
  expect(within(recent).queryByRole("heading", { name: /Garden idea 1/ })).toBeNull();
  expect(requests.every(r => r.method === "GET")).toBe(true);
  expect(sessionStorage.getItem(key)).toBeNull();
});
