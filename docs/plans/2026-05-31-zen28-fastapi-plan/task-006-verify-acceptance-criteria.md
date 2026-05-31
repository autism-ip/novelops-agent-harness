# Task 006: Verify full backend startup and acceptance criteria

**depends-on**: task-005

## Description

Final verification that all ZEN-28 acceptance criteria are met. Start the backend with uvicorn, hit all endpoints, and confirm the full request lifecycle works.

## Execution Context

**Task Number**: 006 of 006
**Phase**: Verification
**Prerequisites**: Task 005 completed, all integration tests pass

## BDD Scenario

```gherkin
Scenario: Backend satisfies all ZEN-28 acceptance criteria
  Given the backend is started with "uvicorn app.main:app"
  When I send GET /api/system/health
  Then the response contains backend status
  When I send GET /api/system/status
  Then the response contains worker/Feishu/OpenCLI placeholders
  When I check for secrets in responses
  Then no API keys or credentials are exposed
  When I check the project layout
  Then it matches the architecture doc module structure
```

## Files to Modify/Create

- No new files — verification only

## Steps

### Step 1: Start backend

```bash
cd backend
BACKEND_API_KEY=verify-key uvicorn app.main:app --port 8000 &
sleep 3
```

### Step 2: Verify acceptance criterion 1

```bash
curl -s http://localhost:8000/api/system/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

### Step 3: Verify acceptance criterion 2

```bash
curl -s http://localhost:8000/api/system/status
# Expected: all 7 fields with placeholder values
```

### Step 4: Verify acceptance criterion 3

```bash
# Server started with uvicorn — criterion met
```

### Step 5: Verify acceptance criterion 4

```bash
# Check no secrets in responses
curl -s http://localhost:8000/api/system/health | grep -c "verify-key" || echo "PASS: no secrets"
curl -s http://localhost:8000/api/system/status | grep -c "verify-key" || echo "PASS: no secrets"
```

### Step 6: Cleanup

```bash
kill %1
```

## Verification Commands

```bash
cd backend && python -m pytest tests/ -v
```

## Success Criteria

- All 4 acceptance criteria from ZEN-28 are met
- All integration tests pass
- No regressions
- Commit: all backend files on feature branch
