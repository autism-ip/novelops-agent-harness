import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HotspotsWorkbench } from "../src/components/hotspots/workbench";
import type { Hotspot, WorkflowRun } from "../src/api/types";

const timestamp = "2026-10-08T00:00:00Z";
const storageKey = "novelops.hotspots.pending";
function hotspot(id: number, source: "douyin" | "manual" = "douyin"): Hotspot {
  return { hotspot_id: `HS-${id}`, title: `Idea ${id}`, source, url: "https://example.test/source",
    rank: id, heat_value: 100, category: "fiction", captured_at: timestamp, status: "normalized",
    dedupe_hash: `hash-${id}`, raw_json: { original: id } };
}
function fixture(initial: Hotspot[] = [], signedIn = true) {
  const rows = [...initial];
  const runs: WorkflowRun[] = [];
  const commands: { path: string; body: Record<string, unknown> }[] = [];
  const known = new Map<string, WorkflowRun>();
  let authorized = signedIn;
  let interrupt = false;
  let rejection: number | null = null;
  let collectionEnabled = true;
  const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://frontend.test");
    const path = url.pathname;
    if (path === "/api/auth/login") {
      const body = JSON.parse(String(init?.body));
      if (body.password !== "workspace-password") return Response.json({ detail: "Invalid credentials" }, { status: 401 });
      authorized = true;
      return Response.json({ detail: "Login successful" });
    }
    if (!authorized) return Response.json({ detail: "Authentication required" }, { status: 401 });
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      commands.push({ path, body });
      if (rejection !== null) { const status = rejection; rejection = null; return Response.json({ detail: "Request rejected" }, { status }); }
      const previous = known.get(body.request_key);
      if (previous) return Response.json(previous);
      if (path === "/api/hotspots/manual") rows.push({ ...hotspot(rows.length + 1, "manual"), title: body.title, url: body.url, category: body.category });
      else if (path === "/api/hotspots/fetch") rows.push(hotspot(rows.length + 1));
      else if (path.endsWith("/discard")) {
        const row = rows.find(item => path === `/api/hotspots/${item.hotspot_id}/discard`);
        if (!row || body.expected_status !== row.status) return Response.json({ detail: "Stale hotspot" }, { status: 409 });
        row.status = "discarded";
      }
      const run: WorkflowRun = { pipeline_run_id: `PR-${runs.length + 1}`, pipeline_type: path === "/api/hotspots/manual" ? "hotspot_manual_v1" : path === "/api/hotspots/fetch" ? "hotspot_ingestion_v1" : "hotspot_discard_v1",
        status: "completed", created_at: timestamp, updated_at: timestamp, steps: [] };
      runs.push(run); known.set(body.request_key, run);
      if (interrupt) { interrupt = false; throw new TypeError("Connection dropped after commit"); }
      return Response.json(run);
    }
    if (path === "/api/hotspots/capabilities") return Response.json({ fetch: collectionEnabled, manual_add: true, discard: true, analyze: false });
    if (path === "/api/workflows") return Response.json(runs);
    if (path.startsWith("/api/workflows/")) return Response.json(runs.find(item => path.endsWith(item.pipeline_run_id)));
    if (path === "/api/hotspots") {
      const offset = Number(url.searchParams.get("offset"));
      const filtered = rows.filter(row => (!url.searchParams.get("source") || row.source === url.searchParams.get("source")) &&
        (!url.searchParams.get("status") || row.status === url.searchParams.get("status")));
      return Response.json({ items: filtered.slice(offset, offset + 20), total: filtered.length, offset, limit: 20 });
    }
    const row = rows.find(item => path === `/api/hotspots/${item.hotspot_id}`);
    if (row) return Response.json(row);
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal("fetch", transport);
  return { rows, runs, commands, transport, interruptNextWrite: () => { interrupt = true; },
    rejectNextWrite: (status: number) => { rejection = status; }, disableCollection: () => { collectionEnabled = false; } };
}

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function () { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });


