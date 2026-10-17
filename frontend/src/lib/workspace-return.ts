/** Keep authentication returns inside known workspace pages, never API or external URLs. */
export function safeWorkspaceReturn(value: unknown): string {
  if (typeof value !== "string") return "/books";
  if (["/", "/books", "/hotspots", "/pipelines", "/agents"].includes(value)) return value;
  const match = /^\/books\/[A-Za-z0-9_-]{1,200}(?:\/chapters\/([1-9]\d{0,4})\/review)?$/.exec(value);
  return match?.[0] === value && (!match[1] || Number(match[1]) <= 10000) ? value : "/books";
}
