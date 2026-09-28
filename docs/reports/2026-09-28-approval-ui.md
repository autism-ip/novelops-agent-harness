# ZEN-37 — opportunity, title and cover approval UI

- Linear: [ZEN-37](https://linear.app/zenhungyep/issue/ZEN-37/build-opportunity-title-and-cover-approval-ui)
- GitHub: [Issue #10](https://github.com/autism-ip/novelops-agent-harness/issues/10)
- Branch: `codex/zen-37-approval-ui`; review base: ZEN-36 [PR #30](https://github.com/autism-ip/novelops-agent-harness/pull/30).

## Delivered

The hotspot detail panel now exposes exact risk and opportunity decisions, including rejection and revision. A revision carries feedback into the next analysis version. Title and cover comparison supports selection, rejection and revision, with feedback carried into the next candidate set. Historical versions remain visible but cannot be selected. Artifact version, model route, prompt, risk notes and workflow state are shown near the decision.

Decision submissions record the editor name and persist the request before POST. The retry control reuses the exact body after an unknown outcome. Valid stale/conflicting decisions are rejected by the backend with a visible message. The selected title unlocks covers; the selected cover is available to the ZEN-38 book bootstrap contract.

Review follow-up: research decisions retain their required opportunity artifact ID for exact retry; creative revision and rejection retain an empty candidate ID. Candidate generation waits for version history before using its revision feedback. Submission failures also appear inside the active research or creative decision panel.

## Verification

| Check | Result |
| --- | --- |
| Frontend pure-state tests | 9 passed, including research and creative approve/revise/reject replay validation |
| Frontend lint, types, build | ESLint zero warnings, TypeScript and Next production build passed |
| Synthetic browser path | Production Next + real FastAPI/Kernel + synthetic model/Feishu HTTP: human risk approval → opportunity revision → second opportunity approval → title revision → second title selection → cover rejection → second cover selection |
| Editor attribution smoke | Approve disabled until editor name supplied; risk approval event stored `operator = Acceptance Editor` |
| Backend inherited | PR #30 full backend non-live suite: 322 passed, 9 integration deselected, 92.89% coverage; ZEN-37 changes only frontend |

The browser checks use synthetic models and Feishu HTTP. Live Base v3, model quality and book bootstrap remain separate acceptance steps. The entered editor name is attribution, not independently authenticated identity.
