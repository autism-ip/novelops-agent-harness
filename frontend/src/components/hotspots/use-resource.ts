"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/api/client";

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in to continue in this workspace.";
    if (error.status === 0 && error.body === "Request cancelled") return "Request cancelled. Refresh to retry.";
    if (error.status === 0)
      return "Request timed out. Retry the same request to check its outcome.";
    if (
      typeof error.body === "object" &&
      error.body &&
      "detail" in error.body &&
      typeof error.body.detail === "string"
    )
      return error.body.detail;
    return `Request failed (${error.status}). Refresh and try again.`;
  }
  return error instanceof Error
    ? error.message
    : "Connection failed. Check the service and retry.";
}

export function useResource<T>(
  path: string | null,
  revision: number,
  pollMs = 0,
  onData?: (data: T) => boolean,
  timeoutMs = 10_000,
) {
  const key = `${path}:${revision}`;
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    error?: unknown;
  }>();
  useEffect(() => {
    if (!path) return;
    let live = true;
    let failures = 0;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      let repeat = true;
      try {
        const data = await api.get<T>(path!, timeoutMs, controller.signal);
        failures = 0;
        if (live) {
          setResult({ key, data });
          repeat = onData?.(data) ?? true;
        }
      } catch (error) {
        if (live) setResult({ key, error });
        failures += 1;
        const transient = !(error instanceof ApiError) || error.status === 0 || error.status === 429 || error.status >= 500;
        repeat = failures < 3 && transient;
      } finally {
        if (live && pollMs && repeat) {
          const delay = failures ? Math.max(pollMs, Math.min(pollMs * 2 ** (failures - 1), 60_000)) : pollMs;
          timer = setTimeout(load, delay);
        }
      }
    }
    void load();
    return () => {
      live = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, key, pollMs, onData, timeoutMs]);
  return {
    data: result?.key === key ? result.data : undefined,
    error: result?.key === key ? result.error : undefined,
    loading: !!path && result?.key !== key,
  };
}
