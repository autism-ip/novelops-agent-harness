export type PendingReview = { path: string; body: Record<string, unknown> };
const domainId = (value: unknown, prefix: string) =>
  typeof value === "string" && new RegExp(`^${prefix}-[a-f0-9]{32}$`).test(value);
const version = (value: unknown) =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 1;

export function parsePendingReview(value: string | null): PendingReview | null {
  try {
    const parsed: unknown = JSON.parse(value ?? "null");
    if (!parsed || typeof parsed !== "object") return null;
    const command = parsed as Record<string, unknown>;
    if (typeof command.path !== "string" || !command.body || typeof command.body !== "object") return null;
    const path = /^\/api\/books\/(BK-[a-f0-9]{32})\/chapters\/([1-9]\d*)\/(review\/(decision|revision)|final-lock)$/.exec(command.path);
    if (!path) return null;
    const body = command.body as Record<string, unknown>;
    if (!domainId(body.version_id, "CV") || !domainId(body.artifact_id, "AR") ||
        !version(body.version_no) || typeof body.operator !== "string" || !body.operator.trim()) return null;
    if (path[3] !== "final-lock") {
      if (!domainId(body.run_id, "PR") || !Number.isSafeInteger(body.expected_gate_version) ||
          Number(body.expected_gate_version) < 0) return null;
      if (path[4] === "decision" && !["approve", "reject"].includes(String(body.action))) return null;
      if (path[4] === "revision") {
        const constraints = body.constraints as Record<string, unknown> | undefined;
        if (!constraints || !["must_keep", "must_change", "do_not_change"].every(key =>
          Array.isArray(constraints[key]) && (constraints[key] as unknown[]).every(item =>
            typeof item === "string" && item.trim()))) return null;
        if (!(constraints.must_change as unknown[]).length) return null;
      }
    }
    return { path: command.path, body };
  } catch { return null; }
}
