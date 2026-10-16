import { webcrypto } from "node:crypto";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("AUTH_PASSWORD", "workspace-password");
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.resetModules();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });
function request(body: string) {
  return new NextRequest("http://frontend.test/api/auth/login", { method: "POST", body,
    headers: { "Content-Type": "application/json" } });
}

test("malformed bodies and wrong passwords do not issue a session", async () => {
  const { POST } = await import("../src/app/api/auth/login/route");
  for (const body of ["invalid-json", "null", '"text"']) {
    const response = await POST(request(body));
    expect(response.status).toBe(400);
    expect(response.cookies.get("session_token")).toBeUndefined();
  }
  const response = await POST(request('{"password":"wrong"}'));
  expect(response.status).toBe(401);
  expect(response.cookies.get("session_token")).toBeUndefined();
});

test("successful login issues an HttpOnly cookie with a verifiable 24-hour expiry", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-08T00:00:00Z"));
  const { POST } = await import("../src/app/api/auth/login/route");
  const { verifyToken } = await import("../src/lib/session");
  const response = await POST(request('{"password":"workspace-password"}'));
  expect(response.status).toBe(200);
  const cookie = response.cookies.get("session_token");
  expect(cookie).toMatchObject({ httpOnly: true, sameSite: "lax", path: "/", maxAge: 86_400 });
  expect(await verifyToken(cookie?.value ?? "")).toBe(`authenticated:${Math.floor(Date.now() / 1000) + 86_400}`);
});

test("production login uses a Secure session cookie", async () => {
  vi.stubEnv("NODE_ENV", "production");
  const { POST } = await import("../src/app/api/auth/login/route");
  const response = await POST(request('{"password":"workspace-password"}'));
  expect(response.cookies.get("session_token")?.secure).toBe(true);
});

test("missing authentication or signing configuration returns a controlled service failure", async () => {
  vi.stubEnv("AUTH_PASSWORD", "");
  const unconfigured = await import("../src/app/api/auth/login/route");
  expect((await unconfigured.POST(request('{"password":"workspace-password"}'))).status).toBe(503);
  vi.stubEnv("AUTH_PASSWORD", "workspace-password");
  vi.stubEnv("SESSION_SECRET", "");
  vi.resetModules();
  const unsigned = await import("../src/app/api/auth/login/route");
  const response = await unsigned.POST(request('{"password":"workspace-password"}'));
  expect(response.status).toBe(503);
  expect(response.cookies.get("session_token")).toBeUndefined();
});
