import type { ReactElement } from "react";
import { expect, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

type ReplayCase = { key: string; raw: unknown; path: string; body: unknown;
  retry: string; clear: string; view: ReactElement;
  getResponses: Record<string, unknown>; successBody: unknown; successStatus: number };

export function resetReplayBoundary() {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear();
}

// Real components/hooks/ApiClient/Storage; only the remote HTTP response is controlled.
export async function exerciseReplayRecovery(scenario: ReplayCase) {
  const bytes = JSON.stringify(scenario.raw); sessionStorage.setItem(scenario.key, bytes);
  const calls: { method: string; path: string; body?: unknown }[] = [];
  let finish: ((response: Response) => void) | undefined;
  let released = false;
  vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init);
    const path = new URL(request.url).pathname;
    if (request.method === "POST") {
      const body = await request.json(); calls.push({ method: "POST", path, body });
      if (calls.filter(c => c.method === "POST").length === 1)
        return await new Promise<Response>(resolve => { finish = resolve; });
      return Response.json(scenario.successBody, { status: scenario.successStatus });
    }
    calls.push({ method: "GET", path });
    if (Object.hasOwn(scenario.getResponses, path)) return Response.json(scenario.getResponses[path]);
    throw new Error(`Unexpected replay context read ${path}`);
  });
  try {
    render(scenario.view); await act(async () => {});
    const retry = screen.getByRole("button", { name: scenario.retry }) as HTMLButtonElement;
    const clear = screen.getByRole("button", { name: scenario.clear }) as HTMLButtonElement;
    // Native clicks share one React event batch. No disabled attribute or private handler is altered.
    await act(async () => { retry.click(); retry.click(); clear.click(); });
    expect(calls.filter(c => c.method === "POST")).toEqual([{ method: "POST", path: scenario.path, body: scenario.body }]);
    expect(sessionStorage.getItem(scenario.key)).toBe(bytes);
    expect(retry.disabled).toBe(true); expect(clear.disabled).toBe(true);
    expect(finish).toBeTypeOf("function");
    await act(async () => { finish!(Response.json({ detail: "Ambiguous save result" }, { status: 503 })); released = true; });
    expect(await screen.findByText("Ambiguous save result")).toBeTruthy();
    expect(sessionStorage.getItem(scenario.key)).toBe(bytes); expect(retry.disabled).toBe(false);
    fireEvent.click(retry);
    await waitFor(() => expect(sessionStorage.getItem(scenario.key)).toBeNull());
    expect(calls.filter(c => c.method === "POST")).toEqual([
      { method: "POST", path: scenario.path, body: scenario.body }, { method: "POST", path: scenario.path, body: scenario.body } ]);
    expect(calls.some(c => c.method === "GET" && (c.path.endsWith("/context") || c.path.includes("bootstrap-context")))).toBe(false);
  } finally {
    // Settle a held transport even if a future regression fails an assertion.
    if (!released && finish) await act(async () => finish!(Response.json({ detail: "Ambiguous save result" }, { status: 503 })));
  }
}
