export type PendingChapter = { path: string; body: Record<string, unknown> };
const id = (value: unknown, prefix: string) =>
  typeof value === "string" && new RegExp(`^${prefix}-[a-f0-9]{32}$`).test(value);
const positive = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 1;

export function parsePendingChapter(value: string | null): PendingChapter | null {
  try {
    const parsed: unknown = JSON.parse(value ?? "null");
    if (!parsed || typeof parsed !== "object") return null;
    const command = parsed as Record<string, unknown>;
    if (typeof command.path !== "string" || !command.body || typeof command.body !== "object") return null;
    const body = command.body as Record<string, unknown>;
    const path = /^\/api\/books\/(BK-[a-f0-9]{32})\/chapters\/([1-9]\d*)\/generations$/.exec(command.path);
    if (!path || body.book_id !== path[1] || body.chapter_no !== Number(path[2]) ||
        !positive(body.version) || !positive(body.start_version_no) ||
        !positive(body.state_version) || !positive(body.brief_version) ||
        !id(body.state_artifact_id, "AR") || !id(body.brief_artifact_id, "AR")) return null;
    if (body.source_version_id !== "" || !body.constraints || typeof body.constraints !== "object") return null;
    const constraints = body.constraints as Record<string, unknown>;
    if (!["must_keep", "must_change", "do_not_change"].every(key =>
      Array.isArray(constraints[key]) && (constraints[key] as unknown[]).length === 0)) return null;
    return { path: command.path, body };
  } catch { return null; }
}
