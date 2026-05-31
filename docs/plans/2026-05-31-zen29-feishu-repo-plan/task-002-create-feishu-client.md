# Task 002: Create Feishu client wrapper

**Type:** impl
**Depends-on:** ["001"]

## BDD Scenario

```gherkin
Scenario: Feishu client authenticates and provides HTTP methods
  Given FEISHU_APP_ID and FEISHU_APP_SECRET are configured in settings
  When the FeishuClient is instantiated
  Then it obtains a tenant_access_token from Feishu API
  And it exposes get, post, put, delete methods that attach the token to requests
  And methods return parsed JSON responses
  And authentication errors raise FeishuAuthError
```

```gherkin
Scenario: Feishu client handles token refresh
  Given a FeishuClient with an expired tenant_access_token
  When any API method is called
  Then the client automatically refreshes the token
  And retries the request with the new token
```

## What to Implement

Create `backend/app/feishu/client.py` with:

- `FeishuAuthError(Exception)` — raised on auth failures
- `FeishuClient` class:
  - `__init__(self, app_id: str, app_secret: str, base_url: str = "https://open.feishu.cn/open-apis")`
  - `_refresh_token(self) -> str` — obtains tenant_access_token
  - `get(self, path: str, params: dict | None = None) -> dict`
  - `post(self, path: str, body: dict | None = None) -> dict`
  - `put(self, path: str, body: dict | None = None) -> dict`
  - `delete(self, path: str) -> dict`

Create `backend/app/feishu/__init__.py` — package marker.

## Files to Create

- `backend/app/feishu/__init__.py`
- `backend/app/feishu/client.py`

## Verification

```bash
cd backend && python -c "
from app.feishu.client import FeishuClient, FeishuAuthError
print('FeishuClient imported OK')
print('FeishuAuthError imported OK')
"
```

Expected: Both imports succeed, exit code 0.
