# ZEN-41 — Book-centered chapter review desk

The Book page keeps chapter generation and editorial review in one chapter-specific workspace. Desktop uses a chapter list/content column beside critique and decisions; mobile stacks them. The primary area shows prose, version status, Critic evidence and deterministic verification. StoryBible, StoryState and Brief summaries appear nearby. Exact source IDs, model route/prompt, token/cost/latency traces and full StoryState are available in expandable details.

## Policy and state

`CHAPTER_REVIEW_FIRST_N` holds the first N chapters at the final verifier. `CHAPTER_REVIEW_SCORE_THRESHOLD` also holds a chapter when any Critic dimension is at or below the configured 1–5 threshold. A zero value disables each gate. A required gate keeps the Harness run `awaiting_approval`; the current verified ChapterVersion remains `review` until the editor decides. A routine pass completes automatically and remains available for optional editorial approval, revision, rejection or final lock. A gated run cannot be regenerated or final-locked until the gate is resolved.

`GET /api/books/{book_id}/chapters/{chapter_no}/review` returns the latest run, exact snapshot, StoryBible, Brief, StoryState summary, all ChapterVersions with linked Critic evidence and each version's deterministic verifier, revision tasks and traces. It may return legacy versions without an Artifact, marked as legacy and shown read-only. The UI uses domain IDs and does not expose Feishu record IDs as action targets. The Story and Brief summary and usage traces describe the current run; switching version history changes the prose, report, verifier and source references together. The read path rejects duplicate ChapterVersion Artifact projections and Critic links from another run or source context. When a rewritten version carries the initial draft's CriticReport, the desk names the earlier version actually scored and says the rewrite has not received another Critic pass.

## Commands and recovery

`POST .../review/decision` names run, version, Artifact, number, editor and gate output version. Approve marks the version `approved`; reject marks it `rejected`. A configured gate also drives the Harness step decision, completing or failing the run. Duplicate identical decisions return the persisted result; stale or conflicting decisions return 409. The generic workflow step-decision route refuses chapter handlers.

`POST .../review/revision` requires the same exact target plus nonempty `must_change`, optional `must_keep` and `do_not_change`. It writes a deterministic RevisionTask linked to the selected source version and its Artifact, stores the frozen generation request, then enqueues a new run. Repeating the same command resumes/returns that task and run; a changed source run, Artifact, version number, editor or constraints conflicts. The new ChapterVersion is appended, never overwritten. A failed or interrupted enqueue leaves the task `open` for safe replay; an accepted enqueue marks it `queued`.

RevisionTask `status` records enqueue progress and remains `queued` after acceptance. The review response adds each task's current `run_status` from its linked WorkflowRun, or `null` before the run exists. The desk labels the source version and live run state so a finished rewrite is not presented as still queued.

`POST .../final-lock` remains the exact, idempotent finalization command. It requires the latest completed run and current selected version, accepts `review` or `approved`, and leaves older ChapterVersions readable. Final lock blocks later mutation. The UI retains unknown-outcome commands in session storage and offers replay with the identical target/body.

## Deployment limits

Add the ZEN-41 RevisionTasks fields in [feishu-schema.md](feishu-schema.md) before enabling live revision. Live Feishu PATCH behavior, permissions, Bitable text/JSON limits, real model quality and configured price accuracy still require production acceptance. A synthetic HTTP fixture validates local behavior only.
