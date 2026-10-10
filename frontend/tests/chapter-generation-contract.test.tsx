import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { ChapterGeneration } from "../src/components/books/chapter-generation";

const book = `BK-${"1".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
const key = `novelops.chapter-generation.pending.${book}`;
const context = { book_id: book, chapter_no: 1, version: 7, start_version_no: 4,
  state_artifact_id: `AR-${"2".repeat(32)}`, state_version: 3,
  brief_artifact_id: `AR-${"3".repeat(32)}`, brief_version: 2, source_version_id: "",
  constraints: { must_keep: [], must_change: [], do_not_change: [] } };
const pending = { path: root + "/generations", body: context };
const eligible = { artifact_id: context.brief_artifact_id, version: 2, content: { scene_goal: "Find the seeds" }, source_refs: [context.state_artifact_id] };
const emptyReview = { latest: null, versions: [], revision_tasks: [] };
type Artifact = { artifact_id: string; version: number; content: Record<string, unknown>; source_refs: string[] };
function run(status: string) {
  return { run: { pipeline_run_id: `PR-${"4".repeat(32)}`, status }, selected: null as Artifact | null,
    critique: null as Artifact | null, snapshot_artifact_id: `AR-${"5".repeat(32)}`, current: true,
    versions: [] as { version_id: string; version_no: number; status: string }[], version_summaries: [] as { version_id: string; version_no: number; status: string }[], usage: { attempts: 0, input_tokens: null, output_tokens: null,
      estimated_cost: null, latency_ms: null, retries: 0 } };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); vi.unstubAllGlobals(); });

function response(input: unknown, init: RequestInit, latest: ReturnType<typeof run> | null = null, hasBrief = true) {
  const path = String(input);
  if (init.method === "POST") return Response.json({ pipeline_run_id: `PR-${"4".repeat(32)}` });
  if (path.endsWith("/generation/latest")) return Response.json(latest);
  if (path.endsWith("/brief/eligible")) return hasBrief ? Response.json(eligible) : Response.json({ detail: "No eligible brief" }, { status: 409 });
  if (path.endsWith("/generation/context")) {
    const chapter = Number(/\/chapters\/(\d+)\//.exec(path)?.[1]);
    return Response.json({ ...context, chapter_no: chapter });
  }
  if (path.endsWith("/review")) return Response.json({ ...emptyReview, latest,
    versions: latest?.versions.map(version => ({ record: { ...version,
      content: latest.selected?.content.prose, chapter_title: latest.selected?.content.title,
      artifact_id: latest.selected?.artifact_id }, artifact: latest.selected, legacy: false,
      report: latest.critique, verification: null })) ?? [] });
  throw new Error("Unexpected generation endpoint: " + path);
}
function serve(latest: ReturnType<typeof run> | null = null, hasBrief = true) {
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(response(input, init, latest, hasBrief)));
  vi.stubGlobal("fetch", transport);
  return transport;
}
const writes = (transport: ReturnType<typeof serve>) => transport.mock.calls.filter(([, init]) => init.method === "POST");

async function open(latest: ReturnType<typeof run> | null = null, hasBrief = true) {
  const transport = serve(latest, hasBrief);
  render(<ChapterGeneration bookId={book} />);
  if (hasBrief) await waitFor(() => expect((screen.getByRole("button", { name: latest ? "Regenerate chapter" : "Generate chapter" }) as HTMLButtonElement).disabled).toBe(!!latest && ["pending", "running", "awaiting_approval"].includes(latest.run.status) || sessionStorage.getItem(key) !== null));
  else await screen.findByText("Approve the StoryBible and generate a current chapter brief first.");
  return transport;
}

test.each([JSON.stringify(pending), "{unreadable"])("failed checked-history clear preserves exact generation intent: %s", async saved => {
  sessionStorage.setItem(key, saved);
  const transport = await open();
  const remove = vi.spyOn(Object.getPrototypeOf(sessionStorage), "removeItem")
    .mockImplementation(() => { throw new Error("Browser storage unavailable"); });
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" }));
  expect(await screen.findByText("Could not clear the saved chapter request. Browser storage unavailable Check browser storage access and try again.")).toHaveProperty("role", "alert");
  expect(sessionStorage.getItem(key)).toBe(saved);
  expect(writes(transport)).toHaveLength(0);
  remove.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(screen.queryByText(/Could not clear the saved chapter request/)).toBeNull();
});

test("generation uses the selected chapter and exact context sources before write", async () => {
  const transport = await open();
  fireEvent.change(screen.getByLabelText("Chapter number"), { target: { value: "2" } });
  await waitFor(() => expect((screen.getByRole("button", { name: "Generate chapter" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Generate chapter" }));
  await waitFor(() => expect(writes(transport)).toHaveLength(1));
  const [path, init] = writes(transport)[0];
  expect(path).toBe(`/api/books/${book}/chapters/2/generations`);
  expect(JSON.parse(String(init.body))).toEqual({ ...context, chapter_no: 2 });
  expect(init.headers).not.toHaveProperty("x-api-key");
  expect(transport.mock.calls.some(([input]) => input === `/api/books/${book}/chapters/2/generation/context`)).toBe(true);
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
});

test("without an eligible brief generation remains disabled and sends no write", async () => {
  const transport = await open(null, false);
  const button = screen.getByRole("button", { name: "Generate chapter" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(button);
  expect(writes(transport)).toHaveLength(0);
  expect(transport.mock.calls.some(([input]) => String(input).endsWith("/generation/context"))).toBe(false);
});

test("invalid chapter bounds disable generation and refresh without context/write", async () => {
  const transport = await open();
  for (const value of ["0", "10001", "1.5"]) {
    fireEvent.change(screen.getByLabelText("Chapter number"), { target: { value } });
    for (const name of ["Generate chapter", "Refresh chapter"]) {
      const button = screen.getByRole("button", { name }) as HTMLButtonElement;
      expect(button.disabled).toBe(true); fireEvent.click(button);
    }
  }
  expect(writes(transport)).toHaveLength(0);
  expect(transport.mock.calls.some(([input]) => String(input).endsWith("/generation/context"))).toBe(false);
});

test.each(["pending", "running", "awaiting_approval"])("a %s chapter run prevents overlapping generation", async status => {
  const transport = await open(run(status));
  const button = screen.getByRole("button", { name: "Regenerate chapter" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fireEvent.click(button);
  expect(writes(transport)).toHaveLength(0);
});

test.each(["completed", "failed", "blocked", "cancelled"])("a %s run can regenerate from a current brief", async status => {
  const transport = await open(run(status));
  fireEvent.click(screen.getByRole("button", { name: "Regenerate chapter" }));
  await waitFor(() => expect(writes(transport)).toHaveLength(1));
  expect(JSON.parse(String(writes(transport)[0][1].body))).toEqual(context);
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
});

test.each([401, 503])("generation read status %s gives contextual guidance without write", async status => {
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(
    String(input).endsWith("/generation/latest") ? Response.json({ detail: "Unavailable" }, { status }) : response(input, init)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  await screen.findByText(status === 401 ? "Sign in to generate chapters." : "Chapter generation is not configured for this workspace.");
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
});

test("context failure sends no chapter request and shows a recovery error", async () => {
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(
    String(input).endsWith("/generation/context") ? Response.json({ detail: "Sources changed" }, { status: 409 }) : response(input, init)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Generate chapter" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Generate chapter" }));
  expect(await screen.findByText("Sources changed")).toHaveProperty("role", "alert");
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("an expired write session preserves original chapter sources for exact retry", async () => {
  let fail = true;
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(
    init.method === "POST" && fail ? Response.json({ detail: "Expired session" }, { status: 401 }) : response(input, init)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Generate chapter" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Generate chapter" }));
  expect(await screen.findByText("Sign in to generate chapters.")).toHaveProperty("role", "alert");
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(pending));
  fireEvent.change(screen.getByLabelText("Chapter number"), { target: { value: "2" } });
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry the same request" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  const posts = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(posts).toHaveLength(2);
  expect(posts[1][0]).toBe(root + "/generations");
  expect(posts[0][1].body).toBe(posts[1][1].body);
});

test("unavailable persistence prevents an untracked generation write", async () => {
  const transport = await open();
  vi.spyOn(Object.getPrototypeOf(sessionStorage), "setItem").mockImplementation(() => { throw new Error("Cannot preserve chapter intent"); });
  fireEvent.click(screen.getByRole("button", { name: "Generate chapter" }));
  expect(await screen.findByText("Cannot preserve chapter intent")).toHaveProperty("role", "alert");
  expect(writes(transport)).toHaveLength(0);
});

test("pending generation writes disable replay/refresh and do not duplicate submission", async () => {
  sessionStorage.setItem(key, JSON.stringify(pending));
  let finish!: (value: Response) => void;
  const transport = vi.fn((input: unknown, init: RequestInit) => init.method === "POST" ?
    new Promise<Response>(resolve => { finish = resolve; }) : Promise.resolve(response(input, init)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same request" }));
  for (const name of ["Retry the same request", "I checked the history", "Refresh chapter"]) {
    const button = screen.getByRole("button", { name }) as HTMLButtonElement;
    expect(button.disabled).toBe(true); fireEvent.click(button);
  }
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(1);
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(pending));
  await act(async () => finish(Response.json({ pipeline_run_id: `PR-${"4".repeat(32)}` })));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
});

test("server snapshot never exposes the tab-local generation command", () => {
  sessionStorage.setItem(key, JSON.stringify(pending));
  const transport = serve();
  const html = renderToString(<ChapterGeneration bookId={book} />);
  expect(html).not.toContain("Retry the same request");
  expect(html).not.toContain(context.state_artifact_id);
  expect(transport).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(pending));
});

test("the verified prose, critique and immutable source IDs remain readable", async () => {
  const latest = run("completed");
  latest.selected = { artifact_id: `AR-${"6".repeat(32)}`, version: 4,
    content: { title: "A shared garden", prose: "Mira finds the seeds behind the gate." },
    source_refs: [latest.snapshot_artifact_id, context.brief_artifact_id] };
  latest.critique = { artifact_id: `AR-${"7".repeat(32)}`, version: 1,
    content: { summary: "A focused garden scene", decision: "pass",
      pacing: { score: 3, evidence: "The middle section needs a clearer beat." } },
    source_refs: [latest.snapshot_artifact_id, context.brief_artifact_id, latest.selected.artifact_id] };
  const version = { version_id: `CV-${"8".repeat(32)}`, version_no: 4, status: "review" };
  latest.versions = [version]; latest.version_summaries = [version];
  const transport = await open(latest);
  expect(screen.getAllByText("Mira finds the seeds behind the gate.").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("A focused garden scene")).toBeTruthy();
  fireEvent.click(screen.getByText(/^(?:Review quality dimensions|Quality dimensions)$/));
  expect(screen.getByText("pacing · 3/5")).toBeTruthy();
  expect(screen.getByText("The middle section needs a clearer beat.")).toBeTruthy();
  expect(screen.getByText("style · ?/5")).toBeTruthy();
  fireEvent.click(screen.getByText(/^(?:Sources and model usage|Sources, usage and trace)$/));
  expect(screen.getByText(latest.snapshot_artifact_id)).toBeTruthy();
  expect(screen.getByText(latest.selected.artifact_id)).toBeTruthy();
  expect(writes(transport)).toHaveLength(0);
});

test("manual chapter refresh reads current run state instead of submitting work", async () => {
  let refreshed = false;
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(
    response(input, init, refreshed ? run("blocked") : null)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Generate chapter" }) as HTMLButtonElement).disabled).toBe(false));
  const initialReads = transport.mock.calls.filter(([input]) => String(input).endsWith("/generation/latest")).length;
  refreshed = true;
  fireEvent.click(screen.getByRole("button", { name: "Refresh chapter" }));
  await screen.findByRole("button", { name: "Regenerate chapter" });
  expect(transport.mock.calls.filter(([input]) => String(input).endsWith("/generation/latest"))).toHaveLength(initialReads + 1);
  expect(screen.getAllByText("blocked").length).toBeGreaterThanOrEqual(1);
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
});

test("a source-stale draft remains readable with explicit regeneration guidance", async () => {
  const latest = run("completed"); latest.current = false;
  latest.selected = { artifact_id: `AR-${"6".repeat(32)}`, version: 4,
    content: { title: "Earlier garden draft", prose: "The earlier garden prose stays readable." },
    source_refs: [latest.snapshot_artifact_id, context.brief_artifact_id] };
  const version = { version_id: `CV-${"8".repeat(32)}`, version_no: 4, status: "candidate" };
  latest.versions = [version]; latest.version_summaries = [version];
  const transport = await open(latest);
  expect(screen.getByText("This draft is not current for final lock. Check the latest StoryState and chapter brief before regenerating.")).toHaveProperty("role", "status");
  expect(screen.getAllByText("The earlier garden prose stays readable.").length).toBeGreaterThanOrEqual(1);
  expect((screen.getByRole("button", { name: "Regenerate chapter" }) as HTMLButtonElement).disabled).toBe(false);
  expect(writes(transport)).toHaveLength(0);
});

test("the context phase prevents repeated generation clicks before a command exists", async () => {
  const contexts: ((response: Response) => void)[] = [];
  const transport = vi.fn((input: unknown, init: RequestInit) => String(input).endsWith("/generation/context") ?
    new Promise<Response>(resolve => { contexts.push(resolve); }) : Promise.resolve(response(input, init)));
  vi.stubGlobal("fetch", transport);
  render(<ChapterGeneration bookId={book} />);
  const button = await screen.findByRole("button", { name: "Generate chapter" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button); fireEvent.click(button);
  const wasDisabled = (button as HTMLButtonElement).disabled;
  const contextCount = contexts.length;
  const hadProgress = screen.queryByText("Preparing chapter generation…") !== null;
  await act(async () => { for (const resolve of contexts) resolve(Response.json(context)); });
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(contextCount).toBe(1);
  expect(wasDisabled).toBe(true);
  expect(hadProgress).toBe(true);
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(1);
});
