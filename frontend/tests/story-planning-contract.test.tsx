import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { StoryPlanning } from "../src/components/books/story-planning";

const book = `BK-${"1".repeat(32)}`;
const run = `PR-${"2".repeat(32)}`;
const artifact = `AR-${"3".repeat(32)}`;
const state = `AR-${"4".repeat(32)}`;
const step = `SR-${"5".repeat(32)}`;
const root = `/api/books/${book}`;
const key = `novelops.story-planning.pending.${book}`;
const bibleContext = { book_id: book, base_state_artifact_id: state, base_version: 2,
  version: 3, change_scope: "initial", feedback: "Existing direction" };
const pending = { path: root + "/bibles", body: bibleContext };
const gate = { run: { pipeline_run_id: run, status: "awaiting_approval", steps: [
  { step_run_id: step, step_key: "review", status: "awaiting_approval", output_version: 5 }] },
  request: { version: 3 }, artifact: { artifact_id: artifact, content: {
    premise: "A shared garden", protagonist: ["Mira", "Ren"], power_rules: { limit: "Shared care" } } },
  current: true, eligible: false, snapshot_artifact_id: "AR-bible-snapshot" };

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); vi.unstubAllGlobals(); });

function serve(bibles: unknown[] = [], briefs: unknown[] = [], approved = false) {
  const transport = vi.fn((input: unknown, init: RequestInit) => {
    const path = String(input);
    const data = init.method === "POST" ? { saved: true } : path.endsWith("/bible/context") ? { ...bibleContext, change_scope: approved ? "major" : "initial" } :
      path.endsWith("/brief/context") ? { book_id: book, chapter_no: 2, state_artifact_id: state,
        state_version: 2, version: 4, feedback: "Server feedback" } : path.endsWith("/bibles") ? bibles : briefs;
    return Promise.resolve(Response.json(data));
  });
  vi.stubGlobal("fetch", transport);
  return transport;
}
const writes = (transport: ReturnType<typeof serve>) => transport.mock.calls.filter(([, init]) => init.method === "POST");

async function open(bibles: unknown[] = [], approved = false, briefs: unknown[] = []) {
  const transport = serve(bibles, briefs, approved);
  render(<StoryPlanning bookId={book} approvedBible={approved} />);
  await waitFor(() => expect(screen.queryByText("Loading story planning…")).toBeNull());
  return transport;
}

test.each([JSON.stringify(pending), "{unreadable"])("failed history clear preserves story planning intent: %s", async saved => {
  sessionStorage.setItem(key, saved);
  const transport = await open();
  const remove = vi.spyOn(Object.getPrototypeOf(sessionStorage), "removeItem")
    .mockImplementation(() => { throw new Error("Browser storage unavailable"); });
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" }));
  expect(await screen.findByText("Could not clear the saved planning request. Browser storage unavailable Check browser storage access and try again.")).toHaveProperty("role", "alert");
  expect(sessionStorage.getItem(key)).toBe(saved);
  expect(writes(transport)).toHaveLength(0);
  remove.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "I checked the history" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(screen.queryByText(/Could not clear the saved planning request/)).toBeNull();
  expect((screen.getByRole("button", { name: "Generate StoryBible" }) as HTMLButtonElement).disabled).toBe(false);
});

test.each([false, true])("StoryBible generation freezes actual context and feedback, approved=%s", async approved => {
  const transport = await open([], approved);
  fireEvent.change(screen.getByLabelText("Feedback for next generation or revision"), { target: { value: approved ? "  Expand the garden  " : "   " } });
  fireEvent.click(screen.getByRole("button", { name: approved ? "Propose major StoryBible change" : "Generate StoryBible" }));
  await waitFor(() => expect(writes(transport)).toHaveLength(1));
  const write = writes(transport)[0];
  expect(write[0]).toBe(root + "/bibles");
  expect(JSON.parse(String(write[1].body))).toEqual({ ...bibleContext, change_scope: approved ? "major" : "initial",
    feedback: approved ? "Expand the garden" : "Existing direction" });
  expect(write[1].headers).not.toHaveProperty("x-api-key");
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect((screen.getByLabelText("Feedback for next generation or revision") as HTMLTextAreaElement).value).toBe("");
  expect(transport.mock.calls.some(([input]) => input === root + "/bible/context")).toBe(true);
});

