# Task 004: Create API key guard middleware

**depends-on**: task-001

## Description

Create a middleware that validates `x-api-key` header on all `/api` requests except health and status endpoints. Requests without a valid key receive 401 Unauthorized.

## Execution Context

**Task Number**: 004 of 006
**Phase**: Core Features
**Prerequisites**: Task 001 completed, FastAPI app exists

## BDD Scenario

```gherkin
Scenario: Request with valid API key passes
  Given the backend API key is "test-key-123"
  When I send GET /api/pipelines with header "x-api-key: test-key-123"
  Then the request is not rejected by the middleware

Scenario: Request without API key is rejected
  Given the backend API key is "test-key-123"
  When I send GET /api/pipelines without x-api-key header
  Then the response status is 401
  And the response body contains "detail": "Invalid or missing API key"

Scenario: Health and status endpoints are exempt from API key check
  Given the backend API key is "test-key-123"
  When I send GET /api/system/health without x-api-key header
  Then the response status is 200
  And the response is not rejected by the middleware
```

## Files to Modify/Create

- Create: `backend/app/api/middleware.py`
- Modify: `backend/app/main.py` (add middleware)

## Steps

### Step 1: Create middleware module

`app/api/middleware.py` should define:

```python
class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates x-api-key header on /api requests.
    Exempts: /api/system/health, /api/system/status, /docs, /openapi.json
    """
    async def dispatch(self, request: Request, call_next) -> Response: ...
```

### Step 2: Wire middleware into app

`app/main.py` should:
- Import `APIKeyMiddleware`
- Add middleware with `settings.BACKEND_API_KEY`

### Step 3: Verify

Middleware should block unauthorized requests and allow authorized ones.

## Verification Commands

```bash
cd backend
BACKEND_API_KEY=test-key-123 uvicorn app.main:app --port 8000 &
sleep 2

# Should pass (exempt)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/system/health

# Should fail (401)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/pipelines

# Should pass (valid key)
curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: test-key-123" http://localhost:8000/api/pipelines

kill %1
```

## Success Criteria

- Requests to `/api/system/health` and `/api/system/status` pass without API key
- Requests to other `/api/*` endpoints without API key get 401
- Requests with valid `x-api-key` header pass through
