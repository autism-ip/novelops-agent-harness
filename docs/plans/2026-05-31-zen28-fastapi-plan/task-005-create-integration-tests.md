# Task 005: Create integration tests for all endpoints

**depends-on**: task-002, task-003, task-004

## Description

Create pytest integration tests using FastAPI's TestClient that verify all endpoints, config loading, and API key guard behavior end-to-end.

## Execution Context

**Task Number**: 005 of 006
**Phase**: Integration
**Prerequisites**: Tasks 002, 003, 004 all completed

## BDD Scenario

```gherkin
Scenario: All system endpoints pass integration tests
  Given a test client with BACKEND_API_KEY="test-key"
  When all system endpoint tests are run
  Then health endpoint returns 200 with correct shape
  And status endpoint returns 200 with all 7 fields
  And API key guard rejects unauthorized requests with 401
  And API key guard allows authorized requests
  And health and status are exempt from API key check
```

## Files to Modify/Create

- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_system_endpoints.py`
- Create: `backend/tests/test_api_key_guard.py`

## Steps

### Step 1: Create test fixtures

`tests/conftest.py` should define:
- `test_client` fixture using `httpx.AsyncClient` with `ASGITransport`
- Set `BACKEND_API_KEY=test-key` in test environment
- Override settings for test isolation

### Step 2: Create system endpoint tests

`tests/test_system_endpoints.py`:
- `test_health_returns_ok` — GET /api/system/health returns 200 + status/version
- `test_status_returns_placeholders` — GET /api/system/status returns 200 + all 7 fields
- `test_health_exposes_no_secrets` — response body does not contain env var values

### Step 3: Create API key guard tests

`tests/test_api_key_guard.py`:
- `test_health_exempt_from_api_key` — GET /api/system/health without key returns 200
- `test_status_exempt_from_api_key` — GET /api/system/status without key returns 200
- `test_missing_api_key_returns_401` — GET /api/pipelines without key returns 401
- `test_wrong_api_key_returns_401` — GET /api/pipelines with wrong key returns 401
- `test_valid_api_key_passes` — GET /api/pipelines with correct key does not return 401

### Step 4: Verify all tests pass

```bash
cd backend && python -m pytest tests/ -v
```

## Verification Commands

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

## Success Criteria

- All tests pass
- Tests use TestClient (no real server needed)
- Tests are isolated (no dependency on external services)
- Coverage of all BDD scenarios from tasks 002, 003, 004
