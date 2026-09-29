"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/api/client";
import { errorMessage, useResource } from "@/components/hotspots/use-resource";
import { Button } from "@/components/ui/button";
import { parsePendingChapter, type PendingChapter } from "./chapter-state";
import { ChapterReviewDesk } from "./chapter-review-desk";

type Artifact = { artifact_id: string; version: number; content: Record<string, unknown>; source_refs: string[] };
type ChapterRun = { run: { pipeline_run_id: string; status: string };
  selected: Artifact | null; critique: Artifact | null; snapshot_artifact_id: string;
  versions: { version_id: string; version_no: number; status: string }[];
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
  const runs = useResource<ChapterRun[]>(validChapter ? `${root}/generations` : null, revision, 5000);
  const brief = useResource<Artifact>(validChapter ? `${root}/brief/eligible` : null, revision, 5000);
  const latest = runs.data?.[0];
  const runBusy = !!latest && !["completed", "failed", "blocked", "cancelled"].includes(latest.run.status);
  const finalLocked = latest?.versions.some(row => row.status === "final") ?? false;
  const unavailable = runs.error instanceof ApiError && runs.error.status === 503;

  async function submit(command: PendingChapter) {
    if (busy.current) return;
    busy.current = true;
    setWorking(true);
    setError(null);
    try {
      setSaved(key, JSON.stringify(command));
      await api.post(command.path, command.body);
      setSaved(key, null);
      setRevision(value => value + 1);
    } catch (cause) { setError(visibleError(cause)); }
    finally { busy.current = false; setWorking(false); }
  }

  async function generate() {
    if (!validChapter || pendingRaw || working || !brief.data) return;
    try {
      const context = await api.get<ChapterContext>(`${root}/generation/context`);
      await submit({ path: `${root}/generations`, body: context });
    } catch (cause) { setError(visibleError(cause)); }
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
      <Button disabled={working || !!pendingRaw || runBusy || finalLocked || !validChapter || !brief.data}
        onClick={() => void generate()}>{finalLocked ? "Chapter final-locked" :
          latest ? "Regenerate chapter" : "Generate chapter"}</Button>
    </div>
    {validChapter && !brief.data && !(brief.loading) &&
      <p className="text-sm text-muted-foreground">Approve the StoryBible and generate a current chapter brief first.</p>}
    {runs.error != null && <p role="alert" className="text-sm text-destructive">{visibleError(runs.error)}</p>}
    {pending && <div className="surface-soft space-y-2 p-4 text-sm" role="status">
      <p>The last submission has an unknown outcome. Retry preserves the same Book, chapter, run version and source artifacts.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={working} onClick={() => void submit(pending)}>Retry the same request</Button>
        <Button variant="ghost" disabled={working} onClick={() => setSaved(key, null)}>I checked the history</Button></div>
    </div>}
    {pendingRaw && !pending && <div className="surface-soft space-y-2 p-4 text-sm" role="alert">
      <p>The saved request is unreadable. Check the chapter history before clearing it.</p>
      <Button variant="outline" onClick={() => setSaved(key, null)}>I checked the history</Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    {validChapter && <ChapterReviewDesk bookId={bookId} chapterNo={chapterNo} refresh={revision}
      onChanged={() => setRevision(value => value + 1)} />}
  </section>;
}
