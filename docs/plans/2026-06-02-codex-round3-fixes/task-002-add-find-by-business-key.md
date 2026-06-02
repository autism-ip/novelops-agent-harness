# Task 002: Add find_by_business_key lookup to BaseRepository

**Type**: impl
**depends-on**: ["001"]

## BDD Scenario

```gherkin
Scenario: find_by_business_key resolves business field to Feishu record_id
  Given a StepRunsRepo with a record {step_run_id: "SR-001", record_id: "rec-abc"}
  When find_by_business_key(step_run_id="SR-001") is called
  Then the result is the dict containing record_id "rec-abc"

Scenario: find_by_business_key returns None for missing record
  Given a StepRunsRepo with no matching records
  When find_by_business_key(step_run_id="SR-MISSING") is called
  Then the result is None
```

## Files to Modify

- `backend/app/feishu/repositories/base.py`
- `backend/tests/test_base_repository.py`

## Steps

1. In `base.py`, add method to `BaseRepository`:
   ```python
   def find_by_business_key(self, **conditions) -> dict | None:
       """Look up a record by business fields, returning the first match or None."""
       results = self.list(filter_expr=self._field_filter(**conditions), page_size=1)
       return results[0] if results else None
   ```

2. In `test_base_repository.py`, add `TestFindByBusinessKey` class:
   - Test that it calls `list()` with correct filter and returns first match
   - Test that it returns `None` when no records match

## Verification

```bash
cd backend && python -m pytest tests/test_base_repository.py -v
```
