export type PendingPlan = { path: string; body: Record<string, unknown> };
const positiveInt = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 1;

export function parsePendingPlan(value: string | null): PendingPlan | null {
  try {
    const parsed: unknown = JSON.parse(value ?? "null");
    if (!parsed || typeof parsed !== "object") return null;
    const command = parsed as Record<string, unknown>;
    if (typeof command.path !== "string" || !command.body || typeof command.body !== "object") return null;
    const body = command.body as Record<string, unknown>;
    const bible = /^\/api\/books\/(BK-[a-f0-9]{32})\/bibles$/.exec(command.path);
    if (bible) return body.book_id === bible[1] && /^AR-[a-f0-9]{32}$/.test(String(body.base_state_artifact_id)) &&
      positiveInt(body.base_version) && positiveInt(body.version) &&
      ["initial", "major"].includes(String(body.change_scope)) ? { path: command.path, body } : null;
    const brief = /^\/api\/books\/(BK-[a-f0-9]{32})\/chapters\/([1-9]\d*)\/briefs$/.exec(command.path);
    if (brief) return body.book_id === brief[1] && Number(body.chapter_no) === Number(brief[2]) &&
      /^AR-[a-f0-9]{32}$/.test(String(body.state_artifact_id)) &&
      positiveInt(body.state_version) && positiveInt(body.version) ? { path: command.path, body } : null;
    const decision = /^\/api\/story-planning\/runs\/PR-[a-f0-9]{32}\/decision$/.test(command.path);
    if (decision) return /^SR-[a-f0-9]{32}$/.test(String(body.step_id)) &&
      positiveInt(body.expected_version) &&
      ["approve", "reject", "revise"].includes(String(body.action)) &&
      typeof body.operator === "string" && !!body.operator.trim() &&
      (body.action === "approve" ? /^AR-[a-f0-9]{32}$/.test(String(body.artifact_id)) : body.artifact_id === "") &&
      (body.action !== "revise" || (typeof body.reason === "string" && !!body.reason.trim()))
      ? { path: command.path, body } : null;
    return null;
  } catch { return null; }
}
