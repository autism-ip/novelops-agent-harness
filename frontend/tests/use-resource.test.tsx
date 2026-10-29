import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { ApiError } from "../src/api/client";
import { errorMessage, useResource } from "../src/components/hotspots/use-resource";

const stopPolling = () => false;
function Resource({ path = "/api/resource", poll = 0, revision = 0, keepPolling = false }: { path?: string | null; poll?: number; revision?: number; keepPolling?: boolean }) {
  const state = useResource<{ value: string }>(path, revision, poll, keepPolling ? undefined : stopPolling);
  return <><output>{state.loading ? "loading" : state.data?.value ?? "no-data"}</output>
    {state.error != null && <p role="alert">{errorMessage(state.error)}</p>}</>;
}
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

test("null resource paths perform no request", () => {
  const transport = vi.fn();
  vi.stubGlobal("fetch", transport);
  render(<Resource path={null} />);
  expect(screen.getByText("no-data")).toBeTruthy();
  expect(transport).not.toHaveBeenCalled();
});

test("unauthorized resources stop polling and show sign-in guidance", async () => {
  const transport = vi.fn().mockImplementation(() => Promise.resolve(Response.json({}, { status: 401 })));
  vi.stubGlobal("fetch", transport);
  render(<Resource poll={100} />);
  expect((await screen.findByRole("alert")).textContent).toBe("Sign in to continue in this workspace.");
  await act(async () => { await new Promise(done => setTimeout(done, 150)); });
  expect(transport).toHaveBeenCalledOnce();
});

test("transient failures retry on the poll interval, then stop when data says so", async () => {
  const transport = vi.fn().mockResolvedValueOnce(Response.json({ detail: "Temporarily unavailable" }, { status: 503 }))
    .mockImplementation(() => Promise.resolve(Response.json({ value: "ready" })));
  vi.stubGlobal("fetch", transport);
  render(<Resource poll={100} />);
  expect((await screen.findByRole("alert")).textContent).toBe("Temporarily unavailable");
  expect(await screen.findByText("ready")).toBeTruthy();
  await act(async () => { await new Promise(done => setTimeout(done, 150)); });
  expect(transport).toHaveBeenCalledTimes(2);
});

test.each(["resolve", "reject"] as const)("an in-flight %s after unmount cannot update or restart polling", async outcome => {
  vi.useFakeTimers();
  let resolve!: (response: Response) => void;
  let reject!: (error: Error) => void;
  const transport = vi.fn().mockImplementation(() => new Promise<Response>((done, fail) => { resolve = done; reject = fail; }));
  vi.stubGlobal("fetch", transport);
  const view = render(<Resource poll={100} />);
  expect(screen.getByText("loading")).toBeTruthy();
  view.unmount();
  await act(async () => {
    if (outcome === "resolve") resolve(Response.json({ value: "stale" }));
    else reject(new Error("late failure"));
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(vi.getTimerCount()).toBe(0);
  expect(transport).toHaveBeenCalledOnce();
});

test("visible errors distinguish uncertain requests and actionable server details", () => {
  expect(errorMessage(new ApiError(0, "Request cancelled"))).toBe("Request cancelled. Refresh to retry.");
  expect(errorMessage(new ApiError(0, "timeout"))).toBe("Request timed out. Retry the same request to check its outcome.");
  expect(errorMessage(new ApiError(409, { detail: "Version changed" }))).toBe("Version changed");
  expect(errorMessage(new ApiError(503, { detail: 123 }))).toBe("Request failed (503). Refresh and try again.");
  expect(errorMessage(new Error("Connection lost"))).toBe("Connection lost");
  expect(errorMessage(undefined)).toBe("Connection failed. Check the service and retry.");
});


test("persistent read failures back off and stop after three, while manual refresh starts a new budget", async () => {
  vi.useFakeTimers();
  const transport = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ detail: "Backend unavailable" }, { status: 503 })));
  vi.stubGlobal("fetch", transport);
  const view = render(<Resource poll={100} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); }); expect(transport).toHaveBeenCalledOnce();
  await act(async () => { await vi.advanceTimersByTimeAsync(100); }); expect(transport).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(199); }); expect(transport).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(1); }); expect(transport).toHaveBeenCalledTimes(3);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); }); expect(transport).toHaveBeenCalledTimes(3);
  expect(screen.getByRole("alert").textContent).toBe("Backend unavailable"); expect(vi.getTimerCount()).toBe(0);
  transport.mockResolvedValueOnce(Response.json({ value: "recovered" }));
  view.rerender(<Resource poll={100} revision={1} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("recovered")).toBeTruthy(); expect(transport).toHaveBeenCalledTimes(4);
});

test("successful reads reset the failure budget and backoff", async () => {
  vi.useFakeTimers();
  const transport = vi.fn().mockResolvedValueOnce(Response.json({}, { status: 503 }))
    .mockResolvedValueOnce(Response.json({ value: "ready" }))
    .mockImplementation(() => Promise.resolve(Response.json({}, { status: 503 })));
  vi.stubGlobal("fetch", transport);
  render(<Resource poll={100} keepPolling />);
  await act(async () => { await vi.advanceTimersByTimeAsync(100); }); expect(screen.getByText("ready")).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(100); }); expect(transport).toHaveBeenCalledTimes(3);
  await act(async () => { await vi.advanceTimersByTimeAsync(100); }); expect(transport).toHaveBeenCalledTimes(4);
  await act(async () => { await vi.advanceTimersByTimeAsync(199); }); expect(transport).toHaveBeenCalledTimes(4);
  await act(async () => { await vi.advanceTimersByTimeAsync(1); }); expect(transport).toHaveBeenCalledTimes(5);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); }); expect(transport).toHaveBeenCalledTimes(5);
});

test("navigating away aborts the old GET and cannot replace the new route data", async () => {
  vi.useFakeTimers(); let oldSignal: AbortSignal | undefined;
  const transport = vi.fn((url: unknown, init: RequestInit) => {
    if (url === "/api/old") { oldSignal = init.signal as AbortSignal; return new Promise<Response>((_done, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")));
    }); }
    return Promise.resolve(Response.json({ value: "new route" }));
  });
  vi.stubGlobal("fetch", transport);
  const view = render(<Resource path="/api/old" poll={100} />);
  view.rerender(<Resource path="/api/new" poll={100} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(oldSignal?.aborted).toBe(true); expect(screen.getByText("new route")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull(); expect(vi.getTimerCount()).toBe(0);
});

test.each([400, 403, 404, 409, 422])("non-transient read status %s waits for explicit refresh", async status => {
  vi.useFakeTimers();
  const transport = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ detail: "Check the requested source" }, { status })));
  vi.stubGlobal("fetch", transport); render(<Resource poll={100} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(transport).toHaveBeenCalledOnce(); expect(screen.getByRole("alert").textContent).toBe("Check the requested source");
});
