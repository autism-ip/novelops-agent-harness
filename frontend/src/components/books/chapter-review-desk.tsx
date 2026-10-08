"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/api/client";
import { useEditorIdentity } from "@/components/hotspots/editor-identity";
import { errorMessage, useResource } from "@/components/hotspots/use-resource";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { parsePendingReview, type PendingReview } from "./review-state";

type Artifact = { artifact_id: string; version: number; content: Record<string, unknown>; source_refs: string[] };
type Version = { record: { version_id: string; version_no: number; status: string; chapter_title: string;
  content: string; artifact_id?: string }; artifact: Artifact | null; legacy: boolean;
  report: Artifact | null; verification: Artifact | null };
type ChapterRun = { run: { pipeline_run_id: string; status: string };
  selected: Artifact | null; critique: Artifact | null; current: boolean; snapshot_artifact_id: string;
  usage: { attempts: number; input_tokens: number | null; output_tokens: number | null;
    estimated_cost: number | null; latency_ms: number | null; retries: number } };
type ReviewState = { latest: ChapterRun | null; story_state?: Record<string, Record<string, unknown>>;
  story_bible?: Artifact; brief?: Artifact; snapshot?: Artifact; verification?: Artifact | null;
  versions: Version[]; revision_tasks: { revision_task_id: string; from_version_id: string;
    status: string; run_status: string | null }[];
  review_gate?: { step_id: string; status: string; output_version: number };
  traces?: { kind: string; route?: string; model?: string; prompt_version?: string;
    input_tokens?: number; output_tokens?: number; estimated_cost?: number; latency_ms?: number; retry_count?: number }[] };

// A live chapter desk read took 65.46 seconds; retain a bounded read deadline.
const REVIEW_READ_TIMEOUT_MS = 120_000;
const EVENT = "novelops-chapter-review-request";
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function saved(key: string) { try { return sessionStorage.getItem(key); } catch { return null; } }
function setSaved(key: string, value: string | null) {
  try { if (value === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, value); }
  finally { window.dispatchEvent(new Event(EVENT)); }
}
function text(value: unknown) { return typeof value === "string" ? value : ""; }
function lines(value: string) { return value.split("\n").map(item => item.trim()).filter(Boolean); }
function visibleError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) return "Sign in to review chapters.";
  return errorMessage(cause);
}
const dimensions = ["pacing", "style", "repetition", "dialogue", "reader_promise", "continuity", "ai_patterns"];
function pollWhileActive(review: ReviewState) {
  return !!review.latest && !["completed", "failed", "blocked", "cancelled", "awaiting_approval"].includes(review.latest.run.status);
}

