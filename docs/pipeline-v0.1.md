# Pipeline v0.1

## Pipeline name

`douyin_to_novel_chapter`

## Goal

Turn a Douyin public hotspot into a reviewed web-novel chapter draft through an observable, approvable, revision-friendly Agent Team workflow.

## Step list

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

## Step details

### 1. fetch_douyin_hotspots

- Agent: `DouyinHotspotCrawlerAgent`
- Tool: OpenCLI
- Output: raw Douyin hotspot records
- Table: `Hotspots`

Boundary:

- Public data only.
- No login bypass.
- No comment scraping.
- No automatic publishing.

### 2. normalize_hotspots

- Agent: `HotspotNormalizeAgent`
- Input: raw hotspot records
- Output: normalized hotspot records with dedupe hash
- Table: `Hotspots`

### 3. analyze_hit_pattern

- Agent: `HitPatternAnalysisAgent`
- Input: normalized hotspot
- Output: hit-pattern analysis
- Table: `HotspotAnalyses`

### 4. analyze_novelization

- Agent: `NovelizationAnalysisAgent`
- Input: hit-pattern analysis
- Output: web-novel directions, reader promise, genre fit, writable angles
- Table: `HotspotAnalyses`

### 5. risk_screen_analysis

- Agent: `RiskScreenAgent`
- Input: analysis output
- Output: risk level, risk notes, pass/revise/reject recommendation
- Table: `ReviewReports` or fields on `HotspotAnalyses`

### 6. approval_analysis

- Agent: `ApprovalAgent`
- Type: approval gate
- Requires human action if risk is high or user wants manual selection.
- Output: ApprovalEvent

### 7. generate_titles

- Agent: `TitleAgent`
- Input: approved analysis
- Output: title candidates, hooks, selling points, scores
- Table: `TitleCandidates`

### 8. generate_cover_plans

- Agent: `CoverAgent`
- Input: approved analysis and title candidates
- Output: cover plans, visual direction, cover prompt, negative prompt
- Table: `CoverPlans`

### 9. approval_title_cover

- Agent: `ApprovalAgent`
- Type: approval gate
- Human selects final title and cover plan.

### 10. create_book

- Agent: `StorySetupAgent`
- Input: approved analysis, title, and cover
- Output: Book row
- Table: `Books`

### 11. init_book_agent_team

- Agent: `OrchestratorAgent`
- Input: Book
- Output: book-scoped AgentStates
- Table: `AgentStates`

### 12. generate_mini_bible

- Agent: `StorySetupAgent`
- Input: Book, analysis, title, cover, initial AgentStates
- Output: MiniBible
- Table: `Books.mini_bible`

### 13. approval_mini_bible

- Agent: `ApprovalAgent`
- Type: approval gate
- Human confirms story setup before chapter generation.

### 14. generate_chapter_briefs

- Agent: `ChapterPlannerAgent`
- Input: MiniBible and AgentStates
- Output: ChapterBriefs
- Table: `ChapterBriefs`

### 15. approval_chapter_briefs

- Agent: `ApprovalAgent`
- Type: approval gate
- Human confirms first chapter briefs.

### 16. create_agent_team_snapshot

- Agent: `OrchestratorAgent`
- Input: current book-scoped AgentStates
- Output: AgentTeamSnapshot
- Table: `AgentTeamSnapshots`

### 17. generate_chapter_draft

- Agent: `ChapterWriterAgent`
- Input: MiniBible, ChapterBrief, AgentTeamSnapshot
- Output: ChapterVersion draft
- Table: `ChapterVersions`

### 18. style_polish

- Agent: `StyleAgent`
- Input: draft chapter
- Output: new ChapterVersion or updated draft version
- Table: `ChapterVersions`

### 19. anti_ai_flavor_rewrite

- Agent: `AntiAIFlavorAgent`
- Input: polished chapter
- Output: less formulaic ChapterVersion
- Table: `ChapterVersions`

### 20. review_chapter

- Agent: `ReviewAgent`
- Input: final draft candidate, MiniBible, ChapterBrief, AgentTeamSnapshot
- Output: ReviewReport
- Table: `ReviewReports`

### 21. human_review

- Agent: `ApprovalAgent`
- Type: approval gate
- Human chooses pass / revise / reject / lock final.

### 22. revise_or_lock_final

- Agent: `ApprovalAgent` or `RewriteAgent`
- If revise: create `RevisionTask`.
- If lock final: mark ChapterVersion status as `final`.

## Status rules

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

## Reliability rules

- Every step must have an idempotency key.
- Every step must have input refs and output refs.
- Every AgentRun must capture model, prompt version, input refs, output refs, and status.
- Every human action creates an ApprovalEvent.
- Any generated chapter rewrite creates a new ChapterVersion.
