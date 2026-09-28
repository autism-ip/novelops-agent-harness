# Opportunity, title and cover decisions (ZEN-37)

The hotspot detail panel is the decision surface for the opportunity, title and cover chain. Analysis and candidate content appear before source metadata; the raw source payload is collapsed under Source details. Each section shows artifact version, model route, prompt and risk details for review. It uses the authenticated domain APIs rather than generic workflow transitions.

## Decision sequence

1. A research run with policy risk waits at `risk_gate`. The editor reviews the assessment and approves, rejects or requests revision for the exact opportunity artifact and step output version.
2. The opportunity `selection` gate then accepts the same three actions. Approval unlocks title generation. A revision decision stores feedback and offers a new analysis version; the previous version remains visible but cannot be selected.
3. A title set offers exact candidate selection, whole-set rejection or revision with feedback. Revision offers a new version that includes the previous immutable candidates and the feedback. Only the current selected title unlocks cover planning.
4. A cover set follows the same choice rules. Its current selected artifact is the input contract for book bootstrap in ZEN-38.

Approve/reject/revise sends a `step_id`, `expected_version`, operator and reason. Candidate approvals also send the exact candidate Artifact ID. A rejected or revised title/cover set sends no candidate ID. The backend writes `ApprovalEvent`; UI status is reloaded from backend state. A stale version or conflicting decision returns a visible error and cannot overwrite a prior event.

The editor types a name once per browser session; it is reused across the decision panels and stored as the event operator. The shared workspace password authenticates access, but does not verify the entered name as a personal identity.

The UI saves each request to session storage before POST. After an uncertain response it offers replay of the same body and exact version rather than creating a new workflow. Regeneration reserves the next version using a fresh context request.

## Configuration and limits

Opportunity actions require `RESEARCH_ENABLED`; title/cover actions require `CREATIVE_ENABLED`. The panel hides unavailable creative controls using `/api/hotspots/capabilities`. Book bootstrap itself belongs to ZEN-38. This UI consumes the selected title/cover contract but does not create a Book record.
