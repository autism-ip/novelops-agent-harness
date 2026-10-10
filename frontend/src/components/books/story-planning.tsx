"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/api/client";
import { useEditorIdentity } from "@/components/hotspots/editor-identity";
import { errorMessage, useResource } from "@/components/hotspots/use-resource";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { parsePendingPlan, type PendingPlan } from "./planning-state";

type WorkflowStep = { step_run_id: string; step_key: string; status: string; output_version: number };
type PlanningRun = { run: { pipeline_run_id: string; status: string; steps: WorkflowStep[] };
  request: { version: number; chapter_no?: number }; artifact: { artifact_id: string; content: Record<string, unknown> } | null;
  current: boolean; eligible: boolean; decision?: { action: string; reason?: string } | null;
  snapshot_artifact_id: string };
type BibleContext = { book_id: string; base_state_artifact_id: string; base_version: number;
  version: number; change_scope: "initial" | "major"; feedback: string };
type BriefContext = { book_id: string; chapter_no: number; state_artifact_id: string;
  state_version: number; version: number; feedback: string };

const EVENT = "novelops-story-planning-request";
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function saved(key: string) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}
function setSaved(key: string, value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } finally { window.dispatchEvent(new Event(EVENT)); }
}
function visibleError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) return "Sign in to use story planning.";
  return errorMessage(cause);
}
function textValue(value: unknown) {
  if (Array.isArray(value)) return value.map(String).join(" · ");
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function StoryPlanning({ bookId, approvedBible }: { bookId: string; approvedBible: boolean }) {
  const key = `novelops.story-planning.pending.${bookId}`;
  const pendingRaw = useSyncExternalStore(subscribe, () => saved(key), () => null);
  const pending = parsePendingPlan(pendingRaw);
  const [revision, setRevision] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [chapter, setChapter] = useState("1");
  const busy = useRef(false);
  const { operator, update: setOperator } = useEditorIdentity();
  const chapterNo = Number(chapter);
  const validChapter = Number.isSafeInteger(chapterNo) && chapterNo >= 1 && chapterNo <= 10000;
  const bibles = useResource<PlanningRun[]>(`/api/books/${encodeURIComponent(bookId)}/bibles`, revision, 5000);
  const briefs = useResource<PlanningRun[]>(validChapter ?
    `/api/books/${encodeURIComponent(bookId)}/chapters/${chapterNo}/briefs` : null, revision, 5000);
  const bible = bibles.data?.[0];
  const brief = briefs.data?.[0];
  const gate = bible?.run.steps.find(step => step.step_key === "review" && step.status === "awaiting_approval");
  const bibleBusy = !!bible && !["completed", "failed", "blocked", "cancelled"].includes(bible.run.status);
  const briefBusy = !!brief && !["completed", "failed", "blocked", "cancelled"].includes(brief.run.status);
  const unavailable = bibles.error instanceof ApiError && bibles.error.status === 503;

  function clearPending() {
    setError(null);
    try { setSaved(key, null); }
    catch (cause) {
      setError(`Could not clear the saved planning request. ${visibleError(cause)} Check browser storage access and try again.`);
    }
  }

  async function submit(request: PendingPlan | (() => Promise<PendingPlan>)) {
    if (busy.current) return;
    busy.current = true;
    setWorking(true);
    setError(null);
    try {
      const command = typeof request === "function" ? await request() : request;
      setSaved(key, JSON.stringify(command));
      await api.post(command.path, command.body);
      setSaved(key, null);
      setRevision(value => value + 1);
      if (!(command.path.endsWith("/decision") && command.body.action === "revise")) setFeedback("");
    } catch (cause) { setError(visibleError(cause)); }
    finally { busy.current = false; setWorking(false); }
  }

  async function startBible() {
    if (pendingRaw || working) return;
    await submit(async () => {
      const context = await api.get<BibleContext>(`/api/books/${encodeURIComponent(bookId)}/bible/context`);
      return { path: `/api/books/${encodeURIComponent(bookId)}/bibles`,
        body: { ...context, feedback: feedback.trim() || context.feedback } };
    });
  }

  async function decide(action: "approve" | "revise" | "reject") {
    if (!gate || !bible?.artifact || !operator.trim() || pendingRaw || working) return;
    if (action === "revise" && !feedback.trim()) {
      setError("Add revision feedback before requesting changes."); return;
    }
    await submit({ path: `/api/story-planning/runs/${encodeURIComponent(bible.run.pipeline_run_id)}/decision`,
      body: { step_id: gate.step_run_id, artifact_id: action === "approve" ? bible.artifact.artifact_id : "",
        expected_version: gate.output_version, action, operator: operator.trim(), reason: feedback.trim() } });
  }

  async function startBrief() {
    if (!validChapter || pendingRaw || working) return;
    await submit(async () => {
      const context = await api.get<BriefContext>(
        `/api/books/${encodeURIComponent(bookId)}/chapters/${chapterNo}/brief/context`);
      return { path: `/api/books/${encodeURIComponent(bookId)}/chapters/${chapterNo}/briefs`,
        body: { ...context, feedback: feedback.trim() } };
    });
  }

  if (unavailable) return <section className="surface p-5 text-sm text-muted-foreground" aria-label="Story planning">
    Story planning is not configured for this workspace.
  </section>;

  return <section className="surface space-y-6 p-5 sm:p-6" aria-label="Story planning">
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Next story decision</p>
      <h2 className="text-xl font-semibold">Story planning</h2>
      <p className="text-sm text-muted-foreground">Build the approved StoryBible, then plan a chapter from an exact StoryState snapshot.</p>
    </div>
    {bibles.loading && <p role="status" className="text-sm">Loading story planning…</p>}
    {bibles.error != null && <p role="alert" className="text-sm text-destructive">{visibleError(bibles.error)}</p>}
    {working && !pendingRaw && <p role="status" className="text-sm">Preparing story planning…</p>}
    {pending && <div className="surface-soft space-y-2 p-4 text-sm" role="status">
      <p>{working ? "Saving story planning… This may take a moment." : "The previous outcome is unconfirmed. Retry sends the same Book, version and artifact IDs."}</p>
      <Button variant="outline" disabled={working} onClick={() => void submit(pending)}>Retry the same request</Button>
      <Button variant="ghost" disabled={working} onClick={clearPending}>I checked the history</Button>
    </div>}
    {pendingRaw && !pending && <div className="surface-soft space-y-2 p-4 text-sm" role="alert">
      <p>Saved request is unreadable. Check the Book history before clearing it.</p>
      <Button variant="outline" onClick={clearPending}>I checked the history</Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="surface-soft space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">StoryBible</h3>
          {bible && <StatusBadge status={bible.run.status} />}
        </div>
        {bible?.artifact ? <div className="space-y-3 text-sm">
          <p className="text-xs text-muted-foreground">Version {bible.request.version} · artifact <span className="break-all">{bible.artifact.artifact_id}</span></p>
          <p className="break-words">{textValue(bible.artifact.content.premise)}</p>
          <p className="text-muted-foreground">Protagonist: {textValue(bible.artifact.content.protagonist)}</p>
          <details className="border-t pt-3"><summary className="min-h-11 cursor-pointer font-medium">Review full StoryBible</summary>
            <dl className="mt-3 space-y-2">{Object.entries(bible.artifact.content).map(([name, value]) =>
              <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")}</dt>
                <dd className="mt-1 break-words text-muted-foreground">{textValue(value)}</dd></div>)}</dl>
          </details>
        </div> : <p className="text-sm text-muted-foreground">{bible ? "Generation is running or needs attention." : "No approved StoryBible yet."}</p>}
        {gate && bible?.current && bible.artifact && <div className="space-y-3 border-t pt-4" aria-label="StoryBible approval">
          <p className="text-sm font-medium">Approve this exact Bible version before canonical state changes.</p>
          <label className="block text-sm">Editor name
            <input className="mt-1.5 block w-full px-3 py-2" value={operator} onChange={event => setOperator(event.target.value)} maxLength={100} required />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={working || !!pendingRaw || !operator.trim()} onClick={() => void decide("approve")}>Approve StoryBible</Button>
            <Button variant="outline" disabled={working || !!pendingRaw || !operator.trim()} onClick={() => void decide("revise")}>Request revision</Button>
            <Button variant="destructive" disabled={working || !!pendingRaw || !operator.trim()} onClick={() => void decide("reject")}>Reject</Button>
          </div>
          <p className="text-xs text-muted-foreground">Decision target: {bible.artifact.artifact_id} · output version {gate.output_version}.</p>
        </div>}
        <label className="block text-sm">Feedback for next generation or revision
          <textarea className="mt-1.5 block w-full px-3 py-2" rows={2} value={feedback} onChange={event => setFeedback(event.target.value)} maxLength={4000} />
        </label>
        <Button variant="outline" disabled={working || !!pendingRaw || bibleBusy} onClick={() => void startBible()}>
          {approvedBible ? "Propose major StoryBible change" : "Generate StoryBible"}
        </Button>
      </div>
      <div className="surface-soft space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Chapter brief</h3>
          {brief && <StatusBadge status={brief.run.status} />}
        </div>
        <label className="block text-sm">Chapter number
          <input className="mt-1.5 block w-full px-3 py-2" type="number" min={1} max={10000}
            value={chapter} onChange={event => setChapter(event.target.value)} />
        </label>
        {brief?.artifact ? <div className="space-y-3 text-sm">
          <p className="text-xs text-muted-foreground">Version {brief.request.version} · {brief.eligible ? "Policy eligible" : "Source version changed or run incomplete"}</p>
          <dl className="space-y-2">{["opening_hook", "scene_goal", "conflict", "payoff", "ending_hook"].map(name =>
            <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")}</dt>
              <dd className="mt-1 break-words text-muted-foreground">{textValue(brief.artifact?.content[name])}</dd></div>)}</dl>
          <details className="break-all text-xs text-muted-foreground"><summary className="cursor-pointer">Source versions</summary>
            <p className="mt-2">State {String(brief.artifact.content.state_artifact_id)} · v{String(brief.artifact.content.state_version)}</p>
            <p>Snapshot {brief.snapshot_artifact_id}</p>
          </details>
        </div> : <p className="text-sm text-muted-foreground">{brief ? "Generation is running or needs attention." : "No brief for this chapter yet."}</p>}
        {briefs.error != null && <p role="alert" className="text-sm text-destructive">{visibleError(briefs.error)}</p>}
        <Button disabled={working || !!pendingRaw || !validChapter || !approvedBible || briefBusy} onClick={() => void startBrief()}>
          {brief ? "Regenerate chapter brief" : "Generate chapter brief"}
        </Button>
        <p className="text-xs text-muted-foreground">Routine briefs proceed automatically after an approved StoryBible. A changed StoryState requires a new brief.</p>
      </div>
    </div>
  </section>;
}
