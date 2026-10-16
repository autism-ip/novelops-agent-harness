"use client";

import { useState } from "react";
import { api } from "@/api/client";
import type { CreativeRun } from "@/api/types";
import { Button } from "@/components/ui/button";
import { errorMessage, useResource } from "./use-resource";
import type { SubmitRequest } from "./state";

export function CreativeResults({ kind, sourceRunId, revision, submit, disabled }: {
  kind: "titles" | "covers";
  sourceRunId: string;
  revision: number;
  submit: (command: SubmitRequest) => Promise<boolean>;
  disabled: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const result = useResource<CreativeRun[]>(`/api/creative/${kind}/${encodeURIComponent(sourceRunId)}/runs`, revision, 5000);
  const latest = result.data?.[0];
  async function generate() {
    setError(null);
    if (!result.data) return;
    await submit(async () => {
      const context = await api.get<{ source_artifact_id: string; next_version: number }>(`/api/creative/${kind}/${encodeURIComponent(sourceRunId)}/context`);
      return { path: `/api/creative/${kind}`, body: { request_key: crypto.randomUUID(), source_run_id: sourceRunId,
        source_artifact_id: context.source_artifact_id, version: context.next_version } };
    });
  }
  async function choose(state: CreativeRun, artifactId: string) {
    const step = state.run.steps?.find(s => s.step_key === "select");
    if (!step) return;
    await submit({ path: `/api/creative/runs/${encodeURIComponent(state.run.pipeline_run_id)}/decision`,
      body: { request_key: crypto.randomUUID(), step_id: step.step_run_id, artifact_id: artifactId,
        action: "approve", expected_version: step.output_version, operator: "workspace-editor" } });
  }
  return <section className="space-y-3 border-t pt-4" aria-label={kind === "titles" ? "Title candidates" : "Cover directions"}>
    <h4 className="font-semibold">{kind === "titles" ? "Title candidates" : "Cover directions"}</h4>
    <Button variant="outline" disabled={disabled || result.loading || !!result.error || !result.data} onClick={() => void generate()}>
      {latest ? `Generate next ${kind === "titles" ? "title" : "cover"} version` : `Generate ${kind === "titles" ? "titles" : "cover directions"}`}
    </Button>
    {error && <p role="alert">{error}</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.loading && <p role="status">Loading {kind}…</p>}
    {result.data?.map(state => <div key={state.run.pipeline_run_id} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">Version {state.request.version} · {state.run.status}</h5>
      {!state.current && <p className="text-amber-700">Historical version: selection is disabled.</p>}
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
          <p className="break-all text-xs text-muted-foreground">{item.artifact_id} · {item.model} · {item.prompt_version}</p>
          {state.decision?.choice_id === item.artifact_id ? <p>Selected</p> :
            state.current && state.run.status === "awaiting_approval" &&
            <Button variant="outline" disabled={disabled} onClick={() => void choose(state, item.artifact_id)}>
              Select {kind === "titles" ? "title" : "cover"} {index + 1}
            </Button>}
        </li>)}
      </ol>
      {kind === "titles" && state.run.status === "completed" && state.decision?.choice_id && state.current &&
        <CreativeResults kind="covers" sourceRunId={state.run.pipeline_run_id} revision={revision} submit={submit} disabled={disabled} />}
    </div>)}
  </section>;
}