export function ChapterReviewDesk({ bookId, chapterNo, refresh, onChanged }: {
  bookId: string; chapterNo: number; refresh: number; onChanged: () => void
}) {
  const root = `/api/books/${encodeURIComponent(bookId)}/chapters/${chapterNo}`;
  const key = `novelops.chapter-review.pending.${bookId}.${chapterNo}`;
  const pendingRaw = useSyncExternalStore(subscribe, () => saved(key), () => null);
  const pending = parsePendingReview(pendingRaw);
  const [revision, setRevision] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNo, setSelectedNo] = useState<number | null>(null);
  const [mustKeep, setMustKeep] = useState("");
  const [mustChange, setMustChange] = useState("");
  const [doNotChange, setDoNotChange] = useState("");
  const [reason, setReason] = useState("");
  const busy = useRef(false);
  const { operator, update: setOperator } = useEditorIdentity();
  const result = useResource<ReviewState>(root + "/review", refresh + revision, 5000, pollWhileActive, REVIEW_READ_TIMEOUT_MS);
  const data = result.data;
  const latest = data?.latest;
  const current = data?.versions.find(entry => entry.record.artifact_id === latest?.selected?.artifact_id);
  const displayed = data?.versions.find(entry => entry.record.version_no === selectedNo) ?? current;
  const shown = displayed?.artifact ?? (displayed === current ? latest?.selected : null);
  const critique = displayed?.report ?? null;
  const verification = displayed?.verification ?? null;
  const critiquedVersion = data?.versions.find(entry =>
    entry.artifact?.artifact_id === critique?.source_refs[2]);
  const reportIsForEarlierDraft = !!shown && !!critiquedVersion &&
    critiquedVersion.artifact?.artifact_id !== shown.artifact_id;
  const chosenIsCurrent = !!current && displayed?.record.version_id === current.record.version_id;
  const gate = data?.review_gate;
  const gatePending = gate?.status === "awaiting_approval";
  const ready = !!latest?.current && !!current && !!latest.selected && chosenIsCurrent &&
    ["completed", "awaiting_approval"].includes(latest.run.status) &&
    ["review", "approved"].includes(current.record.status);
  const locked = data?.versions.some(entry => entry.record.status === "final");
  const blocked = working || !!pendingRaw || !operator.trim() || !ready || !!locked;

  async function submit(command: PendingReview) {
    if (busy.current) return;
    busy.current = true; setWorking(true); setError(null);
    try {
      setSaved(key, JSON.stringify(command));
      await api.post(command.path, command.body);
      setSaved(key, null);
      setRevision(value => value + 1);
      onChanged();
    } catch (cause) { setError(visibleError(cause)); }
    finally { busy.current = false; setWorking(false); }
  }
  function target() {
    if (!latest?.selected || !current || !gate) return null;
    return { run_id: latest.run.pipeline_run_id, version_id: current.record.version_id,
      artifact_id: latest.selected.artifact_id, version_no: current.record.version_no,
      operator: operator.trim(), expected_gate_version: gatePending ? gate.output_version : 0 };
  }
  function decide(action: "approve" | "reject") {
    const body = target();
    if (!body || blocked) return;
    void submit({ path: root + "/review/decision", body: { ...body, action, reason: reason.trim() } });
  }
  function revise() {
    const body = target();
    if (!body || blocked) return;
    const constraints = { must_keep: lines(mustKeep), must_change: lines(mustChange),
      do_not_change: lines(doNotChange) };
    if (!constraints.must_change.length) { setError("Add at least one required change."); return; }
    void submit({ path: root + "/review/revision", body: { ...body, constraints } });
  }
  function lockFinal() {
    const body = target();
    if (!body || blocked || gatePending || latest?.run.status !== "completed") return;
    void submit({ path: root + "/final-lock", body: {
      version_id: body.version_id, artifact_id: body.artifact_id,
      version_no: body.version_no, operator: body.operator } });
  }

  return <div className="space-y-5 border-t pt-5" aria-label="Chapter review desk">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="text-lg font-semibold">Chapter review desk</h3>
        <p className="text-sm text-muted-foreground">Read the draft, inspect the checks, then make the next editorial decision.</p></div>
      {latest && <StatusBadge status={gatePending ? "awaiting_approval" : latest.run.status} />}
    </div>
    {result.loading && !data && <p role="status" className="text-sm">Loading chapter review… Chapter history may take a minute to load.</p>}
    {result.error != null && <p role="alert" className="text-sm text-destructive">{visibleError(result.error)}</p>}
    {!latest && data && (data.versions.length ? <div className="surface-soft space-y-4 p-4 sm:p-5">
      <p className="text-sm text-muted-foreground">Earlier chapter versions are available for reading. Generate a chapter to enable current run review.</p>
      <div className="flex flex-wrap gap-2">{data.versions.map(entry =>
        <button key={entry.record.version_id} type="button" onClick={() => setSelectedNo(entry.record.version_no)}
          aria-pressed={displayed?.record.version_id === entry.record.version_id}
          className="min-h-11 rounded-xl border border-input bg-white px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring">
          v{entry.record.version_no} · {entry.record.status}</button>)}</div>
      {displayed && <><h4 className="font-semibold">{displayed.record.chapter_title}</h4>
        <div className="max-h-[36rem] overflow-auto whitespace-pre-wrap break-words text-sm leading-7">{displayed.record.content}</div>
        {displayed.legacy && <p className="text-xs text-muted-foreground">Legacy version: exact Artifact provenance is unavailable.</p>}</>}
    </div> : <p className="surface-soft p-4 text-sm text-muted-foreground">Generate a chapter to open its review desk.</p>)}
    {latest && !latest.current && !locked && <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
      This draft is not current for final lock. Check the latest StoryState and chapter brief before regenerating.
    </p>}
    {gatePending && <p className="rounded-2xl border border-primary/20 bg-primary/5 p-4 text-sm" role="status">
      This chapter needs an editor decision before the run can complete.</p>}
    {latest && <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(19rem,1fr)]">
      <div className="surface-soft min-w-0 space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold">{displayed ? `Chapter version ${displayed.record.version_no}` : "Chapter draft"}</h4>
          {displayed && <StatusBadge status={displayed.record.status} />}
        </div>
        {displayed ? <>
          <h5 className="text-xl font-semibold">{text(shown?.content.title) || displayed.record.chapter_title}</h5>
          <div className="max-h-[36rem] overflow-auto whitespace-pre-wrap break-words text-sm leading-7">
            {text(shown?.content.prose) || displayed.record.content}
          </div>
          {displayed.legacy && <p className="text-xs text-muted-foreground">Legacy version: exact Artifact provenance is unavailable.</p>}
        </> : <p className="text-sm text-muted-foreground">
          {latest.run.status === "running" ? "The writing loop is running." : "No verified chapter version is ready."}</p>}
        <div className="border-t pt-4"><p className="mb-2 text-sm font-semibold">Version history</p>
          <div className="flex flex-wrap gap-2">{data.versions.map(entry =>
            <button key={entry.record.version_id} type="button" onClick={() => setSelectedNo(entry.record.version_no)}
              aria-pressed={displayed?.record.version_id === entry.record.version_id}
              className={`min-h-11 rounded-xl border px-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring ${displayed?.record.version_id === entry.record.version_id ? "border-primary bg-primary/10 text-primary" : "border-input bg-white hover:bg-accent"}`}>
              v{entry.record.version_no} · {entry.record.status}</button>)}</div>
          {!chosenIsCurrent && displayed && <p className="mt-2 text-xs text-muted-foreground">Select the current version to take an action.</p>}
        </div>
      </div>
      <div className="surface-soft min-w-0 space-y-4 p-4 sm:p-5">
        <h4 className="font-semibold">Critique and decision</h4>
        {critique ? <>
          {reportIsForEarlierDraft && <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            This Critic report scored v{critiquedVersion.record.version_no} before the rewrite. The selected version passed deterministic checks but has not been scored again; read its prose before deciding.
          </p>}
          <p className="text-sm leading-6">{text(critique.content.summary)}</p>
          <p className="text-xs font-medium capitalize text-muted-foreground">Model decision: {text(critique.content.decision)}</p>
          <details className="border-t pt-3 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Quality dimensions</summary>
            <dl className="mt-2 space-y-2">{dimensions.map(name => {
              const score = critique.content[name] as { score?: number; evidence?: string } | undefined;
              return <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")} · {score?.score ?? "?"}/5</dt>
                <dd className="text-muted-foreground">{score?.evidence ?? "No evidence"}</dd></div>;
            })}</dl></details>
        </> : <p className="text-sm text-muted-foreground">The structured critique appears after a verified draft.</p>}
        {verification && <details className="border-t pt-3 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Deterministic checks</summary>
          <ul className="mt-2 space-y-1">{Object.entries(verification.content.checks as Record<string, boolean>).map(([name, passed]) =>
            <li key={name}>{passed ? "✓" : "!"} {name.replaceAll("_", " ")}</li>)}</ul></details>}
        <label className="block text-sm">Editor identity
          <input className="mt-1.5 block w-full px-3 py-2" value={operator}
            onChange={event => setOperator(event.target.value)} maxLength={100} /></label>
        <label className="block text-sm">Decision note
          <textarea className="mt-1.5 block w-full px-3 py-2" rows={2} value={reason}
            onChange={event => setReason(event.target.value)} maxLength={2000} /></label>
        <div className="flex flex-wrap gap-2"><Button disabled={blocked || current?.record.status === "approved"}
          onClick={() => decide("approve")}>Approve</Button>
          <Button variant="outline" disabled={blocked || current?.record.status === "approved"}
            onClick={() => decide("reject")}>Reject</Button>
          <Button variant="secondary" disabled={blocked || gatePending || latest.run.status !== "completed"}
            onClick={lockFinal}>Lock final</Button></div>
        {locked && <p className="text-xs text-muted-foreground">This chapter is final-locked. Earlier versions remain readable.</p>}
        <details className="border-t pt-3 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Request a constrained revision</summary>
          <p className="mt-2 text-xs text-muted-foreground">One item per line. Required changes create a RevisionTask bound to the current version.</p>
          {([["Must keep", mustKeep, setMustKeep], ["Must change", mustChange, setMustChange],
            ["Do not change", doNotChange, setDoNotChange]] as const).map(([label, value, setter]) =>
            <label key={label} className="mt-3 block text-sm">{label}
              <textarea className="mt-1.5 block w-full px-3 py-2" rows={2} value={value}
                onChange={event => setter(event.target.value)} maxLength={2000} /></label>)}
          <Button className="mt-3" variant="outline" disabled={blocked || !lines(mustChange).length}
            onClick={revise}>Create revision and rewrite</Button>
        </details>
      </div>
    </div>}
    {data?.latest && <div className="grid gap-4 md:grid-cols-2">
      <div className="surface-soft min-w-0 space-y-3 p-4 sm:p-5">
        <h4 className="font-semibold">Current run story and chapter brief</h4>
        <dl className="space-y-2 text-sm">
          <div><dt className="font-medium">Premise</dt><dd className="text-muted-foreground">{text(data.story_bible?.content.premise) || "Unavailable"}</dd></div>
          <div><dt className="font-medium">Protagonist</dt><dd className="text-muted-foreground">{text(data.story_bible?.content.protagonist) || "Unavailable"}</dd></div>
          {["opening_hook", "scene_goal", "conflict", "payoff", "ending_hook"].map(name =>
            <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")}</dt>
              <dd className="text-muted-foreground">{text(data.brief?.content[name]) || "Unavailable"}</dd></div>)}
        </dl>
        <details className="border-t pt-3 text-xs text-muted-foreground"><summary className="min-h-11 cursor-pointer font-medium">StoryState summary</summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(data.story_state, null, 2)}</pre></details>
      </div>
      <div className="surface-soft min-w-0 space-y-3 p-4 sm:p-5">
        <h4 className="font-semibold">Source and run details</h4>
        <p className="text-sm text-muted-foreground">Selected version sources and current run usage remain available here.</p>
        <details className="border-t pt-3 text-xs text-muted-foreground"><summary className="min-h-11 cursor-pointer font-medium">Sources, usage and trace</summary>
          <dl className="mt-2 space-y-1 break-all">
            <div><dt>Version snapshot</dt><dd>{shown?.source_refs[0] ?? "Unavailable"}</dd></div>
            <div><dt>Version brief</dt><dd>{shown?.source_refs[1] ?? "Unavailable"}</dd></div>
            <div><dt>Version source artifacts</dt><dd>{shown?.source_refs.join(" · ") ?? "Unavailable"}</dd></div>
            <div><dt>Current run StoryState</dt><dd>{text(data.snapshot?.content.state_artifact_id)}</dd></div>
            <div><dt>Current run StoryBible</dt><dd>{data.story_bible?.artifact_id}</dd></div>
            <div><dt>Model attempts</dt><dd>{latest?.usage.attempts} · {latest?.usage.retries} retries</dd></div>
            <div><dt>Tokens</dt><dd>{latest?.usage.input_tokens ?? "unknown"} input · {latest?.usage.output_tokens ?? "unknown"} output</dd></div>
            <div><dt>Estimated cost</dt><dd>{latest?.usage.estimated_cost ?? "unavailable"}</dd></div>
          </dl>
          <ul className="mt-3 space-y-1">{data.traces?.filter(item => item.kind === "model").map((item, index) =>
            <li key={index}>{item.route} · {item.model} · {item.prompt_version} · {item.latency_ms ?? "?"} ms</li>)}</ul>
        </details>
        {!!data.revision_tasks.length && <p className="text-xs text-muted-foreground">
          Revision tasks: {data.revision_tasks.map(task => {
            const source = data.versions.find(entry => entry.record.version_id === task.from_version_id);
            return `v${source?.record.version_no ?? "?"} → ${task.run_status ? `run ${task.run_status}` : task.status}`;
          }).join(" · ")}</p>}
      </div>
    </div>}
    {pending && <div className="surface-soft space-y-2 p-4 text-sm" role="status">
      <p>The last review command has an unknown outcome. Retry uses the same exact version and editor identity.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={working}
        onClick={() => void submit(pending)}>Retry the same command</Button>
        <Button variant="ghost" disabled={working} onClick={() => setSaved(key, null)}>I checked the version history</Button></div>
    </div>}
    {pendingRaw && !pending && <div className="surface-soft space-y-2 p-4 text-sm" role="alert">
      <p>The saved review command is unreadable. Check the version history before clearing it.</p>
      <Button variant="outline" onClick={() => setSaved(key, null)}>I checked the version history</Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
  </div>;
}
