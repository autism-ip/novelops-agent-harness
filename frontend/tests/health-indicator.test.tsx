import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
const get = vi.hoisted(() => vi.fn());
vi.mock("@/api/client", async importOriginal => ({ ...await importOriginal<typeof import("@/api/client")>(), api: { get } }));
import { HealthIndicator } from "@/components/health-indicator";
const ready = { backend_status: "running", worker_status: "running", active_pipeline_runs: 1, pending_steps: 0, failed_steps: 0 };
afterEach(() => { cleanup(); get.mockReset(); });
test("status progresses from checking to HTTP connected with separate scheduler state", async () => {
  let resolve!: (value: typeof ready) => void;
  get.mockReturnValue(new Promise(done => { resolve = done; }));
  render(<HealthIndicator />);
  expect(screen.getByText("Checking execution…")).toBeTruthy();
  expect(get).toHaveBeenCalledWith("/api/system/status", 10_000, expect.any(AbortSignal));
  resolve(ready);
  expect(await screen.findByText("Backend Connected")).toBeTruthy();
  expect(screen.getByText("Scheduler running")).toBeTruthy();
});
test("a non-running HTTP backend does not claim a healthy execution state", async () => {
  get.mockResolvedValue({ ...ready, backend_status: "degraded", worker_status: "unknown" }); render(<HealthIndicator />);
  expect(await screen.findByText("Backend Unreachable")).toBeTruthy();
  expect(screen.getByText("Scheduler status unknown")).toBeTruthy();
});
test("a failed status request remains unavailable rather than claiming worker readiness", async () => {
  get.mockRejectedValue(new Error("connection lost")); render(<HealthIndicator />);
  expect(await screen.findByText("Execution status unavailable")).toBeTruthy();
  expect(screen.getByText("connection lost")).toBeTruthy();
  expect(screen.queryByText("Scheduler running")).toBeNull();
});
test.each(["resolve", "reject"] as const)("late status %s after navigation does not restore the indicator", async outcome => {
  let resolve!: (value: typeof ready) => void; let reject!: (error: Error) => void;
  get.mockReturnValue(new Promise((done, fail) => { resolve = done; reject = fail; }));
  const view = render(<HealthIndicator />); view.unmount();
  await act(async () => { if (outcome === "resolve") resolve(ready); else reject(new Error("late failure")); });
  expect(screen.queryByText("Backend Connected")).toBeNull();
  expect(screen.queryByText("Execution status unavailable")).toBeNull();
  expect(get).toHaveBeenCalledOnce();
  expect(get.mock.calls[0][2].aborted).toBe(true);
});
