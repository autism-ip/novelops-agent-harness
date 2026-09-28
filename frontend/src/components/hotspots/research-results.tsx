"use client";

import { useState } from "react";
import { api } from "@/api/client";
import type { OpportunityAnalysis } from "@/api/types";
import { Button } from "@/components/ui/button";
import { errorMessage, useResource } from "./use-resource";
import { CreativeResults } from "./creative-results";
import { useEditorIdentity } from "./editor-identity";
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
      {analysis.risk.content.requires_review && <p>{analysis.decisions.some(decision => decision.action === "approve" &&
        analysis.run.steps?.some(step => step.step_key === "risk_gate" && step.step_run_id === decision.target_id)) ?
        "Human risk review approved." : "Human risk review is required before this opportunity can continue."}</p>}
      {analysis.risk.content.rule_flags.length > 0 && <p>Rule flags: {analysis.risk.content.rule_flags.join(", ")}</p>}
      {analysis.risk.content.assessments.map((assessment, index) =>
        <div key={index} className="space-y-1">
          <p>{index === 0 ? "Research risk assessment" : "Additional risk review"} · Confidence {Math.round(assessment.confidence * 100)}%</p>
          {assessment.flags.length > 0 && <p>Semantic flags: {assessment.flags.join(", ")}</p>}
          <ul className="list-inside list-disc">{[...assessment.reasons, ...assessment.uncertainties].map((v, i) => <li key={i}>{v}</li>)}</ul>
        </div>)}
    </div>}
    {analysis.opportunity && <details><summary className="cursor-pointer">Analysis provenance</summary>
      <p className="break-all">Artifact: {analysis.opportunity.artifact_id}</p>
      <p>Route: {analysis.opportunity.route} · Model: {analysis.opportunity.model} · Prompt: {analysis.opportunity.prompt_version}</p>
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

function AnalysisActions({ analysis, submit, disabled }: { analysis: OpportunityAnalysis;
  submit: (command: Pending) => Promise<boolean>; disabled: boolean }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { operator, update: setOperator } = useEditorIdentity();
  const gate = analysis.run.steps?.find(step => step.status === "awaiting_approval" &&
    ["risk_gate", "selection"].includes(step.step_key));
  const revision = analysis.decisions.find(decision => decision.action === "revise");
  async function decide(action: "approve" | "reject" | "revise") {
    if (!gate || !analysis.opportunity || !operator.trim()) return;
    if (action === "revise" && !reason.trim()) { setError("Add revision feedback before requesting changes."); return; }
    setError(null);
    await submit({ path: `/api/analyses/${encodeURIComponent(analysis.run.pipeline_run_id)}/decision`,
      body: { request_key: crypto.randomUUID(), step_id: gate.step_run_id,
        artifact_id: analysis.opportunity.artifact_id, expected_version: gate.output_version,
        action, operator: operator.trim(), reason: reason.trim() } });
  }
  async function regenerate() {
    setError(null);
    try {
      const context = await api.get<{ next_version: number; source_hash: string; can_analyze: boolean }>(
        `/api/hotspots/${encodeURIComponent(analysis.request.hotspot_id)}/research-context`);
      if (!context.can_analyze) throw new Error("This source is no longer available for analysis.");
      await submit({ path: "/api/analyses", body: { request_key: crypto.randomUUID(), items: [{
        hotspot_id: analysis.request.hotspot_id, source_hash: context.source_hash,
        version: context.next_version, revision_of: analysis.run.pipeline_run_id,
        feedback: reason.trim() || revision?.reason || "" }] } });
    } catch (cause) { setError(errorMessage(cause)); }
  }
  if (!analysis.current) return null;
  if (!gate && !revision) return null;
  return <section aria-label="Opportunity decision" className="space-y-3 rounded border p-3 text-sm">
    {gate && <>
      <p className="font-medium">{gate.step_key === "risk_gate" ? "Review risk before selecting this opportunity" : "Choose this opportunity for title planning"}</p>
      <label className="block">Editor name
        <input className="mt-1 block w-full rounded border p-2" value={operator} onChange={event => setOperator(event.target.value)} maxLength={100} required />
      </label>
      <label className="block">Decision note or revision request
        <textarea className="mt-1 block w-full rounded border p-2" value={reason} onChange={event => setReason(event.target.value)} maxLength={4000} rows={2} />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button disabled={disabled || !operator.trim()} onClick={() => void decide("approve")}>Approve {gate.step_key === "risk_gate" ? "risk" : "opportunity"}</Button>
        <Button variant="outline" disabled={disabled || !operator.trim()} onClick={() => void decide("revise")}>Request revision</Button>
        <Button variant="destructive" disabled={disabled || !operator.trim()} onClick={() => void decide("reject")}>Reject</Button>
      </div>
      <p className="text-muted-foreground">Decision applies to artifact {analysis.opportunity?.artifact_id} · output version {gate.output_version}.</p>
    </>}
    {!gate && revision && <>
      <p>Revision requested: {revision.reason}</p>
      <Button variant="outline" disabled={disabled} onClick={() => void regenerate()}>Regenerate analysis from feedback</Button>
    </>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

export function ResearchHistory({ hotspotId, revision, submit, disabled, creative }: { hotspotId: string; revision: number;
  creative: boolean;
  submit: (command: Pending) => Promise<boolean>; disabled: boolean }) {
  const result = useResource<OpportunityAnalysis[]>(`/api/hotspots/${encodeURIComponent(hotspotId)}/analyses`, revision, 5000);
  return <section aria-label="Analysis history" className="space-y-3">
    <h3 className="font-semibold">Analysis history</h3>
    {result.loading && <p role="status">Loading analyses…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.data?.length === 0 && <p>No analysis yet. Select this hotspot and choose Analyze selected.</p>}
    {result.data?.map(analysis => <div key={analysis.run.pipeline_run_id} className="space-y-3">
      <AnalysisCard analysis={analysis} />
      <AnalysisActions analysis={analysis} submit={submit} disabled={disabled} />
      {creative && analysis.current && analysis.approval_status === "approved" &&
        <CreativeResults kind="titles" sourceRunId={analysis.run.pipeline_run_id} revision={revision} submit={submit} disabled={disabled} />}
    </div>)}
  </section>;
}
