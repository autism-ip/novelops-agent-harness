# Task 001: Add lark-oapi dependency

**Type:** setup
**Depends-on:** []

## BDD Scenario

```gherkin
Scenario: Feishu SDK dependency is available
  Given the backend project uses pyproject.toml for dependency management
  When I add the lark-oapi package to dependencies
  Then `pip install -e ".[dev]"` succeeds without errors
  And `python -c "import lark_oapi"` exits with code 0
```

## What to Implement

Add `lark-oapi` (official Feishu/Lark Python SDK) to `backend/pyproject.toml` dependencies.

## Files to Modify

- `backend/pyproject.toml` — add `"lark-oapi>=1.0.0"` to `[project] dependencies`

## Verification

```bash
cd backend && pip install -e ".[dev]" && python -c "import lark_oapi; print('OK')"
```

Expected: `OK` printed, exit code 0.
