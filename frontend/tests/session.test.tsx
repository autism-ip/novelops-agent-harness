import { webcrypto } from "node:crypto";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  vi.stubEnv("SESSION_SECRET", "s".repeat(32));
  vi.resetModules();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

test("a signed session verifies before expiry and fails after expiry", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-08T00:00:00Z"));
  const { signSessionToken, verifyToken } = await import("../src/lib/session");
  const token = await signSessionToken("authenticated", 60);
  expect(await verifyToken(token)).toBe(`authenticated:${Math.floor(Date.now() / 1000) + 60}`);
  vi.advanceTimersByTime(59_000);
  expect(await verifyToken(token)).not.toBeNull();
  vi.advanceTimersByTime(1_000);
  expect(await verifyToken(token)).toBeNull();
});

test("tampering and malformed signatures never authenticate", async () => {
  const { signToken, verifyToken } = await import("../src/lib/session");
  const token = await signToken("authenticated");
  expect(await verifyToken(token)).toBe("authenticated");
  expect(await verifyToken(token.replace("authenticated", "administrator"))).toBeNull();
  expect(await verifyToken("missing-signature")).toBeNull();
  expect(await verifyToken(".bad")).toBeNull();
  expect(await verifyToken("authenticated.%%%" )).toBeNull();
});

test("missing or short server secrets cannot sign sessions", async () => {
  vi.stubEnv("SESSION_SECRET", "");
  vi.resetModules();
  let session = await import("../src/lib/session");
  await expect(session.signSessionToken("authenticated", 60)).rejects.toThrow("SESSION_SECRET environment variable is required");
  vi.stubEnv("SESSION_SECRET", "short");
  vi.resetModules();
  session = await import("../src/lib/session");
  await expect(session.signSessionToken("authenticated", 60)).rejects.toThrow("SESSION_SECRET must be at least 32 characters");
});

test("browser crypto verification failure fails closed", async () => {
  const { signToken, verifyToken } = await import("../src/lib/session");
  const token = await signToken("authenticated");
  const subtle = webcrypto.subtle;
  vi.stubGlobal("crypto", { subtle: {
    importKey: subtle.importKey.bind(subtle),
    verify: async () => { throw new Error("crypto unavailable"); },
  } });
  expect(await verifyToken(token)).toBeNull();
});
