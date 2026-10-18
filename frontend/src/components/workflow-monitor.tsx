/**
 * [INPUT]: Authenticated workflow observations and the shared bounded read hook
 * [OUTPUT]: Responsive persisted workflow/agent-step inspection; read-only recovery
 * [POS]: Shared Pipelines and Agents workspace surface
 */
"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { WorkflowRun } from "@/api/types";
import { ApiError } from "@/api/client";
import { useResource, errorMessage } from "@/components/hotspots/use-resource";
import { WORKFLOW_LABELS } from "@/components/hotspots/state";
import { HealthIndicator } from "@/components/health-indicator";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

export function WorkflowMonitor({ mode }: { mode: "workflows" | "agents" }) {
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const detailRegion = useRef<HTMLElement>(null);
  const revealedRun = useRef<string | null>(null);
  const runs = useResource<WorkflowRun[]>("/api/workflows", revision, 10_000);
  const detail = useResource<WorkflowRun>(selected ? `/api/workflows/${encodeURIComponent(selected)}` : null, revision, 5_000);
  const detailRunId = detail.data?.pipeline_run_id;
  useEffect(() => {
    if (!selected || detailRunId !== selected || revealedRun.current === selected) return;
    revealedRun.current = selected;
    const region = detailRegion.current!;
    const bounds = region.getBoundingClientRect();
    if (bounds.top < 96 || bounds.bottom > window.innerHeight - 96)
      region.scrollIntoView({ block: "start" });
  }, [selected, detailRunId]);
  const agentView = mode === "agents";
  const path = agentView ? "/agents" : "/pipelines";
  const steps = detail.data?.steps;
  const classified = Array.isArray(steps) && steps.every(s => ["agent", "tool", "service"].includes(s.kind ?? ""));
  const visibleSteps = Array.isArray(steps) ? steps.filter(s => !agentView || s.kind === "agent") : [];
  const authNeeded = [runs.error, detail.error].some(e => e instanceof ApiError && e.status === 401);
  const total = runs.data?.length ?? 0;
  const page = Math.min(offset, Math.floor(Math.max(0, total - 1) / 20) * 20);
  const ordered = [...(runs.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return <div className="page-shell app-reveal space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2"><h1 className="page-title">{agentView ? "Agents" : "Pipelines"}</h1>
        <p className="page-intro">{agentView ? "Inspect agent execution within its recorded workflow." : "Follow persisted workflow progress and inspect the steps that need attention."}</p></div>
      <Button variant="outline" onClick={() => setRevision(v => v + 1)}>Refresh activity</Button>
    </header>
    <div className="surface p-5 sm:p-6"><HealthIndicator /></div>
    {authNeeded && <Link href={`/sign-in?returnTo=${encodeURIComponent(path)}`} className="inline-flex min-h-11 items-center text-primary underline">Sign in to inspect activity</Link>}
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section id="recorded-workflows" tabIndex={-1} className="surface min-w-0 scroll-mt-24 p-5 sm:p-6" aria-label="Recorded workflows">
        <h2 className="text-xl font-semibold">Recorded workflows</h2>
        {runs.loading && <p role="status" className="mt-4">Loading workflows…</p>}
        {runs.error != null && <p role="alert" className="mt-4 text-destructive">{errorMessage(runs.error)}</p>}
        {runs.data && runs.data.length === 0 && <div className="mt-4 space-y-3"><p>No workflow runs have been recorded.</p><Link href="/hotspots" className="inline-flex min-h-11 items-center text-primary underline">Open hotspots</Link></div>}
        {runs.data && runs.data.length > 0 && <ul className="mt-4 divide-y divide-border">
          {ordered.slice(page, page + 20).map(run => <li key={run.pipeline_run_id}>
            <button aria-pressed={selected === run.pipeline_run_id} onClick={() => { setSelected(run.pipeline_run_id); detailRegion.current?.focus(); }} className="flex min-h-16 w-full flex-wrap items-center justify-between gap-3 rounded-xl px-3 py-4 text-left transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-pressed:bg-accent motion-reduce:transition-none">
              <span className="min-w-0 flex-1"><span className="block break-words font-semibold">{WORKFLOW_LABELS[run.pipeline_type] ?? run.pipeline_type}</span><span className="mt-1 block break-all text-sm text-muted-foreground">{run.created_at}</span></span><StatusBadge status={run.status} />
            </button>
          </li>)}
        </ul>}
        {total > 20 && <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          <span>{total} workflows · showing {page + 1}–{Math.min(page + 20, total)}</span>
          <Button variant="outline" disabled={page === 0} onClick={() => setOffset(page - 20)}>Previous workflows</Button>
          <Button variant="outline" disabled={page + 20 >= total} onClick={() => setOffset(page + 20)}>Next workflows</Button>
        </div>}
      </section>
      <section ref={detailRegion} tabIndex={-1} className="surface min-w-0 scroll-mt-24 p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:p-6 lg:sticky lg:top-24" aria-label="Workflow details">
        <h2 className="text-xl font-semibold">{agentView ? "Agent steps" : "Workflow details"}</h2>
        {selected && <a href="#recorded-workflows" onClick={() => { revealedRun.current = selected; }} className="mt-2 inline-flex min-h-11 items-center text-primary underline">Back to workflows</a>}
        {!selected && <p className="mt-4 text-muted-foreground">{agentView ? "Choose a workflow to inspect its agent steps." : "Choose a workflow to inspect its persisted steps."}</p>}
        {detail.loading && <p role="status" className="mt-4">Loading workflow steps…</p>}
        {detail.error != null && <p role="alert" className="mt-4 text-destructive">{errorMessage(detail.error)}</p>}
        {detail.data && <div className="mt-4 space-y-4">
          <StatusBadge status={detail.data.status} />
          <p className="break-all text-sm text-muted-foreground">{detail.data.pipeline_run_id}</p>
          {(!Array.isArray(steps) || (agentView && !classified)) ? <p role="alert">{agentView ? "Agent step history is incomplete. Refresh activity to read it again." : "Step history is incomplete. Refresh activity to read it again."}</p> : <>
            {visibleSteps.length === 0 && <p>{agentView ? "This workflow has no agent steps." : "No steps have been recorded for this workflow."}</p>}
            <ol className="divide-y divide-border">{visibleSteps.map(step => <li key={step.step_run_id} className="space-y-2 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3"><span className="min-w-0 break-words font-semibold">{step.step_key}</span><StatusBadge status={step.status} /></div>
              {step.error_message && <p className="break-words text-sm text-destructive">{step.error_message}</p>}
            </li>)}</ol>
          </>}
        </div>}
      </section>
    </div>
  </div>;
}
