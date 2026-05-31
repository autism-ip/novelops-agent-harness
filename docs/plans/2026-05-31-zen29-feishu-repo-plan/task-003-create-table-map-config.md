# Task 003: Create table map config

**Type:** impl
**Depends-on:** ["001"]

## BDD Scenario

```gherkin
Scenario: Table map centralizes all 16 table definitions
  Given the Feishu schema defines 16 tables
  When I import the table map module
  Then all 16 table names are accessible as constants
  And each table has a field mapping dict (Python field name → Feishu field name)
  And the map includes: Agents, AgentStates, AgentRuns, PipelineRuns, StepRuns, Hotspots, HotspotAnalyses, TitleCandidates, CoverPlans, Books, ChapterBriefs, ChapterVersions, ReviewReports, RevisionTasks, AgentTeamSnapshots, ApprovalEvents
```

```gherkin
Scenario: Table map is configuration-driven
  Given the table map is loaded
  When FEISHU_APP_TOKEN is set in environment
  Then the app_token is accessible from config
  And table IDs can be overridden via environment variables
```

## What to Implement

Create `backend/app/feishu/table_map.py` with:

- `TABLE_NAMES` — dict mapping logical name to Feishu table name for all 16 tables
- `FIELD_MAPS` — dict mapping logical name to `{python_field: feishu_field}` for all 16 tables
- `TableMapConfig` class:
  - `app_token: str` — Feishu Bitable app token (from env `FEISHU_APP_TOKEN`)
  - `get_table_id(self, name: str) -> str` — returns table ID for a logical name
  - `get_field_map(self, name: str) -> dict[str, str]` — returns field mapping

The 16 tables (from `docs/feishu-schema.md`):
Agents, AgentStates, AgentRuns, PipelineRuns, StepRuns, Hotspots, HotspotAnalyses, TitleCandidates, CoverPlans, Books, ChapterBriefs, ChapterVersions, ReviewReports, RevisionTasks, AgentTeamSnapshots, ApprovalEvents

## Files to Create

- `backend/app/feishu/table_map.py`

## Verification

```bash
cd backend && python -c "
from app.feishu.table_map import TABLE_NAMES, FIELD_MAPS
assert len(TABLE_NAMES) == 16
assert len(FIELD_MAPS) == 16
print(f'OK: {len(TABLE_NAMES)} tables, {len(FIELD_MAPS)} field maps')
"
```

Expected: `OK: 16 tables, 16 field maps`, exit code 0.
