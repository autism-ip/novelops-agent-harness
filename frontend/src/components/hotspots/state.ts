export type Filters = {
  source: string;
  status: string;
  from: string;
  to: string;
};
export type Pending = {
  path: string;
  body: Record<string, unknown> & { request_key: string };
};

export function canClearRejected(status: number, retry: boolean): boolean {
  return !retry && [401, 404, 409, 422].includes(status);
}

export function listPath(filters: Filters, offset: number) {
  const params = new URLSearchParams({ offset: String(offset), limit: "20" });
  if (filters.source) params.set("source", filters.source);
  if (filters.status) params.set("status", filters.status);
  if (filters.from && filters.to && filters.from > filters.to)
    throw new Error("Start date must precede end date.");
  if (filters.from)
    params.set(
      "captured_from",
      new Date(`${filters.from}T00:00:00`).toISOString(),
    );
  if (filters.to)
    params.set(
      "captured_to",
      new Date(`${filters.to}T23:59:59.999`).toISOString(),
    );
  return `/api/hotspots?${params}`;
}

export function parsePending(value: string | null): Pending | null {
  try {
    const parsed = JSON.parse(value ?? "null");
    if (
      !parsed ||
      typeof parsed.path !== "string" ||
      !/^\/api\/hotspots\/(fetch|manual|[\w-]+\/discard)$/.test(parsed.path)
    )
      return null;
    if (
      !parsed.body ||
      typeof parsed.body !== "object" ||
      typeof parsed.body.request_key !== "string" ||
      !parsed.body.request_key.trim()
    )
      return null;
    return parsed;
  } catch {
    return null;
  }
}

export function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export const TERMINAL = new Set([
  "completed",
  "failed",
  "blocked",
  "cancelled",
]);
export const WORKFLOW_LABELS: Record<string, string> = {
  hotspot_ingestion_v1: "Collect public hotspots",
  hotspot_manual_v1: "Add a hotspot",
  hotspot_discard_v1: "Discard a hotspot",
};
