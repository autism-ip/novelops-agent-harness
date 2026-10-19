# ZEN-39 — StoryBible and chapter planning

Enable `STORY_PLANNING_ENABLED=true` only with the Book runtime, persistent Harness intent journal, and configured `story_architect` and `chapter_planner` model routes in `MODEL_ROUTES_JSON`. This feature uses the existing Books, StoryStates, Artifacts, Traces, PipelineRuns, StepRuns, and ApprovalEvents storage. ChapterBriefs are versioned Artifacts; the older `ChapterBriefs` table is not a second source of truth.

## StoryBible and canonical state

`GET /api/books/{book_id}/bible/context` returns the current exact StoryState artifact ID/version and next Bible version. Submit that body to `POST /api/books/{book_id}/bibles`. The Harness creates a deterministic workflow ID for the Book and Bible version. `StoryArchitectAgent` generates a strict StoryBible Artifact with premise, protagonist, core conflict, power rules, reader promise, style contract, and forbidden rules. Extra or missing fields fail validation; generated text is data, not executable instructions.

The `review` step always waits for a human, including the initial Bible and later major direction changes. `GET /api/story-planning/runs/{run_id}` exposes the artifact, step, exact output version, and current status. `POST /api/story-planning/runs/{run_id}/decision` must submit the review step ID, Bible artifact ID on approval, output version, operator, and action (`approve`, `reject`, `revise`). A revision requires feedback, which the next Bible context carries forward; the next request must include nonempty feedback. Approval checks that the Book still points to the exact frozen base StoryState and that the Bible Artifact matches the review output.

After approval, the Harness applies a deterministic, schema-validated patch to StoryBible, Characters, PowerSystem, and StyleContract, saves an immutable next-version StoryState Artifact, creates a StoryStates projection, then moves the Book pointer. The new Artifact references the prior state and approved Bible. Previous state and Bible versions remain readable by Artifact ID. If the final Book pointer write is interrupted, the same step replays the same IDs/content. An ambiguous storage write blocks for reconciliation; a new request cannot silently reuse a reserved Bible version with different inputs.

## StoryContextSnapshot and ChapterBrief

`GET /api/books/{book_id}/chapters/{chapter_no}/brief/context` returns the current exact state and next brief version. It rejects Books without an approved Bible. `POST /api/books/{book_id}/chapters/{chapter_no}/briefs` creates an immutable StoryContextSnapshot from the current state version/hash/content and Bible artifact. The snapshot has exact source refs and survives later state changes.

`ChapterPlannerAgent` produces a strict draft with opening hook, scene goal, conflict, payoff, and ending hook. The Harness materializes a ChapterBrief Artifact with those fields plus Book/chapter number, exact StoryState artifact ID/version/hash, snapshot ID, and Bible ID. Routine brief generation needs no approval; `GET /api/books/{book_id}/chapters/{chapter_no}/brief/eligible` exposes only a completed latest-version brief whose source state is still current. Chapter generation in ZEN-40 consumes this eligibility boundary. Regeneration reserves a new brief version; older drafts, snapshots, and briefs remain immutable.

## Limits and recovery

Model calls, Feishu access, and persistence still depend on deployment credentials and table schema. Offline tests use synthetic model output and HTTP storage. The workflow keeps one writer and a persistent intent journal. A model validation failure fails its version; a later request uses the next version. A source state change invalidates an uncommitted Bible or current brief, and the editor must refresh context. The backend does not infer approval from a generated artifact alone.

## Editorial direction and source data

The authenticated API continues to accept `feedback`. Internally, `story-architect-v2` and `chapter-planner-v2` receive it as an explicit `editor_instruction`, separate from immutable source text. The Bible input also carries the validated `initial`/`major` change scope; proposals still require exact human approval before changing canonical state. Chapter direction cannot override canonical snapshot rules, and a prior brief that contradicts those rules is corrected rather than preserved. Source narrative cannot supply an instruction by including a similarly named field. Clients cannot submit the internal field through the public request schema.

This input boundary and strict schema validation do not prove semantic compliance. The acceptance driver inspects a newly generated brief before spending on its chapter; observed contradictions remain failures, even when source eligibility is valid.

### Planning language versus chapter prose

`chapter-planner-v3` produces an author-facing plan. The canonical StoryBible style contract governs downstream chapter prose; it does not require the planning fields themselves to be drafted first-person scenes. The planner follows the editor's field-specific person, sentence limits and exact quoted text/punctuation, with canonical facts still authoritative. This change follows a real DeepSeek result that preserved the canonical rule/name/ending but ignored the requested planning perspective and payoff sentence count. Semantic compliance still requires independent runtime review; schema validation alone cannot establish it. Frozen prompt hashes remain binding: a queued Bible or brief blocks before a model call if its prompt contract changes, with no generated output or canonical state mutation after enqueue.

### Explicit editor message contract

`story-architect-v3` and `chapter-planner-v4` opt in to the validated `editor_instruction` field as a final user message, after unchanged source JSON. System canonical/scope rules remain above that user direction. The field selection is included in input provenance; API feedback and source refs remain unchanged. A bounded real diagnostic of the exact failed v3 messages passed the original perspective/sentence/name/quote checks only after this structural addition. This diagnostic is not business workflow completion; a source-matched native continuation and independent review are still required. Frozen tasks retain their original prompt contract.

## Final chapter history for the next plan

A new brief freezes a chapter/run-specific planning snapshot, retaining the canonical StoryState and Bible plus the nearest earlier final ChapterVersion when one exists. It includes that chapter's complete bounded prose, Artifact ID, content hash, chapter/version number and domain ID. Source refs include the final Artifact; non-final candidates, future chapters and other Books do not become history. The deterministic builder verifies the immutable Artifact, domain projection and passing verification evidence. Duplicate finals, missing canonical history or conflicting provenance stop planning before a model call. Legacy final rows without an Artifact need reconciliation rather than guessed canonical prose.

The planner treats `prior_final_chapters` as completed narrative history, never instructions. This does not add a memory Agent or a model pass, and does not silently patch StoryState from prose. A later change to the relevant final history makes the old brief ineligible and stops a queued plan before generation. A new explicit brief version receives a new immutable snapshot even if the StoryState version stayed the same. Exact command replay returns its existing run and does not regenerate paid content. Existing completed legacy snapshots remain readable; chapter 1 has no earlier chapter history.

Brief reads batch the brief and snapshot in a single response-scoped Artifact read. This preserves the existing read budget without retaining a mutable cache between requests or skipping fresh execution/decision checks. Writer, Critic and Rewrite consume this frozen historical context downstream in ZEN-40.

When `STORY_PLANNING_ENABLED` is enabled, configure `FEISHU_TABLE_ID_CHAPTER_VERSIONS` with read access even if chapter generation is disabled. Planning owns its canonical-history reader and fails during runtime composition when the table configuration is absent; it does not depend on a later chapter-service flag to register that repository. Existing additive canonical Artifact metadata is read without introducing a second store.

Internal chapter consumers can obtain the exact original BriefRequest together with
its eligible Brief and freshly verified planning snapshot in one read. The full
editor direction is retained up to the existing 4000-character input limit; a
five-field plan is not a lossless substitute. Caller-local edits do not persist,
and public Brief/read response shapes remain unchanged. This adds no provider
request and does not rewrite an existing planning Artifact.
