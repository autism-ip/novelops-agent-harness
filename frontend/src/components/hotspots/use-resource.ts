"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/api/client";

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in to view and manage hotspots.";
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
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      let repeat = true;
      try {
        const data = await api.get<T>(path!);
        if (live) {
          setResult({ key, data });
          repeat = onData?.(data) ?? true;
        }
      } catch (error) {
        if (live) setResult({ key, error });
        if (error instanceof ApiError && error.status === 401) repeat = false;
      } finally {
        if (live && pollMs && repeat) timer = setTimeout(load, pollMs);
      }
    }
    void load();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [path, key, pollMs, onData]);
  return {
    data: result?.key === key ? result.data : undefined,
    error: result?.key === key ? result.error : undefined,
    loading: !!path && result?.key !== key,
  };
}
