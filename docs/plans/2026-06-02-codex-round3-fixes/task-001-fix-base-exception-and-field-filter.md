# Task 001: Fix base.py exception handling and add _field_filter

**Type**: impl
**depends-on**: []

## BDD Scenario

```gherkin
Scenario: get() only catches FeishuNotFoundError
  Given a BaseRepository with a mock client
  When the client raises FeishuAuthError on get()
  Then the exception propagates to the caller
  And the result is NOT None

Scenario: get() returns None for genuine not-found
  Given a BaseRepository with a mock client
  When the client raises FeishuNotFoundError on get()
  Then get() returns None

Scenario: _field_filter builds correct filter expressions
  Given a BaseRepository with field_map {"book_id": "Book ID", "chapter_no": "Chapter No"}
  When _field_filter is called with book_id="B001" and chapter_no=5
  Then the result is 'CurrentValue.[Book ID] = "B001" && CurrentValue.[Chapter No] = 5'
```

## Files to Modify

- `backend/app/feishu/repositories/base.py`
- `backend/tests/test_base_repository.py`

## Steps

1. In `base.py`:
   - Add import: `from app.feishu.client import FeishuNotFoundError`
   - Change `get()` from `except Exception:` to `except FeishuNotFoundError:`
   - Add `_field_filter(**conditions)` method that maps Python field names through `self._field_map` and builds `CurrentValue.[feishu_field] = "value"` clauses (int values unquoted, str values quoted)

2. In `test_base_repository.py`:
   - Add `from app.feishu.client import FeishuNotFoundError`
   - Change `test_get_returns_none_on_error` mock from `Exception("not found")` to `FeishuNotFoundError("not found", code=1254043)`
   - Add `TestFieldFilter` class with tests for known keys, int values, and multi-field AND

## Verification

```bash
cd backend && python -m pytest tests/test_base_repository.py -v
```
