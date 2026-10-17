import { afterEach, expect, test, vi } from "vitest";
import { NextRequest } from "next/server";
import { webcrypto } from "node:crypto";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules(); });

test("decoded traversal segments never reach the backend", async () => {
  vi.stubEnv("BACKEND_API_URL", "http://backend.test");
  vi.stubEnv("BACKEND_API_KEY", "private-key");
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.stubGlobal("crypto", webcrypto);
  vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session");
  const token = await signSessionToken("authenticated", 60);
  const { GET } = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockResolvedValue(Response.json({ ok: true }));
  vi.stubGlobal("fetch", upstream);
  for (const segment of [".", "..", "a/b", "..\\private", "%2e%2e", "?mode=evil", "#cut"]) {
    const request = new NextRequest("http://frontend.test/api/invalid");
    request.cookies.set("session_token", token);
    const response = await GET(request, { params: Promise.resolve({ path: [segment] }) });
    expect(response.status, segment).toBe(400);
  }
  expect(upstream).not.toHaveBeenCalled();
});

test("public health is forwarded without a browser or server API key", async () => {
  vi.stubEnv("BACKEND_API_URL", "http://backend.test");
  vi.stubEnv("BACKEND_API_KEY", "private-key");
  vi.resetModules();
  const { GET } = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockResolvedValue(new Response("healthy", { status: 200, headers: { "Content-Type": "text/plain" } }));
  vi.stubGlobal("fetch", upstream);
  const request = new NextRequest("http://frontend.test/api/system/health?probe=1", {
    headers: { "x-api-key": "browser-forged" },
  });
  const response = await GET(request, { params: Promise.resolve({ path: ["system", "health"] }) });
  expect(response.status).toBe(200);
  expect(await response.text()).toBe("healthy");
  const [url, init] = upstream.mock.calls[0];
  expect(url).toBe("http://backend.test/api/system/health?probe=1");
  expect(init.method).toBe("GET");
  expect(init.signal).toBe(request.signal);
  expect(init.headers.get("x-api-key")).toBeNull();
});

test("protected requests require a signed session and inject only the server key", async () => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("BACKEND_API_URL", "http://backend.test");
  vi.stubEnv("BACKEND_API_KEY", "private-key");
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session");
  const { GET, POST } = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockResolvedValue(Response.json({ created: true }, { status: 201 }));
  vi.stubGlobal("fetch", upstream);
  const params = { params: Promise.resolve({ path: ["hotspots", "manual"] }) };
  expect((await GET(new NextRequest("http://frontend.test/api/hotspots/manual"), params)).status).toBe(401);
  const forged = new NextRequest("http://frontend.test/api/hotspots/manual");
  forged.cookies.set("session_token", "forged.invalid");
  expect((await GET(forged, params)).status).toBe(401);
  expect(upstream).not.toHaveBeenCalled();
  const request = new NextRequest("http://frontend.test/api/hotspots/manual?source=manual", {
    method: "POST", headers: { "Content-Type": "application/json", "x-api-key": "browser-forged" },
    body: JSON.stringify({ title: "Idea" }),
  });
  request.cookies.set("session_token", await signSessionToken("authenticated", 60));
  const response = await POST(request, params);
  expect(response.status).toBe(201);
  expect(await response.json()).toEqual({ created: true });
  const [url, init] = upstream.mock.calls[0];
  expect(url).toBe("http://backend.test/api/hotspots/manual?source=manual");
  expect(init.method).toBe("POST");
  expect(init.body).toBe('{"title":"Idea"}');
  expect(init.headers.get("x-api-key")).toBe("private-key");
});

test("protected proxy fails closed when signing or backend key is unconfigured", async () => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("BACKEND_API_KEY", "private-key");
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session");
  const token = await signSessionToken("authenticated", 60);
  const request = new NextRequest("http://frontend.test/api/hotspots");
  request.cookies.set("session_token", token);
  vi.stubEnv("SESSION_SECRET", "");
  vi.resetModules();
  let route = await import("../src/app/api/[...path]/route");
  const params = { params: Promise.resolve({ path: ["hotspots"] }) };
  expect((await route.GET(request, params)).status).toBe(503);
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.stubEnv("BACKEND_API_KEY", "");
  vi.resetModules();
  route = await import("../src/app/api/[...path]/route");
  expect((await route.GET(request, params)).status).toBe(503);
});

