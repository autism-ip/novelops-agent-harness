# Task 003: Create health and status endpoints

**depends-on**: task-001

## Description

Create two system endpoints: `GET /api/system/health` for basic liveness check and `GET /api/system/status` for component status including worker, Feishu, and OpenCLI placeholders.

## Execution Context

**Task Number**: 003 of 006
**Phase**: Core Features
**Prerequisites**: Task 001 completed, FastAPI app exists with `/api` router

## BDD Scenario

```gherkin
Scenario: Health endpoint returns backend status
  Given the FastAPI server is running
  When I send GET /api/system/health
  Then the response status is 200
  And the response body contains "status": "ok"
  And the response body contains "version": "0.1.0"

Scenario: Status endpoint returns component placeholders
  Given the FastAPI server is running
  When I send GET /api/system/status
  Then the response status is 200
  And the response body contains "backend_status": "running"
  And the response body contains "worker_status": "not_started"
  And the response body contains "feishu_status": "not_configured"
  And the response body contains "opencli_status": "not_configured"
  And the response body contains "active_pipeline_runs": 0
  And the response body contains "pending_steps": 0
  And the response body contains "failed_steps": 0
```

## Files to Modify/Create

- Create: `backend/app/api/routes/system.py`
- Modify: `backend/app/api/routes/__init__.py` (register router)
- Modify: `backend/app/main.py` (include system router)

## Steps

### Step 1: Create system route module

`app/api/routes/system.py` should define:

```python
# Response models
class HealthResponse(BaseModel):
    status: str
    version: str

class StatusResponse(BaseModel):
    backend_status: str
    worker_status: str
    feishu_status: str
    opencli_status: str
    active_pipeline_runs: int
    pending_steps: int
    failed_steps: int

# Endpoints
@router.get("/system/health", response_model=HealthResponse)
@router.get("/system/status", response_model=StatusResponse)
```

### Step 2: Register router

Wire system router into the `/api` prefix router.

### Step 3: Verify

Both endpoints should return correct JSON shapes.

## Verification Commands

```bash
cd backend
uvicorn app.main:app --port 8000 &
sleep 2

# Health check
curl -s http://localhost:8000/api/system/health | python -m json.tool

# Status check
curl -s http://localhost:8000/api/system/status | python -m json.tool

kill %1
```

## Success Criteria

- `GET /api/system/health` returns `{"status": "ok", "version": "0.1.0"}`
- `GET /api/system/status` returns all 7 fields with placeholder values
- Response models enforce correct JSON shape
