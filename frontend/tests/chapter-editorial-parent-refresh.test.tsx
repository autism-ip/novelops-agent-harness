import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChapterGeneration } from "../src/components/books/chapter-generation";

const book = `BK-${"a".repeat(32)}`;
const runId = `PR-${"b".repeat(32)}`;
const versionId = `CV-${"c".repeat(32)}`;
const artifactId = `AR-${"d".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
const pendingKey = `novelops.chapter-review.pending.${book}.1`;
const prose = "Mira opens the garden gate and returns the seed to her neighbor.";
const selected = { artifact_id: artifactId, version: 2,
  content: { title: "The garden gate", prose }, source_refs: [] };
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test.each(["approve", "final-lock"] as const)("the real nested %s action refreshes its generation parent without creating another draft", async action => {
  let status = "review";
  let finish!: () => void;
  const requests: Request[] = [];
  const transport = vi.fn(async (url: unknown, init?: RequestInit) => {
    const request = new Request(new URL(String(url), "http://frontend.test"), init);
    requests.push(request);
    const path = new URL(request.url).pathname;
    if (request.method === "POST") {
      if (path !== root + (action === "approve" ? "/review/decision" : "/final-lock"))
        throw new Error(`Unexpected editorial write ${path}`);
      return await new Promise<Response>(resolve => { finish = () => {
        status = action === "approve" ? "approved" : "final";
        resolve(Response.json({ saved: true }));
      }; });
    }
    const latest = { run: { pipeline_run_id: runId, status: "completed" }, current: true,
      selected, critique: null, snapshot_artifact_id: `AR-${"e".repeat(32)}`,
      versions: [{ version_id: versionId, version_no: 2, status }],
      usage: { attempts: 1, input_tokens: 10, output_tokens: 20, estimated_cost: 0, latency_ms: 1, retries: 0 } };
    if (path === root + "/generation/latest") return Response.json(latest);
    if (path === root + "/brief/eligible") return Response.json({ artifact_id: `AR-${"f".repeat(32)}`,
      version: 1, content: { scene_goal: "Return the seed" }, source_refs: [] });
    if (path === root + "/review") return Response.json({ latest,
      versions: [{ record: { version_id: versionId, version_no: 2, status,
        chapter_title: "The garden gate", content: prose, artifact_id: artifactId },
        artifact: selected, legacy: false, report: null, verification: null }],
      revision_tasks: [], review_gate: { step_id: "gate", status: "success", output_version: 3 } });
    throw new Error(`Unexpected editorial read ${path}`);
  });
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  await screen.findByText(prose);
  fireEvent.change(screen.getByLabelText("Editor identity"), { target: { value: "  editor  " } });
  const button = screen.getByRole("button", { name: action === "approve" ? "Approve" : "Lock final" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  const reads = (suffix: string) => requests.filter(r => r.method === "GET" && new URL(r.url).pathname === root + suffix).length;
  const before = { latest: reads("/generation/latest"), brief: reads("/brief/eligible"), review: reads("/review") };
  fireEvent.click(button);
  await waitFor(() => expect(requests.filter(r => r.method === "POST")).toHaveLength(1));
  const post = requests.find(r => r.method === "POST")!;
  const target = { version_id: versionId, artifact_id: artifactId, version_no: 2, operator: "editor" };
  expect(await post.clone().json()).toEqual(action === "approve" ? {
    ...target, run_id: runId, expected_gate_version: 0, action: "approve", reason: "" } : target);
  expect(JSON.parse(sessionStorage.getItem(pendingKey)!)).toEqual({
    path: new URL(post.url).pathname, body: await post.clone().json() });
  expect(reads("/generation/latest")).toBe(before.latest);
  await act(async () => finish());
  await waitFor(() => {
    expect(reads("/generation/latest")).toBe(before.latest + 1);
    expect(reads("/brief/eligible")).toBe(before.brief + 1);
    expect(reads("/review")).toBe(before.review + 1);
    expect(sessionStorage.getItem(pendingKey)).toBeNull();
    expect(screen.getByRole("button", { name: action === "approve" ? "Regenerate chapter" : "Chapter final-locked" })).toHaveProperty("disabled", action !== "approve");
  });
  expect(screen.getByRole("button", { name: "Approve" })).toHaveProperty("disabled", true);
  expect(screen.getByText(prose)).toBeTruthy();
  expect(requests.filter(r => r.method === "POST")).toHaveLength(1);
  expect(requests.some(r => /\/generation\/context$|\/generations$/.test(new URL(r.url).pathname))).toBe(false);
  expect(sessionStorage.getItem(`novelops.chapter-generation.pending.${book}`)).toBeNull();
});
