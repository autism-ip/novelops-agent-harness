# Task 007: Verify integration with Feishu API

**Type:** test
**Depends-on:** ["006"]

## BDD Scenario

```gherkin
Scenario: End-to-end CRUD against real Feishu Bitable
  Given FEISHU_APP_ID, FEISHU_APP_SECRET, and FEISHU_APP_TOKEN are configured
  And a test table exists in the Bitable app
  When I create a record via the repository
  Then the record exists in Feishu
  When I read the record by ID
  Then the fields match the created data
  When I update a field
  Then the updated value is persisted
  When I delete the record
  Then the record no longer exists
```

```gherkin
Scenario: Acceptance criteria — repository layer hides Feishu details
  Given the repository layer is imported
  When agent code uses repositories
  Then no direct Feishu API URLs or auth tokens are visible
  And all table/field names are accessed through the table map
  And the client handles auth, retries, and errors transparently
```

## What to Implement

Create `backend/tests/test_feishu_integration.py`:
- Mark all tests with `@pytest.mark.integration` (skip when env vars missing)
- Test create → read → update → delete cycle on a real table
- Verify field mapping round-trips correctly

## Verification

```bash
cd backend && python -m pytest tests/test_feishu_integration.py -v -m integration
```

Expected: Tests pass when Feishu credentials configured. Tests skip gracefully when env vars missing.
