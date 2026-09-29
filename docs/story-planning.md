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
