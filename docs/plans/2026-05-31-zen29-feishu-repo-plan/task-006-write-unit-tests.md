# Task 006: Write unit tests for client and repositories

**Type:** test
**Depends-on:** ["005"]

## BDD Scenario

```gherkin
Scenario: FeishuClient unit tests with mocked HTTP
  Given a FeishuClient with mocked HTTP responses
  When authenticate is called
  Then tenant_access_token is stored
  And the token is attached to subsequent requests

  When a request returns 401
  Then the token is refreshed and the request is retried
```

```gherkin
Scenario: BaseRepository CRUD tests with mocked client
  Given a BaseRepository with a mocked FeishuClient
  When create({"name": "test"}) is called
  Then the client.post is called with correct path and field-mapped body
  And the created record is returned

  When get("rec_123") is called
  Then the client.get is called with the correct record path
  And the record is returned with Python field names
```

```gherkin
Scenario: Field mapping correctness
  Given a BaseRepository with field_map {"book_id": "Book ID", "title": "Title"}
  When _to_feishu({"book_id": "B001", "title": "My Novel"}) is called
  Then the result is {"Book ID": "B001", "Title": "My Novel"}

  When _from_feishu({"Book ID": "B001", "Title": "My Novel"}) is called
  Then the result is {"book_id": "B001", "title": "My Novel"}
```

```gherkin
Scenario: Table map completeness
  Given the table map module
  When TABLE_NAMES is inspected
  Then it contains exactly 16 entries
  And FIELD_MAPS contains exactly 16 entries
  And every TABLE_NAMES key has a corresponding FIELD_MAPS entry
```

## What to Implement

Create `backend/tests/test_feishu_client.py`:
- Test token acquisition, attachment, auto-refresh on 401, error handling

Create `backend/tests/test_base_repository.py`:
- Test CRUD operations with mocked FeishuClient
- Test field mapping (_to_feishu, _from_feishu)

Create `backend/tests/test_table_map.py`:
- Test 16 tables present, field maps completeness

## Verification

```bash
cd backend && python -m pytest tests/test_feishu_client.py tests/test_base_repository.py tests/test_table_map.py -v
```

Expected: All tests pass, exit code 0.
