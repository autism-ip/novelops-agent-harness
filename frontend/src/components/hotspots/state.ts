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

export function isDecisionPath(path: string): boolean {
  return /^\/api\/(?:analyses|creative\/runs)\/[\w-]+\/decision$/.test(path);
}

export function canClearRejected(status: number, retry: boolean): boolean {
  return !retry && [401, 404, 409, 422].includes(status);
}

export function clampOffset(offset: number, total: number): number {
  return Math.min(offset, Math.floor(Math.max(0, total - 1) / 20) * 20);
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
      !(parsed.path === "/api/analyses" || /^\/api\/creative\/(titles|covers)$/.test(parsed.path) || isDecisionPath(parsed.path) ||
        /^\/api\/hotspots\/(fetch|manual|[\w-]+\/discard)$/.test(parsed.path))
    )
      return null;
    if (parsed.path === "/api/analyses" && (!Array.isArray(parsed.body.items) || !parsed.body.items.length ||
        parsed.body.items.length > 20 || parsed.body.items.some((item: Record<string, unknown>) =>
          !item || typeof item.hotspot_id !== "string" || !item.hotspot_id ||
          !Number.isSafeInteger(item.version) || Number(item.version) < 1 ||
          typeof item.source_hash !== "string" || !/^[a-f0-9]{64}$/.test(item.source_hash)))) return null;
    if (isDecisionPath(parsed.path) && (!parsed.body || typeof parsed.body !== "object" ||
        typeof parsed.body.step_id !== "string" || !parsed.body.step_id ||
        typeof parsed.body.artifact_id !== "string" ||
        !["approve", "reject", "revise"].includes(parsed.body.action) ||
        !Number.isSafeInteger(parsed.body.expected_version) || parsed.body.expected_version < 1 ||
        (parsed.body.action === "approve" && !parsed.body.artifact_id) ||
        (parsed.body.action === "revise" && (typeof parsed.body.reason !== "string" || !parsed.body.reason.trim())))) return null;
    if (/^\/api\/creative\/(titles|covers)$/.test(parsed.path) && (!parsed.body || typeof parsed.body !== "object" ||
        typeof parsed.body.source_run_id !== "string" || !parsed.body.source_run_id ||
        typeof parsed.body.source_artifact_id !== "string" || !Number.isSafeInteger(parsed.body.version))) return null;
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
  hotspot_research_v1: "Research story opportunities",
  title_candidates_v1: "Generate title candidates",
  cover_plans_v1: "Plan cover directions",
};

export function workflowBusy(run: { pipeline_type: string; status: string }): boolean {
  return !TERMINAL.has(run.status) && !(["hotspot_research_v1", "title_candidates_v1", "cover_plans_v1"].includes(run.pipeline_type) && run.status === "awaiting_approval");
}
