"use client";

import { useState } from "react";
import { api } from "@/api/client";
import type { CreativeRun } from "@/api/types";
import { Button } from "@/components/ui/button";
import { errorMessage, useResource } from "./use-resource";
import type { Pending, SubmitResult } from "./state";
import { useEditorIdentity } from "./editor-identity";

export function CreativeResults({ kind, sourceRunId, revision, submit, disabled }: {
  kind: "titles" | "covers";
  sourceRunId: string;
  revision: number;
  submit: (command: Pending) => Promise<SubmitResult>;
  disabled: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const { operator, update: setOperator } = useEditorIdentity();
  const result = useResource<CreativeRun[]>(`/api/creative/${kind}/${encodeURIComponent(sourceRunId)}/runs`, revision, 5000);
  const latest = result.data?.[0];
  async function generate() {
    setError(null);
    if (!result.data) { setError("Candidate history is still loading. Wait for it before generating a new version."); return; }
    try {
      const context = await api.get<{ source_artifact_id: string; next_version: number }>(`/api/creative/${kind}/${encodeURIComponent(sourceRunId)}/context`);
      const revision = latest?.decision?.action === "revise" && latest.current ? latest : null;
      const outcome = await submit({ path: `/api/creative/${kind}`, body: { request_key: crypto.randomUUID(), source_run_id: sourceRunId,
        source_artifact_id: context.source_artifact_id, version: context.next_version,
        ...(revision ? { revision_of: revision.run.pipeline_run_id, feedback: reason.trim() || revision.decision?.reason || "" } : {}) } });
      if (!outcome.ok) setError(outcome.error);
    } catch (cause) { setError(errorMessage(cause)); }
  }
  async function decide(state: CreativeRun, action: "approve" | "reject" | "revise", artifactId = "") {
    const step = state.run.steps?.find(s => s.step_key === "select");
    if (!step || !operator.trim()) return;
    if (action === "revise" && !reason.trim()) { setError("Add revision feedback before requesting changes."); return; }
    setError(null);
    const outcome = await submit({ path: `/api/creative/runs/${encodeURIComponent(state.run.pipeline_run_id)}/decision`,
      body: { request_key: crypto.randomUUID(), step_id: step.step_run_id, artifact_id: artifactId,
        action, expected_version: step.output_version, operator: operator.trim(), reason: reason.trim() } });
    if (!outcome.ok) setError(outcome.error);
  }
  return <section className="space-y-3 border-t pt-4" aria-label={kind === "titles" ? "Title candidates" : "Cover directions"}>
    <h4 className="font-semibold">{kind === "titles" ? "Title candidates" : "Cover directions"}</h4>
    <Button variant="outline" disabled={disabled || result.loading || !!result.error || !result.data} onClick={() => void generate()}>
      {latest?.decision?.action === "revise" ? `Regenerate ${kind} from feedback` : latest ? `Generate next ${kind === "titles" ? "title" : "cover"} version` : `Generate ${kind === "titles" ? "titles" : "cover directions"}`}
    </Button>
    {error && <p role="alert">{error}</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.loading && <p role="status">Loading {kind}…</p>}
    {result.data?.map(state => <div key={state.run.pipeline_run_id} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">Version {state.request.version} · {state.run.status}</h5>
      {!state.current && <p className="text-amber-700">Historical version: selection is disabled.</p>}
      {state.decision?.action === "revise" && <p>Revision requested: {state.decision.reason}</p>}
      {state.decision?.action === "reject" && <p>Rejected{state.decision.reason ? `: ${state.decision.reason}` : "."}</p>}
      {state.current && state.run.status === "awaiting_approval" && <div className="space-y-2">
        <label className="block text-sm">Editor name
          <input className="mt-1 block w-full rounded border p-2" value={operator} onChange={event => setOperator(event.target.value)} maxLength={100} required />
        </label>
        <label className="block text-sm">Decision note or revision request
          <textarea className="mt-1 block w-full rounded border p-2" value={reason} onChange={event => setReason(event.target.value)} maxLength={4000} rows={2} />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={disabled || !operator.trim()} onClick={() => void decide(state, "revise")}>Request revision</Button>
          <Button variant="destructive" disabled={disabled || !operator.trim()} onClick={() => void decide(state, "reject")}>Reject {kind === "titles" ? "titles" : "cover directions"}</Button>
        </div>
      </div>}
      <ol className="space-y-3">
        {state.candidates.map((item, index) => <li key={item.artifact_id} className="space-y-1 border-t pt-2">
          <p className="font-medium">{index + 1}. {item.content.title ?? item.content.visual_direction}</p>
          {kind === "titles" ? <>
            <p>{item.content.hook} · {item.content.selling_point}</p>
            <p>Click {item.content.click_score} · Genre fit {item.content.genre_fit_score}</p>
            {item.content.risk_notes && <p>Risk note: {item.content.risk_notes}</p>}
          </> : <>
            <p>Style: {item.content.style}</p><p>Elements: {item.content.main_elements?.join(", ")}</p>
            <details><summary>Cover prompt</summary><p>{item.content.cover_prompt}</p><p>Avoid: {item.content.negative_prompt}</p></details>
          </>}
          <p className="break-all text-xs text-muted-foreground">Artifact v{item.version}: {item.artifact_id} · Route {item.route} · Model {item.model} · Prompt {item.prompt_version}</p>
          {state.decision?.choice_id === item.artifact_id ? <p>Selected</p> :
            state.current && state.run.status === "awaiting_approval" &&
            <Button variant="outline" disabled={disabled || !operator.trim()} onClick={() => void decide(state, "approve", item.artifact_id)}>
              Select {kind === "titles" ? "title" : "cover"} {index + 1}
            </Button>}
        </li>)}
      </ol>
      {kind === "titles" && state.run.status === "completed" && state.decision?.choice_id && state.current &&
        <CreativeResults kind="covers" sourceRunId={state.run.pipeline_run_id} revision={revision} submit={submit} disabled={disabled} />}
    </div>)}
  </section>;
}
