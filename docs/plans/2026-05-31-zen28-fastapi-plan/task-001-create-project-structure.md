# Task 001: Create project structure and dependencies

**depends-on**: (none)

## Description

Create the backend project directory layout, `pyproject.toml` with dependencies, and the FastAPI app entrypoint `app/main.py` that can be started with `uvicorn app.main:app`.

## Execution Context

**Task Number**: 001 of 006
**Phase**: Setup
**Prerequisites**: Feature branch `feature/ZEN-28-fastapi-skeleton` checked out

## BDD Scenario

```gherkin
Scenario: Backend project starts with uvicorn
  Given the project has a pyproject.toml with FastAPI and uvicorn dependencies
  And the project has an app/main.py with a FastAPI instance
  When I run "uvicorn app.main:app --host 0.0.0.0 --port 8000"
  Then the server starts without errors
  And the server is listening on port 8000
```

## Files to Modify/Create

- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`

## Steps

### Step 1: Create directory structure

Create the following layout:

```text
backend/
  pyproject.toml
  app/
    __init__.py
    main.py
    api/
      __init__.py
      routes/
        __init__.py
```

### Step 2: Define pyproject.toml

Dependencies (minimum):
- `fastapi >= 1.0.0`
- `uvicorn[standard] >= 0.30.0`
- `pydantic-settings >= 2.0.0`
- `httpx` (dev/test dependency)
- `pytest` (dev/test dependency)
- `pytest-asyncio` (dev/test dependency)

Project metadata: name `novelops-backend`, python `>=3.12`

### Step 3: Create FastAPI entrypoint

`app/main.py` should:
- Create a FastAPI instance with title "NovelOps Agent Harness", version "0.1.0"
- Include an empty API router prefix `/api`
- The app object must be importable as `app.main:app`

### Step 4: Verify

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server should start without errors.

## Verification Commands

```bash
# Install dependencies
cd backend && pip install -e ".[dev]"

# Start server (should not crash)
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/docs | head -5
kill %1
```

## Success Criteria

- `backend/app/main.py` exists and exports `app`
- `uvicorn app.main:app` starts without import errors
- FastAPI auto-docs accessible at `/docs`
