# Task 007: Update config files (.env.example, pyproject.toml)

**Type**: config
**depends-on**: []

## BDD Scenario

```gherkin
Scenario: .env.example has all 16 table ID placeholders
  Given the .env.example file
  When the file is read
  Then it contains FEISHU_TABLE_ID_AGENTS through FEISHU_TABLE_ID_APPROVAL_EVENTS (16 entries)
  And all values are empty (placeholder only)

Scenario: pyproject.toml has asyncio_mode
  Given pyproject.toml
  When [tool.pytest.ini_options] is read
  Then asyncio_mode = "auto" is present
```

## Files to Modify

- `backend/.env.example`
- `backend/pyproject.toml`

## Steps

1. In `.env.example`:
   - Add `FEISHU_APP_TOKEN=` placeholder after FEISHU_APP_SECRET
   - Add all 16 `FEISHU_TABLE_ID_*=` placeholders (AGENTS, AGENT_STATES, AGENT_RUNS, PIPELINE_RUNS, STEP_RUNS, HOTSPOTS, HOTSPOT_ANALYSES, TITLE_CANDIDATES, COVER_PLANS, BOOKS, CHAPTER_BRIEFS, CHAPTER_VERSIONS, REVIEW_REPORTS, REVISION_TASKS, AGENT_TEAM_SNAPSHOTS, APPROVAL_EVENTS)

2. In `pyproject.toml`:
   - Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`

## Verification

```bash
cd backend && python -m pytest --co -q 2>&1 | tail -5
```
