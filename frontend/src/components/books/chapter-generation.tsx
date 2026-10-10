"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/api/client";
import { errorMessage, useResource } from "@/components/hotspots/use-resource";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { parsePendingChapter, type PendingChapter } from "./chapter-state";

type Artifact = { artifact_id: string; version: number; content: Record<string, unknown>; source_refs: string[] };
type ChapterRun = { run: { pipeline_run_id: string; status: string };
  selected: Artifact | null; critique: Artifact | null; snapshot_artifact_id: string;
  current: boolean;
  versions: { version_id: string; version_no: number; status: string }[];
  version_summaries: { version_id: string; version_no: number; status: string }[];
  usage: { attempts: number; input_tokens: number | null; output_tokens: number | null;
    estimated_cost: number | null; latency_ms: number | null; retries: number } };
type ChapterContext = { book_id: string; chapter_no: number; version: number; start_version_no: number;
  state_artifact_id: string; state_version: number;
  brief_artifact_id: string; brief_version: number;
  source_version_id: string;
  constraints: { must_keep: string[]; must_change: string[]; do_not_change: string[] } };

const EVENT = "novelops-chapter-generation-request";
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function saved(key: string) { try { return sessionStorage.getItem(key); } catch { return null; } }
function setSaved(key: string, value: string | null) {
  try { if (value === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, value); }
  finally { window.dispatchEvent(new Event(EVENT)); }
}
function visibleError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) return "Sign in to generate chapters.";
  return errorMessage(cause);
}
function stringValue(value: unknown) { return typeof value === "string" ? value : ""; }
function pollWhileActive(run: ChapterRun | null) {
  return !!run && !["completed", "failed", "blocked", "cancelled"].includes(run.run.status);
}

