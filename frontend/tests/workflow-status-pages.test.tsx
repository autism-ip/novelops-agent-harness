/**
 * [INPUT]: Real workspace pages/hooks with controlled fetch and viewport geometry.
 * [OUTPUT]: Persisted workflow/status contracts and settled asynchronous reveal assertions.
 * [POS]: ZEN-107 workflow observation regression gate; no production effect replacement.
 */
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PipelinesPage from "../src/app/pipelines/page";
import AgentsPage from "../src/app/agents/page";
import DashboardPage from "../src/app/page";

const running = { backend_status: "running", worker_status: "running", feishu_status: "connected", opencli_status: "not_configured", active_pipeline_runs: 1, pending_steps: 2, failed_steps: 0, last_tick: "2026-10-18T06:00:00Z", last_error: null };
const run = { pipeline_run_id: "PR-live", pipeline_type: "hotspot_ingestion_v1", status: "running", created_at: "2026-10-18T06:00:00Z", updated_at: "2026-10-18T06:01:00Z" };
const steps = [ { step_run_id: "SR-fetch", step_key: "fetch", kind: "tool", status: "success" }, { step_run_id: "SR-agent", step_key: "research", kind: "agent", status: "running" } ];
function backend(options: { runs?: unknown[]; detail?: unknown; runtime?: unknown; fail?: string; status?: number } = {}) {
  const transport = vi.fn(async (input: unknown, init?: RequestInit) => {
    const path = String(input);
    if (path === options.fail) return Response.json({ detail: "Workflow history is unavailable" }, { status: options.status ?? 503 });
    if (path === "/api/system/status") return Response.json(options.runtime ?? running);
    if (path === "/api/workflows") return Response.json(options.runs ?? [run]);
    if (path === "/api/workflows/PR-live") return Response.json(options.detail ?? { ...run, steps });
    throw new Error(`Unexpected ${init?.method ?? "GET"} ${path}`);
  });
  vi.stubGlobal("fetch", transport); return transport;
}
const scroll = vi.fn();
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
beforeEach(() => { scroll.mockReset(); Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scroll }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); if (originalScroll) Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScroll); else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView"); });

test("pipelines displays real persisted runs and their steps through read-only endpoints", async () => {
  const transport = backend(); render(<PipelinesPage />);
  const inspect = await screen.findByRole("button", { name: /Collect public hotspots/ });
  expect(screen.queryByText("No pipelines yet")).toBeNull();
  fireEvent.click(inspect);
  const detail = await screen.findByRole("region", { name: "Workflow details" });
  expect(await within(detail).findByText("fetch")).toBeTruthy();
  expect(document.activeElement).toBe(detail);
  expect(within(detail).getByRole("link", { name: "Back to workflows" }).getAttribute("href")).toBe("#recorded-workflows");
  expect(within(detail).getByText("research")).toBeTruthy();
  expect(within(detail).getByText("PR-live")).toBeTruthy();
  expect(transport.mock.calls.every(([path, init]) => ["/api/workflows", "/api/workflows/PR-live", "/api/system/status"].includes(String(path)) && (!init?.method || init.method === "GET"))).toBe(true);
});

test("unknown workflow history shows loading instead of a fabricated empty state", () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); render(<PipelinesPage />);
  expect(screen.getByText("Loading workflows…")).toBeTruthy();
  expect(screen.queryByText("No workflow runs have been recorded.")).toBeNull();
});

test("an actual empty workflow history offers a real entry point", async () => {
  backend({ runs: [] }); render(<PipelinesPage />);
  expect(await screen.findByText("No workflow runs have been recorded.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Open hotspots" }).getAttribute("href")).toBe("/hotspots");
});

test("a storage failure remains visible and refresh can recover the workflow history", async () => {
  const transport = backend({ fail: "/api/workflows" }); render(<PipelinesPage />);
  expect(await screen.findByText("Workflow history is unavailable")).toBeTruthy();
  expect(screen.queryByText("No workflow runs have been recorded.")).toBeNull();
  transport.mockImplementation(async (input: unknown) => Response.json(String(input) === "/api/workflows" ? [run] : running));
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  expect(await screen.findByRole("button", { name: /Collect public hotspots/ })).toBeTruthy();
});

test.each([PipelinesPage, AgentsPage])("authentication failures give a workspace sign-in path without claiming empty activity", async Page => {
  backend({ fail: "/api/workflows", status: 401 }); render(<Page />);
  expect(await screen.findByText("Sign in to continue in this workspace.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Sign in to inspect activity" }).getAttribute("href")).toBe(`/sign-in?returnTo=${encodeURIComponent(Page === AgentsPage ? "/agents" : "/pipelines")}`);
  expect(screen.queryByText("No agents running")).toBeNull();
});

test("agents are inspected within a real workflow rather than an invented global registry", async () => {
  const transport = backend(); render(<AgentsPage />);
  expect(screen.getByText("Choose a workflow to inspect its agent steps.")).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  const detail = await screen.findByRole("region", { name: "Workflow details" });
  expect(await within(detail).findByText("research")).toBeTruthy();
  expect(within(detail).queryByText("fetch")).toBeNull();
  expect(transport.mock.calls.every(([path]) => String(path) !== "/api/agents")).toBe(true);
});

test("an agent-free workflow is stated only after its step list is read", async () => {
  backend({ detail: { ...run, steps: [steps[0]] } }); render(<AgentsPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("This workflow has no agent steps.")).toBeTruthy();
});

