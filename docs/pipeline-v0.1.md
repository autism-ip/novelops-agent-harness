# Pipeline v0.1 — Historical Design

> **Status: superseded for new implementation work.** This document is retained as the historical v0.1 pipeline baseline. New work follows `docs/architecture.md` v0.2 and the current Linear/GitHub issues.
>
> Key v0.2 changes: deterministic Harness services replace system Agents; data collection/normalization are not LLM Agents; canonical `StoryState` replaces per-role Agent memory; `StoryContextSnapshot` replaces `AgentTeamSnapshot`; chapter generation uses `Writer → Verifier → Critic → Rewrite-if-needed → Verifier`; human approval is selective rather than mandatory at every stage.

## Pipeline name

`douyin_to_novel_chapter`

## Original v0.1 goal

Turn a Douyin public hotspot into a reviewed web-novel chapter draft through an observable, approvable, revision-friendly Agent Team workflow.

## Original step list

```text
fetch_douyin_hotspots
normalize_hotspots
analyze_hit_pattern
analyze_novelization
risk_screen_analysis
approval_analysis
generate_titles
generate_cover_plans
approval_title_cover
create_book
init_book_agent_team
generate_mini_bible
approval_mini_bible
generate_chapter_briefs
approval_chapter_briefs
create_agent_team_snapshot
generate_chapter_draft
style_polish
anti_ai_flavor_rewrite
review_chapter
human_review
revise_or_lock_final
```

## v0.2 mapping

The original linear pipeline is decomposed into composable workflows:

```text
Research ingestion / hotspot workflow
        ↓
Opportunity intelligence / title / cover workflow
        ↓
Book bootstrap / canonical StoryState workflow
        ↓
Chapter planning workflow
        ↓
Chapter generation / critique / revision workflow
```

### Research ingestion

`fetch_douyin_hotspots` and `normalize_hotspots` become deterministic Harness/tool steps using the existing OpenCLI adapter and Feishu storage provider. No LLM call is required.

### Opportunity intelligence

The old hit-pattern/novelization/risk Agent chain is consolidated around a small semantic research surface plus deterministic schema/rule verification and selective human review.

### Book bootstrap

`init_book_agent_team` is replaced by initialization of canonical, versioned `StoryState` namespaces.

### Story setup and planning

`generate_mini_bible` evolves into StoryBible/StoryState generation through `StoryArchitectAgent`. `ChapterPlannerAgent` produces versioned ChapterBrief Artifacts.

### Snapshot

`create_agent_team_snapshot` is replaced by `StoryContextSnapshot`, which references explicit StoryState and Artifact versions used for a chapter.

### Chapter generation

The original sequence:

```text
generate_chapter_draft
style_polish
anti_ai_flavor_rewrite
review_chapter
```

is replaced by:

```text
build_context
  ↓
write_chapter
  ↓
deterministic_verify
  ↓
semantic_critique
  ↓
rewrite_if_required
  ↓
verify
  ↓
selective_human_gate
  ↓
finalize
```

## Historical v0.1 status rules

### PipelineRun status

```text
pending
running
waiting_approval
paused
failed
completed
```

### StepRun status

```text
pending
running
success
failed
blocked
skipped
```

### Approval status

```text
pending
approved
rejected
revise
```

These values may be migrated as part of the v0.2 state-machine alignment. New lifecycle transitions should be centralized behind the Harness state-transition service.

## Historical reliability rules retained in v0.2

- Important operations remain idempotent at the business level.
- Steps keep explicit input/output references.
- Generated artifacts and rewrites remain versioned; no silent overwrite.
- Human actions remain auditable through ApprovalEvents.
- Model-backed executions retain model/prompt/run provenance.

For the current implementation baseline, see [Architecture v0.2](architecture.md) and the latest Linear/GitHub issues.