test("unavailable request storage blocks writes until a public recheck succeeds", async () => {
  const store = fixture();
  const read = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("Storage blocked", "SecurityError"); });
  render(<HotspotsWorkbench />);
  await screen.findByText(/Cannot read saved requests/);
  expect((screen.getByRole("button", { name: "Fetch public hotspots" }) as HTMLButtonElement).disabled).toBe(true);
  expect(store.commands).toHaveLength(0);
  read.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "Check request storage" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Fetch public hotspots" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Fetch public hotspots" }));
  await within(await screen.findByRole("table")).findByRole("button", { name: "Idea 1" });
  expect(store.commands).toHaveLength(1);
});

test("storage becoming unreadable before activation prevents any write and surfaces recovery", async () => {
  const store = fixture(); render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  const read = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("Storage blocked", "SecurityError"); });
  fireEvent.click(screen.getByRole("button", { name: "Fetch public hotspots" }));
  await screen.findByText(/Cannot read saved requests/);
  expect(store.commands).toHaveLength(0);
  expect((screen.getByRole("button", { name: "Fetch public hotspots" }) as HTMLButtonElement).disabled).toBe(true);
  read.mockRestore();
});

test("failed corrupt-intent clearance preserves original bytes and recovers through the same control", async () => {
  const store = fixture(); sessionStorage.setItem(storageKey, "{unreadable");
  render(<HotspotsWorkbench />); await screen.findByText(/Saved request is unreadable/);
  const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("Clear denied", "SecurityError"); });
  fireEvent.click(screen.getByRole("button", { name: "I have checked recent workflows" }));
  await screen.findByText(/Could not clear saved request.*Clear denied/);
  expect(sessionStorage.getItem(storageKey)).toBe("{unreadable"); expect(store.commands).toHaveLength(0);
  expect((screen.getByRole("button", { name: "Fetch public hotspots" }) as HTMLButtonElement).disabled).toBe(true);
  remove.mockRestore(); fireEvent.click(screen.getByRole("button", { name: "I have checked recent workflows" }));
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(screen.queryByText(/Could not clear saved request/)).toBeNull();
});

test("rejected new write and failed clearance show both causes and retain exact retry identity", async () => {
  const store = fixture(); store.rejectNextWrite(422); render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("Clear denied", "SecurityError"); });
  fireEvent.click(screen.getByRole("button", { name: "Fetch public hotspots" }));
  await screen.findByText(/Request rejected.*Could not clear saved request.*Clear denied/);
  const saved = sessionStorage.getItem(storageKey); expect(JSON.parse(saved!)).toEqual(store.commands[0]);
  expect(store.rows).toHaveLength(0);
  expect((screen.getByRole("button", { name: "Retry same request" }) as HTMLButtonElement).disabled).toBe(false);
  remove.mockRestore(); fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(store.commands).toHaveLength(2); expect(store.commands[1]).toEqual(store.commands[0]); expect(store.rows).toHaveLength(1);
});

test("committed write with failed clearance replays the exact command without a second workflow", async () => {
  const store = fixture(); render(<HotspotsWorkbench />); await screen.findByText("No hotspot workflows yet.");
  const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("Clear denied", "SecurityError"); });
  fireEvent.click(screen.getByRole("button", { name: "Fetch public hotspots" }));
  await screen.findByText(/Could not clear saved request.*Clear denied/);
  const saved = sessionStorage.getItem(storageKey); expect(JSON.parse(saved!)).toEqual(store.commands[0]);
  expect(store.rows).toHaveLength(1); expect(store.runs).toHaveLength(1);
  remove.mockRestore(); fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
  expect(store.commands).toHaveLength(2); expect(store.commands[1]).toEqual(store.commands[0]);
  expect(store.rows).toHaveLength(1); expect(store.runs).toHaveLength(1);
});