test.each([undefined, null, [{ ...steps[0], kind: undefined }]])("missing step/classification data does not claim no agent work (%j)", async value => {
  backend({ detail: { ...run, steps: value } }); render(<AgentsPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("Agent step history is incomplete. Refresh activity to read it again.")).toBeTruthy();
  expect(screen.queryByText("This workflow has no agent steps.")).toBeNull();
});

test("a failed workflow-detail read does not fabricate successful or empty steps", async () => {
  backend({ fail: "/api/workflows/PR-live" }); render(<PipelinesPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("Workflow history is unavailable")).toBeTruthy();
  expect(screen.queryByText("No steps have been recorded for this workflow.")).toBeNull();
});

test("HTTP availability and a stopped scheduler are visible together on the dashboard", async () => {
  backend({ runtime: { ...running, worker_status: "stopped", feishu_status: "unreachable", last_error: "FeishuAPIError" } }); render(<DashboardPage />);
  expect(await screen.findByText("Backend Connected")).toBeTruthy();
  expect(screen.getByText("Scheduler stopped")).toBeTruthy();
  expect(screen.getByText("Execution needs attention. Inspect workflow state before retrying a command.")).toBeTruthy();
  expect(screen.queryByText("Scheduler running")).toBeNull();
});

test("a missing scheduler is not represented as zero real work", async () => {
  backend({ runtime: { ...running, worker_status: "not_started", active_pipeline_runs: 0, pending_steps: 0, failed_steps: 0, last_tick: null } }); render(<DashboardPage />);
  expect(await screen.findByText("Scheduler not started")).toBeTruthy();
  expect(screen.queryByText("0 active workflows")).toBeNull();
});

test("an unreadable execution status is unknown and refreshable", async () => {
  const transport = backend({ fail: "/api/system/status" }); render(<DashboardPage />);
  expect(await screen.findByText("Execution status unavailable")).toBeTruthy();
  expect(screen.queryByText("Scheduler running")).toBeNull();
  transport.mockImplementation(async () => Response.json(running));
  fireEvent.click(screen.getByRole("button", { name: "Refresh execution status" }));
  await waitFor(() => expect(screen.getByText("Scheduler running")).toBeTruthy());
});

test("long histories stay paginated and can be read in both directions", async () => {
  backend({ runs: Array.from({ length: 21 }, (_, i) => ({ ...run, pipeline_run_id: `PR-${i}`, pipeline_type: `run_${i}`, created_at: `2026-10-18T06:00:${String(i).padStart(2, "0")}Z` })) }); render(<PipelinesPage />);
  const region = screen.getByRole("region", { name: "Recorded workflows" });
  expect(await within(region).findByRole("button", { name: /run_20/ })).toBeTruthy();
  expect(within(region).queryByRole("button", { name: /run_0 / })).toBeNull();
  fireEvent.click(within(region).getByRole("button", { name: "Next workflows" }));
  expect(within(region).getByRole("button", { name: /run_0/ })).toBeTruthy();
  expect(within(region).queryByRole("button", { name: /run_20/ })).toBeNull();
  fireEvent.click(within(region).getByRole("button", { name: "Previous workflows" }));
  expect(within(region).getByRole("button", { name: /run_20/ })).toBeTruthy();
});

test("persisted step failures are visible without issuing repair commands", async () => {
  const transport = backend({ detail: { ...run, status: "blocked", steps: [{ ...steps[0], status: "blocked", error_message: "AmbiguousWrite: reconciliation required" }] } }); render(<PipelinesPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("AmbiguousWrite: reconciliation required")).toBeTruthy();
  expect(transport.mock.calls.every(([,init]) => !init?.method || init.method === "GET")).toBe(true);
});

test.each([undefined, []])("workflow step history distinguishes missing from confirmed empty (%j)", async value => {
  backend({ detail: { ...run, steps: value } }); render(<PipelinesPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText(value ? "No steps have been recorded for this workflow." : "Step history is incomplete. Refresh activity to read it again.")).toBeTruthy();
});

test("loaded details below the visible area are revealed once without repeated refresh scrolling", async () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 600, 350, 500));
  const transport = backend(); render(<PipelinesPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("fetch")).toBeTruthy();
  await waitFor(() => expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: "start" }));
  fireEvent.click(screen.getByRole("button", { name: "Refresh activity" }));
  await waitFor(() => expect(transport.mock.calls.filter(([p]) => p === "/api/workflows/PR-live")).toHaveLength(2));
  expect(await screen.findByText("fetch")).toBeTruthy();
  await act(async () => {});
  expect(scroll).toHaveBeenCalledOnce();
});

test("a desktop detail already visible is not scrolled away from the list", async () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 96, 600, 400));
  backend(); render(<PipelinesPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  expect(await screen.findByText("fetch")).toBeTruthy();
  await act(async () => {});
  expect(scroll).not.toHaveBeenCalled();
});

test("returning to the list before a slow detail arrives prevents a later scroll jump", async () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 600, 350, 500));
  let resolve!: (response: Response) => void;
  const transport = backend();
  transport.mockImplementation(async input => String(input) === "/api/workflows/PR-live" ? new Promise<Response>(done => { resolve = done; }) : Response.json(String(input) === "/api/workflows" ? [run] : running));
  render(<PipelinesPage />); fireEvent.click(await screen.findByRole("button", { name: /Collect public hotspots/ }));
  fireEvent.click(screen.getByRole("link", { name: "Back to workflows" }));
  resolve(Response.json({ ...run, steps }));
  expect(await screen.findByText("fetch")).toBeTruthy();
  await act(async () => {});
  expect(scroll).not.toHaveBeenCalled();
});