export function ChapterGeneration({ bookId }: { bookId: string }) {
  const [chapter, setChapter] = useState("1");
  const [revision, setRevision] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const chapterNo = Number(chapter);
  const validChapter = Number.isSafeInteger(chapterNo) && chapterNo >= 1 && chapterNo <= 10000;
  const root = `/api/books/${encodeURIComponent(bookId)}/chapters/${chapterNo}`;
  const key = `novelops.chapter-generation.pending.${bookId}`;
  const pendingRaw = useSyncExternalStore(subscribe, () => saved(key), () => null);
  const pending = parsePendingChapter(pendingRaw);
  const runs = useResource<ChapterRun | null>(validChapter ? `${root}/generation/latest` : null,
    revision, 5000, pollWhileActive);
  const brief = useResource<Artifact>(validChapter ? `${root}/brief/eligible` : null, revision, 5000);
  const latest = runs.data;
  const runBusy = !!latest && !["completed", "failed", "blocked", "cancelled"].includes(latest.run.status);
  const unavailable = runs.error instanceof ApiError && runs.error.status === 503;

  function clearPending() {
    setError(null);
    try { setSaved(key, null); }
    catch (cause) {
      setError(`Could not clear the saved chapter request. ${visibleError(cause)} Check browser storage access and try again.`);
    }
  }

  async function submit(request: PendingChapter | (() => Promise<PendingChapter>)) {
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
    } catch (cause) { setError(visibleError(cause)); }
    finally { busy.current = false; setWorking(false); }
  }

  async function generate() {
    if (!validChapter || pendingRaw || working || !brief.data) return;
    await submit(async () => {
      const context = await api.get<ChapterContext>(`${root}/generation/context`);
      return { path: `${root}/generations`, body: context };
    });
  }

  if (unavailable) return <section className="surface p-5 text-sm text-muted-foreground" aria-label="Chapter generation">
    Chapter generation is not configured for this workspace.
  </section>;

  return <section className="surface space-y-5 p-5 sm:p-6" aria-label="Chapter generation">
    <div className="space-y-2"><p className="text-xs font-semibold uppercase tracking-wide text-primary">From plan to draft</p>
      <h2 className="text-xl font-semibold">Chapter generation</h2>
      <p className="text-sm text-muted-foreground">Write from the current approved brief, check hard rules, then review a structured critique. Rewrites run only when needed.</p></div>
    <div className="flex flex-wrap items-end gap-3">
      <label className="block min-w-32 text-sm">Chapter number
        <input className="mt-1.5 block w-full px-3 py-2" type="number" min={1} max={10000}
          value={chapter} onChange={event => setChapter(event.target.value)} />
      </label>
      <Button disabled={working || !!pendingRaw || runBusy || !validChapter || !brief.data}
        onClick={() => void generate()}>{latest ? "Regenerate chapter" : "Generate chapter"}</Button>
      <Button variant="ghost" disabled={working || !validChapter}
        onClick={() => setRevision(value => value + 1)}>Refresh chapter</Button>
    </div>
    {validChapter && !brief.data && !(brief.loading) &&
      <p className="text-sm text-muted-foreground">Approve the StoryBible and generate a current chapter brief first.</p>}
    {runs.error != null && <p role="alert" className="text-sm text-destructive">{visibleError(runs.error)}</p>}
    {working && !pendingRaw && <p role="status" className="text-sm">Preparing chapter generation…</p>}
    {pending && <div className="surface-soft space-y-2 p-4 text-sm" role="status">
      <p>{working ? "Saving chapter generation… This may take a moment." : "The last submission has an unknown outcome. Retry preserves the same Book, chapter, run version and source artifacts."}</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={working} onClick={() => void submit(pending)}>Retry the same request</Button>
        <Button variant="ghost" disabled={working} onClick={clearPending}>I checked the history</Button></div>
    </div>}
    {pendingRaw && !pending && <div className="surface-soft space-y-2 p-4 text-sm" role="alert">
      <p>The saved request is unreadable. Check the chapter history before clearing it.</p>
      <Button variant="outline" onClick={clearPending}>I checked the history</Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    {latest && <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(17rem,1fr)]">
      <div className="surface-soft min-w-0 space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Latest chapter</h3>
          <StatusBadge status={latest.run.status} /></div>
        {!latest.current && !latest.versions.some(version => version.status === "final") &&
          <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
            This draft is not current for final lock. Check the latest StoryState and chapter brief before regenerating.
          </p>}
        {latest.selected ? <><p className="text-xs text-muted-foreground">Version {latest.selected.version} · {latest.versions.at(-1)?.status}</p>
          <h4 className="text-lg font-semibold">{stringValue(latest.selected.content.title)}</h4>
          <p className="line-clamp-5 whitespace-pre-wrap text-sm leading-7">{stringValue(latest.selected.content.prose)}</p>
          <details className="border-t pt-3 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Read full chapter</summary>
            <div className="mt-3 max-h-[36rem] overflow-auto whitespace-pre-wrap break-words leading-7">{stringValue(latest.selected.content.prose)}</div>
          </details></> : <p className="text-sm text-muted-foreground">{runBusy ? "The writing loop is running." : "No verified chapter version is ready for review."}</p>}
      </div>
      <div className="surface-soft min-w-0 space-y-4 p-4 sm:p-5">
        <h3 className="font-semibold">Critique and versions</h3>
        {latest.critique ? <><p className="text-sm">{stringValue(latest.critique.content.summary)}</p>
          <p className="text-xs font-medium capitalize text-muted-foreground">Decision: {stringValue(latest.critique.content.decision)}</p>
          <details className="border-t pt-3 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Review quality dimensions</summary>
            <dl className="mt-3 space-y-2">{["pacing", "style", "repetition", "dialogue", "reader_promise", "continuity", "ai_patterns"].map(name => {
              const dimension = latest.critique?.content[name] as { score?: number; evidence?: string } | undefined;
              return <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")} · {dimension?.score ?? "?"}/5</dt>
                <dd className="text-muted-foreground">{dimension?.evidence ?? "No evidence"}</dd></div>;
            })}</dl>
          </details></> : <p className="text-sm text-muted-foreground">Critique appears after the first verified draft.</p>}
        <div className="border-t pt-3"><p className="mb-2 text-sm font-medium">Version history</p>
          <ul className="space-y-1 text-sm">{latest.version_summaries.map(version =>
            <li key={version.version_id}>v{version.version_no} · {version.status}</li>)}</ul></div>
        <details className="border-t pt-3 text-xs text-muted-foreground"><summary className="min-h-11 cursor-pointer font-medium">Sources and model usage</summary>
          <dl className="mt-2 space-y-1 break-all"><div><dt>Context snapshot</dt><dd>{latest.snapshot_artifact_id}</dd></div>
            <div><dt>Chapter artifact</dt><dd>{latest.selected?.artifact_id ?? "Not selected"}</dd></div>
            <div><dt>Model attempts</dt><dd>{latest.usage.attempts} · {latest.usage.retries} retries</dd></div>
            <div><dt>Tokens</dt><dd>{latest.usage.input_tokens ?? "unknown"} input · {latest.usage.output_tokens ?? "unknown"} output</dd></div>
            <div><dt>Estimated cost</dt><dd>{latest.usage.estimated_cost ?? "unavailable"}</dd></div></dl>
        </details>
      </div>
    </div>}
  </section>;
}
