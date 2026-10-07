import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/api/client", () => ({ api: { get } }));

import { HealthIndicator } from "@/components/health-indicator";

afterEach(() => {
  cleanup();
  get.mockReset();
});

test("health status progresses from checking to connected on an OK response", async () => {
  let resolve!: (value: { status: string }) => void;
  get.mockReturnValue(new Promise((done) => { resolve = done; }));
  render(<HealthIndicator />);
  expect(screen.getByText("Checking backend...")).toBeTruthy();
  expect(get).toHaveBeenCalledWith("/api/system/health");
  resolve({ status: "ok" });
  expect(await screen.findByText("Backend Connected")).toBeTruthy();
});

test("a non-OK backend response is shown as unreachable", async () => {
  get.mockResolvedValue({ status: "degraded" });
  render(<HealthIndicator />);
  expect(await screen.findByText("Backend Unreachable")).toBeTruthy();
});

test("a failed health request is shown as unreachable", async () => {
  get.mockRejectedValue(new Error("connection lost"));
  render(<HealthIndicator />);
  expect(await screen.findByText("Backend Unreachable")).toBeTruthy();
});
