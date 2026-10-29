import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { ApiError } from "../src/api/client";
import { errorMessage, useResource } from "../src/components/hotspots/use-resource";

const stopPolling = () => false;
function Resource({ path = "/api/resource", poll = 0 }: { path?: string | null; poll?: number }) {
  const state = useResource<{ value: string }>(path, 0, poll, stopPolling);
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
  expect((await screen.findByRole("alert")).textContent).toBe("Sign in to view and manage hotspots.");
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
  expect(errorMessage(new ApiError(0, "timeout"))).toBe("Request timed out. Retry the same request to check its outcome.");
  expect(errorMessage(new ApiError(409, { detail: "Version changed" }))).toBe("Version changed");
  expect(errorMessage(new ApiError(503, { detail: 123 }))).toBe("Request failed (503). Refresh and try again.");
  expect(errorMessage(new Error("Connection lost"))).toBe("Connection lost");
  expect(errorMessage(undefined)).toBe("Connection failed. Check the service and retry.");
});
