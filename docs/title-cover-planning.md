# Title and cover planning (ZEN-36 / GitHub #9)

## Enablement

Title/cover planning reuses the single writer, Feishu StorageProvider, ArtifactStore,
ModelRouter and ResearchService. Set `CREATIVE_ENABLED=true` only after enabling
`RESEARCH_ENABLED`, configuring `titles` and `covers` routes in `MODEL_ROUTES_JSON`,
and supplying their server-side provider keys. No long-lived title/cover Agent
state or second database is created.

The v0.2 Base needs `FEISHU_TABLE_ID_TITLE_CANDIDATES` and
`FEISHU_TABLE_ID_COVER_PLANS`. In addition to the existing fields, provision
`artifact_id`, `version`, `pipeline_run_id` and `source_artifact_id` (text except
numeric `version`) in both tables. Provision text `choice_id` in ApprovalEvents.
The title and cover tables are projections; immutable Artifacts, workflow steps
and ApprovalEvents remain authoritative.

## Workflow and API

- Title flow: exact approved opportunity → model-backed candidate set → ten to
  twenty validated `TitleCandidate` Artifacts → human selection.
- Cover flow: exact selected title, still backed by a current approved opportunity
  → model-backed direction set → three to five validated `CoverPlan` Artifacts →
  human selection. Plans contain visual direction, elements, style, an image
  prompt and negative prompt. No image is produced.
- Both flows preserve versioned sets and candidate Artifacts. The model attempt
  trace records route/model/prompt, source ref, latency, tokens, estimated cost
  when configured, failures and the output set Artifact. Candidate Artifacts
  reference that set and retain its resolved model identity.

All routes use the existing backend API key or signed frontend session proxy:

1. `GET /api/creative/{titles|covers}/{source_run_id}/context` returns exact
   `source_artifact_id` and `next_version`.
2. `POST /api/creative/{titles|covers}` takes `{source_run_id,
   source_artifact_id, version, feedback?, revision_of?}`. Identity is
   `(kind, source_run_id, version)`; a byte-identical replay returns the same
   run, changed inputs conflict. A revision parent must be the latest current
   revision-requested version, with nonblank feedback. Prior candidates become
   frozen input references. Model/prompt configuration changes block pending
   execution instead of silently changing a reserved version.
3. `GET /api/creative/{kind}/{source_run_id}/runs` lists newest-first results.
   `GET /api/creative/runs/{run_id}` includes steps, candidate Artifacts,
   decision and `current` status.
4. `POST /api/creative/runs/{run_id}/decision` takes `{step_id,
   artifact_id, expected_version, action, operator, reason?}`. Approve requires
   a candidate Artifact in the exact validated set. Reject/revise require no
   choice; revise requires a reason. One ApprovalEvent records the choice ID,
   action and reason per step output version. Replaying the same decision is
   idempotent; changing the choice conflicts.
5. `GET /api/creative/runs/{run_id}/selected` returns the selected immutable
   Artifact only if its own version and all upstream versions remain current.
   Book bootstrap (#11) must consume this API/service, not a Feishu status cell.

Generic workflow creation rejects reserved `creative:` request keys, creative
workflow types and handlers. Generic step approval cannot choose a title or cover
without an explicit validated candidate ID.

## Validation and recovery

The schema requires at least ten distinct titles with hooks, selling points,
scores and risk notes; it requires three distinct cover directions with all
prompt fields. NFKC/case/punctuation normalization detects duplicate titles.
Simple deterministic content rules reject contact information and selected
sensitive phrases in titles and cover prompts. Schema/model validation occurs
before the set Artifact is persisted. ModelRouter's configured retry budget is
the only automatic model retry budget; the kernel does not multiply paid calls
after exhaustion. These rules reduce obvious problems but are not a complete
copyright, trademark, legal, content-safety or marketability review.

The frontend stores the exact generation or choice payload before POST. After a
timeout, reload and retry use the same source/version/step/candidate identity.
Feishu projection is repeatable from persisted candidates and decisions after
restart. The backend remains the single writer; do not remove its intent journal.

## Verification boundary

Run the unchanged backend pytest/coverage gate, Ruff, frontend `npm test` and
`npm run check`. `python -m tests.ui_fixture_app` exercises the real API/kernel
over loopback with synthetic Feishu HTTP and synthetic model responses. This
does not prove live model quality, provider token pricing, app credentials,
Base v3 compatibility or Feishu production quotas. PR #23 remains the storage
dependency gate; title/cover model quality still needs representative human
review before deployment.
