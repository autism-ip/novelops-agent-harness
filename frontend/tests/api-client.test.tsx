import { afterEach, expect, test, vi } from "vitest";
import { ApiError, createApiClient } from "../src/api/client";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

test("an explicitly configured client injects its key and serializes writes", async () => {
  const transport = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ id: "record-1" })));
  vi.stubGlobal("fetch", transport);
  const client = createApiClient({ baseUrl: "http://server.test", apiKey: "server-only-key" });
  expect(await client.get("/api/record")).toEqual({ id: "record-1" });
  expect(await client.post("/api/record", { title: "New record" })).toEqual({ id: "record-1" });
  expect(transport.mock.calls[0][0]).toBe("http://server.test/api/record");
  expect(transport.mock.calls[0][1].headers["x-api-key"]).toBe("server-only-key");
  expect(transport.mock.calls[1][1]).toMatchObject({ method: "POST", body: '{"title":"New record"}' });
});

test("non-JSON failures retain HTTP status and a usable error body", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json", { status: 502, statusText: "Bad Gateway" })));
  const client = createApiClient({ baseUrl: "" });
  await expect(client.get("/api/record")).rejects.toMatchObject({ status: 502, body: "Bad Gateway" });
});

test("a ten-second timeout aborts the request and reports uncertain outcome", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((_input: unknown, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  }));
  vi.stubGlobal("fetch", transport);
  const client = createApiClient({ baseUrl: "" });
  const pending = client.post("/api/record", { title: "New record" });
  const assertion = expect(pending).rejects.toMatchObject({ status: 0, body: "Request timeout" });
  await vi.advanceTimersByTimeAsync(10_000);
  await assertion;
  expect(transport.mock.calls[0][1].signal?.aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});

test("network failures preserve their cause and release the timeout", async () => {
  vi.useFakeTimers();
  const failure = new TypeError("Network unavailable");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure));
  const client = createApiClient({ baseUrl: "" });
  await expect(client.get("/api/record")).rejects.toBe(failure);
  expect(vi.getTimerCount()).toBe(0);
  expect(new ApiError(401, {}).message).toBe("API error 401");
});
