import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChapterReviewDesk } from "../src/components/books/chapter-review-desk";
import { api, ApiError } from "../src/api/client";

vi.mock("@/api/client", () => ({
  api: { post: vi.fn() },
  ApiError: class ApiError extends Error { constructor(public status: number, message: string) { super(message); } },
}));
vi.mock("@/components/hotspots/editor-identity", () => ({
  useEditorIdentity: () => ({ operator: "editor", update: vi.fn() }),
}));
vi.mock("@/components/hotspots/use-resource", () => ({
  useResource: () => ({ data: activeReview, loading: false, error: resourceError }),
  errorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "Request failed",
}));

const book = `BK-${"a".repeat(32)}`;
const run = `PR-${"b".repeat(32)}`;
const version1 = `CV-${"c".repeat(32)}`;
const version2 = `CV-${"d".repeat(32)}`;
const artifact1 = `AR-${"e".repeat(32)}`;
const artifact2 = `AR-${"f".repeat(32)}`;
const root = `/api/books/${book}/chapters/1`;
const storageKey = `novelops.chapter-review.pending.${book}.1`;
const review = {
  latest: {
    run: { pipeline_run_id: run, status: "awaiting_approval" }, current: true,
    selected: { artifact_id: artifact2, version: 2, content: { title: "Revised title", prose: "Revised prose" }, source_refs: ["state", "brief", artifact1] },
    snapshot_artifact_id: "state", usage: { attempts: 1, input_tokens: 10, output_tokens: 20, estimated_cost: 0, latency_ms: 100, retries: 0 },
  },
  versions: [
    { record: { version_id: version1, version_no: 1, status: "review", chapter_title: "First title", content: "First prose", artifact_id: artifact1 },
      artifact: { artifact_id: artifact1, version: 1, content: { title: "First title", prose: "First prose" }, source_refs: ["state", "brief"] },
      legacy: false, report: { artifact_id: "old-report", version: 1, content: { summary: "First critique", decision: "revise" }, source_refs: ["state", "brief", artifact1] }, verification: null },
    { record: { version_id: version2, version_no: 2, status: "review", chapter_title: "Revised title", content: "Revised prose", artifact_id: artifact2 },
      artifact: { artifact_id: artifact2, version: 2, content: { title: "Revised title", prose: "Revised prose" }, source_refs: ["state", "brief", artifact1] },
      legacy: false, report: { artifact_id: "new-report", version: 2, content: { summary: "Revised critique", decision: "approve" }, source_refs: ["state", "brief", artifact1] }, verification: null },
  ],
  revision_tasks: [], review_gate: { step_id: "gate", status: "awaiting_approval", output_version: 7 },
};

let activeReview: unknown = review;
let resourceError: unknown = null;
afterEach(() => { cleanup(); sessionStorage.clear(); vi.clearAllMocks(); vi.restoreAllMocks(); activeReview = review; resourceError = null; });

test("historical version follows its own critique and disables editing", () => {
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("Revised prose")).toBeTruthy();
  expect(screen.getByText("Revised critique")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "v1 · review" }));
  expect(screen.getByText("First prose")).toBeTruthy();
  expect(screen.getByText("First critique")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText("Select the current version to take an action.")).toBeTruthy();
});

test("approval posts the exact version and gate, then clears saved intent", async () => {
  const post = vi.mocked(api.post).mockResolvedValue({});
  const onChanged = vi.fn();
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  fireEvent.change(screen.getByLabelText("Decision note"), { target: { value: "  Looks good  " } });
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith(root + "/review/decision", {
    run_id: run, version_id: version2, artifact_id: artifact2, version_no: 2,
    operator: "editor", expected_gate_version: 7, action: "approve", reason: "Looks good",
  }, 120_000));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(sessionStorage.getItem(storageKey)).toBeNull();
});

test("failed submission preserves the exact pending command for retry", async () => {
  const post = vi.mocked(api.post).mockRejectedValueOnce(new Error("Network interrupted")).mockResolvedValueOnce({});
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await screen.findByText("Network interrupted");
  const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
  expect(saved.path).toBe(root + "/review/decision");
  expect(saved.body.version_id).toBe(version2);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same command" }));
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  expect(post.mock.calls[1]).toEqual(post.mock.calls[0]);
  await waitFor(() => expect(sessionStorage.getItem(storageKey)).toBeNull());
});

test("revision requires a concrete change and submits trimmed constraints", async () => {
  const post = vi.mocked(api.post).mockResolvedValue({});
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  fireEvent.click(screen.getByText("Request a constrained revision"));
  const create = screen.getByRole("button", { name: "Create revision and rewrite" }) as HTMLButtonElement;
  expect(create.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Must keep"), { target: { value: "  Keep protagonist  \n\n  Keep setting " } });
  fireEvent.change(screen.getByLabelText("Must change"), { target: { value: "  Tighten pacing  \n\n  Fix continuity " } });
  fireEvent.change(screen.getByLabelText("Do not change"), { target: { value: "  Ending reveal  " } });
  expect(create.disabled).toBe(false);
  fireEvent.click(create);
  await waitFor(() => expect(post).toHaveBeenCalledWith(root + "/review/revision", {
    run_id: run, version_id: version2, artifact_id: artifact2, version_no: 2,
    operator: "editor", expected_gate_version: 7,
    constraints: { must_keep: ["Keep protagonist", "Keep setting"], must_change: ["Tighten pacing", "Fix continuity"], do_not_change: ["Ending reveal"] },
  }, 120_000));
});

test("unreadable saved command asks for history check before clearing", () => {
  sessionStorage.setItem(storageKey, "{not-json");
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("The saved review command is unreadable. Check the version history before clearing it.")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "I checked the version history" }));
  expect(sessionStorage.getItem(storageKey)).toBeNull();
});


