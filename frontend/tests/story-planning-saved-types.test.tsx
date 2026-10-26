import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StoryPlanning } from "../src/components/books/story-planning";
import { parsePendingPlan } from "../src/components/books/planning-state";

type Command = { path: string; body: Record<string, unknown> };
const book = `BK-${"a".repeat(32)}`, artifact = `AR-${"b".repeat(32)}`;
const run = `PR-${"c".repeat(32)}`, step = `SR-${"d".repeat(32)}`;
const key = `novelops.story-planning.pending.${book}`;
const bible: Command = { path: `/api/books/${book}/bibles`, body: { book_id: book,
  base_state_artifact_id: artifact, base_version: 2, version: 3, change_scope: "major", feedback: "Keep the original cost" } };
const brief: Command = { path: `/api/books/${book}/chapters/1/briefs`, body: { book_id: book,
  chapter_no: 1, state_artifact_id: artifact, state_version: 2, version: 3, feedback: "Keep the original cost" } };
const decision: Command = { path: `/api/story-planning/runs/${run}/decision`, body: { step_id: step,
  artifact_id: artifact, expected_version: 2, action: "approve", operator: "Original editor", reason: "Checked the rules" } };
const changed = (base: Command, fields: Record<string, unknown>): Command => ({ ...base, body: { ...base.body, ...fields } });
const malformed = [
  { name: "Bible source ID array", command: changed(bible, { base_state_artifact_id: [artifact] }) },
  { name: "Bible change scope array", command: changed(bible, { change_scope: ["major"] }) },
  { name: "Brief string chapter identity", command: changed(brief, { chapter_no: "1" }) },
  { name: "Brief boolean chapter identity", command: changed(brief, { chapter_no: true }) },
  { name: "Brief source ID array", command: changed(brief, { state_artifact_id: [artifact] }) },
  { name: "Decision step ID array", command: changed(decision, { step_id: [step] }) },
  { name: "Decision Artifact ID array", command: changed(decision, { artifact_id: [artifact] }) },
  { name: "Decision reject action array", command: changed(decision, { action: ["reject"], artifact_id: "" }) },
  { name: "Decision approve action array with no Artifact", command: changed(decision, { action: ["approve"], artifact_id: "" }) },
  { name: "Decision revise action array with no feedback", command: changed(decision, { action: ["revise"], artifact_id: "", reason: "" }) },
];
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

test.each(malformed)("a saved $name never reaches POST and remains available for history recovery", async ({ command }) => {
  const bytes = JSON.stringify(command); sessionStorage.setItem(key, bytes);
  const posts: { path: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init);
    const path = new URL(request.url).pathname;
    if (request.method === "POST") { posts.push({ path, body: await request.json() });
      return Response.json({ detail: "Synthetic unknown write outcome" }, { status: 503 }); }
    if (path === `/api/books/${book}/bibles` || path === `/api/books/${book}/chapters/1/briefs`) return Response.json([]);
    if (path === `/api/story-planning/runs/${run}`) return Response.json({ run: { pipeline_run_id: run }, request: { book_id: book } });
    throw new Error(`Unexpected saved command read ${path}`);
  });
  render(<StoryPlanning bookId={book} approvedBible />);
  await act(async () => {});
  const retry = screen.queryByRole("button", { name: "Retry the same request" });
  if (retry) fireEvent.click(retry);
  await act(async () => {});
  expect(posts).toEqual([]);
  expect(screen.queryByRole("button", { name: "Retry the same request" })).toBeNull();
  expect(screen.getByText("Saved request is unreadable. Check the Book history before clearing it.")).toBeTruthy();
  expect(sessionStorage.getItem(key)).toBe(bytes);
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" }));
  expect(sessionStorage.getItem(key)).toBeNull();
});

test.each([null, "null", "false", "0", '"not a command"', "[]", "{}",
  JSON.stringify({ path: 3, body: bible.body }), JSON.stringify({ path: bible.path, body: null }),
  JSON.stringify({ path: bible.path, body: "not an object" })])("malformed saved planning envelopes are not domain commands: %s", bytes => {
  expect(parsePendingPlan(bytes, book)).toBeNull();
});
