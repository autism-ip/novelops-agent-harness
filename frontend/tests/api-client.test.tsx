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


test("a stalled success body remains inside the request deadline", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((_input: unknown, init: RequestInit) => Promise.resolve(new Response(
    new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('{"title":'));
      init.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")));
    } }), { headers: { "Content-Type": "application/json" } }
  )));
  vi.stubGlobal("fetch", transport);
  const pending = createApiClient({ baseUrl: "" }).get("/api/chapter");
  const assertion = expect(pending).rejects.toMatchObject({ status: 0, body: "Request timeout" });
  await vi.advanceTimersByTimeAsync(9_999);
  expect(transport.mock.calls[0][1].signal?.aborted).toBe(false);
  await vi.advanceTimersByTimeAsync(1);
  expect(transport.mock.calls[0][1].signal?.aborted).toBe(true);
  await assertion;
  expect(vi.getTimerCount()).toBe(0);
});

test("a fully received malformed success body preserves its parsing error and clears its timer", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("invalid json")));
  await expect(createApiClient({ baseUrl: "" }).get("/api/chapter")).rejects.toBeInstanceOf(SyntaxError);
  expect(vi.getTimerCount()).toBe(0);
});


test("a slow complete JSON body uses the configured read deadline and returns exact data", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_input: unknown, init: RequestInit) => Promise.resolve(new Response(
    new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('{"title":'));
      const timer = setTimeout(() => { controller.enqueue(new TextEncoder().encode('"Garden at dawn"}')); controller.close(); }, 26_703);
      init.signal?.addEventListener("abort", () => { clearTimeout(timer); controller.error(new DOMException("Aborted", "AbortError")); });
    } })
  ))));
  const pending = createApiClient({ baseUrl: "" }).get("/api/chapter", 120_000);
  await vi.advanceTimersByTimeAsync(26_703);
  expect(await pending).toEqual({ title: "Garden at dawn" });
  expect(vi.getTimerCount()).toBe(0);
});


test("a stalled HTTP error body reports timeout rather than a fabricated server error", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_input: unknown, init: RequestInit) => Promise.resolve(new Response(
    new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('{"detail":'));
      init.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")));
    } }), { status: 502, statusText: "Bad Gateway" }
  ))));
  const pending = createApiClient({ baseUrl: "" }).post("/api/chapter", { action: "approve" });
  const assertion = expect(pending).rejects.toMatchObject({ status: 0, body: "Request timeout" });
  await vi.advanceTimersByTimeAsync(10_000);
  await assertion;
  expect(vi.getTimerCount()).toBe(0);
});