test("write methods preserve method and body without forwarding browser credentials", async () => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("BACKEND_API_URL", "http://backend.test");
  vi.stubEnv("BACKEND_API_KEY", "private-key");
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session");
  const route = await import("../src/app/api/[...path]/route");
  const token = await signSessionToken("authenticated", 60);
  const upstream = vi.fn().mockImplementation(() => Promise.resolve(new Response("backend rejected", { status: 409, headers: { "Content-Type": "" } })));
  vi.stubGlobal("fetch", upstream);
  for (const method of ["PUT", "PATCH", "DELETE"] as const) {
    const request = new NextRequest("http://frontend.test/api/workflows/PR-abc", {
      method, headers: { "x-api-key": "browser-forged", "Content-Type": "application/json" }, body: method === "DELETE" ? undefined : "payload",
    });
    request.cookies.set("session_token", token);
    const response = await route[method](request, { params: Promise.resolve({ path: ["workflows", "PR-abc"] }) });
    expect(response.status).toBe(409);
    expect(response.headers.get("Content-Type")).toBe("application/json");
    expect(await response.text()).toBe("backend rejected");
    const call = upstream.mock.calls.at(-1);
    if (!call) throw new Error("Missing upstream request");
    const [url, init] = call;
    expect(url).toBe("http://backend.test/api/workflows/PR-abc");
    expect(init.method).toBe(method);
    expect(init.body).toBe(method === "DELETE" ? "" : "payload");
    expect(init.headers.get("x-api-key")).toBe("private-key");
    expect(init.headers.get("Content-Type")).toBe("application/json");
  }
});


test.each(["GET", "POST", "HEAD"] as const)("upstream %s transport failure is safe, actionable and never retried", async method => {
  vi.stubGlobal("crypto", webcrypto); vi.stubEnv("BACKEND_API_KEY", "private-key"); vi.stubEnv("SESSION_SECRET", "s".repeat(32)); vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session"); const route = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockRejectedValue(new Error("private-key backend transport details")); vi.stubGlobal("fetch", upstream);
  const request = new NextRequest("http://frontend.test/api/records", { method, body: method === "POST" ? '{"command":"same"}' : undefined });
  request.cookies.set("session_token", await signSessionToken("authenticated", 60));
  const response = await route[method === "HEAD" ? "GET" : method](request, { params: Promise.resolve({ path: ["records"] }) });
  expect(response.status).toBe(method === "POST" ? 502 : 503);
  const body = await response.json(); expect(body.detail).toBe(method !== "POST"
    ? "Backend service is unavailable. Check the service, then refresh."
    : "The request outcome is unknown. Check the saved request and retry that exact request.");
  expect(JSON.stringify(body)).not.toContain("private-key"); expect(upstream).toHaveBeenCalledOnce();
});

test("a truncated upstream write body never fabricates a successful commit response", async () => {
  vi.stubGlobal("crypto", webcrypto); vi.stubEnv("BACKEND_API_KEY", "private-key"); vi.stubEnv("SESSION_SECRET", "s".repeat(32)); vi.resetModules();
  const { signSessionToken } = await import("../src/lib/session"); const { POST } = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockResolvedValue(new Response(new ReadableStream({ start(controller) { controller.error(new Error("private transport details")); } }), { status: 201 })); vi.stubGlobal("fetch", upstream);
  const request = new NextRequest("http://frontend.test/api/records", { method: "POST", body: '{}' }); request.cookies.set("session_token", await signSessionToken("authenticated", 60));
  const response = await POST(request, { params: Promise.resolve({ path: ["records"] }) });
  expect(response.status).toBe(502); expect(await response.json()).toEqual({ detail: "The request outcome is unknown. Check the saved request and retry that exact request." }); expect(upstream).toHaveBeenCalledOnce();
});


test.each([204, 205, 304])("bodyless upstream status %s is preserved rather than reported as unknown", async status => {
  vi.stubEnv("BACKEND_API_URL", "http://backend.test"); vi.resetModules();
  const { GET } = await import("../src/app/api/[...path]/route");
  const upstream = vi.fn().mockResolvedValue(new Response(null, { status })); vi.stubGlobal("fetch", upstream);
  const response = await GET(new NextRequest("http://frontend.test/api/system/health"), { params: Promise.resolve({ path: ["system", "health"] }) });
  expect(response.status).toBe(status); expect(await response.text()).toBe(""); expect(upstream).toHaveBeenCalledOnce();
});