test.each(["approve", "revise", "reject"] as const)("exact StoryBible %s binds gate, artifact and editor", async action => {
  const transport = await open([gate]);
  expect((screen.getByRole("button", { name: "Approve StoryBible" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Editor name"), { target: { value: "  Mei  " } });
  fireEvent.change(screen.getByLabelText("Feedback for next generation or revision"), { target: { value: "  Clarify the garden rule  " } });
  fireEvent.click(screen.getByRole("button", { name: action === "approve" ? "Approve StoryBible" : action === "revise" ? "Request revision" : "Reject" }));
  await waitFor(() => expect(writes(transport)).toHaveLength(1));
  expect(writes(transport)[0][0]).toBe(`/api/story-planning/runs/${run}/decision`);
  expect(JSON.parse(String(writes(transport)[0][1].body))).toEqual({ step_id: step,
    artifact_id: action === "approve" ? artifact : "", expected_version: 5, action,
    operator: "Mei", reason: "Clarify the garden rule" });
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect((screen.getByLabelText("Feedback for next generation or revision") as HTMLTextAreaElement).value)
    .toBe(action === "revise" ? "  Clarify the garden rule  " : "");
});

test("revision requires actionable feedback and never sends an empty request", async () => {
  const transport = await open([gate]);
  fireEvent.change(screen.getByLabelText("Editor name"), { target: { value: "Mei" } });
  fireEvent.click(screen.getByRole("button", { name: "Request revision" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Add revision feedback before requesting changes.");
  expect(writes(transport)).toHaveLength(0);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("an approved Bible permits a brief bound to the selected chapter and state", async () => {
  const transport = await open([], true);
  fireEvent.change(screen.getByLabelText("Chapter number"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Feedback for next generation or revision"), { target: { value: "  End at the gate  " } });
  fireEvent.click(screen.getByRole("button", { name: "Generate chapter brief" }));
  await waitFor(() => expect(writes(transport)).toHaveLength(1));
  expect(writes(transport)[0][0]).toBe(root + "/chapters/2/briefs");
  expect(JSON.parse(String(writes(transport)[0][1].body))).toEqual({ book_id: book, chapter_no: 2,
    state_artifact_id: state, state_version: 2, version: 4, feedback: "End at the gate" });
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
});

test("missing approval and invalid chapter disable brief generation without write", async () => {
  const transport = await open();
  expect((screen.getByRole("button", { name: "Generate chapter brief" }) as HTMLButtonElement).disabled).toBe(true);
  for (const value of ["0", "10001", "1.5"]) {
    fireEvent.change(screen.getByLabelText("Chapter number"), { target: { value } });
    expect((screen.getByRole("button", { name: "Generate chapter brief" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Generate chapter brief" }));
  }
  expect(writes(transport)).toHaveLength(0);
});

test("Bible, brief source details and eligibility reflect actual returned values", async () => {
  const brief = { ...gate, run: { ...gate.run, status: "completed", steps: [] }, eligible: true,
    request: { version: 4 }, snapshot_artifact_id: "AR-brief-snapshot", artifact: { artifact_id: "AR-brief", content: {
      opening_hook: "The gate opens", scene_goal: ["Find seeds", "Meet Ren"], conflict: "Lost map",
      payoff: { outcome: "Seeds found" }, ending_hook: "The flower speaks", state_artifact_id: state, state_version: 2 } } };
  await open([gate], true, [brief]);
  expect(screen.getAllByText("Mira · Ren", { exact: false })).toHaveLength(2);
  fireEvent.click(screen.getByText("Review full StoryBible"));
  expect(screen.getByText('{"limit":"Shared care"}')).toBeTruthy();
  expect(screen.getByText("The flower speaks")).toBeTruthy();
  expect(screen.getByText("Find seeds · Meet Ren")).toBeTruthy();
  expect(screen.getByText('{"outcome":"Seeds found"}')).toBeTruthy();
  expect(screen.getByText("Version 4 · Policy eligible")).toBeTruthy();
  fireEvent.click(screen.getByText("Source versions"));
  expect(screen.getByText(`State ${state} · v2`)).toBeTruthy();
  expect(screen.getByText("Snapshot AR-brief-snapshot")).toBeTruthy();
});

test.each([401, 503])("planning read status %s gives contextual sign-in or unconfigured guidance", async status => {
  const transport = vi.fn(() => Promise.resolve(Response.json({ detail: "Unavailable" }, { status })));
  vi.stubGlobal("fetch", transport);
  render(<StoryPlanning bookId={book} approvedBible={false} />);
  expect(await screen.findAllByText(status === 401 ? "Sign in to use story planning." : "Story planning is not configured for this workspace.")).toHaveLength(status === 401 ? 2 : 1);
  expect(sessionStorage.getItem(key)).toBeNull();
  expect(transport).toHaveBeenCalledTimes(2);
});

test("failed exact decision keeps the signed command for identical replay after recovery", async () => {
  let fail = true;
  const transport = vi.fn((input: unknown, init: RequestInit) => Promise.resolve(
    init.method === "POST" ? Response.json(fail ? { detail: "Version changed" } : { saved: true }, { status: fail ? 409 : 200 }) :
      Response.json(String(input).endsWith("/bibles") ? [gate] : [])));
  vi.stubGlobal("fetch", transport);
  render(<StoryPlanning bookId={book} approvedBible={false} />);
  await screen.findByLabelText("Editor name");
  fireEvent.change(screen.getByLabelText("Editor name"), { target: { value: "Mei" } });
  fireEvent.click(screen.getByRole("button", { name: "Approve StoryBible" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Version changed");
  const saved = sessionStorage.getItem(key);
  expect(JSON.parse(saved!).body.operator).toBe("Mei");
  fireEvent.change(screen.getByLabelText("Editor name"), { target: { value: "Ren" } });
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry the same request" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  const posts = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(posts).toHaveLength(2);
  expect(posts[0][1].body).toBe(posts[1][1].body);
  expect(posts[1][1].body).toBe(JSON.stringify(JSON.parse(saved!).body));
});

test("server snapshot keeps saved planning request and editor local to the tab", () => {
  sessionStorage.setItem(key, JSON.stringify(pending));
  sessionStorage.setItem("novelops.editor.name", "Private editor");
  const transport = serve();
  const html = renderToString(<StoryPlanning bookId={book} approvedBible={false} />);
  expect(html).toContain("Loading story planning");
  expect(html).not.toContain("Private editor");
  expect(html).not.toContain("Retry the same request");
  expect(transport).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(pending));
});

test.each(["bible", "brief"] as const)("a %s context failure preserves feedback and sends no write", async kind => {
  const transport = vi.fn((...args: [unknown, RequestInit]) => Promise.resolve(
    String(args[0]).endsWith("/context") ? Response.json({ detail: "Session expired" }, { status: 401 }) : Response.json([])));
  vi.stubGlobal("fetch", transport);
  render(<StoryPlanning bookId={book} approvedBible={true} />);
  await waitFor(() => expect(screen.queryByText("Loading story planning…")).toBeNull());
  fireEvent.change(screen.getByLabelText("Feedback for next generation or revision"), { target: { value: "Keep this feedback" } });
  fireEvent.click(screen.getByRole("button", { name: kind === "bible" ? "Propose major StoryBible change" : "Generate chapter brief" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Sign in to use story planning.");
  expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
  expect(sessionStorage.getItem(key)).toBeNull();
  expect((screen.getByLabelText("Feedback for next generation or revision") as HTMLTextAreaElement).value).toBe("Keep this feedback");
});

test("failed intent persistence prevents an untracked planning write and keeps feedback", async () => {
  const transport = await open();
  vi.spyOn(Object.getPrototypeOf(sessionStorage), "setItem").mockImplementation(() => { throw new Error("Cannot preserve planning intent"); });
  fireEvent.change(screen.getByLabelText("Feedback for next generation or revision"), { target: { value: "Keep the garden" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate StoryBible" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Cannot preserve planning intent");
  expect(writes(transport)).toHaveLength(0);
  expect((screen.getByLabelText("Feedback for next generation or revision") as HTMLTextAreaElement).value).toBe("Keep the garden");
});

test("running Bible and brief show progress and prevent overlapping generation", async () => {
  const active = { ...gate, artifact: null, current: false,
    run: { ...gate.run, status: "running", steps: [] } };
  const transport = await open([active], true, [active]);
  expect(screen.getAllByText("Generation is running or needs attention.")).toHaveLength(2);
  expect(screen.queryByRole("button", { name: "Approve StoryBible" })).toBeNull();
  for (const name of ["Propose major StoryBible change", "Regenerate chapter brief"]) {
    const button = screen.getByRole("button", { name }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
  }
  expect(writes(transport)).toHaveLength(0);
});

test.each(["bible", "brief"] as const)("the %s context phase blocks repeated planning clicks", async kind => {
  const contexts: ((response: Response) => void)[] = [];
  const transport = vi.fn((input: unknown, init: RequestInit) => String(input).endsWith("/context") ?
    new Promise<Response>(resolve => { contexts.push(resolve); }) : Promise.resolve(Response.json(init.method === "POST" ? { saved: true } : [])));
  vi.stubGlobal("fetch", transport);
  render(<StoryPlanning bookId={book} approvedBible={true} />);
  await waitFor(() => expect(screen.queryByText("Loading story planning…")).toBeNull());
  const button = screen.getByRole("button", { name: kind === "bible" ? "Propose major StoryBible change" : "Generate chapter brief" });
  fireEvent.click(button); fireEvent.click(button);
  const wasDisabled = (button as HTMLButtonElement).disabled;
  const contextCount = contexts.length;
  const hadProgress = screen.queryByText("Preparing story planning…") !== null;
  const data = kind === "bible" ? { ...bibleContext, change_scope: "major" } : {
    book_id: book, chapter_no: 1, state_artifact_id: state, state_version: 2, version: 4, feedback: "" };
  await act(async () => { for (const resolve of contexts) resolve(Response.json(data)); });
  await waitFor(() => expect(transport.mock.calls.filter(([, init]) => init.method === "POST").length).toBeGreaterThanOrEqual(1));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(contextCount).toBe(1);
  expect(wasDisabled).toBe(true);
  expect(hadProgress).toBe(true);
  const posts = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(posts).toHaveLength(1);
  expect(JSON.parse(String(posts[0][1].body))).toEqual(data);
});
