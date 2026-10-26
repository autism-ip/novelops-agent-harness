export type PendingPlan = { path: string; body: Record<string, unknown> };
const domainId = (value: unknown, prefix: string) =>
  typeof value === "string" && new RegExp(`^${prefix}-[a-f0-9]{32}$`).test(value);
const positiveInt = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 1;

export function parsePendingPlan(value: string | null, bookId?: string): PendingPlan | null {
  try {
    const parsed: unknown = JSON.parse(value ?? "null");
    if (!parsed || typeof parsed !== "object") return null;
    const command = parsed as Record<string, unknown>;
    if (typeof command.path !== "string" || !command.body || typeof command.body !== "object") return null;
    const body = command.body as Record<string, unknown>;
    const bible = /^\/api\/books\/(BK-[a-f0-9]{32})\/bibles$/.exec(command.path);
    if (bible) return (bookId === undefined || bible[1] === bookId) &&
      body.book_id === bible[1] && domainId(body.base_state_artifact_id, "AR") &&
      positiveInt(body.base_version) && positiveInt(body.version) &&
      typeof body.change_scope === "string" && ["initial", "major"].includes(body.change_scope) ? { path: command.path, body } : null;
    const brief = /^\/api\/books\/(BK-[a-f0-9]{32})\/chapters\/([1-9]\d*)\/briefs$/.exec(command.path);
    if (brief) return (bookId === undefined || brief[1] === bookId) &&
      Number.isSafeInteger(Number(brief[2])) && Number(brief[2]) <= 10000 &&
      body.book_id === brief[1] && body.chapter_no === Number(brief[2]) &&
      domainId(body.state_artifact_id, "AR") &&
      positiveInt(body.state_version) && positiveInt(body.version) ? { path: command.path, body } : null;
    const decision = /^\/api\/story-planning\/runs\/PR-[a-f0-9]{32}\/decision$/.test(command.path);
    if (decision) return domainId(body.step_id, "SR") &&
      positiveInt(body.expected_version) &&
      typeof body.action === "string" && ["approve", "reject", "revise"].includes(body.action) &&
      typeof body.operator === "string" && !!body.operator.trim() &&
      (body.action === "approve" ? domainId(body.artifact_id, "AR") : body.artifact_id === "") &&
      (body.action !== "revise" || (typeof body.reason === "string" && !!body.reason.trim()))
      ? { path: command.path, body } : null;
    return null;
  } catch { return null; }
}
