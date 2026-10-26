import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { AnalysisCard } from "../src/components/hotspots/research-results";
import type { OpportunityAnalysis } from "../src/api/types";

const riskId = "SR-risk", selectionId = "SR-selection";
function analysis(): OpportunityAnalysis {
  return { run: { pipeline_run_id: "PR-analysis", pipeline_type: "hotspot_research_v1", status: "running",
    created_at: "2026-10-26T00:00:00Z", updated_at: "2026-10-26T00:00:00Z",
    steps: [{ step_run_id: riskId, step_key: "risk_gate", status: "awaiting_approval", output_version: 2 },
      { step_run_id: selectionId, step_key: "selection", status: "pending", output_version: 0 }] },
    request: { version: 3, hotspot_id: "HS-garden" }, source: { title: "A city garden" }, current: true,
    approval_status: "running", decisions: [], opportunity: null, risk: null };
}
function risk(): NonNullable<OpportunityAnalysis["risk"]> {
  return { content: { level: "high", requires_review: true, rule_flags: ["Named person"], assessments: [
    { reasons: ["Check the quoted statement."], uncertainties: ["Identity is unconfirmed."], flags: ["Attribution"], confidence: 0.75 },
    { reasons: ["Keep the fictional setting."], uncertainties: [], flags: [], confidence: 0.9 },
  ] } };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("an analysis with no artifacts keeps its real source, version and workflow state without empty provenance", () => {
  const transport = vi.fn(() => { throw new Error("Reading a card must not start a request"); });
  vi.stubGlobal("fetch", transport);
  render(<AnalysisCard analysis={analysis()} />);
  expect(screen.getByRole("heading", { name: "A city garden · Version 3" })).toBeTruthy();
  expect(screen.getByText("running")).toBeTruthy();
  expect(screen.queryByText("Review full analysis and provenance")).toBeNull();
  expect(screen.queryByText(/Human risk review/)).toBeNull();
  expect(screen.queryByText(/^Artifact /)).toBeNull();
  expect(transport).not.toHaveBeenCalled();
});

test("risk-only results remain reviewable before an opportunity exists, including both assessments and uncertainty", () => {
  const data = analysis(); data.risk = risk(); data.approval_status = "awaiting_risk_review";
  render(<AnalysisCard analysis={data} />);
  expect(screen.getByText("Needs human risk review")).toBeTruthy();
  expect(screen.getByText("Risk: high")).toBeTruthy();
  const details = screen.getByText("Review full analysis and provenance").closest("details")!;
  expect(details.open).toBe(false);
  for (const text of ["Human risk review is required before this opportunity can continue.", "Rule flags: Named person",
    "Research risk assessment · Confidence 75%", "Additional risk review · Confidence 90%", "Semantic flags: Attribution",
    "Check the quoted statement.", "Identity is unconfirmed.", "Keep the fictional setting."])
    expect(within(details).getByText(text)).toBeTruthy();
  expect(screen.queryByText("Core emotions")).toBeNull();
  expect(screen.queryByText(/^Route:/)).toBeNull();
});

const decisions = [
  { label: "no event", action: null, target: riskId, steps: true, approved: false },
  { label: "risk rejection", action: "reject", target: riskId, steps: true, approved: false },
  { label: "risk revision", action: "revise", target: riskId, steps: true, approved: false },
  { label: "opportunity approval", action: "approve", target: selectionId, steps: true, approved: false },
  { label: "another run's risk approval", action: "approve", target: "SR-other", steps: true, approved: false },
  { label: "no step identity", action: "approve", target: riskId, steps: false, approved: false },
  { label: "matching risk approval", action: "approve", target: riskId, steps: true, approved: true },
];
test.each(decisions)("risk review copy follows its own event and step: $label", ({ action, target, steps, approved }) => {
  const data = analysis(); data.risk = risk();
  data.decisions = action ? [{ action, target_id: target, target_version: 2, reason: "Reviewed the attribution" }] : [];
  if (!steps) delete data.run.steps;
  render(<AnalysisCard analysis={data} />);
  const approvedCopy = "Human risk review approved.";
  const requiredCopy = "Human risk review is required before this opportunity can continue.";
  expect(screen.getByText(approved ? approvedCopy : requiredCopy)).toBeTruthy();
  expect(screen.queryByText(approved ? requiredCopy : approvedCopy)).toBeNull();
});

test("automatic low risk has no invented human approval, flags, or assessments", () => {
  const data = analysis(); data.risk = { content: { level: "low", requires_review: false, rule_flags: [], assessments: [] } };
  render(<AnalysisCard analysis={data} />);
  expect(screen.getByText("Risk: low")).toBeTruthy();
  expect(screen.queryByText(/Human risk review/)).toBeNull();
  expect(screen.queryByText(/^Rule flags:/)).toBeNull();
  expect(screen.queryByText(/Confidence/)).toBeNull();
});

test.each([true, false])("opportunity content and provenance stay attached to the displayed version (current=%s)", current => {
  const data = analysis(); data.current = current; data.approval_status = "approved";
  data.opportunity = { artifact_id: "AR-garden-v3", route: "research", model: "recorded-model", prompt_version: "opportunity-v3",
    content: { summary: "Neighbors restore their shared garden.", core_emotions: ["Hope"], hit_patterns: ["A hidden seed"],
      genre_fit: ["Cozy fantasy"], reader_promise: "See the garden bloom", novelization_directions: ["A reluctant gardener"] } };
  render(<AnalysisCard analysis={data} />);
  expect(screen.getByText(data.opportunity.content.summary)).toBeTruthy();
  expect(screen.getByText("Artifact AR-garden-v3")).toBeTruthy();
  expect(screen.getByText("Approved opportunity")).toBeTruthy();
  for (const text of ["Hope", "A hidden seed", "Cozy fantasy", "See the garden bloom", "A reluctant gardener",
    "Route: research · Model: recorded-model · Prompt: opportunity-v3"]) expect(screen.getByText(text)).toBeTruthy();
  expect(screen.queryByText(/Historical analysis:/) !== null).toBe(!current);
});
