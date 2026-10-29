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

function fillManual(title: string) {
  fireEvent.click(screen.getByRole("button", { name: "Add manually" }));
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("Source URL"), { target: { value: "https://example.test/idea" } });
  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "adventure" } });
  fireEvent.click(screen.getByRole("button", { name: "Save hotspot" }));
}

test("pagination and filters reset selection to the visible results", async () => {
  fixture(Array.from({ length: 21 }, (_, i) => hotspot(i + 1, i === 20 ? "manual" : "douyin")));
  render(<HotspotsWorkbench />);
  await screen.findByRole("button", { name: "Idea 1" });
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Idea 1" }));
  expect(screen.getByText("1 selected")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await screen.findByRole("button", { name: "Idea 21" });
  expect(screen.getByText("0 selected")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Previous" }));
  await screen.findByRole("button", { name: "Idea 1" });
  fireEvent.change(screen.getByLabelText("Source", { selector: "select" }), { target: { value: "manual" } });
  await screen.findByRole("button", { name: "Idea 21" });
  expect(screen.queryByRole("button", { name: "Idea 1" })).toBeNull();
  expect((screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement).disabled).toBe(true);
});

test("manual add, detail and discard preserve the exact user command", async () => {
  const store = fixture();
  render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  fillManual("A new idea");
  await screen.findByRole("button", { name: "A new idea" });
  expect(store.commands[0].body).toMatchObject({ title: "A new idea", url: "https://example.test/idea", category: "adventure" });
  expect(typeof store.commands[0].body.request_key).toBe("string");
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "A new idea" }));
  const dialog = await screen.findByRole("dialog", { name: "Hotspot details" });
  await within(dialog).findByText("A new idea");
  expect(within(dialog).getByRole("link", { name: "Open source" }).getAttribute("rel")).toBe("noopener noreferrer");
  fireEvent.click(within(dialog).getByRole("button", { name: "Discard hotspot" }));
  await waitFor(() => expect(store.rows[0].status).toBe("discarded"));
  expect(store.commands[1]).toMatchObject({ path: "/api/hotspots/HS-1/discard", body: { expected_status: "normalized" } });
  await waitFor(() => expect((within(dialog).getByRole("button", { name: "Discard hotspot" }) as HTMLButtonElement).disabled).toBe(true));
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("an interrupted create survives remount and retries the same saved identity", async () => {
  const store = fixture();
  store.interruptNextWrite();
  const first = render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  fillManual("Uncertain idea");
  await screen.findByText("Connection dropped after commit");
  const saved = sessionStorage.getItem(storageKey);
  expect(saved).not.toBeNull();
  first.unmount();
  render(<HotspotsWorkbench />);
  await screen.findByRole("button", { name: "Retry same request" });
  fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
  await waitFor(() => expect(store.commands).toHaveLength(2));
  expect(store.commands[1]).toEqual(store.commands[0]);
  expect(store.rows).toHaveLength(1);
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
});

test("authentication failures show a sign-in flow that refreshes data after success", async () => {
  fixture([], false);
  render(<HotspotsWorkbench />);
  await screen.findByText("Sign in to NovelOps");
  fireEvent.change(screen.getByLabelText("Workspace password"), { target: { value: "wrong" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("Invalid workspace password. Try again.");
  fireEvent.change(screen.getByLabelText("Workspace password"), { target: { value: "workspace-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("No hotspots match these filters. Fetch public hotspots or add an idea manually.");
  expect(screen.queryByText("Sign in to NovelOps")).toBeNull();
});

test("public collection uses a new key and displays the persisted workflow", async () => {
  const store = fixture();
  render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  fireEvent.click(screen.getByRole("button", { name: "Fetch public hotspots" }));
  await screen.findByRole("button", { name: "Idea 1" });
  expect(store.commands[0]).toMatchObject({ path: "/api/hotspots/fetch", body: { limit: 50 } });
  expect(String(store.commands[0].body.request_key)).not.toBe("");
  expect(screen.getByText("Run: PR-1")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Hide workflow details" }));
  expect(screen.queryByText("Run: PR-1")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Collect public hotspots/ }));
  await screen.findByText("Run: PR-1");
});

test("disabled collection and invalid date range prevent unsafe requests", async () => {
  const store = fixture([hotspot(1)]);
  store.disableCollection();
  render(<HotspotsWorkbench />);
  await screen.findByRole("button", { name: "Idea 1" });
  expect((screen.getByRole("button", { name: "Fetch public hotspots" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Public collection is unavailable/)).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Idea 1" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Idea 1" }));
  expect(screen.getByText("0 selected")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Captured from"), { target: { value: "2026-10-09" } });
  fireEvent.change(screen.getByLabelText("Captured through"), { target: { value: "2026-10-08" } });
  expect(screen.getByText("Start date must precede end date.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Idea 1" })).toBeNull();
  fireEvent.change(screen.getByLabelText("Captured from"), { target: { value: "" } });
  await screen.findByRole("button", { name: "Idea 1" });
  fireEvent.change(screen.getByLabelText("Status", { selector: "select" }), { target: { value: "discarded" } });
  await screen.findByText("No hotspots match these filters. Fetch public hotspots or add an idea manually.");
});

test("a rejected new command clears intent while a rejected uncertain retry retains it", async () => {
  const store = fixture();
  store.rejectNextWrite(422);
  const first = render(<HotspotsWorkbench />);
  await screen.findByText("No hotspot workflows yet.");
  fillManual("Rejected idea");
  await screen.findByText("Request rejected");
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect(store.rows).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByText("New manual hotspot")).toBeNull();
  first.unmount();
  const pending = { path: "/api/hotspots/manual", body: { request_key: "uncertain-key", title: "Earlier idea", url: "", category: "" } };
  sessionStorage.setItem(storageKey, JSON.stringify(pending));
  store.rejectNextWrite(409);
  render(<HotspotsWorkbench />);
  fireEvent.click(await screen.findByRole("button", { name: "Retry same request" }));
  await screen.findByText("Request rejected");
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? "null")).toEqual(pending);
  expect(screen.getByRole("button", { name: "Retry same request" })).toBeTruthy();
});

test("corrupt saved commands block new work until history is checked", async () => {
  fixture();
  sessionStorage.setItem(storageKey, "invalid-json");
  render(<HotspotsWorkbench />);
  await screen.findByText(/Saved request is unreadable/);
  expect((screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "I have checked recent workflows" }));
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  await waitFor(() => expect((screen.getByRole("button", { name: "Add manually" }) as HTMLButtonElement).disabled).toBe(false));
});
