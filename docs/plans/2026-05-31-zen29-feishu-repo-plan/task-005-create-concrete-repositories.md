# Task 005: Create concrete repositories for all 16 tables

**Type:** impl
**Depends-on:** ["002", "003", "004"]

## BDD Scenario

```gherkin
Scenario: Each of the 16 tables has a dedicated repository
  Given the Feishu schema defines 16 tables
  When I import the repository module
  Then 16 concrete repository classes are available
  And each extends BaseRepository
  And each is pre-configured with the correct table_id and field_map
  And each exposes domain-specific query methods where applicable
```

```gherkin
Scenario: Repositories are wired through a factory
  Given a FeishuClient and TableMapConfig
  When I call create_repositories(client, config)
  Then a dict of all 16 repository instances is returned
  And each repository is ready to use
```

## What to Implement

Create 16 repository files in `backend/app/feishu/repositories/`:

| File | Class | Table | Domain methods |
|------|-------|-------|----------------|
| `agents.py` | `AgentsRepo` | Agents | `find_by_role(role)` |
| `agent_states.py` | `AgentStatesRepo` | AgentStates | `find_by_agent(agent_id)`, `find_by_status(status)` |
| `agent_runs.py` | `AgentRunsRepo` | AgentRuns | `find_by_agent(agent_id)`, `find_by_pipeline(pipeline_run_id)` |
| `pipeline_runs.py` | `PipelineRunsRepo` | PipelineRuns | `find_by_status(status)`, `find_by_type(pipeline_type)` |
| `step_runs.py` | `StepRunsRepo` | StepRuns | `find_by_pipeline(pipeline_run_id)`, `claim_step(step_run_id, owner)` |
| `hotspots.py` | `HotspotsRepo` | Hotspots | `find_by_status(status)`, `find_by_dedupe_hash(hash)` |
| `hotspot_analyses.py` | `HotspotAnalysesRepo` | HotspotAnalyses | `find_by_hotspot(hotspot_id)` |
| `title_candidates.py` | `TitleCandidatesRepo` | TitleCandidates | `find_by_analysis(analysis_id)` |
| `cover_plans.py` | `CoverPlansRepo` | CoverPlans | `find_by_title(title_id)` |
| `books.py` | `BooksRepo` | Books | `find_by_status(status)` |
| `chapter_briefs.py` | `ChapterBriefsRepo` | ChapterBriefs | `find_by_book(book_id)` |
| `chapter_versions.py` | `ChapterVersionsRepo` | ChapterVersions | `find_by_chapter(book_id, chapter_no)` |
| `review_reports.py` | `ReviewReportsRepo` | ReviewReports | `find_by_target(target_type, target_id)` |
| `revision_tasks.py` | `RevisionTasksRepo` | RevisionTasks | `find_by_status(status)` |
| `agent_team_snapshots.py` | `AgentTeamSnapshotsRepo` | AgentTeamSnapshots | `find_by_chapter(book_id, chapter_no)` |
| `approval_events.py` | `ApprovalEventsRepo` | ApprovalEvents | `find_by_target(target_type, target_id)` |

Create `backend/app/feishu/repositories/factory.py` with:
- `create_repositories(client, config) -> dict[str, BaseRepository]` — returns all 16 repos

## Verification

```bash
cd backend && python -c "
from app.feishu.repositories.factory import create_repositories
from app.feishu.repositories import (
    agents, agent_states, agent_runs, pipeline_runs, step_runs,
    hotspots, hotspot_analyses, title_candidates, cover_plans,
    books, chapter_briefs, chapter_versions, review_reports,
    revision_tasks, agent_team_snapshots, approval_events
)
print('All 16 repositories imported OK')
"
```

Expected: All imports succeed, exit code 0.
