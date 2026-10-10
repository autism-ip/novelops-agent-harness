import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HotspotsWorkbench } from "../src/components/hotspots/workbench";
import type { Hotspot, WorkflowRun } from "../src/api/types";
const key = "novelops.hotspots.pending", stamp = "2026-10-10T00:00:00Z";
function fixture(partial: boolean) {
  const rows: Hotspot[] = [1, 2].map(i => ({ hotspot_id: `HS-${i}`, title: `Batch idea ${i}`, source: "manual", url: "", rank: i, heat_value: 100, category: "fiction", captured_at: stamp, status: "normalized", dedupe_hash: String(i).repeat(64), raw_json: {} }));
  const run: WorkflowRun = { pipeline_run_id: "PR-batch", pipeline_type: "hotspot_research_v1", status: "completed", created_at: stamp, updated_at: stamp, steps: [] };
  const response = { runs: partial ? [run] : [], errors: rows.slice(partial ? 1 : 0).map(row => ({ hotspot_id: row.hotspot_id, detail: "Source changed before reservation" })) };
  const commands: { path: string; body: Record<string, unknown>; saved: string | null }[] = [];
  const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://frontend.test").pathname;
    if (init?.method === "POST" && path === "/api/analyses") {
      commands.push({ path, body: JSON.parse(String(init.body)), saved: sessionStorage.getItem(key) });
      return Response.json(response, { status: 201 });
    }
    if (path === "/api/hotspots") return Response.json({ items: rows, total: 2, offset: 0, limit: 20 });
    if (path === "/api/hotspots/capabilities") return Response.json({ fetch: true, manual_add: true, discard: true, analyze: true });
    if (path === "/api/workflows") return Response.json(commands.length ? response.runs : []);
    if (path === "/api/workflows/PR-batch") return Response.json(run);
    if (path === "/api/analyses/PR-batch") return Response.json({ run, request: { hotspot_id: "HS-1", version: 1 }, source: rows[0], current: true, approval_status: "approved", decisions: [], opportunity: null, risk: null });
    const row = rows.find(row => path === `/api/hotspots/${row.hotspot_id}/research-context`);
    if (row) return Response.json({ next_version: 1, source_hash: row.dedupe_hash, can_analyze: true });
    throw new Error(`Unexpected HTTP request ${path}`);
  });
  vi.stubGlobal("fetch", transport);
  return { commands, response, rows };
}
beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
for (const partial of [false, true]) {
  test(`${partial ? "partial" : "all"} batch failures survive local clearance failure and exact retry`, async () => {
    const store = fixture(partial); render(<HotspotsWorkbench />); const table = await screen.findByRole("table");
    for (const row of store.rows) fireEvent.click(within(table).getByRole("checkbox", { name: `Select ${row.title}` }));
    const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("Local clear denied", "SecurityError"); });
    fireEvent.click(screen.getByRole("button", { name: "Analyze selected" }));
    await screen.findByText(/HS-2: Source changed before reservation.*Could not clear saved request.*Local clear denied/);
    expect(store.commands).toHaveLength(1);
    const saved = sessionStorage.getItem(key); expect(saved).toBe(store.commands[0].saved);
    expect(JSON.parse(saved!)).toMatchObject({ path: "/api/analyses", body: { items: store.rows.map(row => ({ hotspot_id: row.hotspot_id, source_hash: row.dedupe_hash, version: 1 })) } });
    if (!partial) expect(screen.getByRole("alert").textContent).toContain("HS-1: Source changed before reservation");
    expect((screen.getByRole("button", { name: "Retry same request" }) as HTMLButtonElement).disabled).toBe(false);
    remove.mockRestore(); fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
    expect(store.commands).toHaveLength(2); expect(store.commands[1].body).toEqual(store.commands[0].body);
    expect(screen.getByRole("alert").textContent).toContain("HS-2: Source changed before reservation");
    expect(screen.getByRole("alert").textContent).not.toContain("Local clear denied");
    if (partial) await screen.findByText("Run: PR-batch");
    else expect(screen.queryByText("Run: PR-batch")).toBeNull();
  });
}
