export type BootstrapContext = {
  book_id: string;
  cover_run_id: string;
  cover_artifact_id: string;
  title_artifact_id: string;
  opportunity_artifact_id: string;
};

export function parsePendingBook(value: string | null): BootstrapContext | null {
  try {
    const item: unknown = JSON.parse(value ?? "null");
    if (!item || typeof item !== "object") return null;
    const data = item as Record<string, unknown>;
    if (!/^BK-[a-f0-9]{32}$/.test(String(data.book_id)) ||
        !/^PR-[a-f0-9]{32}$/.test(String(data.cover_run_id)) ||
        ["cover_artifact_id", "title_artifact_id", "opportunity_artifact_id"].some(
          key => !/^AR-[a-f0-9]{32}$/.test(String(data[key])))) return null;
    return item as BootstrapContext;
  } catch {
    return null;
  }
}