test("a stale current draft remains readable but cannot submit editorial changes", () => {
  activeReview = { ...review, latest: { ...review.latest, current: false } };
  const post = vi.mocked(api.post);
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("This draft is not current for final lock. Check the latest StoryState and chapter brief before regenerating.")).toBeTruthy();
  expect(screen.getByText("Revised prose")).toBeTruthy();
  for (const label of ["Approve", "Reject", "Lock final"]) {
    const button = screen.getByRole("button", { name: label }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
  }
  expect(post).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "v1 · review" }));
  expect(screen.getByText("First prose")).toBeTruthy();
});

test("a final-locked chapter preserves historical reading and disables every editorial action", () => {
  activeReview = { ...review, latest: { ...review.latest, run: { ...review.latest.run, status: "completed" } },
    versions: review.versions.map(entry => entry.record.version_id === version2
      ? { ...entry, record: { ...entry.record, status: "final" } } : entry) };
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("This chapter is final-locked. Earlier versions remain readable.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Must change"), { target: { value: "Rewrite the ending" } });
  for (const label of ["Approve", "Reject", "Lock final", "Create revision and rewrite"]) {
    expect((screen.getByRole("button", { name: label }) as HTMLButtonElement).disabled).toBe(true);
  }
  expect(vi.mocked(api.post)).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "v1 · review" }));
  expect(screen.getByText("First prose")).toBeTruthy();
  expect(screen.getByText("First critique")).toBeTruthy();
});

test("a Critic report for the earlier draft is explicitly distinguished from the selected rewrite", () => {
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText(/This Critic report scored v1 before the rewrite/)).toBeTruthy();
  expect(screen.getByText("Revised prose")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "v1 · review" }));
  expect(screen.queryByText(/This Critic report scored v1 before the rewrite/)).toBeNull();
  expect(screen.getByText("First critique")).toBeTruthy();
});

test("legacy versions without a current generation remain available for reading only", () => {
  // A legacy row has prose but no immutable Artifact provenance or current run.
  activeReview = { ...review, latest: null, versions: [
    { ...review.versions[0], artifact: null, legacy: true, report: null, verification: null },
  ] };
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("Earlier chapter versions are available for reading. Generate a chapter to enable current run review.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "v1 · review" }));
  expect(screen.getByText("First prose")).toBeTruthy();
  expect(screen.getByText("Legacy version: exact Artifact provenance is unavailable.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(vi.mocked(api.post)).not.toHaveBeenCalled();
});

test("an unstarted chapter offers generation guidance without an editorial action", () => {
  activeReview = { ...review, latest: null, versions: [] };
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("Generate a chapter to open its review desk.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Lock final" })).toBeNull();
});

test("a running chapter without a verified draft cannot be approved or locked", () => {
  activeReview = { ...review, latest: { ...review.latest, run: { ...review.latest.run, status: "running" }, selected: null },
    versions: [] };
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByText("The writing loop is running.")).toBeTruthy();
  for (const label of ["Approve", "Reject", "Lock final"]) {
    expect((screen.getByRole("button", { name: label }) as HTMLButtonElement).disabled).toBe(true);
  }
});

test("expired authentication gives sign-in guidance without discarding a saved exact command", () => {
  const command = { path: root + "/review/decision", body: { run_id: run, version_id: version2,
    artifact_id: artifact2, version_no: 2, operator: "editor", expected_gate_version: 7, action: "approve", reason: "" } };
  sessionStorage.setItem(storageKey, JSON.stringify(command));
  activeReview = null;
  resourceError = new ApiError(401, "Expired session");
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={vi.fn()} />);
  expect(screen.getByRole("alert").textContent).toContain("Sign in to review chapters.");
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? "null")).toEqual(command);
  expect(vi.mocked(api.post)).not.toHaveBeenCalled();
});

test("failure to persist recovery intent prevents sending an untracked write", async () => {
  const post = vi.mocked(api.post).mockResolvedValue({});
  const onChanged = vi.fn();
  render(<ChapterReviewDesk bookId={book} chapterNo={1} refresh={0} onChanged={onChanged} />);
  vi.spyOn(Object.getPrototypeOf(sessionStorage), "setItem").mockImplementation(() => { throw new Error("Storage unavailable"); });
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Storage unavailable");
  expect(post).not.toHaveBeenCalled();
  expect(onChanged).not.toHaveBeenCalled();
});
