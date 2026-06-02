# Task 008: Run full test suite and verify all fixes

**Type**: test
**depends-on**: ["001", "002", "003", "004", "005", "006", "007"]

## BDD Scenario

```gherkin
Scenario: All tests pass after review fixes
  Given all review fix tasks are complete
  When the full test suite is run
  Then all tests pass with exit code 0
  And no test is skipped due to import errors
```

## Steps

1. Run full test suite: `cd backend && python -m pytest -v`
2. Verify no `FeishuAuthError` is raised where `FeishuAPIError` should be
3. Verify `step_runs.claim_step` uses record_id (not business key)
4. Verify `base.py get()` only catches `FeishuNotFoundError`
5. Verify `.env.example` has 16 table ID placeholders
6. Verify `pyproject.toml` has `asyncio_mode = "auto"`

## Verification

```bash
cd backend && python -m pytest -v --tb=short
```
