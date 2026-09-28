"use client";

import type { OpportunityAnalysis } from "@/api/types";
import { errorMessage, useResource } from "./use-resource";
import { CreativeResults } from "./creative-results";
import type { Pending } from "./state";

const labels: Record<string, string> = {
  awaiting_risk_review: "Needs human risk review",
  awaiting_selection: "Ready for opportunity selection",
  approved: "Approved opportunity",
  revision_requested: "Revision requested",
  rejected: "Rejected",
};

export function AnalysisCard({ analysis }: { analysis: OpportunityAnalysis }) {
  const content = analysis.opportunity?.content;
  return <article className="space-y-3 rounded-lg border p-4 text-sm break-words">
    <h3 className="font-semibold">{analysis.source.title} · Version {analysis.request.version}</h3>
    <p>{labels[analysis.approval_status] ?? analysis.approval_status}</p>
    {!analysis.current && <p className="text-amber-700">Historical analysis: the source changed, was discarded, or has a newer version. It cannot be approved for use.</p>}
    {content && <>
      <p>{content.summary}</p>
      <dl className="space-y-3">
        {Object.entries({ "Core emotions": content.core_emotions, "Hit patterns": content.hit_patterns,
          "Genre fit": content.genre_fit, "Reader promise": [content.reader_promise],
          "Story directions": content.novelization_directions }).map(([label, values]) =>
          <div key={label}><dt className="font-medium">{label}</dt><dd><ul className="list-inside list-disc">{values.map((v, i) => <li key={i}>{v}</li>)}</ul></dd></div>)}
      </dl>
    </>}
    {analysis.risk && <div className="space-y-2 border-t pt-3">
      <p className="font-medium">Risk: {analysis.risk.content.level}</p>
      {analysis.risk.content.requires_review && <p>Human review is required before this opportunity can continue.</p>}
      <ul className="list-inside list-disc">{[...analysis.risk.content.rule_flags,
        ...analysis.risk.content.assessments.flatMap(a => [...a.reasons, ...a.uncertainties])].map((v, i) => <li key={i}>{v}</li>)}</ul>
    </div>}
    {analysis.opportunity && <details><summary className="cursor-pointer">Analysis provenance</summary>
      <p className="break-all">Artifact: {analysis.opportunity.artifact_id}</p>
      <p>Model: {analysis.opportunity.model} · Prompt: {analysis.opportunity.prompt_version}</p>
    </details>}
  </article>;
}

export function ResearchResult({ runId, revision }: { runId: string; revision: number }) {
  const result = useResource<OpportunityAnalysis>(`/api/analyses/${encodeURIComponent(runId)}`, revision, 5000);
  return <div aria-label="Opportunity analysis" className="space-y-3">
    {result.loading && <p role="status">Loading analysis…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.data && <AnalysisCard analysis={result.data} />}
  </div>;
}

export function ResearchHistory({ hotspotId, revision, submit, disabled }: { hotspotId: string; revision: number;
  submit: (command: Pending) => Promise<boolean>; disabled: boolean }) {
  const result = useResource<OpportunityAnalysis[]>(`/api/hotspots/${encodeURIComponent(hotspotId)}/analyses`, revision, 5000);
  return <section aria-label="Analysis history" className="space-y-3">
    <h3 className="font-semibold">Analysis history</h3>
    {result.loading && <p role="status">Loading analyses…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.data?.length === 0 && <p>No analysis yet. Select this hotspot and choose Analyze selected.</p>}
    {result.data?.map(analysis => <div key={analysis.run.pipeline_run_id} className="space-y-3">
      <AnalysisCard analysis={analysis} />
      {analysis.current && analysis.approval_status === "approved" &&
        <CreativeResults kind="titles" sourceRunId={analysis.run.pipeline_run_id} revision={revision} submit={submit} disabled={disabled} />}
    </div>)}
  </section>;
}
